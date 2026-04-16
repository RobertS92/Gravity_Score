# NIL applications — what Gravity does in the market

For the **full stack** (formula vs NN, scrapers, Velocity roadmap, terminal routing), see **[GRAVITY_UNIFIED_SPEC.md](./GRAVITY_UNIFIED_SPEC.md)**.

The **Gravity NIL Intelligence Terminal** serves multiple buyer needs from **one score engine**. The applications are not separate products: they are **different query workflows** against the same underlying athlete data, scores, and comparables.

Primary commercial seats cluster into **three buyer groups** (compliance, agents, brands). **Score monitoring** spans those seats. **Insurance** is a separate B2B data product with no terminal UI.

---

## Application 1: CSC compliance — deal valuation reports

**Buyer:** NIL attorneys and sports agents (highest urgency; primary monetizable workflow).

**Job-to-be-done:** Before submitting to **NIL Go**, answer:

1. Does this deal fall within the range of compensation for similarly situated athletes?
2. What are the **CSC denial risks**?

**Terminal workflow**

1. User enters a natural-language deal in the query bar, e.g.  
   *“Assess a $175,000 apparel deal for Travis Hunter, 3-year contract, 4 posts per month, Nike as brand.”*
2. The agent loads the athlete’s current Gravity score, runs **comparables** (~15 similar athletes), surfaces **verified apparel deals** in range, places the proposed dollar amount vs **10th–90th percentile** compensation, and scores the deal on the **three CSC criteria**:
   - Payor association  
   - Valid business purpose  
   - Range of compensation  
3. The main panel switches to **Deal Assessment**.
4. **Generate report** produces a **PDF** suitable for CSC / NIL Go submission.

**Report contents (target)**

- Gravity score breakdown with **SHAP** factor citations  
- Comparable athletes with **known deal values**  
- Range chart: where the proposed deal sits vs the band  
- CSC pre-clearance **scorecard**  
- **Methodology** section attorneys can cite  

**Commercial framing:** typical **$500–$2,000** per report event.

---

## Application 2: Agent negotiation preparation

**Buyer:** Sports agents managing a roster (e.g. ~12 athletes).

**Job-to-be-done:** Before negotiation, portal decisions, or renewals, know:

- Each client’s **current commercial value** and **trajectory**  
- **NIL environment** at schools the client might join  

**Terminal workflows**

1. **Watchlist (sidebar)**  
   - *“Show me all my clients’ scores and who’s moved in the last 30 days.”*  
   - Pre-computed where possible; at a glance: **rising Velocity** (negotiate now) vs **rising Risk** (flag before the next deal).

2. **Program comparison**  
   - e.g. *“How would Marcus Harris’s Gravity Score change if he transferred from Ole Miss to Ohio State?”*  
   - **NIL environment score** per school, **delta across all five Gravity components**, **projected deal ceiling** change.  
   - Main panel: **Program Comparison** (two schools side by side).

3. **Category deal ceiling (comparables)**  
   - e.g. *“What’s the deal ceiling for a food and beverage brand for Malik Nabers?”*  
   - **10th–90th percentile** for similar athletes in that **brand category**, with **which verified deals** anchored the benchmark.  
   - Renders in **Deal Assessment** (ceiling / benchmark mode) when the API returns structured fields.

---

## Application 3: Brand–athlete matching

**Buyer:** Brand marketing teams and sports agencies running campaigns.

**Job-to-be-done:** With budget, category, risk tolerance, and audience, **shortlist** athletes without manually reviewing hundreds of profiles.

**Terminal workflow**

1. User enters a brief, e.g.  
   *“Find athletes for a regional bank campaign in the Southeast, $40K budget per athlete, max 2 transfers, no controversy history.”*
2. Agent filters by **brand–category fit** (e.g. financial services weights **Proof** and market size), **geography** (e.g. Southeast DMAs), **risk** (controversy / transfers), computes **Brand–Athlete Fit Scores**, returns a **ranked list**.
3. Main panel: **Brand Match** view.

**Athlete card (target)**

- Overall **fit score**  
- **Audience alignment** (e.g. social overlap vs target demo, e.g. 25–45 adults)  
- **Category authenticity** (credibility for the category)  
- **Commercial activation** (engagement, posting consistency)  
- **Risk alignment** vs stated tolerance  
- **Estimated deal cost range**  

**Handoff:** **Assess deal** on a row opens **Deal Assessment** with **category and budget** pre-populated (terminal + API contract).

---

## Application 4: Score monitoring and alerts

**Buyer:** Any seat with watchlisted athletes.

**Job-to-be-done:** Catch **material** changes in commercial value (Velocity, Risk, Brand, etc.) early.

**Mechanics**

- **Daily** incremental checks on watchlisted athletes for **Velocity** and **Risk** signals; **weekly** full score refresh (aligned with scraper / ML jobs).  
- When a score moves beyond a **user-defined threshold**, an **alert** appears (e.g. sidebar count + list).

**Alert format (example)**

> Travis Hunter — Brand score up 8 pts. **Cause:** 180K Instagram followers in 7 days after viral highlight. **Recommendation:** negotiate pending endorsements before the market adjusts.

**Terminal behavior**

- Click alert → **Athlete profile** with **score history** (chart), **SHAP** highlights for the move, **Generate report** available.

---

## Application 5: Insurance underwriting data feed

**Buyer:** Insurers and program administrators (B2B **licensing** — not a terminal workflow).

**Product:** Structured **API** payload per athlete:

- Risk score, Velocity score  
- **Injury history** decomposition  
- **Controversy** exposure  
- **Eligibility** risk  
- Actuarial-friendly fields: **confidence intervals**, decay-weighted injury history, **90-day volatility**  

**UI:** **Not shown** in the terminal. Consumed by partners (e.g. Players Health, CBIZ Sports, Zurich) pricing **NIL contract protection**.

---

## Implementation map (this repo)

| Application | Terminal UI | Backend direction |
|-------------|-------------|-------------------|
| 1 CSC deals | `DealAssessmentView` (`report`), PDF TBD | `POST /v1/query` → structured `deal`, comparables, CSC |
| 2 Agent | `WatchlistView`, `ProgramComparisonView`, deal ceiling in `DealAssessmentView` | Watchlist/alerts APIs; agent tools for program NIL + comparables |
| 3 Brand match | `BrandMatch` | `filter_by_brand_fit` + structured `matches[]` |
| 4 Alerts | `AlertsPanel`, `AthleteProfile` | `score_alerts` + history endpoint |
| 5 Insurance | None | Dedicated underwriting API / export (future) |

Canonical product copy lives in this file; the live **Home** screen in `gravity-terminal` summarizes the same applications for operators.
