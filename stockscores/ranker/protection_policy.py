"""Pure one-contract exit policy shared by independent paper executors."""

from decimal import Decimal

TARGET_SWITCH = Decimal("0.75")
STOP_SWITCH = Decimal("0.60")


def desired_exit(*, bid, stop, target, currently_target):
    width = target - stop
    progress = (bid - stop) / width if width > 0 else Decimal("0")
    if currently_target:
        return "stop" if progress < STOP_SWITCH else "target"
    return "target" if progress >= TARGET_SWITCH else "stop"
