"""The shot zones of a field-goal attempt: 14 places on the floor (distance band, split by side for
the twos and corner/above-the-break/deep threes), shared by the Plays like similarity.

Each zone is named ``band_side`` (``short_l``) or a three's place (``corner3_r``, ``three_c``,
``deep3``); ``shot_zones`` assigns every located shot one of them. ``x`` < 0 is the left side.
"""

import numpy as np
import pandas as pd

from eurohoops.parse.shots import CORNER_END_Y_M

ZONES = (
    "rim",
    "short_l",
    "short_c",
    "short_r",
    "mid_l",
    "mid_c",
    "mid_r",
    "long2_l",
    "long2_c",
    "long2_r",
    "corner3_l",
    "three_c",
    "corner3_r",
    "deep3",
)
SIDE_DEG = 45.0  # twos wider than this from the basket's axis are left or right


def shot_zones(shots: pd.DataFrame) -> pd.Series:
    """Zone of each shot (``ZONES``); x < 0 is the left side."""
    angle = np.degrees(np.arctan2(shots["x"], shots["y"]))
    side = np.select([angle < -SIDE_DEG, angle > SIDE_DEG], ["l", "r"], "c")
    corner = np.where(shots["x"] < 0, "corner3_l", "corner3_r")
    band = shots["band"].to_numpy(str)
    zone = np.select(
        [
            np.isin(band, ["rim", "deep3"]),
            (band == "three") & (shots["y"] < CORNER_END_Y_M),
            band == "three",
        ],
        [band, corner, "three_c"],
        default=np.char.add(np.char.add(band, "_"), side.astype(str)),
    )
    return pd.Series(zone, index=shots.index, dtype=str)
