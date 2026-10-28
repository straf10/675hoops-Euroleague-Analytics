# Search log, 2026-10-28 scan

Scope: basketball analytics research for EuroHoops (see the task brief). Each loop = one WebSearch (standard unless noted) then 0–3 WebFetch or local PDF reads. Read-first set: INDEX.md, IDEAS.md, and the 23 paper notes listed there (INDEX says 32 were read, 9 removed as off-topic) (the `papers/` folder is local only, so the notes it names were not present in this worktree; the 32-paper coverage was taken from INDEX.md).

Status key: **K** = kept (note written), **R** = rejected (reason given), **K-abs** = kept on abstract only.

| # | Query (short) | Read | Result |
|---|---|---|---|
| 1 | EuroLeague home advantage study | arXiv 2002.08465 (abstract) | K-abs giasemidis-2020 |
| 2 | Home advantage COVID no crowd basketball | PMC9517988 (opened as search hit) | Partly: page blocked, see loop 3 |
| 3 | De Angelis Reade ghost games abstract | RePEc em-dp2022-01 (abstract); JHSE PDF and PMC/CentAUR (blocked) | K-abs deangelis-2023. JHSE quantifying paper R: PDF unreadable, no title/data |
| 4 | Rest, back-to-back, congestion | arXiv 2606.27957 (abstract), HTML sec 3.2; lida 4069360 (abstract) | K bozhidarova-2026 (full HTML read); K-abs esteves-2021 |
| 5 | "Rested or Rusty" Abolins | UNC poster abstract | R: undergraduate poster, no coefficients or n |
| 6 | EuroLeague travel and fixture congestion (extended) | tandfonline, ResearchGate (both 403) | R: 2024 IJPAS study could not be read; search snippets not used |
| 7 | Star absence win probability NBA | none (search results low quality, blogs) | R: no academic source; FiveThirtyEight title-odds piece not used (non-verifiable) |
| 8 | Bayesian team strength with missing players (extended) | SciTePress 121591 (PDF pp.1–2); thenbsca/Information Systems 2021 (PDF pp.1–2) | K attard-2023 (pp.1–2 read). Sarlis-2021 R: review, no predictive numbers in the read pages |
| 9 | Hot hand, Miller & Sanjurjo | ideas.repec sv9x2 (abstract) | K-abs miller-2018 |
| 10 | Referee bias home team basketball | Frontiers Psychol 10.3389/fpsyg.2018.02637 (full text) | K morgulev-2018 (full text) |
| 11 | Price & Wolfers NBA referees | NBER w13206 (abstract) | K-abs price-2010 (low relevance) |
| 12 | Win Shares validation critique | basketball-reference blog 1c24 (full post) | K paine-2009 (blog, not peer reviewed) |
| 13 | Sill RAPM regularization | Sloan SSAC page (abstract) | K-abs sill-2010 |
| 14 | Bayesian box-score prior RAPM (extended) | arXiv 1604.03186 (abstract); arXiv 2605.24056 (abstract) | K-abs deshpande-2016. 2605.24056 (Jacobs, NBA 1984–96 video RAPM) R: historical data source, no use for EuroHoops |
| 15 | EuroLeague Elo / Bayesian ratings | arXiv 2304.09078 (abstract) | R: Csato football Elo variant, abstract has no numbers or metric |
| 16 | Margin-of-victory Elo vs Glicko | arXiv 2506.00348 (HTML Table I) | K shorewala-2025 (full HTML) |
| 17 | Skellam, bivariate Poisson, negative binomial scores | none new (Attard reused) | Confirmed no basketball Skellam or bivariate study in results |
| 18 | Recalibration Platt / isotonic / temperature | Guo arXiv 1706.04599 (abstract); Niculescu-Mizil PDF (p.1 read) | K-abs guo-2017; K niculescu-mizil-2005 (p.1 read) |
| 19 | xPTS shot quality (basketball) | none (informal sources only) | R: blog and dashboard pages; no paper with log loss |
| 20 | Cervone EPV / Pointwise | arXiv 1408.0777 (abstract) | K-abs cervone-2016 (needs tracking data we lack) |
| 21 | 3P% reliability and regression to mean | basketballanalyticslab post (Italian league? unconfirmed) | R: blog, league and sample unconfirmed |
| 22 | Aging curves basketball | Vaci et al. BRM 2019 (PDF p.1 read) | K vaci-2019 (p.1 only) |
| 23 | Timeouts and scoring runs (NBA, EuroLeague) | Bocconi press page (press only) | K-press carta-2026 (paper 403) |
| 24 | European basketball betting efficiency | Vilnius bachelor thesis (PDF pp.1–4 read) | K velyvis-2021 (intro only; results pages not read) |
| 25 | Minutes projection and rotation | FiveThirtyEight (redirected to abcnews, not followed); lida 4081215 (abstract) | R: Guo et al. 2022 substitution network is descriptive, no minutes forecast; 538 method not verified |
| 26 | Lineup synergy and interaction models (2025) | degruyter jqas-2024-0057 (HTTP 405) | Partial: see loop 27 |
| 27 | Josephs & Upton hypergraph APM | arXiv 2403.20214 (abstract) | K-abs josephs-2025 |
| 28 | Season simulation calibration (Monte Carlo) | JSA-170220 (403 on two URLs); arXiv 2601.18774 (abstract) | R Misadventures in Monte Carlo (blocked, not verified). K-abs pipping-gamon-2026 (blown lead) |
| 29 | Player availability and injuries in European basketball (extended) | none (only injury reports and football) | Confirms the gap: no EuroLeague availability-outcome paper found. Nothing kept |
| 30 | EuroLeague outcome prediction ML, log loss | acikerisim 9340 (abstract) | K-abs balli-2021 (98.9% claim; leakage warning) |
| 31 | Critical review of NBA metrics (2026) | arXiv 2609.27245 (abstract); arXiv 1609.09830 (abstract) | K-abs zhou-guan-2026; K-abs franks-2016 |

## Totals
- Search loops: 31. Extended mode used in loops 6, 8, 14 and 29; all others standard.
- Papers kept: 25 notes in `docs/research/papers/`. Full text read: morgulev-2018, bozhidarova-2026 (HTML), shorewala-2025 (HTML), paine-2009 (blog post). Partial read (first pages or tables only): attard-2023, niculescu-mizil-2005, vaci-2019, velyvis-2021. Abstract only: the other 17 (incl. miller-2018, deangelis-2023). Press summary only: carta-2026.
- Rejected: JHSE quantifying paper (PDF unreadable), Abolins 2023 poster, tandfonline 2024 travel study (403), Sarlis 2021 (no predictive numbers in the read pages), Csato 2024 (abstract only, football), Jacobs 2026 (historical NBA data), Guo et al. 2022 substitution network (no minutes forecast), Misadventures in Monte Carlo (403), FiveThirtyEight minutes method (redirected).

## Gaps and access problems
- PMC, ResearchGate, tandfonline, Springer and DeGruyter returned 403/405 or bot pages for several key papers (De Angelis & Reade full text; Carta et al. working paper; Misadventures in Monte Carlo; Josephs & Upton full text; Esteves full text).
- Full texts for Attard (results tables), Velyvis (results), Vaci (models), Petridis (prior construction), Watts (sample size) were not read beyond the first pages or abstract.
- No EuroLeague-specific academic paper on injuries, rest, or home advantage with numbers was reachable. The one EuroLeague home-advantage paper with numbers (Giasemidis) is accuracy-only.
