-- Staging Parquet -> marts, EuroCup part (research only). Appended to games and teams by
-- eurohoops.marts.build_marts when the EuroCup staging files exist.
INSERT INTO games SELECT 'eurocup' AS competition, * FROM read_parquet({eurocup_games});

INSERT INTO teams SELECT 'eurocup' AS competition, * FROM read_parquet({eurocup_teams});
