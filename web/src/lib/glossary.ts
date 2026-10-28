// The Glossary's terms: only what the live pages show (column heads, tooltips, labels). The page
// renders from this list, and `shownOn` names the pages where each term appears so a later check
// can confirm none has been left behind when a page changes.

type GlossaryGroup =
  | "Box score"
  | "Shooting"
  | "Rates and samples"
  | "Team ratings"
  | "Forecasts"
  | "Player projections"
  | "Player ratings"
  | "Accolades";

interface GlossaryTerm {
  /** Stable anchor: /glossary/#ts-pct. Never rename one; other pages may link to it. */
  id: string;
  /** The label as the pages print it. */
  term: string;
  /** The long name, where the label is an abbreviation. */
  name?: string;
  group: GlossaryGroup;
  /** One or two plain sentences. */
  def: string;
  formula?: string;
  /** Pages (route patterns under the site root) where the term is shown. */
  shownOn: string[];
}

export const GROUPS: GlossaryGroup[] = [
  "Box score",
  "Shooting",
  "Rates and samples",
  "Team ratings",
  "Forecasts",
  "Player projections",
  "Player ratings",
  "Accolades",
];

const PL = "players";
const PP = "players/[slug]";
const TI = "teams";
const TP = "teams/[code]";
const LD = "leaders";
const CM = "compare";
const FC = "forecasts";
const HM = "home";
const ST = "standings";
const GM = "games/[id]";

export const TERMS: GlossaryTerm[] = [
  // Box score
  { id: "scoring-run", term: "Scoring run", group: "Box score", def: "A stretch of points by one team that the other team does not interrupt. Each game page shows each team's three biggest.", shownOn: [GM] },
  { id: "assist-network", term: "Assist network", group: "Box score", def: "Each assist paired with the basket it set up, so passer to scorer. The network has a line for each pair of players who assisted each other at least once, thicker for more assists; it draws the top eight players. The list counts the points the scorer made and needs two assists to show. The matched share says how many box-score assists could be paired.", shownOn: [TP] },
  { id: "gp", term: "GP", name: "Games played", group: "Box score", def: "The games a player appeared in.", shownOn: [PL, PP, CM] },
  { id: "gs", term: "GS", name: "Games started", group: "Box score", def: "The games a player was in the starting five.", shownOn: [PP, CM] },
  {
    id: "min",
    term: "MIN",
    name: "Minutes",
    group: "Box score",
    def: "Minutes played per game. It stays a per-game figure even when other columns are scaled to 36 minutes or 100 possessions.",
    shownOn: [PL, PP, TP, LD],
  },
  { id: "pts", term: "PTS", name: "Points", group: "Box score", def: "Points scored.", shownOn: [PL, PP, TP, LD, CM] },
  { id: "reb", term: "REB", name: "Rebounds", group: "Box score", def: "Rebounds, offensive and defensive together.", shownOn: [PL, PP, TP, LD, CM] },
  {
    id: "ast",
    term: "AST",
    name: "Assists",
    group: "Box score",
    def: "Passes that lead straight to a made basket, as the official scorer records them.",
    shownOn: [PL, PP, TP, LD, CM],
  },
  { id: "stl", term: "STL", name: "Steals", group: "Box score", def: "Times a player takes the ball from an opponent.", shownOn: [PL, PP, TP, LD] },
  { id: "blk", term: "BLK", name: "Blocks", group: "Box score", def: "Opponent shots a player blocks.", shownOn: [PL, PP, TP, LD] },
  { id: "tov", term: "TOV", name: "Turnovers", group: "Box score", def: "Times a player loses the ball to the other side. Fewer is better.", shownOn: [PL, PP, TP] },
  {
    id: "pir",
    term: "PIR",
    name: "Performance Index Rating",
    group: "Box score",
    def: "The EuroLeague's own one-number summary of a player's game. Good plays add to it and bad ones take away.",
    shownOn: [PL, PP, TP, LD],
  },
  {
    id: "plus-minus",
    term: "+/-",
    name: "Plus-minus",
    group: "Box score",
    def: "Points the player's team scored minus points it allowed while he was on court.",
    shownOn: [PL],
  },

  // Shooting
  { id: "fga", term: "FGA", name: "Field-goal attempts", group: "Shooting", def: "Shots from the floor, twos and threes. Free throws are not counted.", shownOn: [PL] },
  { id: "fg-pct", term: "FG%", name: "Field-goal percentage", group: "Shooting", def: "Field goals made per attempt.", shownOn: [PL, PP, LD] },
  { id: "2p-pct", term: "2P%", name: "Two-point percentage", group: "Shooting", def: "Two-pointers made per attempt.", shownOn: [PL] },
  { id: "3pa", term: "3PA", name: "Three-point attempts", group: "Shooting", def: "Shots tried from behind the three-point line.", shownOn: [PL] },
  { id: "3p-pct", term: "3P%", name: "Three-point percentage", group: "Shooting", def: "Three-pointers made per attempt.", shownOn: [PL, PP, TP, LD] },
  { id: "fta", term: "FTA", name: "Free-throw attempts", group: "Shooting", def: "Free throws taken.", shownOn: [PL] },
  { id: "ft-pct", term: "FT%", name: "Free-throw percentage", group: "Shooting", def: "Free throws made per attempt.", shownOn: [PL, PP, TP, LD] },
  {
    id: "efg-pct",
    term: "eFG%",
    name: "Effective field-goal percentage",
    group: "Shooting",
    def: "Field-goal percentage that credits a made three at one and a half times a made two, because it is worth that much more.",
    formula: "(FGM + 0.5 × 3PM) / FGA",
    shownOn: [PL, LD, TP, TI],
  },
  {
    id: "ts-pct",
    term: "TS%",
    name: "True shooting percentage",
    group: "Shooting",
    def: "Points per shooting chance, with threes and free throws counted. It is the fairest single measure of how efficiently someone scores.",
    formula: "PTS / (2 × (FGA + 0.44 × FTA))",
    shownOn: [PL, PP, TP, LD, CM],
  },
  {
    id: "usg-pct",
    term: "USG%",
    name: "Usage percentage",
    group: "Shooting",
    def: "The share of his team's shots, free-throw trips and turnovers that a player ends while he is on court.",
    formula: "(FGA + 0.44 × FTA + TOV) as a share of the team's, while on court",
    shownOn: [PL, LD],
  },
  {
    id: "3pa-rate",
    term: "3PA rate",
    group: "Shooting",
    def: "Three-point attempts per field-goal attempt: how much of a player's shooting comes from three.",
    shownOn: [PP, TI],
  },
  {
    id: "ft-rate",
    term: "Free-throw rate",
    group: "Shooting",
    def: "How often a side gets to the line compared with how often it shoots from the floor. The team rankings count free throws made per 100 field-goal attempts. The four-factors table counts free-throw attempts per field-goal attempt.",
    shownOn: [TP, PP, TI],
  },
  {
    id: "opp-efg",
    term: "Opponent eFG%",
    group: "Shooting",
    def: "The effective field-goal percentage that opponents shoot against a club. Lower is better.",
    shownOn: [TP, TI],
  },
  {
    id: "opp-ft-rate",
    term: "Opponent free-throw rate",
    group: "Shooting",
    def: "The free-throw rate a club allows its opponents. Lower is better.",
    shownOn: [TP, TI],
  },
  {
    id: "opp-3pa-rate",
    term: "Opponent 3PA rate",
    group: "Shooting",
    def: "Three-point attempts per field-goal attempt that a club allows its opponents. It is a style, so neither way is better.",
    shownOn: [TI],
  },

  // Rates and samples
  { id: "per-game", term: "Per game", group: "Rates and samples", def: "The average over the games played. This is the default view.", shownOn: [PL, LD, CM] },
  {
    id: "per-36",
    term: "Per 36",
    group: "Rates and samples",
    def: "Each figure scaled to 36 minutes on court, so a starter and a bench player can be compared at the same playing time.",
    shownOn: [PL, CM],
  },
  {
    id: "per-100",
    term: "Per 100",
    group: "Rates and samples",
    def: "Each figure scaled to 100 possessions, which removes the effect of playing for a fast or a slow team.",
    shownOn: [PL, PP],
  },
  {
    id: "possession",
    term: "Possession",
    group: "Rates and samples",
    def: "One turn with the ball for a team. It ends with a shot, a turnover or a trip to the line.",
    shownOn: [TP, PL, PP],
  },
  { id: "totals", term: "Totals", group: "Rates and samples", def: "The season or career sum rather than an average.", shownOn: [LD, CM] },
  {
    id: "last-n",
    term: "Last 5, Last 10, Last 20",
    group: "Rates and samples",
    def: "Only a player's most recent games, to show current form.",
    shownOn: [PL, PP],
  },

  // Team ratings
  { id: "ortg", term: "ORtg", name: "Offensive rating", group: "Team ratings", def: "Points a team scores per 100 possessions.", shownOn: [TI, TP] },
  {
    id: "drtg",
    term: "DRtg",
    name: "Defensive rating",
    group: "Team ratings",
    def: "Points a team allows per 100 opponent possessions. Lower is better.",
    shownOn: [TI, TP],
  },
  {
    id: "net-rating",
    term: "Net rating",
    group: "Team ratings",
    def: "Offensive rating minus defensive rating: points scored minus points allowed per 100 possessions. The Teams page ranks clubs by it. For a player, the same figure for his team while he is on court (on the Players page, ranked from 15 possessions a game), or on and off the floor on his page.",
    formula: "100 × (+/−) ÷ possessions",
    shownOn: [TI, TP, PP, PL, LD],
  },
  { id: "pace", term: "Pace", group: "Team ratings", def: "Possessions per 40 minutes. A high number means a fast game.", shownOn: [TI, TP] },
  { id: "lineup-net", term: "Lineup net rating", group: "Team ratings", def: "Points the club scored minus points it allowed per 100 possessions that a duo or five-man unit played together. Few possessions make it swing widely.", shownOn: [TP] },
  { id: "lineup-range", term: "Range (±)", name: "Lineup range", group: "Team ratings", def: "A rough 95% range either side of a lineup's net rating, from its possession count alone. A wide range means the rating says little yet.", shownOn: [TP] },
  {
    id: "four-factors",
    term: "Four factors",
    group: "Team ratings",
    def: "The four things that decide most games: shooting (eFG%), turnovers, rebounding and free throws. Each is shown for a club's offense and for its defense.",
    shownOn: [TP],
  },
  {
    id: "tov-rate",
    term: "Turnover rate",
    group: "Team ratings",
    def: "Turnovers per 100 plays. Lower is better on offense.",
    formula: "TOV / (FGA + 0.44 × FTA + TOV)",
    shownOn: [TP, TI],
  },
  {
    id: "returning-minutes",
    term: "Returning minutes",
    group: "Team ratings",
    def: "The share of last season's minutes for the club that went to players on this season's roster. Each player counts by his minutes, so a starter who leaves weighs more than a bench player. It says how much of the team is back, not whether the team is better or worse. A club with no earlier EuroLeague season has none.",
    formula: "last season's minutes of players on this roster ÷ last season's minutes for the club",
    shownOn: [TP, TI],
  },
  {
    id: "turnovers-forced",
    term: "Turnovers forced",
    group: "Team ratings",
    def: "Opponent turnovers per 100 opponent plays. Higher is better.",
    shownOn: [TP, TI],
  },
  {
    id: "orb-pct",
    term: "Offensive rebound %",
    group: "Team ratings",
    def: "The share of a club's own misses that it rebounds.",
    formula: "own offensive rebounds / (own offensive + opponent defensive rebounds)",
    shownOn: [TP, TI],
  },
  {
    id: "drb-pct",
    term: "Defensive rebound %",
    group: "Team ratings",
    def: "The share of opponents' misses that the club rebounds.",
    shownOn: [TP, TI],
  },
  {
    id: "schedule-strength",
    term: "Schedule strength",
    name: "Mean opponent rating",
    group: "Team ratings",
    def: "The average power rating of the opponents on a club's schedule. A higher number means a harder schedule.",
    shownOn: [TP],
  },

  // Forecasts
  {
    id: "power-rating",
    term: "Power rating",
    name: "Elo rating",
    group: "Forecasts",
    def: "One number for team strength, an Elo rating. It rises after a win and falls after a loss, by more for an upset or a big margin. 1500 is an average team.",
    shownOn: [HM],
  },
  {
    id: "mean-opponent-elo",
    term: "Mean opponent Elo",
    group: "Team ratings",
    def: "The average Elo rating of the teams a team has played or will play. The venue-adjusted figure takes off the home-court advantage when the team is at home and adds it when away, so a home game against a strong team counts for less.",
    shownOn: [TP, TI],
  },
  {
    id: "average-team-win",
    term: "Average team win",
    group: "Team ratings",
    def: "How often a team of average strength would win the same games, at the same venues. Above 50% means the schedule is easy for the team's rating; below 50% means it is hard.",
    shownOn: [TP],
  },
  {
    id: "schedule-rest",
    term: "Rest days",
    group: "Team ratings",
    def: "Days since a team's previous game in either competition, capped at 7. The schedule's rest figures show the team's average and its opponents' average before each game.",
    shownOn: [TP],
  },
  {
    id: "win-probability",
    term: "Win probability",
    group: "Forecasts",
    def: "The chance, set before tip-off, that the home side wins. It comes mainly from the gap between the two power ratings.",
    shownOn: [HM, FC],
  },
  {
    id: "expected-margin",
    term: "Expected margin",
    group: "Forecasts",
    def: "The points by which the home side is forecast to win, or to lose if the number is negative.",
    shownOn: [FC],
  },
  {
    id: "picks-right",
    term: "Picks right, Picked the winner",
    group: "Forecasts",
    def: "How often the favourite won. A forecast is right when the side given more than a 50% chance wins the game.",
    shownOn: [FC],
  },
  {
    id: "projected-wins",
    term: "Wins",
    name: "Projected wins",
    group: "Forecasts",
    def: "On the Season projection page, the wins a club is projected to add over the rest of the season, averaged across many simulated seasons.",
    shownOn: [ST],
  },
  {
    id: "season-chances",
    term: "Top 6, Play-in, Playoffs, Final Four, Final, Title",
    group: "Forecasts",
    def: "The share of simulated seasons in which a club finishes in that place or reaches that stage. Sixth place or better goes straight to the playoffs; seventh to tenth play in.",
    shownOn: [ST],
  },

  // Player projections
  {
    id: "projection",
    term: "Projected",
    group: "Player projections",
    def: "The central estimate for a player's next season, built from his past seasons.",
    shownOn: [PP],
  },
  {
    id: "interval-80",
    term: "80% interval",
    group: "Player projections",
    def: "The range a figure should land in four times out of five. A wide range means the player has little history to go on.",
    shownOn: [PP],
  },
  {
    id: "impact",
    term: "Impact",
    group: "Player projections",
    def: "The net points per 100 possessions a player adds against an average player, offense and defense together. Zero is average. The projection is shown two ways: from his box score alone, and with his on/off record added (the same rating as the past-season rows).",
    shownOn: [PP],
  },
  {
    id: "position",
    term: "Position: Guard, Forward, Centre",
    group: "Box score",
    def: "The position the EuroLeague lists for a player that season: guard, forward or centre. A player listed by two clubs in a season takes the listing of the club he played most games for; one with no listing that season keeps his latest.",
    shownOn: [PL, PP],
  },
  {
    id: "min-per-game",
    term: "Min/game",
    group: "Rates and samples",
    def: "The fewest minutes a game a player needs to be listed. Pick a preset.",
    shownOn: [PL],
  },
  {
    id: "shot-making",
    term: "Shot making",
    group: "Shooting",
    def: "Points per shot above or below what the league scores from the same spot, shown as a heatmap: the more teal, the better than the league; the more orange, the worse. Each shot counts 2 or 3 points, and the league's rate is its field-goal percentage from that spot. Spots with few shots fade toward zero.",
    shownOn: [PP, TP],
  },
  {
    id: "shot-zones",
    term: "Shot zones",
    group: "Shooting",
    def: "Where a shot was taken, by its spot on the court: at the rim (within 1.5 m of the basket), paint (inside the lane up to the free-throw line), mid-range (other two-pointers), corner three, above-break three, and deep three (8 m and beyond). Picking a zone shows only its shots on the chart.",
    shownOn: [TP],
  },
  {
    id: "pts-per-shot",
    term: "Pts/shot",
    name: "Points per shot",
    group: "Shooting",
    formula: "Points scored / field-goal attempts",
    def: "Points each shot is worth on average: 2 for a two-pointer, 3 for a three, nothing for a miss.",
    shownOn: [TP],
  },
  {
    id: "distance-bands",
    term: "At the rim, Short, Mid-range, Long two, Three, Deep three",
    group: "Shooting",
    def: "Shots grouped by distance from the basket: at the rim (under 1.5 m), short (to 3 m), mid-range (to 5 m), long two, three-pointer, and deep three (8 m and beyond).",
    shownOn: [TP, PP],
  },
  {
    id: "against-the-league",
    term: "Against the league",
    group: "Rates and samples",
    def: "A player's figure next to the league average for the season. The average and the leaderboard count players with at least 10 minutes a game who played at least a quarter of the most games anyone played. The arrow is green when the gap is good for the player, red when it is not; usage has no better side.",
    shownOn: [PP],
  },
  {
    id: "on-off",
    term: "On court, Off court, On/off",
    group: "Rates and samples",
    def: "His team's points scored minus points allowed per 100 possessions while he is on the floor, and while he sits, in the games he played. On/off is the first minus the second. It moves a lot from season to season.",
    formula: "net per 100 = 100 × (points for − points against) ÷ possessions",
    shownOn: [PP],
  },
  {
    id: "clutch",
    term: "Clutch",
    group: "Rates and samples",
    def: "The last 5 minutes of the fourth quarter, or at any point in overtime, with the score within 5 points. Shown: his minutes, his points, and his team's net per 100 possessions while he is on the floor.",
    shownOn: [PP],
  },
  {
    id: "league-rank",
    term: "League rank",
    group: "Team ratings",
    def: "The club's position in the regular-season standings, first at the top. During the season it is the standing today.",
    shownOn: [TP],
  },
  {
    id: "el-seasons",
    term: "EuroLeague seasons",
    group: "Team ratings",
    def: "The seasons a club has played in the EuroLeague since 2007-08, the first season in our data, up to the season shown.",
    shownOn: [TP],
  },
  {
    id: "league-average-median",
    term: "League average, League median",
    group: "Team ratings",
    def: "On a team's rows, the tick marks the average of all clubs and the hollow dot the middle club. Rows read better to the right, so lower turnover rates and lower opponent figures sit on the right.",
    shownOn: [TP],
  },
  {
    id: "brier",
    term: "Brier score",
    group: "Forecasts",
    def: "The average squared gap between the chance given to a home win and what happened (1 for a home win, 0 otherwise). Lower is better; saying 50% every time scores 0.25.",
    shownOn: [FC],
  },
  {
    id: "log-loss",
    term: "Log loss",
    group: "Forecasts",
    def: "The average of minus the log of the chance given to the side that won. Confident wrong calls cost the most. Lower is better.",
    shownOn: [FC],
  },
  {
    id: "other-models",
    term: "M1, M5",
    group: "Forecasts",
    def: "Two other team models that log a forecast for every game alongside the one the site shows. They are compared on the games they all called.",
    shownOn: [FC],
  },
  // Player ratings
  {
    id: "rapm",
    term: "RAPM",
    name: "Regularised adjusted plus-minus",
    group: "Player ratings",
    def: "Points per 100 possessions a player's team scores and allows with him on the floor, adjusted for his teammates and opponents, shrunk toward a box-score estimate. Zero is average, and a higher total is better. EuroLeague only: the Greek Basket League has too few play-by-play stints to rate.",
    formula: "O-RAPM + D-RAPM",
    shownOn: [PP, PL],
  },
  {
    id: "win-shares",
    term: "WS",
    name: "Win shares",
    group: "Player ratings",
    def: "The wins a player's box-score production adds to his team over a season: offensive win shares plus defensive win shares. Points per win is fitted on EuroLeague seasons (35.5 points of differential a win). EuroLeague only.",
    formula: "WS = OWS + DWS",
    shownOn: [PP, PL, LD],
  },
  {
    id: "offensive-win-shares",
    term: "OWS",
    name: "Offensive win shares",
    group: "Player ratings",
    def: "The wins from scoring and creating above a replacement player: the points he produces, less 0.92 points per possession at the league rate for each possession he uses, in points per win.",
    formula: "OWS = (PProd − 0.92 × league PPP × possessions used) / 35.5",
    shownOn: [PP, PL, LD],
  },
  {
    id: "defensive-win-shares",
    term: "DWS",
    name: "Defensive win shares",
    group: "Player ratings",
    def: "The wins from defence above a replacement player, from his defensive rating: stops from steals, blocks, defensive rebounds and forced misses, which are estimated from the box score. Caveat: the stops are box-score proxies, not counted on video, so DWS is the weakest of the three win shares figures.",
    formula: "DWS = (MIN / team MIN) × team possessions × (1.08 × league PPP − DRtg / 100) / 35.5",
    shownOn: [PP, PL, LD],
  },
  {
    id: "ws-per-40",
    term: "WS/40",
    name: "Win shares per 40 minutes",
    group: "Player ratings",
    def: "Win shares for every 40 minutes on court, the length of a EuroLeague game. Use it to compare players who play different minutes.",
    formula: "WS/40 = WS / MIN × 40",
    shownOn: [PP, PL, LD],
  },
  {
    id: "o-rapm",
    term: "O-RAPM",
    name: "Offensive RAPM",
    group: "Player ratings",
    def: "The offensive part of RAPM: points per 100 possessions his offense adds against an average player. Positive is better.",
    shownOn: [PP],
  },
  {
    id: "d-rapm",
    term: "D-RAPM",
    name: "Defensive RAPM",
    group: "Player ratings",
    def: "The defensive part of RAPM: points per 100 possessions his defense keeps off the scoreboard against an average player. Positive is better: a negative number means the team allows more with him on the floor.",
    shownOn: [PP],
  },
  {
    id: "interval-90",
    term: "90% interval",
    group: "Player ratings",
    def: "The range a rating should fall in nine times out of ten, if the model is right. A wide range means a short sample: little playing time, so little evidence.",
    shownOn: [PP],
  },
  {
    id: "final-four-rate",
    term: "Final Four rate",
    group: "Rates and samples",
    def: "The seasons he reached the Final Four, as a share of the seasons he played since 2007-08. A Final Four season is one where his club played a semifinal, the third-place game or the final.",
    formula: "Final Four seasons ÷ seasons played",
    shownOn: [CM],
  },
  {
    id: "playoff-rate",
    term: "Playoff rate",
    group: "Rates and samples",
    def: "The seasons he reached the playoffs, as a share of the seasons he played since 2007-08. A Final Four season counts as a playoff season.",
    formula: "Playoff seasons ÷ seasons played",
    shownOn: [CM],
  },
  // Compare: accolades (career rows). Since 2007-08: careers that started earlier are incomplete.
  {
    id: "euroleague-titles",
    term: "EuroLeague titles",
    group: "Accolades",
    def: "The seasons his club won the EuroLeague while he played for it. A player of the champion counts, even if he missed the Final Four.",
    shownOn: [CM],
  },
  {
    id: "final-appearances",
    term: "Final appearances",
    group: "Accolades",
    def: "The seasons his club reached the final, lost or won, while he played for it. A season counts once, even if he played for two clubs that season.",
    shownOn: [CM],
  },
  {
    id: "stat-titles",
    term: "Stat titles",
    group: "Accolades",
    def: "The seasons he led the EuroLeague in points, rebounds, assists, steals, blocks or PIR per game. Only qualified players count: at least a quarter of the season's most games and ten minutes a game. A tie counts for each leader. Covers 2007-08 onwards.",
    shownOn: [CM],
  },
  {
    id: "euroleague-seasons",
    term: "EuroLeague seasons",
    group: "Accolades",
    def: "The EuroLeague seasons he played at least one game in, since 2007-08.",
    shownOn: [CM],
  },
  {
    id: "clubs-played",
    term: "Clubs",
    group: "Accolades",
    def: "The different EuroLeague clubs he played a game for, since 2007-08.",
    shownOn: [CM],
  },
  {
    id: "career-games",
    term: "Games played",
    group: "Accolades",
    def: "The EuroLeague games he played in his career, from the box scores.",
    shownOn: [CM],
  },
  // Players page: advanced measures
  {
    id: "ast-tov",
    term: "AST/TOV",
    name: "Assists per turnover",
    group: "Box score",
    def: "Assists divided by turnovers: more assists for each turnover is better. Shown as a dash with no turnovers. Ranked from one turnover a game.",
    formula: "AST ÷ TOV",
    shownOn: [PL],
  },
  {
    id: "ast-pct",
    term: "AST%",
    name: "Assist percentage",
    group: "Box score",
    def: "The share of his team's baskets that he assisted while on court. Uses his team's totals over the games he played, not only the minutes he was on court. Ranked from ten minutes a game.",
    formula: "100 × AST ÷ ((MIN ÷ (team minutes ÷ 5)) × team FGM − FGM)",
    shownOn: [PL, LD],
  },
  {
    id: "reb-pct",
    term: "REB%",
    name: "Rebound percentage",
    group: "Box score",
    def: "The share of the rebounds available while he was on court that he grabbed, offence and defence together. Uses his team's totals over the games he played. Ranked from ten minutes a game.",
    formula: "100 × REB × (team minutes ÷ 5) ÷ (MIN × (team REB + opponent REB))",
    shownOn: [PL],
  },
  {
    id: "tov-pct",
    term: "TOV%",
    name: "Turnover percentage",
    group: "Box score",
    def: "The share of his possessions that end in a turnover. Lower is better. Ranked from ten minutes a game.",
    formula: "100 × TOV ÷ (FGA + 0.44 × FTA + TOV)",
    shownOn: [CM],
  },
  {
    id: "percentile-polygon",
    term: "Percentile profile",
    group: "Rates and samples",
    def: "Each player's place among the qualified players of his season (or of the career pool), per measure: 100 is the best and 0 the worst. Rings mark 25, 50, 75 and 100. Turnover % is inverted, so fewer turnovers reach the outside. Usage has no better side, so high usage reads as 100.",
    shownOn: [CM],
  },
];
