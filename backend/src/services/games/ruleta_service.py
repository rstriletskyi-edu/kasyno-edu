import asyncio
import secrets
from collections.abc import Callable

from src.configs.games.ruleta import RuletaSettings, get_ruleta_settings
from src.models.auth import AuthenticatedUser
from src.models.ruleta import (
    RuletaBetResultResponse,
    RuletaSpinRequest,
    RuletaSpinResponse,
)
from src.services.games.ruleta_rules import calculate_bet_payout, get_pocket_color
from src.services.user_service import UserService
from src.utils.exceptions import BetLimitExceededError


class RuletaService:
    """Server-authoritative European Roulette game service."""

    BET_REASON = "Ruleta: zakład"
    WIN_REASON = "Ruleta: wygrana"

    def __init__(
        self,
        user_service: UserService,
        settings: RuletaSettings | None = None,
        rng: Callable[[], int] | None = None,
    ) -> None:
        self._user_service = user_service
        self._settings = settings or get_ruleta_settings()
        self._rng = rng or (lambda: secrets.randbelow(37))

    def _validate_limits(self, payload: RuletaSpinRequest) -> None:
        if len(payload.bets) > self._settings.max_bets_per_spin:
            raise BetLimitExceededError(
                f"Number of bets exceeds maximum allowed ({self._settings.max_bets_per_spin})"
            )
        total_bet = 0
        for bet in payload.bets:
            if bet.amount < self._settings.min_bet_amount:
                raise BetLimitExceededError(
                    f"Bet amount must be at least {self._settings.min_bet_amount}"
                )
            if bet.amount > self._settings.max_bet_amount:
                raise BetLimitExceededError(
                    f"Bet amount cannot exceed {self._settings.max_bet_amount}"
                )
            total_bet += bet.amount
        if total_bet > self._settings.max_total_bet:
            raise BetLimitExceededError(
                f"Total bet {total_bet} exceeds maximum allowed ({self._settings.max_total_bet})"
            )

    async def spin(
        self,
        user: AuthenticatedUser,
        payload: RuletaSpinRequest,
    ) -> RuletaSpinResponse:
        """Spin the wheel, evaluate all bets server-side, and settle credits atomically."""
        self._validate_limits(payload)

        winning_number = self._rng()
        if isinstance(winning_number, bool) or not 0 <= winning_number <= 36:
            raise ValueError(f"RNG produced invalid pocket number: {winning_number}")

        color = get_pocket_color(winning_number)
        results: list[RuletaBetResultResponse] = []
        total_bet = 0
        total_payout = 0

        for bet in payload.bets:
            won, payout = calculate_bet_payout(
                bet.bet_type,
                bet.numbers,
                bet.selection,
                bet.amount,
                winning_number,
            )
            total_bet += bet.amount
            total_payout += payout
            results.append(
                RuletaBetResultResponse(
                    bet_type=bet.bet_type,
                    numbers=bet.numbers,
                    selection=bet.selection,
                    amount=bet.amount,
                    won=won,
                    payout=payout,
                )
            )

        new_balance = await asyncio.to_thread(
            self._user_service.settle_game_wager,
            user,
            total_bet,
            total_payout,
            self.BET_REASON,
            self.WIN_REASON,
        )

        return RuletaSpinResponse(
            winning_number=winning_number,
            color=color,
            total_bet=total_bet,
            total_payout=total_payout,
            net_profit=total_payout - total_bet,
            new_balance=new_balance,
            bets=results,
        )
