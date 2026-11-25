import asyncio
from collections.abc import Callable
import secrets

from src.configs.games.slots import SlotsSettings, get_slots_settings
from src.models.auth import AuthenticatedUser
from src.models.slots import (
    SlotsConfigResponse,
    SlotsPaytableEntryResponse,
    SlotsSpinRequest,
    SlotsSpinResponse,
    SlotsSymbolResponse,
)
from src.services.games.slots_rules import (
    SlotMachineConfig,
    calculate_theoretical_rtp,
    evaluate_spin,
    get_slots_machine_config,
    pick_symbol_by_roll,
)
from src.services.user_service import UserService
from src.utils.exceptions import BetLimitExceededError


class SlotsService:
    """Server-authoritative classic 3x1 slot machine (Jednoręki bandyta) service."""

    BET_REASON = "Sloty: zakład"
    WIN_REASON = "Sloty: wygrana"

    def __init__(
        self,
        user_service: UserService,
        settings: SlotsSettings | None = None,
        machine: SlotMachineConfig | None = None,
        rng: Callable[[int], int] | None = None,
    ) -> None:
        self._user_service = user_service
        self._settings = settings or get_slots_settings()
        self._machine = machine or get_slots_machine_config()
        self._rng = rng or secrets.randbelow

    @staticmethod
    def build_config(
        settings: SlotsSettings,
        machine: SlotMachineConfig | None = None,
    ) -> SlotsConfigResponse:
        """Build public slot machine config, optionally including probabilities and RTP."""
        resolved_machine = machine or get_slots_machine_config()
        if settings.expose_rtp:
            probabilities = resolved_machine.symbol_probabilities()
            rtp: float | None = calculate_theoretical_rtp(resolved_machine)
        else:
            probabilities = {}
            rtp = None

        return SlotsConfigResponse(
            reels=resolved_machine.reels,
            rows=resolved_machine.rows,
            min_bet_amount=settings.min_bet_amount,
            max_bet_amount=settings.max_bet_amount,
            symbols=[
                SlotsSymbolResponse(
                    id=symbol.id,
                    label=symbol.label,
                    probability=probabilities.get(symbol.id) if settings.expose_rtp else None,
                )
                for symbol in resolved_machine.symbols
            ],
            paytable=[
                SlotsPaytableEntryResponse(
                    symbol=rule.symbol,
                    count=rule.count,
                    multiplier=rule.multiplier,
                    name=rule.name,
                )
                for rule in resolved_machine.paytable
            ],
            rtp=rtp,
        )

    def _validate_limits(self, payload: SlotsSpinRequest) -> None:
        if payload.bet_amount < self._settings.min_bet_amount:
            raise BetLimitExceededError(
                f"Bet amount must be at least {self._settings.min_bet_amount}"
            )
        if payload.bet_amount > self._settings.max_bet_amount:
            raise BetLimitExceededError(
                f"Bet amount cannot exceed {self._settings.max_bet_amount}"
            )

    async def spin(
        self,
        user: AuthenticatedUser,
        payload: SlotsSpinRequest,
    ) -> SlotsSpinResponse:
        """Spin 3 independent reels, evaluate the paytable, and settle credits atomically."""
        self._validate_limits(payload)

        reel_ids = [
            pick_symbol_by_roll(
                self._machine, self._rng(self._machine.total_weight)
            ).id
            for _ in range(self._machine.reels)
        ]

        matched = evaluate_spin(self._machine, reel_ids)
        if matched is not None:
            payout = payload.bet_amount * matched.multiplier
            matched_response = SlotsPaytableEntryResponse(
                symbol=matched.symbol,
                count=matched.count,
                multiplier=matched.multiplier,
                name=matched.name,
            )
        else:
            payout = 0
            matched_response = None

        new_balance = await asyncio.to_thread(
            self._user_service.settle_game_wager,
            user,
            payload.bet_amount,
            payout,
            self.BET_REASON,
            self.WIN_REASON,
        )

        return SlotsSpinResponse(
            reels=reel_ids,
            won=matched is not None,
            matched_combination=matched_response,
            bet_amount=payload.bet_amount,
            payout=payout,
            net_profit=payout - payload.bet_amount,
            new_balance=new_balance,
        )
