import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.configs.games.blackjack import BlackjackSettings, get_blackjack_settings
from src.models.auth import AuthenticatedUser
from src.models.blackjack import (
    BlackjackAction,
    BlackjackGameResponse,
    BlackjackOutcome,
    BlackjackStartRequest,
    BlackjackStatus,
    CardResponse,
)
from src.services.games.blackjack_rules import (
    Card,
    calculate_payout,
    create_shuffled_shoe,
    evaluate_hand,
    play_dealer_hand,
    resolve_outcome,
)
from src.services.user_service import UserService
from src.utils.exceptions import (
    BetLimitExceededError,
    BlackjackActiveGameExistsError,
    BlackjackGameNotFoundError,
    BlackjackInvalidActionError,
)


@dataclass
class _BlackjackRound:
    game_id: str
    uid: str
    shoe: list[Card]
    player_cards: list[Card]
    dealer_cards: list[Card]
    bet_amount: int
    status: BlackjackStatus
    outcome: BlackjackOutcome | None
    payout: int
    balance: int
    expires_at: datetime
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class BlackjackSessionStore:
    """In-memory round store with TTL expiration and per-user active round limits."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._rounds: dict[str, _BlackjackRound] = {}

    def now(self) -> datetime:
        return self._clock()

    def purge_expired(self) -> None:
        current_time = self._clock()
        expired_ids = [
            gid for gid, round_state in self._rounds.items() if round_state.expires_at <= current_time
        ]
        for gid in expired_ids:
            del self._rounds[gid]

    def active_count_for_user(self, uid: str) -> int:
        self.purge_expired()
        return sum(
            1
            for round_state in self._rounds.values()
            if round_state.uid == uid and round_state.status == BlackjackStatus.IN_PROGRESS
        )

    def put(self, round_state: _BlackjackRound) -> None:
        self._rounds[round_state.game_id] = round_state

    def require(self, uid: str, game_id: str) -> _BlackjackRound:
        self.purge_expired()
        round_state = self._rounds.get(game_id)
        if round_state is None or round_state.uid != uid:
            raise BlackjackGameNotFoundError()
        return round_state


class BlackjackService:
    """Server-authoritative Classic Blackjack game service."""

    BET_REASON = "Blackjack: zakład"
    DOUBLE_REASON = "Blackjack: podwojenie"
    WIN_REASON = "Blackjack: wygrana"
    PUSH_REASON = "Blackjack: zwrot"

    def __init__(
        self,
        user_service: UserService,
        settings: BlackjackSettings | None = None,
        store: BlackjackSessionStore | None = None,
        deck_factory: Callable[[int], list[Card]] | None = None,
    ) -> None:
        self._user_service = user_service
        self._settings = settings or get_blackjack_settings()
        self._store = store or BlackjackSessionStore()
        self._deck_factory = deck_factory or create_shuffled_shoe

    def _validate_bet_limits(self, bet_amount: int) -> None:
        if bet_amount < self._settings.min_bet_amount:
            raise BetLimitExceededError(
                f"Bet amount must be at least {self._settings.min_bet_amount}"
            )
        if bet_amount > self._settings.max_bet_amount:
            raise BetLimitExceededError(
                f"Bet amount cannot exceed {self._settings.max_bet_amount}"
            )

    def _payout_reason(self, outcome: BlackjackOutcome) -> str:
        return self.PUSH_REASON if outcome == BlackjackOutcome.PUSH else self.WIN_REASON

    @staticmethod
    def _to_response(round_state: _BlackjackRound) -> BlackjackGameResponse:
        player_eval = evaluate_hand(round_state.player_cards)
        if round_state.status == BlackjackStatus.IN_PROGRESS:
            visible_dealer = [round_state.dealer_cards[0]]
            dealer_hidden = len(round_state.dealer_cards) - 1
            actions = [BlackjackAction.HIT, BlackjackAction.STAND]
            if len(round_state.player_cards) == 2:
                actions.append(BlackjackAction.DOUBLE)
        else:
            visible_dealer = list(round_state.dealer_cards)
            dealer_hidden = 0
            actions = []

        dealer_eval = evaluate_hand(visible_dealer)
        return BlackjackGameResponse(
            game_id=round_state.game_id,
            status=round_state.status,
            outcome=round_state.outcome,
            bet_amount=round_state.bet_amount,
            payout=round_state.payout,
            net_profit=round_state.payout - round_state.bet_amount,
            new_balance=round_state.balance,
            player_cards=[
                CardResponse(rank=card.rank, suit=card.suit)
                for card in round_state.player_cards
            ],
            player_value=player_eval.value,
            player_is_soft=player_eval.is_soft,
            dealer_cards=[
                CardResponse(rank=card.rank, suit=card.suit) for card in visible_dealer
            ],
            dealer_value=dealer_eval.value,
            dealer_hidden_cards=dealer_hidden,
            available_actions=actions,
        )

    async def _finish_dealer_turn(
        self,
        user: AuthenticatedUser,
        round_state: _BlackjackRound,
    ) -> None:
        play_dealer_hand(round_state.dealer_cards, round_state.shoe)
        outcome = resolve_outcome(round_state.player_cards, round_state.dealer_cards)
        payout = calculate_payout(round_state.bet_amount, outcome)
        if payout > 0:
            round_state.balance = await asyncio.to_thread(
                self._user_service.credit_game_payout,
                user,
                payout,
                self._payout_reason(outcome),
            )
        round_state.status = BlackjackStatus.FINISHED
        round_state.outcome = outcome
        round_state.payout = payout

    async def start(
        self,
        user: AuthenticatedUser,
        payload: BlackjackStartRequest,
    ) -> BlackjackGameResponse:
        """Start a Blackjack round, escrow wager, deal cards, and handle natural Blackjack."""
        self._validate_bet_limits(payload.bet_amount)
        if (
            self._store.active_count_for_user(user.uid)
            >= self._settings.max_active_games_per_user
        ):
            raise BlackjackActiveGameExistsError()

        shoe = list(self._deck_factory(self._settings.deck_count))
        if len(shoe) < 4:
            raise ValueError("Shoe must contain at least 4 cards")

        p1, d1, p2, d2 = shoe.pop(0), shoe.pop(0), shoe.pop(0), shoe.pop(0)
        player_cards = [p1, p2]
        dealer_cards = [d1, d2]

        player_eval = evaluate_hand(player_cards)
        dealer_eval = evaluate_hand(dealer_cards)

        game_id = str(uuid4())
        expires_at = self._store.now() + timedelta(
            seconds=self._settings.session_ttl_seconds
        )

        if player_eval.is_blackjack or dealer_eval.is_blackjack:
            outcome = resolve_outcome(player_cards, dealer_cards)
            payout = calculate_payout(payload.bet_amount, outcome)
            new_balance = await asyncio.to_thread(
                self._user_service.settle_game_wager,
                user,
                payload.bet_amount,
                payout,
                self.BET_REASON,
                self._payout_reason(outcome),
            )
            round_state = _BlackjackRound(
                game_id=game_id,
                uid=user.uid,
                shoe=shoe,
                player_cards=player_cards,
                dealer_cards=dealer_cards,
                bet_amount=payload.bet_amount,
                status=BlackjackStatus.FINISHED,
                outcome=outcome,
                payout=payout,
                balance=new_balance,
                expires_at=expires_at,
            )
        else:
            new_balance = await asyncio.to_thread(
                self._user_service.deduct_game_wager,
                user,
                payload.bet_amount,
                self.BET_REASON,
            )
            round_state = _BlackjackRound(
                game_id=game_id,
                uid=user.uid,
                shoe=shoe,
                player_cards=player_cards,
                dealer_cards=dealer_cards,
                bet_amount=payload.bet_amount,
                status=BlackjackStatus.IN_PROGRESS,
                outcome=None,
                payout=0,
                balance=new_balance,
                expires_at=expires_at,
            )

        self._store.put(round_state)
        return self._to_response(round_state)

    async def get_game(
        self,
        user: AuthenticatedUser,
        game_id: str,
    ) -> BlackjackGameResponse:
        """Return the current state of an owned Blackjack round."""
        round_state = self._store.require(user.uid, game_id)
        async with round_state.lock:
            return self._to_response(round_state)

    async def hit(
        self,
        user: AuthenticatedUser,
        game_id: str,
    ) -> BlackjackGameResponse:
        """Draw one card for the player; resolve immediately on bust or 21."""
        round_state = self._store.require(user.uid, game_id)
        async with round_state.lock:
            if round_state.status != BlackjackStatus.IN_PROGRESS:
                raise BlackjackInvalidActionError("Blackjack game is already finished")
            if not round_state.shoe:
                raise ValueError("Shoe ran out of cards")

            round_state.player_cards.append(round_state.shoe.pop(0))
            player_eval = evaluate_hand(round_state.player_cards)
            if player_eval.is_bust:
                round_state.status = BlackjackStatus.FINISHED
                round_state.outcome = BlackjackOutcome.PLAYER_BUST
                round_state.payout = 0
            elif player_eval.value == 21:
                await self._finish_dealer_turn(user, round_state)

            return self._to_response(round_state)

    async def stand(
        self,
        user: AuthenticatedUser,
        game_id: str,
    ) -> BlackjackGameResponse:
        """End player turn, play out dealer S17 hand, and settle payout."""
        round_state = self._store.require(user.uid, game_id)
        async with round_state.lock:
            if round_state.status != BlackjackStatus.IN_PROGRESS:
                raise BlackjackInvalidActionError("Blackjack game is already finished")

            await self._finish_dealer_turn(user, round_state)
            return self._to_response(round_state)

    async def double_down(
        self,
        user: AuthenticatedUser,
        game_id: str,
    ) -> BlackjackGameResponse:
        """Double the wager on a 2-card hand, draw one card, and resolve the round."""
        round_state = self._store.require(user.uid, game_id)
        async with round_state.lock:
            if round_state.status != BlackjackStatus.IN_PROGRESS:
                raise BlackjackInvalidActionError("Blackjack game is already finished")
            if len(round_state.player_cards) != 2:
                raise BlackjackInvalidActionError(
                    "Double down is only allowed on the initial two-card hand"
                )
            if not round_state.shoe:
                raise ValueError("Shoe ran out of cards")

            additional_bet = round_state.bet_amount
            new_balance = await asyncio.to_thread(
                self._user_service.deduct_game_wager,
                user,
                additional_bet,
                self.DOUBLE_REASON,
            )
            round_state.bet_amount += additional_bet
            round_state.balance = new_balance
            round_state.player_cards.append(round_state.shoe.pop(0))

            if evaluate_hand(round_state.player_cards).is_bust:
                round_state.status = BlackjackStatus.FINISHED
                round_state.outcome = BlackjackOutcome.PLAYER_BUST
                round_state.payout = 0
            else:
                await self._finish_dealer_turn(user, round_state)

            return self._to_response(round_state)
