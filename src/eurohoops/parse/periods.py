"""Period numbers from the play-by-play ``MINUTE`` field. A leaf module: it imports nothing else."""

QUARTER_MINUTES = 10
OVERTIME_MINUTES = 5
REGULATION_MINUTES = 40  # MINUTE 1-40 is regulation
OT_FIRST_MINUTE = REGULATION_MINUTES + 1  # MINUTE 41-45 is the first overtime
OT_END_MARKERS = ("EP", "EG")


def period_from_minute(minute: int, end_marker: bool = False) -> int:
    """Period of a ``MINUTE``: quarters 1-4, then 5 for 41-45, 6 for 46-50, and so on.

    An overtime period-end marker carries the next minute, so with ``end_marker`` it maps back
    to the period it ends (46 is period 5). Overtime rows must be clamped to at least
    ``OT_FIRST_MINUTE`` first, or a minute below 41 reads as regulation.
    """
    if minute <= REGULATION_MINUTES:
        return (max(minute, 1) - 1) // QUARTER_MINUTES + 1
    index = (minute - OT_FIRST_MINUTE) // OVERTIME_MINUTES  # 0 for 41-45
    if end_marker:
        return 4 + max(index, 1)
    return 5 + index
