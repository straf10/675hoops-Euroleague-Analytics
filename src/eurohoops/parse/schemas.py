"""Helpers shared by the pandera contracts."""

from typing import Any

import pandas as pd
import pandera.pandas as pa


def schema_dtypes(schema: pa.DataFrameSchema) -> dict[str, str]:
    """Pandas dtypes of a schema's columns (strings as the default ``str`` dtype).

    Cast to these before validating: an empty frame's columns are ``object`` otherwise.
    """
    return {
        name: "str" if str(column.dtype).startswith("string") else str(column.dtype)
        for name, column in schema.columns.items()
    }


def box_count(value: Any) -> int:
    """A box-score count. A fraction (80.5) or a boolean raises; it is never truncated to an int."""
    if isinstance(value, bool):
        raise ValueError(f"box count {value!r} is a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError(f"box count {value!r} is not a whole number")


def validated(frame: pd.DataFrame, schema: pa.DataFrameSchema) -> pd.DataFrame:
    """Cast ``frame`` to the schema's dtypes, then validate it."""
    return schema.validate(frame.astype(schema_dtypes(schema)))
