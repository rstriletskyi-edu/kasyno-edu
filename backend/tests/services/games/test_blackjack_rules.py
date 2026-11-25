from pydantic import ValidationError
import pytest

from src.configs.games.blackjack import BlackjackSettings
from src.services.games.blackjack_rules import (
    BlackjackOutcome,
    Card,
    Rank,
    Suit,
    build_shoe,
    calculate_payout,
    create_shuffled_shoe,
    evaluate_hand,
    play_dealer_hand,
    resolve_outcome,
    shuffle_shoe,
)


def c(rank: Rank, suit: Suit = Suit.SPADES) -> Card:
    return Card(rank=rank, suit=suit)


def test_shoe_integrity_and_shuffle_preserve_exact_cards() -> None:
    shoe = build_shoe(6)
    assert len(shoe) == 312
    assert len(set(shoe)) == 52

    shuffled = create_shuffled_shoe(6)
    assert len(shuffled) == 312
    assert sorted((card.suit.value, card.rank.value) for card in shuffled) == sorted(
        (card.suit.value, card.rank.value) for card in shoe
    )

    with pytest.raises(ValueError):
        build_shoe(0)
    with pytest.raises(ValueError):
        build_shoe(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        shuffle_shoe(shoe, rng=lambda _n: -1)


def test_evaluate_hand_handles_aces_soft_hard_and_blackjack() -> None:
    natural = evaluate_hand([c(Rank.ACE), c(Rank.KING)])
    assert natural.value == 21
    assert natural.is_soft is True
    assert natural.is_blackjack is True
    assert natural.is_bust is False

    three_card_21 = evaluate_hand([c(Rank.SEVEN), c(Rank.FOUR), c(Rank.ACE), c(Rank.NINE)])
    assert three_card_21.value == 21
    assert three_card_21.is_soft is False
    assert three_card_21.is_blackjack is False

    soft_17 = evaluate_hand([c(Rank.ACE), c(Rank.SIX)])
    assert soft_17.value == 17
    assert soft_17.is_soft is True

    two_aces_and_nine = evaluate_hand([c(Rank.ACE), c(Rank.ACE), c(Rank.NINE)])
    assert two_aces_and_nine.value == 21
    assert two_aces_and_nine.is_soft is True

    two_aces_and_ten = evaluate_hand([c(Rank.ACE), c(Rank.ACE), c(Rank.TEN)])
    assert two_aces_and_ten.value == 12
    assert two_aces_and_ten.is_soft is False

    bust = evaluate_hand([c(Rank.TEN), c(Rank.NINE), c(Rank.FIVE)])
    assert bust.value == 24
    assert bust.is_bust is True


def test_dealer_follows_s17_stands_on_soft_and_hard_17_and_hits_16() -> None:
    soft_17_hand = [c(Rank.ACE), c(Rank.SIX)]
    shoe = [c(Rank.TEN)]
    play_dealer_hand(soft_17_hand, shoe)
    assert len(soft_17_hand) == 2
    assert len(shoe) == 1

    hard_17_hand = [c(Rank.TEN), c(Rank.SEVEN)]
    play_dealer_hand(hard_17_hand, shoe)
    assert len(hard_17_hand) == 2

    draw_from_16 = [c(Rank.TEN), c(Rank.SIX)]
    shoe_for_draw = [c(Rank.FIVE), c(Rank.TWO)]
    play_dealer_hand(draw_from_16, shoe_for_draw)
    assert [card.rank for card in draw_from_16] == [Rank.TEN, Rank.SIX, Rank.FIVE]
    assert len(shoe_for_draw) == 1


@pytest.mark.parametrize(
    ("player", "dealer", "expected_outcome"),
    [
        ([c(Rank.ACE), c(Rank.JACK)], [c(Rank.TEN), c(Rank.NINE)], BlackjackOutcome.PLAYER_BLACKJACK),
        ([c(Rank.TEN), c(Rank.NINE)], [c(Rank.ACE), c(Rank.QUEEN)], BlackjackOutcome.DEALER_BLACKJACK),
        ([c(Rank.ACE), c(Rank.KING)], [c(Rank.ACE), c(Rank.TEN)], BlackjackOutcome.PUSH),
        ([c(Rank.TEN), c(Rank.SEVEN), c(Rank.FIVE)], [c(Rank.TEN), c(Rank.SEVEN)], BlackjackOutcome.PLAYER_BUST),
        ([c(Rank.TEN), c(Rank.EIGHT)], [c(Rank.TEN), c(Rank.SIX), c(Rank.TEN)], BlackjackOutcome.DEALER_BUST),
        ([c(Rank.TEN), c(Rank.NINE)], [c(Rank.TEN), c(Rank.EIGHT)], BlackjackOutcome.PLAYER_WIN),
        ([c(Rank.TEN), c(Rank.SEVEN)], [c(Rank.TEN), c(Rank.NINE)], BlackjackOutcome.DEALER_WIN),
        ([c(Rank.TEN), c(Rank.EIGHT)], [c(Rank.NINE), c(Rank.NINE)], BlackjackOutcome.PUSH),
        # 21 from 3 cards loses to dealer natural Blackjack
        ([c(Rank.SEVEN), c(Rank.SEVEN), c(Rank.SEVEN)], [c(Rank.ACE), c(Rank.KING)], BlackjackOutcome.DEALER_BLACKJACK),
    ],
)
def test_resolve_outcome_covers_all_cases(
    player: list[Card],
    dealer: list[Card],
    expected_outcome: BlackjackOutcome,
) -> None:
    assert resolve_outcome(player, dealer) == expected_outcome


@pytest.mark.parametrize(
    ("bet", "outcome", "expected_payout"),
    [
        (10, BlackjackOutcome.PLAYER_BLACKJACK, 25),
        (5, BlackjackOutcome.PLAYER_BLACKJACK, 12),
        (10, BlackjackOutcome.PLAYER_WIN, 20),
        (10, BlackjackOutcome.DEALER_BUST, 20),
        (10, BlackjackOutcome.PUSH, 10),
        (10, BlackjackOutcome.DEALER_BLACKJACK, 0),
        (10, BlackjackOutcome.PLAYER_BUST, 0),
        (10, BlackjackOutcome.DEALER_WIN, 0),
    ],
)
def test_calculate_payout_all_outcomes_and_3_to_2_rounding(
    bet: int, outcome: BlackjackOutcome, expected_payout: int
) -> None:
    assert calculate_payout(bet, outcome) == expected_payout


def test_blackjack_settings_reads_env_and_validates_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLACKJACK_MIN_BET_AMOUNT", "10")
    monkeypatch.setenv("BLACKJACK_MAX_BET_AMOUNT", "500")
    monkeypatch.setenv("BLACKJACK_DECK_COUNT", "4")
    monkeypatch.setenv("BLACKJACK_SESSION_TTL_SECONDS", "900")
    monkeypatch.setenv("BLACKJACK_MAX_ACTIVE_GAMES_PER_USER", "2")

    settings = BlackjackSettings(_env_file=None)
    assert settings.min_bet_amount == 10
    assert settings.max_bet_amount == 500
    assert settings.deck_count == 4
    assert settings.session_ttl_seconds == 900
    assert settings.max_active_games_per_user == 2

    with pytest.raises(ValidationError):
        BlackjackSettings(_env_file=None, min_bet_amount=100, max_bet_amount=50)
    with pytest.raises(ValidationError):
        BlackjackSettings(_env_file=None, deck_count=9)
    with pytest.raises(ValidationError):
        BlackjackSettings(_env_file=None, session_ttl_seconds=30)
    with pytest.raises(ValidationError):
        BlackjackSettings(_env_file=None, max_active_games_per_user=0)
