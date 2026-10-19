"""Source status of unplayed games, read from cached ESAKE schedule pages (no network).

An ESAKE schedule block (``<div class="esake-program-game">``) holds one game's date and TV
cells and a link carrying its ``idgame`` code. When the cells say ``ΑΝΑΒΑΛΛΕΤΑΙ`` ("is
postponed") the source has postponed the game, which explains an unplayed past game.
"""

POSTPONED = "ΑΝΑΒΑΛΛΕΤΑΙ"
GAME_BLOCK = '<div class="esake-program-game">'
POSTPONED_REASON = "postponed: the cached ESAKE schedule row marks it ΑΝΑΒΑΛΛΕΤΑΙ (not played)"


def schedule_marks(page: str, idgame: str) -> str | None:
    """The schedule block of ``idgame`` in one cached page, or None when the page lacks it."""
    at = page.find(f"idgame={idgame}")
    if at < 0:
        return None
    start = page.rfind(GAME_BLOCK, 0, at)
    end = page.find(GAME_BLOCK, at)
    return page[start : end if end > 0 else None]


def is_postponed(page: str, idgame: str) -> bool:
    """True when the cached page's schedule block for ``idgame`` marks the game postponed."""
    block = schedule_marks(page, idgame)
    return block is not None and POSTPONED in block
