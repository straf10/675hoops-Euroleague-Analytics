"""Read model of the read-only API: the marts, prediction logs and committed reports as JSON-ready
dicts (weeks 16-18, L5). ``api/app.py`` only serves what these functions return.

Rules
-----
- Nothing is fitted or simulated here. A route reads a committed report, a log, a mart table, or
  calls a pure function the pipeline already owns (``publish.site_data``, ``stats.export
  .build_payloads``, ``models.player_seasons.build_player_seasons``, Elo's ``season_ratings``).
- Read-only: DuckDB is only opened through ``marts.read_games`` / ``read_teams`` / ``read_table``
  (``read_only=True``); no function writes a file.
- A ``Store`` is a snapshot. It holds the root of a data tree (repo-root-relative paths from
  ``eurohoops.config``) and memoises the expensive loads (marts, box scores, shots, the stats
  payloads, the player-season frame) for its lifetime, so one process builds each once. Logs are
  read on every call; committed reports once per Store. Start a new ``Store`` to see newer data.
- ``NotFound`` carries the reason a route answers 404 with; a malformed committed report is a bug
  and raises its own error (pandera / KeyError), not a 404.
- Source team codes everywhere (``team.code``); ``team.display_code`` is the site's real-life code
  (``publish.DISPLAY_CODES``). No birth date or age is read or returned.
"""
