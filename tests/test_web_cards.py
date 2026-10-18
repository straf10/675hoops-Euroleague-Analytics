"""The share cards in web/src: their routes, the rules they follow, and where they are linked.

The cards are rendered at build time (sharp, from site.json and the player loaders). These source
checks keep the rules a build would not notice breaking: the card routes exist, only the live season
gets player cards, cards mention no odds or betting, misses are crosses, pages link their cards."""

import re

from tests.conftest import REPO

WEB = REPO / "web" / "src"
CARDS = WEB / "lib" / "cards"
PAGES = WEB / "pages"
ROUTES = {
    "round": PAGES / "cards" / "[name].png.ts",
    "game": PAGES / "cards" / "games" / "[id].png.ts",
    "player": PAGES / "cards" / "players" / "[slug].png.ts",
}
PLAYER_PAGE = PAGES / "players" / "[slug].astro"
FORECASTS_PAGE = PAGES / "forecasts" / "index.astro"
BASE = WEB / "layouts" / "Base.astro"
# Betting language: nothing a card draws or links to. Identifiers such as `picks` pass.
BETTING = re.compile(r"\b(?:odds|bookmakers?|betting|bets?|stakes?)\b", re.IGNORECASE)


def test_each_card_route_exists() -> None:
    for name, path in ROUTES.items():
        assert path.is_file(), f"missing {name} card route at {path.relative_to(REPO)}"
        assert "image/png" in path.read_text(encoding="utf-8"), f"{name} route does not answer PNG"


def test_card_sources_mention_no_betting_language() -> None:
    for path in sorted([*CARDS.glob("*.ts"), *ROUTES.values()]):
        text = path.read_text(encoding="utf-8")
        assert not BETTING.search(text), f"{path.relative_to(REPO)} mentions betting language"


def test_only_the_live_season_gets_player_cards() -> None:
    text = (CARDS / "players.ts").read_text(encoding="utf-8")
    # Players whose latest season is the live one, and nothing else.
    assert "Math.max(...p.seasons) === live" in text
    assert "playerCardInput" in text and "latest.season !== live.season" in text


def test_player_page_gates_affiliation_and_card_on_the_live_season() -> None:
    text = PLAYER_PAGE.read_text(encoding="utf-8")
    assert "current = live !== undefined && latest.season === live.season" in text
    assert re.search(r"affiliation:\s*current\s*\?", text), "affiliation depends on the live season"
    assert ": undefined" in text, "affiliation is omitted (undefined) when not current"
    assert 'current="players" image={card}' in text, "the player page passes its card as og:image"


def test_base_layout_takes_an_optional_share_card() -> None:
    text = BASE.read_text(encoding="utf-8")
    assert re.search(r"image\?:\s*\{\s*path:\s*string", text), "Base.astro takes an optional image"
    assert 'card ?? { path: "/og.png"' in text, "the default social card stays /og.png"


def test_forecasts_page_hides_the_round_card_links() -> None:
    # Share-card links are hidden while their use is measured; the PNG routes stay.
    text = FORECASTS_PAGE.read_text(encoding="utf-8")
    assert "/cards/round-" not in text
    assert "Share cards (PNG)" not in text


def test_misses_are_crosses_not_rings() -> None:
    # The site's shot marker: a blue cross for a miss, an orange dot for a make (lib/shotmarks.ts).
    text = (CARDS / "player.ts").read_text(encoding="utf-8")
    assert re.search(r"stroke=\"\$\{BLUE\}\"", text), "misses use the blue stroke"
    assert not re.search(r"circle\([^)]*BLUE", text), "a miss must not be a blue ring"
