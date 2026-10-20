-- Staging Parquet -> marts, GBL part: appends the GBL rows to the EuroLeague tables built by
-- games.sql (same result as one UNION ALL BY NAME of both competitions). Brace fields are quoted
-- file paths filled in by eurohoops.marts.
CREATE OR REPLACE TABLE games AS
SELECT * FROM games
UNION ALL BY NAME
SELECT 'gbl' AS competition, * FROM read_parquet({gbl_games});

CREATE OR REPLACE TABLE teams AS
SELECT * FROM teams
UNION ALL BY NAME
SELECT 'gbl' AS competition, * FROM read_parquet({gbl_teams});
