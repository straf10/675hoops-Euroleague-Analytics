"""Coach names from the EuroLeague box scores (``Stats[i].Coach``, e.g. ``KOKOSKOV, IGOR``).

Spellings are compared by their name tokens: accents, punctuation and initials go, and the order
of surname and first name does not matter, so ``BLATT DAVID`` and ``BLATT, DAVID`` are one coach.
``ALIASES`` maps the spellings whose tokens differ (typos, a nickname, a middle name, a shortened
first name) to the canonical spelling of the same coach; every alias was checked by hand against
the cached box scores (team and season overlap). ``DISPLAY`` overrides the name built from the
canonical spelling (``SURNAME, FIRST`` -> ``First Surname``). Blank and placeholder entries
(``EXCLUDED``) name no coach. Two coaches may never share a slug: ``resolve`` raises instead.
"""

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

# Placeholder values in the cache that name no coach (2008 Ljubljana and Berlin box scores).
EXCLUDED = frozenset({"SSS", "XX"})

# Raw spelling in the cache -> canonical spelling (also a raw spelling or a comma form).
ALIASES: dict[str, str] = {
    # Alfonso "Sito" Alonso: the same coach at Baskonia (2016) and Barcelona (2017)
    "ALONSO SITO": "ALONSO, ALFONSO",
    "ALONSO, SITO": "ALONSO, ALFONSO",
    "ALIMPIJEVIC, D.": "ALIMPIJEVIC, DUSAN",
    "ALIMPJEVIC, DUSAN": "ALIMPIJEVIC, DUSAN",
    "ATAMAN ERGIN": "ATAMAN, HALIL ERGIN",
    "ATAMAN, ERGIN": "ATAMAN, HALIL ERGIN",
    "BAGATZKIS AINARS": "BAGATSKIS, AINARS",
    "BARTOZAS, GIORGIOS": "BARTZOKAS, GEORGIOS",
    "BARTYOKAS GEORGIOS": "BARTZOKAS, GEORGIOS",
    "BARTZOKAS, G.": "BARTZOKAS, GEORGIOS",
    "BATZOKAS, GEORGIOS": "BARTZOKAS, GEORGIOS",
    "BLATT DAVID": "BLATT, DAVID MICHAEL",
    "BLATT, DAVID": "BLATT, DAVID MICHAEL",
    "BLATT, DAVIC MICHAEL": "BLATT, DAVID MICHAEL",
    "BLATT, DAVIDMICHAEL": "BLATT, DAVID MICHAEL",
    "BLATT, DAVIS MICHAEL": "BLATT, DAVID MICHAEL",
    "CALVANI MARCO": "CALVANI, MARCO",
    "CALVINI MARCO": "CALVANI, MARCO",
    "CANCELLIERI MASSIMO": "CANCELLIERI, MASSIMO",
    "ERNAK, SELCUK": "ERNAK, BURAK SELCUK",
    "EVEN PELED, AVRAHAM": "EVEN, AVI",
    "FILIPOVSKI SASA": "FILIPOVSKI, SASA",
    "GARCIA RENESES, ALEJANDRO": "GARCIA RENESES, AITO",
    "GONZALES, ISRAEL": "GONZALEZ, ISRAEL",
    "GONZALEZ NUNEZ, ISRAEL": "GONZALEZ, ISRAEL",
    "GRIMAU GRAGERA, ROGER": "GRIMAU, ROGER",
    "HERVE PHILIPPE": "PHILIPPE, HERVE",
    "PHILIPPE HERVE": "PHILIPPE, HERVE",
    "ITOUDIS DIMITRIOS": "ITOUDIS, DIMITRIS",
    "ITOUDIS DIMITRIOUS": "ITOUDIS, DIMITRIS",
    "ITOUDIS, DIMITRIOS": "ITOUDIS, DIMITRIS",
    "ITOUDIS,DIMITRIOS": "ITOUDIS, DIMITRIS",
    "ITOUDIS, DIMITROS": "ITOUDIS, DIMITRIS",
    "ITUDIS, DIMITRIOS": "ITOUDIS, DIMITRIS",
    "IVANOV DUSKO": "IVANOVIC, DUSKO",
    "JASIKEVICIUS, S.": "JASIKEVICIUS, SARUNAS",
    "JASIKEVICIUS, SARAS": "JASIKEVICIUS, SARUNAS",
    "JESUS, MATEO": "MATEO, CHUS",
    "MATEO DIEZ, JESUS": "MATEO, CHUS",
    "MATEO DIEZ, JESUS ALFONSO": "MATEO, CHUS",
    "JULBE ALFRED": "JULBE, ALFRED",
    "KATTACHE, DAVID ODED": "KATTASH, ODED",
    "KATTACHE, ODED": "KATTASH, ODED",
    "KATTASH, DAVID ODED": "KATTASH, ODED",
    "KATTASHE, DAVID ODED": "KATTASH, ODED",
    "LASO BIURRUN": "LASO, PABLO",
    "LASO BIURRUN, PABLO": "LASO, PABLO",
    "LASO, P.": "LASO, PABLO",
    "MALDONADO RUIZ, SALVADOR": "MALDONADO, SALVADOR",
    "MALDONADO, SAALBADOR": "MALDONADO, SALVADOR",
    "MALDONADO, SALVA": "MALDONADO, SALVADOR",
    "MARTINEZ SANCHEZ, PEDRO": "MARTINEZ, PEDRO",
    "MARTINEZ, P.": "MARTINEZ, PEDRO",
    "MUMBRU MURCIA, ALEX": "MUMBRU, ALEX",
    "OBRADOVIC ZELIMIR": "OBRADOVIC, ZELJKO",
    "OBRADOVIC, ZELIMIR": "OBRADOVIC, ZELJKO",
    "OBRAOVIC, ZELIMIR": "OBRADOVIC, ZELJKO",
    "ZELIMIR OBRADOVIC": "OBRADOVIC, ZELJKO",
    "ZELIMIR, OBRADOVIC": "OBRADOVIC, ZELJKO",
    "SASA OBRADOVIC": "OBRADOVIC, SASA",
    "PARKER, TERENCE JONATHAN": "PARKER, TJ",
    "PASCUAL VIVES XAVIER": "PASCUAL, XAVI",
    "PASCUAL VIVES, X.": "PASCUAL, XAVI",
    "PASCUAL VIVES, XAVIER": "PASCUAL, XAVI",
    "PASCUAL XAVI": "PASCUAL, XAVI",
    "PASCUAL, VIVES XAVIER": "PASCUAL, XAVI",
    "PASCUAL, XAVIER": "PASCUAL, XAVI",
    "PASCUAL,X.": "PASCUAL, XAVI",
    "XAVIER PASCUAL VIVES": "PASCUAL, XAVI",
    "PASHUTIN EVGENIY": "PASHUTIN, EVGENY",
    "PASHUTIN EVGENNY": "PASHUTIN, EVGENY",
    "PEDOULAKIS, ARGYRIS": "PEDOULAKIS, ARGYRIOS",
    "PENARROYA RODRIGUEZ, JUAN": "PENARROYA, JOAN",
    "PENNAROYA RODRIGUEZ JUAN": "PENARROYA, JOAN",
    "PENNARROYA RODRIGUEZ, JUAN": "PENARROYA, JOAN",
    "PERASOVIC, V.": "PERASOVIC, VELIMIR",
    "PESIC, SVETISLAC": "PESIC, SVETISLAV",
    "PIANGIANI SIMONE": "PIANIGIANI, SIMONE",
    "PIANIGIANI, S.": "PIANIGIANI, SIMONE",
    "PITINO, RICHARD ANDREW": "PITINO, RICK",
    "PLAZA DURAN, JOAN": "PLAZA, JOAN",
    "PLAZA, J.": "PLAZA, JOAN",
    "PLAZA, JUAN": "PLAZA, JOAN",
    "PONSARNAU GOENAGA, JAUME": "PONSARNAU, JAUME",
    "PRIFTIS, DIMITRIOS": "PRIFTIS, DIMITRIS",
    "RADONIC, DEJAN": "RADONJIC, DEJAN",
    "REPESA, JASMINE": "REPESA, JASMIN",
    "SCHILLER, MARTIN CHRISTIAN": "SCHILLER, MARTIN",
    "SFAIROPOULOS GIANNIS": "SFAIROPOULOS, IOANNIS",
    "SFAIROPOULOS IONNIS": "SFAIROPOULOS, IOANNIS",
    "SFAIROPOULOS, I.": "SFAIROPOULOS, IOANNIS",
    "SFAIROPOULOS, IOANIS": "SFAIROPOULOS, IOANNIS",
    "SFAIROPOULUS IOANNIS": "SFAIROPOULOS, IOANNIS",
    "SPANOULIS VASILEIOS": "SPANOULIS, VASSILIS",
    "TINCHIERI ANDREA": "TRINCHIERI, ANDREA",
    "TRINCHERI, ANDREA": "TRINCHIERI, ANDREA",
    "TRINCHERIE ANDREA": "TRINCHIERI, ANDREA",
    "TRINCHIERI, A.": "TRINCHIERI, ANDREA",
    "VIDORETTA JESUS": "VIDORRETA, JESUS",
    "VIDORRETA, J.": "VIDORRETA, JESUS",
    "VIDORRETA, TXUS": "VIDORRETA, JESUS",
    "ZDOVC, JURIJ": "ZDOVC, JURE",
    "VALDEOLIMILLOS SERGIO": "VALDEOLIMILLOS, SERGIO",
}

# Canonical spelling -> display name, where the built name is not the one people use.
DISPLAY: dict[str, str] = {
    "ALONSO, ALFONSO": "Sito Alonso",
    "ATAMAN, HALIL ERGIN": "Ergin Ataman",
    "BLATT, DAVID MICHAEL": "David Blatt",
    "OBRADOVIC, ZELJKO": "Željko Obradović",
    "OBRADOVIC, SASA": "Saša Obradović",
    "PARKER, TJ": "TJ Parker",
    "PENARROYA, JOAN": "Joan Peñarroya",
    "PESIC, SVETISLAV": "Svetislav Pešić",
    "MARTINEZ, PEDRO": "Pedro Martínez",
    "PHILIPPE, HERVE": "Hervé Philippe",
}


@dataclass(frozen=True)
class Coach:
    slug: str  # URL key, ASCII (``zeljko-obradovic``)
    name: str  # display name (``Željko Obradović``)


def _tokens(spelling: str) -> frozenset[str]:
    """The name tokens of a spelling: ASCII letters, upper case, two letters or more."""
    folded = unicodedata.normalize("NFKD", spelling).encode("ascii", "ignore").decode("ascii")
    return frozenset(w for w in re.findall(r"[A-Za-z]+", folded.upper()) if len(w) >= 2)


def _built_name(spelling: str) -> str:
    """``SURNAME, FIRST`` -> ``First Surname``; a spelling without a comma keeps its order."""
    if "," in spelling:
        surname, _, first = spelling.partition(",")
        spelling = f"{first} {surname}"
    return " ".join(word.capitalize() for word in spelling.split())


def _slug(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


def resolve(counts: Mapping[str, int]) -> dict[str, Coach | None]:
    """Each raw spelling in ``counts`` (spelling -> games it appears in) -> its coach.

    ``None`` for a blank or excluded spelling. The display name of a coach comes from his most
    frequent comma spelling (``DISPLAY`` overrides it). Raises ``ValueError`` when two coaches
    would share a slug, which means an alias is missing.
    """
    groups: dict[frozenset[str], Counter[str]] = defaultdict(Counter)
    canonical: dict[str, str] = {}
    for raw, games in counts.items():
        text = raw.strip()
        if not text or text in EXCLUDED:
            continue
        spelling = ALIASES.get(raw, raw)
        if not _tokens(spelling):
            continue
        canonical[raw] = spelling
        groups[_tokens(spelling)][spelling] += games
    coach_of: dict[frozenset[str], Coach] = {}
    used: dict[str, frozenset[str]] = {}
    for key, spellings in groups.items():
        comma = {s: n for s, n in spellings.items() if "," in s} or dict(spellings)
        best = max(comma.items(), key=lambda item: (item[1], item[0]))[0]
        name = DISPLAY.get(best, _built_name(best))
        slug = _slug(name)
        if slug in used and used[slug] != key:
            raise ValueError(f"coaches {sorted(used[slug])} and {sorted(key)} both slug {slug!r}")
        used[slug] = key
        coach_of[key] = Coach(slug=slug, name=name)
    return {
        raw: (coach_of[_tokens(canonical[raw])] if raw in canonical else None) for raw in counts
    }
