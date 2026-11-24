import pytest

from src.services.llm.credits_factory import build_credits_calculator, linear_credits
from src.utils.exceptions import LlmNotConfiguredError


def test_linear_credits_map_score_onto_zero_to_ten() -> None:
    assert linear_credits(0) == 0
    assert linear_credits(85) == 8
    assert linear_credits(100) == 10
    assert build_credits_calculator("linear")(33) == 3
    with pytest.raises(LlmNotConfiguredError, match="Unsupported credits engine"):
        build_credits_calculator("future-engine")
