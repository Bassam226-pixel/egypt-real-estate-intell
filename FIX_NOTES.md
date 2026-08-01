# Fix Notes — Real estate shown as lowest-return + highest-volatility

Date: 2026-08-01

## Bug report

In the Streamlit recommender (http://localhost:8501), a profile of
EGP 100,000 / **Low risk** / **Long** duration returned real estate as both the
lowest expected-return asset **and** the highest-volatility asset. That made it
the riskiest-looking asset, so the optimizer gave it ~zero weight.

## Root cause

`gold.asset_scores` (built by `spark_jobs/gold/asset_scores.py`) mixes four
**incomparable** statistics:

| asset | roi_proxy (return) | vol_proxy (risk) |
|---|---|---|
| stocks | −2.1% — trailing **3-month** return | 19.6% — real 90d time-series vol |
| gold | +23.2% — trailing **1-year** return | 29.3% — real time-series vol |
| silver | +78.1% — trailing **1-year** return | 65.2% — real time-series vol |
| real_estate | +3.5% — **annual rental yield** (not a return) | **87%** — cross-sectional CV of price/m² across districts |

For real estate specifically:
1. **Return was a yield, not a return.** RE listings are a single snapshot with
   no price history, so the job borrowed the district gross rental yield (3.48%).
   Compared to trailing 1-yr price returns (gold/silver) it always looked like the
   worst return.
2. **Volatility was dispersion, not volatility.** `stddev(price_per_sqm)/avg` across
   districts = 0.87, inflated by a price-per-sqm outlier of ~759,090 EGP (vs avg
   61,083). That is cross-sectional price spread, not investment risk — yet the
   optimizer treated it as the riskiest asset's vol. Real estate's actual
   long-run investment volatility is typically ~5–15%.

## Changes made

### 1. `spark_jobs/gold/asset_scores.py` — `_real_estate_row()`

Replaced the borrowed proxies with documented assumptions (RE has no price history,
so no time-series return/vol can be computed):

- Added module constants:
  - `RE_ANNUAL_APPRECIATION = 0.04`
  - `RE_ANNUAL_VOLATILITY = 0.10`
- `roi_proxy` = `avg(gross_yield_pct)/100 + 0.04` → **0.0748** (~7.5%),
  label `avg_gross_yield_plus_assumed_appreciation`.
- `vol_proxy` = **0.10**, label `assumed_longrun_annualized_vol`.
- `roi_proxy` is now stored in **decimal** units (matching stocks/gold/silver),
  so all four rows share one unit convention.

### 2. `app/engine/recommender.py`

Removed the fragile unit heuristic:

```python
# before
if "pct" in label.lower():
    raw_roi /= 100.0
```

The data layer now guarantees decimal `roi_proxy` for all rows, so the heuristic
(which silently corrupted any decimal value whose label contained "pct") was deleted.

## Rebuild steps performed

1. Started the `jupyter` container (Spark runtime).
2. Rebuilt the table: `python -m spark_jobs.gold.asset_scores`
   (createOrReplace on Nessie `main`).
3. Rebuilt the Streamlit image with the app change:
   `docker compose up -d --build streamlit`.
4. Stopped the temporary `jupyter` container (demo scope does not include it).

## Verification

- `gold.asset_scores` via Dremio now returns:
  `real_estate  roi=0.0748  vol=0.1000`.
- End-to-end run of `Recommender.recommend()` (100k / low / long):

| asset | weight | expected return | volatility |
|---|---|---|---|
| **real_estate** | **49.9%** (top pick) | 7.5% | **10.0%** ← lowest |
| stocks | 25.4% | −2.1% | 19.6% |
| gold | 17.0% | 23.2% | 29.3% |
| silver | 7.7% | 78.1% | 65.2% |

Real estate is now the stable low-vol anchor and the top pick for a low-risk /
long-horizon profile, as intended.

## Known observation (pre-existing, not fixed)

For Low risk the mean-variance solver's `target_vol = 0.10` is **infeasible** with
real estate capped at 40% (the minimum achievable portfolio volatility is ~14–15%).
The solver returns `None` and the app silently falls back to
`risk_parity_weights()`, which only honors the duration-based `max_re_weight`
(60% for long), not the risk-level `max_single_asset_weight` (40% for low).
This is why the recommendation shows real estate at 49.9% (under the 60% long cap
but above the 40% single-asset cap). Same behavior existed before this fix
(confirmed: solver also returned `None` with the old data). A follow-up fix would
make the fallback respect `max_single_asset_weight` too.

---

# Fix Notes — Clear verdict + recommendation-only RAG (2026-08-01)

## What changed

### 1. Clear single-asset verdict + best specific pick
- `app/engine/recommender.py` — added module-level `best_specific_pick(result)`:
  returns the first pick of the top asset's drilldown (best stock ticker, best
  property listing, or metal ROI row).
- `app/streamlit_app.py` (Recommendation tab) — after "Get Recommendation" a bold
  banner shows **"You should invest in: {top_asset_class}"** plus the highlighted
  single best pick, e.g. "Best property: Port Fuad — Land, 462 sqm, EGP 75,000
  (EGP 162/sqm)". The allocation table/pie and per-asset expanders remain below.

### 2. RAG ingests ONLY the recommendation result (not the gold layer)
- `app/rag/ingest.py` — replaced `ingest_all()` (which pushed the entire
  `gold.asset_scores` / `market_snapshot` / `stock_scores` / `re_sale_metrics`
  into ChromaDB) with `ingest_recommendation(rec)`:
  - Builds documents **only** from the `RecommendationResult`: one portfolio
    summary doc + one doc per drilldown (stocks / real_estate / gold / silver).
  - **Resets the collection first** (delete + recreate) so ChromaDB holds only the
    latest recommendation.
  - All docs tagged `type=recommendation` with a `scope` metadata.
- `app/rag/query.py` — system prompt now describes context as "the current
  recommendation" instead of the full lakehouse.
- `app/streamlit_app.py` (Ask AI tab):
  - **Auto-ingests** each new recommendation into ChromaDB right after it is
    generated (Ask AI works immediately).
  - Manual **"Re-ingest Recommendation into ChromaDB"** button retained.
  - Removed the "Ingest Gold Layer into ChromaDB" button and its gold-layer
    provider fetches.

### 3. Embedding model pre-seeded at build
- `app/Dockerfile` — added a `RUN` step that loads ChromaDB's default ONNX
  embedding model (`all-MiniLM-L6-v2`, ~80 MB) during the image build, so the
  first auto-ingest doesn't block on a runtime download.

## Verified

- `Recommender.recommend()` → verdict `real_estate`, best pick
  `Port Fuad — Land, 462 sqm, EGP 75,000 (EGP 162/sqm)`.
- `ingest_recommendation()` stored exactly **5 docs** (portfolio + 4 asset
  drilldowns), all `type=recommendation`; no gold-layer docs.
- `answer_question("Which asset class should I invest in...")` answered from the
  recommendation context: top pick Real Estate (50%), best property Port Fuad.

