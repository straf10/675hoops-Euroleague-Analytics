import pandas as pd

from eurohoops.parse.player_names import PLAYER_NAMES_SCHEMA, euroleague_names


def test_euroleague_names_strip_padding_and_split_the_name() -> None:
    players = pd.DataFrame(
        {
            "player_id": ["P012099", "P012099", "P004193"],
            "player": ["GROSBER, DORIAN", "GROSBER, DORIAN", "JBAM"],
            "dorsal": ["2", "2", ""],
            "team": ["BER", "BER", "CHL"],
            "season": [2024, 2024, 2012],
            "sec": [600, 300, 120],
        }
    )
    names = euroleague_names(players).astype(object)
    names = names.where(names.notna(), None)
    PLAYER_NAMES_SCHEMA.validate(euroleague_names(players))
    columns = ["source_id", "jersey", "surname_raw", "first_raw", "games", "minutes"]
    assert names[columns].to_numpy().tolist() == [
        ["P004193", None, "JBAM", "", 1, 2.0],
        ["P012099", "2", "GROSBER", "DORIAN", 2, 15.0],
    ]
