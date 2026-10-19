"""Coach name normalisation (parse/coach_names.py): spellings of one coach resolve to one coach."""

from eurohoops.parse.coach_names import ALIASES, EXCLUDED, resolve


def _one(*spellings: str) -> set[tuple[str, str]]:
    found = resolve({s: 1 for s in spellings}).values()
    return {(c.slug, c.name) for c in found if c is not None}


def test_comma_and_order_variants_are_one_coach() -> None:
    assert _one("KOKOSKOV, IGOR", "KOKOSKOV IGOR") == {("igor-kokoskov", "Igor Kokoskov")}
    assert _one("ALIMPIJEVIC DUSAN", "ALIMPIJEVIC, DUSAN") == {
        ("dusan-alimpijevic", "Dusan Alimpijevic")
    }


def test_alias_table_merges_typos_nicknames_and_middle_names() -> None:
    assert _one("BLATT DAVID", "BLATT, DAVID", "BLATT, DAVIS MICHAEL", "BLATT, DAVID MICHAEL") == {
        ("david-blatt", "David Blatt")
    }
    assert _one("ALONSO, SITO", "ALONSO, ALFONSO") == {("sito-alonso", "Sito Alonso")}
    assert _one("SFAIROPOULOS GIANNIS", "SFAIROPOULOS, IOANNIS") == {
        ("ioannis-sfairopoulos", "Ioannis Sfairopoulos")
    }


def test_accents_do_not_split_a_coach() -> None:
    resolved = resolve({"VIDORRETA, JESÚS": 1, "VIDORRETA, JESUS": 21})
    assert {(c.slug, c.name) for c in resolved.values() if c} == {
        ("jesus-vidorreta", "Jesus Vidorreta")
    }
    # The most frequent spelling names the coach: an accented spelling keeps its accent.
    accented = resolve({"VIDORRETA, JESÚS": 5, "VIDORRETA, JESUS": 1})
    assert {c.name for c in accented.values() if c} == {"Jesús Vidorreta"}


def test_display_override_keeps_the_accented_name_and_ascii_slug() -> None:
    assert _one("OBRADOVIC, ZELIMIR", "ZELIMIR OBRADOVIC", "OBRADOVIC, ZELJKO") == {
        ("zeljko-obradovic", "Željko Obradović")
    }
    assert _one("OBRADOVIC, SASA") == {("sasa-obradovic", "Saša Obradović")}


def test_different_people_stay_apart() -> None:
    assert _one("DJORDJEVIC, ALEKSANDAR") != _one("DJORDJEVIC, SASA")
    assert _one("PARKER, TJ") != _one("PARKER, TONY")


def test_blank_and_placeholder_spellings_name_no_coach() -> None:
    resolved = resolve({"": 3, **{s: 1 for s in EXCLUDED}, "KOKOSKOV, IGOR": 2})
    assert resolved[""] is None
    assert all(resolved[s] is None for s in EXCLUDED)
    assert resolved["KOKOSKOV, IGOR"] is not None


def test_display_name_is_the_most_frequent_comma_spelling() -> None:
    resolved = resolve({"PASCUAL, XAVI": 116, "PASCUAL XAVI": 3, "PASCUAL, XAVIER": 9})
    names = {c.name for c in resolved.values() if c is not None}
    assert names == {"Xavi Pascual"}


def test_every_alias_target_is_a_coach_of_its_own() -> None:
    targets = set(ALIASES.values())
    for target in targets:
        assert resolve({target: 1})[target] is not None
    for variant, canonical in ALIASES.items():
        assert variant != canonical
        assert resolve({variant: 1})[variant] == resolve({canonical: 1})[canonical]
