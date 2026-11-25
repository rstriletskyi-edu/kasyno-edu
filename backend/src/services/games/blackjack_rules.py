from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
import secrets


class Suit(str, Enum):
    """Standard 52-card deck suit."""

    SPADES = "spades"
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"


class Rank(str, Enum):
    """Standard 52-card deck rank."""

    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


class BlackjackStatus(str, Enum):
    """Lifecycle status of a Blackjack round."""

    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class BlackjackOutcome(str, Enum):
    """Terminal result of a finished Blackjack round."""

    PLAYER_BLACKJACK = "player_blackjack"
    DEALER_BLACKJACK = "dealer_blackjack"
    PLAYER_WIN = "player_win"
    DEALER_WIN = "dealer_win"
    PLAYER_BUST = "player_bust"
    DEALER_BUST = "dealer_bust"
    PUSH = "push"


class BlackjackAction(str, Enum):
    """Player actions available during an in-progress round."""

    HIT = "hit"
    STAND = "stand"
    DOUBLE = "double"


@dataclass(frozen=True)
class Card:
    """Immutable playing card."""

    rank: Rank
    suit: Suit


@dataclass(frozen=True)
class HandEvaluation:
    """Computed Classic Blackjack hand totals and flags."""

    value: int
    is_soft: bool
    is_blackjack: bool
    is_bust: bool


_BASE_VALUES: dict[Rank, int] = {
    Rank.TWO: 2,
    Rank.THREE: 3,
    Rank.FOUR: 4,
    Rank.FIVE: 5,
    Rank.SIX: 6,
    Rank.SEVEN: 7,
    Rank.EIGHT: 8,
    Rank.NINE: 9,
    Rank.TEN: 10,
    Rank.JACK: 10,
    Rank.QUEEN: 10,
    Rank.KING: 10,
}


def build_shoe(deck_count: int = 6) -> list[Card]:
    """Build an unshuffled shoe containing `deck_count` standard 52-card decks."""
    if isinstance(deck_count, bool) or deck_count < 1:
        raise ValueError("deck_count must be at least 1")
    return [
        Card(rank=rank, suit=suit)
        for _ in range(deck_count)
        for suit in Suit
        for rank in Rank
    ]


def shuffle_shoe(
    cards: Sequence[Card],
    rng: Callable[[int], int] | None = None,
) -> list[Card]:
    """Return a Fisher-Yates shuffled copy of `cards` using a CSPRNG by default."""
    draw = rng or secrets.randbelow
    shuffled = list(cards)
    for idx in range(len(shuffled) - 1, 0, -1):
        swap_idx = draw(idx + 1)
        if isinstance(swap_idx, bool) or not 0 <= swap_idx <= idx:
            raise ValueError(f"RNG returned invalid shuffle index {swap_idx} for bound {idx + 1}")
        shuffled[idx], shuffled[swap_idx] = shuffled[swap_idx], shuffled[idx]
    return shuffled


def create_shuffled_shoe(
    deck_count: int = 6,
    rng: Callable[[int], int] | None = None,
) -> list[Card]:
    """Create a freshly shuffled multi-deck shoe."""
    return shuffle_shoe(build_shoe(deck_count), rng=rng)


def evaluate_hand(cards: Sequence[Card]) -> HandEvaluation:
    """Evaluate a Blackjack hand, treating Aces as 11 when safe and 1 otherwise."""
    total = 0
    soft_aces = 0

    for card in cards:
        if card.rank == Rank.ACE:
            total += 11
            soft_aces += 1
        else:
            total += _BASE_VALUES[card.rank]

    while total > 21 and soft_aces > 0:
        total -= 10
        soft_aces -= 1

    return HandEvaluation(
        value=total,
        is_soft=soft_aces > 0,
        is_blackjack=len(cards) == 2 and total == 21,
        is_bust=total > 21,
    )


def play_dealer_hand(dealer_cards: list[Card], shoe: list[Card]) -> list[Card]:
    """Draw cards for the dealer until reaching at least 17 (S17: stands on all 17s)."""
    while evaluate_hand(dealer_cards).value < 17:
        if not shoe:
            raise ValueError("Shoe ran out of cards during dealer turn")
        dealer_cards.append(shoe.pop(0))
    return dealer_cards


def resolve_outcome(
    player_cards: Sequence[Card],
    dealer_cards: Sequence[Card],
) -> BlackjackOutcome:
    """Resolve the Classic Blackjack outcome between player and dealer hands."""
    player_eval = evaluate_hand(player_cards)
    dealer_eval = evaluate_hand(dealer_cards)

    if player_eval.is_blackjack and dealer_eval.is_blackjack:
        return BlackjackOutcome.PUSH
    if player_eval.is_blackjack:
        return BlackjackOutcome.PLAYER_BLACKJACK
    if dealer_eval.is_blackjack:
        return BlackjackOutcome.DEALER_BLACKJACK
    if player_eval.is_bust:
        return BlackjackOutcome.PLAYER_BUST
    if dealer_eval.is_bust:
        return BlackjackOutcome.DEALER_BUST
    if player_eval.value > dealer_eval.value:
        return BlackjackOutcome.PLAYER_WIN
    if player_eval.value < dealer_eval.value:
        return BlackjackOutcome.DEALER_WIN
    return BlackjackOutcome.PUSH


def calculate_payout(bet_amount: int, outcome: BlackjackOutcome) -> int:
    """Return total integer payout (stake + profit) for the given bet and outcome."""
    if isinstance(bet_amount, bool) or bet_amount <= 0:
        raise ValueError("bet_amount must be positive")
    if outcome == BlackjackOutcome.PLAYER_BLACKJACK:
        return (bet_amount * 5) // 2
    if outcome in (BlackjackOutcome.PLAYER_WIN, BlackjackOutcome.DEALER_BUST):
        return bet_amount * 2
    if outcome == BlackjackOutcome.PUSH:
        return bet_amount
    return 0
