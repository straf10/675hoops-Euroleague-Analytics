// The Glossary's terms: only what the live pages show (column heads, tooltips, labels). The page
// renders from this list, and `shownOn` names the pages where each term appears so a later check
// can confirm none has been left behind when a page changes.

export type GlossaryGroup =
  | "Box score"
  | "Shooting"
  | "Rates and samples"
  | "Team ratings"
  | "Forecasts"
  | "Player projections"
  | "Player ratings";

export interface GlossaryTerm {
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

export const TERMS: GlossaryTerm[] = [
  // Box score
  { id: "gp", term: "GP", name: "Games played", group: "Box score", def: "The games a player appeared in.", shownOn: [PL, PP, CM] },
  { id: "gs", term: "GS", name: "Games started", group: "Box score", def: "The games a player was in the starting five.", shownOn: [PP, CM] },
  {
    id: "min",
    term: "MIN",
    name: "Minutes",
    group: "Box score",
    def: "Minutes played per game. It stays a per-game figure even when other columns are scaled to 36 minutes or 100 possessions.",
    shownOn: [PL, PP, TP],
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
  { id: "stl", term: "STL", name: "Steals", group: "Box score", def: "Times a player takes the ball from an opponent.", shownOn: [PL, PP, TP] },
  { id: "blk", term: "BLK", name: "Blocks", group: "Box score", def: "Opponent shots a player blocks.", shownOn: [PL, PP, TP] },
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
    shownOn: [PL, LD],
  },

  // Shooting
  { id: "fga", term: "FGA", name: "Field-goal attempts", group: "Shooting", def: "Shots from the floor, twos and threes. Free throws are not counted.", shownOn: [PL] },
  { id: "fg-pct", term: "FG%", name: "Field-goal percentage", group: "Shooting", def: "Field goals made per attempt.", shownOn: [PL, PP] },
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
    shownOn: [PL],
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
    def: "Offensive rating minus defensive rating. The Teams page ranks clubs by it. On a player page, the same figure for his team while he is on or off the floor.",
    shownOn: [TI, TP, PP],
  },
  { id: "pace", term: "Pace", group: "Team ratings", def: "Possessions per 40 minutes. A high number means a fast game.", shownOn: [TI, TP] },
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
    def: "Where a shot was taken, by its spot on the court: at the rim (within 1.25 m of the basket), paint (inside the lane up to the free-throw line), mid-range (other two-pointers), corner three, above-break three, and deep three (8 m and beyond). Picking a zone shows only its shots on the chart.",
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
    shownOn: [LD, PP],
  },
  {
    id: "o-rapm",
    term: "O-RAPM",
    name: "Offensive RAPM",
    group: "Player ratings",
    def: "The offensive part of RAPM: points per 100 possessions his offense adds against an average player. Positive is better.",
    shownOn: [LD, PP],
  },
  {
    id: "d-rapm",
    term: "D-RAPM",
    name: "Defensive RAPM",
    group: "Player ratings",
    def: "The defensive part of RAPM: points per 100 possessions his defense keeps off the scoreboard against an average player. Positive is better: a negative number means the team allows more with him on the floor.",
    shownOn: [LD, PP],
  },
  {
    id: "interval-90",
    term: "90% interval",
    group: "Player ratings",
    def: "The range a rating should fall in nine times out of ten, if the model is right. A wide range means a short sample: little playing time, so little evidence.",
    shownOn: [LD, PP],
  },
];
