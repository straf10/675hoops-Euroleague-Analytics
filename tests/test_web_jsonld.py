"""The schema.org markup in web/src: one escaping component, pure builders, no odds or picks.

Built output is checked by hand (the JSON-LD blocks in ../site parse and carry the right types);
these source checks keep the rules that a build would not notice breaking."""

import re

from tests.conftest import REPO

WEB = REPO / "web" / "src"
JSONLD = WEB / "lib" / "jsonld.ts"
JSONLD_COMPONENT = WEB / "components" / "JsonLd.astro"
GAMES_COMPONENT = WEB / "components" / "GamesJsonLd.astro"
DOWNLOADS = WEB / "pages" / "downloads" / "index.astro"
# Betting language and the forecast fields that carry win chances: none belong in markup.
BETTING = re.compile(
    r"\b(?:odds|bookmakers?|betting|bet|picks?|p_home|exp_margin|closing)\b",
    re.IGNORECASE,
)


def test_json_ld_component_escapes_angle_brackets() -> None:
    text = JSONLD_COMPONENT.read_text(encoding="utf-8")
    assert 'replace(/</g, "\\\\u003c")' in text, "a '<' in the data could close the script tag"
    assert "set:html=" in text


def test_only_the_component_writes_json_ld_blocks() -> None:
    # index.astro keeps its own WebSite block; every other page or component uses JsonLd.
    offenders = [
        str(path.relative_to(WEB))
        for path in sorted(WEB.rglob("*.astro"))
        if path not in (JSONLD_COMPONENT, WEB / "pages" / "index.astro")
        and 'type="application/ld+json"' in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_builders_and_markup_mention_no_odds_or_picks() -> None:
    for path in (JSONLD, JSONLD_COMPONENT, GAMES_COMPONENT):
        text = path.read_text(encoding="utf-8")
        assert not BETTING.search(text), f"{path.relative_to(WEB)} mentions betting or win chances"


def test_forecast_log_dataset_is_cc_by_and_euroleague_datasets_point_to_the_terms() -> None:
    text = DOWNLOADS.read_text(encoding="utf-8")
    # Two licenses in the page: CC BY 4.0 on the project's own forecast log, and the page's terms
    # section on the EuroLeague datasets (Google wants a license or terms URL on every Dataset).
    assert len(re.findall(r"^\s*license:", text, re.MULTILINE)) == 2
    assert 'const CC_BY = "https://creativecommons.org/licenses/by/4.0/"' in text
    forecast = text[text.index("const forecastLog") : text.index("const datasets")]
    assert "license: CC_BY" in forecast
    # The EuroLeague-derived datasets are credited to Euroleague and point only at the terms.
    league = text[text.index("const leagueDatasets") : text.index("const predictionsDir")]
    assert "license: TERMS" in league
    assert "CC_BY" not in league
    assert "isBasedOn: EUROLEAGUE" in league
    assert "creditText: EUROLEAGUE_CREDIT" in league


def test_builders_stay_pure() -> None:
    # The builders take plain data and return plain objects: no imports at all.
    text = JSONLD.read_text(encoding="utf-8")
    assert not re.search(r"^import\s", text, re.MULTILINE), "jsonld.ts should have no imports"
