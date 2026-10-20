-- Staging Parquet -> marts, EuroLeague part. Brace fields are quoted file paths filled in by
-- eurohoops.marts. games_gbl.sql appends the GBL rows when their staging files exist.
CREATE OR REPLACE TABLE games AS
SELECT 'euroleague' AS competition, * FROM read_parquet({euroleague_games});

CREATE OR REPLACE TABLE teams AS
SELECT 'euroleague' AS competition, * FROM read_parquet({euroleague_teams});
