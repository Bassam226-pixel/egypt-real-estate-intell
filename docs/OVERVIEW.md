# Pipeline Overview — Silver to Finished Product

**Egyptian Investment Lakehouse** — the full journey from cleaned Silver data all the
way to the running recommendation app and its RAG assistant.

> This document is written as presentation prep: every section explains **what** was
> built and **why**, in dependency order. For the transformation-by-transformation
> technical log (including real bugs hit against the live stack) see
> [`PIPELINE.md`](../PIPELINE.md); for the two most recent app/data fixes see
> [`FIX_NOTES.md`](../FIX_NOTES.md).

---

## 1. Executive summary

We ingest raw Egyptian market data (stocks, gold/silver, FX, real estate) into an
open-source **lakehouse** — Apache Iceberg tables on **AWS S3**, cataloged by
**Project Nessie**, processed by **Apache Spark** (local mode), orchestrated by
**Airflow**, and served through **Dremio** for SQL/BI. On top of the lake sits a
**Streamlit investment-recommendation app**: it reads the Gold-layer marts through
Dremio, runs a mean-variance / risk-parity portfolio optimizer, gives a clear
**"you should invest in X"** verdict with the single best specific pick, and backs
it with an **Ask-AI RAG assistant** (ChromaDB + an NVIDIA-hosted LLM) that only
ingests the current recommendation.

```
Raw files (CSV / JSON)                  ── Bronze (no Iceberg tables)
   │  ingestion/loaders/ (boto3 upload)
   ▼
s3://<bucket>/raw/...                   ── raw source files
   │  Spark (local) + Iceberg
   ▼
silver.*  (8 cleaned tables)            ── SILVER
   │  Spark + Iceberg
   ▼
gold.*    (7 analytics marts)           ── GOLD
   │
   ├──► Nessie (catalog, main branch)  ──► Dremio (SQL serving)
   │                                        │
   │                                        └──► Streamlit app (recommendation engine + UI)
   │
   └──► Recommendation result ──► ChromaDB (vector store) ──► Ask-AI (NVIDIA LLM)
```

---

## 2. Short Bronze context (raw files → S3)

Bronze is intentionally dumb. `ingestion/loaders/` just copies each local source file
to `s3://<bucket>/raw/...` with plain `boto3` (no Spark, no schema). There are **no
`bronze.*` Iceberg tables** — Silver reads the raw files directly.

| Loader | Raw file(s) uploaded |
|---|---|
| `load_stocks.py` | `batch_eod_all_stocks.csv`, `fundamentals_all.csv`, `live_quotes_all.csv` |
| `load_egx_index.py` | `EGX30_index.csv` |
| `load_metals.py` | `authority_prices.csv` (LBMA history since 1968), `spot_prices.csv` |
| `load_fx.py` | `currency_rates.csv` |
| `load_re_sales.py` | `aqarmap_data.json`, `propertyfinder_data.json`, `bayut_data.json` |
| `load_re_rentals.py` | `rental_listings.csv` |

Real-estate listings were scraped by `ingestion/scrapers/` (Aqarmap done, PropertyFinder
done, Bayut still partially collected). **Fix applied along the way:** `load_re_sales.py`
originally uploaded only a 300-row enrichment sample; it now uploads the full base
listings from all three platforms so Silver can dedupe across them.

---

## 3. Stack & infrastructure (`docker-compose.yml`)

| Service | Tech | Role | Port(s) |
|---|---|---|---|
| `nessie-postgres` | Postgres 16 | Nessie's JDBC2 version store (holds catalog pointers, not data) | 5433 |
| `nessie` | Nessie 0.99.0 | Iceberg catalog with Git-like branching; data lives on S3 | 19120 |
| `jupyter` | Spark 3.5.3 notebook | Runs every Silver/Gold Spark job (local mode) | 8888 |
| `dremio` | Dremio OSS | SQL serving engine; reads Nessie/Iceberg, exposes to BI + app | 9047, 31010, 32010 |
| `chromadb` | ChromaDB | Vector store for the RAG assistant (`--profile rag`) | 8003 |
| `streamlit` | Streamlit | The recommendation + property-finder + Ask-AI app | 8501 |
| `postgres` / `redis` / `airflow-*` | — | Airflow orchestration stack (LocalExecutor) | 5432 / 6379 / 8082 |
| `api` / `frontend` | — | **Scaffolding only** — directories not created yet | 8000 / 3000 |

~16 GB RAM recommended (Spark + Airflow + Postgres + Dremio together).

---

## 4. Common infrastructure (`spark_jobs/common/`)

These three modules are the "plumbing" every job uses.

- **`spark_session.py`** — builds a local-mode SparkSession wired to the **Nessie catalog**
  (default branch `main`). Resolves a **version-matched** set of JARs automatically via
  `spark.jars.packages`:
  - `iceberg-spark-runtime-3.5_2.12:1.11.0`
  - `nessie-spark-extensions-3.5_2.12:0.108.3`
  - `hadoop-aws:3.3.4` + `aws-java-sdk-bundle:1.12.262` (matched to the Spark 3.5.3 / Hadoop 3.3.4 image)
  - *Why:* no manual JAR downloads; and the trio must move together if the base image
    is ever upgraded (Nessie has no Spark-extensions build past 3.5).
- **`io.py`** — the read/write boundary:
  - `read_csv`/`read_json` read **`s3a://`** (Hadoop filesystem) for raw files.
  - `write_table`/`read_table` use **`s3://`** (Iceberg `S3FileIO`) for table data.
  - `write_table` does `createOrReplace` (DataFrame API, not SQL `CREATE TABLE`, to avoid
    Nessie stale-reference conflicts).
  - `add_metadata(df, source)` appends `_ingested_at` + `_source_file` — **lineage** on
    every table (which raw file / upstream table built it).
- **`nessie.py`** — `check_connection()` (REST ping before paying Spark startup) and
  `ensure_namespaces()` (creates `bronze/silver/gold` namespaces if missing).

---

## 5. Silver layer — 8 cleaned tables

Each job reads raw files directly and writes a typed, cleaned Iceberg table. **No Silver
job depends on another Silver table being written first** (where FX conversion is needed,
jobs import the function from `clean_fx.py` instead of reading its published table).

| Silver table | Source | Key transformations | Why it matters |
|---|---|---|---|
| `stock_eod` | `batch_eod_all_stocks.csv` | Strip `.CA` → `ticker`; **split/dividend back-adjusted `adj_close`** (log-sum-exp over a forward window — Spark has no running-product aggregate); `daily_return = close/prev − 1` | Correct return series despite corporate actions (currently all 0, but logic is right) |
| `fx_rates` | `currency_rates.csv` | Filter to EGP + majors (`USD EUR GBP JPY CHF CNY SAR AED`); collapse the same-day double-scrape to one rate/currency/day; derive `units_per_usd` | Clean FX for cross-currency conversion |
| `metals` | `authority_prices.csv` + `spot_prices.csv` | Union two shapes into one table (`kind = history | spot`); both get `price_egp` via the single EGP rate | Unified gold/silver price history (1968–2026) + current spot |
| `fundamentals` | `fundamentals_all.csv` | Typed financials; **`roe_proxy` = `price_to_book / trailing_pe`** (the P/B÷P/E identity sidesteps missing book-value data) | Valuation inputs for stock scoring |
| `stock_quotes` | `live_quotes_all.csv` | Live single-day quote per ticker with real, non-zero `volume` | The only source of real volume in the project |
| `egx30_index` | `EGX30_index.csv` | Typed OHLCV + `daily_return` | Benchmark index panel |
| `re_sales` | 3 JSON platforms | Normalize each platform's messy strings; `listing_id` parsed from the **link** (Bayut has no ID field); district extraction (Aqarmap first segment; Bayut/PropertyFinder second-to-last segment); drop rows missing district / non-positive price/area; **dedupe on `(district, bedrooms, price_egp, area_sqm)`** (no shared ID across platforms); derive `price_per_sqm_egp` | Clean, cross-platform, deduped sale listings — the engine's real-estate universe |
| `re_rentals` | `rental_listings.csv` | Normalize `monthly_rent_egp` (yearly ÷ 12; ~56 USD rows converted to EGP); require district + lat/lon; dedupe on `listing_id`; **`for_recommendation_use = false`** | Dashboard-only rental data — never feeds the engine |

**Why the `for_recommendation_use` tag exists:** real **rentals** must never feed the
recommendation engine — only **sales** do. The tag is stamped at Silver so the
engine/dashboard boundary survives every downstream join.

---

## 6. Gold layer — 7 analytics marts

Gold reads Silver (and sometimes other Gold) tables. **Order matters** — later jobs read
earlier jobs' written tables:

```
stock_returns_vol ──► stock_scores
gold_metal_roi
re_sale_metrics ──► re_district_metrics
                            └──► asset_scores
silver.egx30_index + silver.metals + silver.fx_rates ──► market_snapshot
```

| Gold table | Reads | Produces (purpose) |
|---|---|---|
| `stock_returns_vol` | `silver.stock_eod` | Full per-ticker daily panel: `momentum_3m` (63-trading-day return — history is only ~118 days, so the skeleton's 126-day lag would be all-null) and `vol_90d` (90-day stdev of daily returns, annualized ×√252) |
| `stock_scores` | `silver.fundamentals` + `gold.stock_returns_vol` + `silver.stock_quotes` | Cross-sectional 0–1 scores: `norm_roe`, `div_yield_score`, `vol_score` (inverted), `liquidity_score` (from **live quotes** — `stock_eod.volume` is always 0 in this scrape) |
| `gold_metal_roi` | `silver.metals` | Trailing 1/3/5/10-yr ROI for gold & silver (USD and EGP) via as-of join on the nearest price |
| `re_sale_metrics` | `silver.re_sales` | **Engine-eligible**: district-level `avg/median/min/max price_per_sqm`, `listing_count` (drop districts with <3 listings so one noisy listing can't set a district's price). No rent/yield columns. `for_recommendation_use = true` |
| `re_district_metrics` | `gold.re_sale_metrics` + `silver.re_rentals` | **Dashboard-only**: inner join sale+rental per district; `gross_yield_pct = (avg_rent_per_sqm×12 / avg_price_per_sqm)×100`. `for_recommendation_use = false` |
| `asset_scores` | `gold.stock_returns_vol` + `gold.gold_metal_roi` + `silver.re_sales` + `gold.re_district_metrics` | **Cross-asset comparison** — one `roi_proxy` + `vol_proxy` per asset class. This is the optimizer's input |
| `market_snapshot` | `silver.egx30_index` + `silver.metals` + `silver.fx_rates` | Tidy long fact table `(category, symbol, metric, value, unit)` via Spark `stack()` — different entities don't share a wide shape |

### `gold.asset_scores` in depth (the engine's heart)

| asset | roi_proxy (return) | vol_proxy (risk) |
|---|---|---|
| stocks | equal-weight avg of `momentum_3m` | equal-weight avg of `vol_90d` |
| gold | trailing 1-yr EGP return | fresh 90-day annualized vol from `daily_metal_prices()` |
| silver | trailing 1-yr EGP return | fresh 90-day annualized vol |
| real_estate | avg district **gross rental yield + 4% assumed appreciation** | **assumed 10%** long-run annualized vol |

Stocks and metals have genuine daily price history, so their return/vol are real
time-series statistics. **Real estate has no price history at all** — the listings are a
single snapshot — so its numbers are *documented assumptions* spelled out in the
`roi_proxy_label` / `vol_proxy_label` columns.

> **Fix applied (2026-08-01):** real estate originally used the raw district rental
> yield as "return" (3.5%) and the **cross-sectional coefficient of variation of
> price/m² (0.87)** as "volatility". That dispersion statistic — inflated by a
> 759,000 EGP/sqm outlier vs a 61,000 avg — made real estate look like the *riskiest*
> asset in the optimizer, so a low-risk/long profile gave it ~zero weight. Now RE uses
> **yield + 4% appreciation (~7.5%)** and **10% volatility**, making it the stable
> low-vol anchor it should be. Constants live at the top of `asset_scores.py`
> (`RE_ANNUAL_APPRECIATION`, `RE_ANNUAL_VOLATILITY`).

---

## 7. Serving layer — Nessie, Dremio, registration

- **Nessie** is the Iceberg catalog. Every table lives under `nessie.<layer>.<table>` on
  the `main` branch. Spark writes there directly; Dremio reads it. Git-like branching
  exists (`/api/v2/trees`) — the intended (not yet enforced) quality gate would write to
  a run branch and merge to `main` only on pass.
- **Dremio** is the SQL serving layer: `SELECT * FROM nessie.gold.stock_scores`. It was
  set up **once** through the UI (admin `admin/admin123`, add **Nessie source** pointing
  at `http://nessie:19120/api/v2`, with the S3 storage credentials) — see
  `DREMIO_SETUP.md`. The app talks to it over its **REST API** (`apiv2/login` +
  `api/v3/sql` + job polling).
- **`register_tables.py`** — a standalone helper that registers already-written Iceberg
  tables (found by scanning S3 for their `metadata/*.metadata.json`) into Nessie via the
  Nessie REST API. Useful as a manual fallback to reconcile the catalog with what's on S3.

---

## 8. Recommendation engine (`app/engine/`)

The flow when a user clicks **Get Recommendation**:

```
UserProfile(amount, risk_level, duration)
   │
   ├─► risk_profiler.get_risk_params()      low/med/high → target_vol, max single-asset
   │                                        weight, min/max stock weight, preference
   ├─► risk_profiler.get_duration_params()  short/med/long → max RE weight, min liquidity
   │
   ├─► optimizer.mean_variance_optimize()   maximize Sharpe subject to target vol + bounds
   │      • correlation matrix (stocks↔gold −0.15, gold↔silver +0.70, RE↔stocks +0.30, …)
   │      • bounds: per-asset caps (RE ≤ duration cap, stocks ≤ risk cap)
   │      • if infeasible (returns None) → risk_parity_weights() fallback
   │
   ├─► compute_portfolio_stats()            expected return, volatility, Sharpe, risk contribs
   │
   ├─► recommender._drill_*()               specific picks per asset class:
   │      stocks → top 3 by composite score (ROE, dividend yield, liquidity,
   │                momentum, inverted vol)
   │      real_estate → actual listings within the RE budget
   │      gold/silver → trailing ROI table
   │
   └─► RecommendationResult                  allocations + drilldowns + verdict
        + best_specific_pick()               single best stock ticker / property / metal
```

Design points worth presenting:

- **Risk parity fallback:** for Low risk the 10% target volatility is *infeasible* with
  real estate capped at 40% (minimum achievable portfolio vol is ~14–15%), so the solver
  returns `None` and the app falls back to inverse-volatility risk-parity weights. This
  is why RE can sit above the 40% single-asset cap but under the 60% long-duration cap.
  *(Pre-existing behavior, documented in FIX_NOTES.md.)*
- **Clear verdict (added 2026-08-01):** the UI now leads with a bold
  **"You should invest in: {top asset}"** banner and highlights the single best specific
  pick (best stock ticker / best property) — not just a portfolio of weights.

---

## 9. Streamlit UI (`app/streamlit_app.py`) — 3 tabs

1. **Recommendation** — amount / risk / duration inputs → verdict banner + best pick →
   allocation table + pie → per-asset detail expanders (stock picks with scores, property
   listings with links, metal ROI) → rationale.
2. **Property Finder** — budget / district / type / bedrooms / area filters against
   `silver.re_sales`; relaxed search if no exact matches.
3. **Ask AI** — RAG chat over the current recommendation (see below).

All data comes through `DremioDataProvider` (REST login → SQL submit → job poll → rows).

---

## 10. RAG pipeline (`app/rag/`)

The original design ingested the **entire gold layer** into ChromaDB
(`asset_scores` + `market_snapshot` + `stock_scores` + `re_sale_metrics`) so the AI could
answer general questions about the whole lakehouse.

**Change (2026-08-01):** we now ingest **only the recommendation result**:

- `ingest_recommendation(rec)` builds a handful of documents from the
  `RecommendationResult` (one portfolio summary + one per asset-class drilldown) and
  **resets the collection first** (delete + recreate), so ChromaDB holds exactly one
  thing: the latest recommendation.
- The app **auto-ingests** after each recommendation and keeps a manual
  **"Re-ingest Recommendation into ChromaDB"** button. The whole-gold-layer button was
  removed.
- `answer_question()` retrieves the closest documents from ChromaDB, injects the current
  recommendation, and calls an **NVIDIA-hosted LLM** (`meta/llama-3.3-70b-instruct`) for a
  concise, grounded answer.
- **Embedding model pre-seeded at build:** the Dockerfile warms up ChromaDB's default
  `all-MiniLM-L6-v2` ONNX model so the first auto-ingest doesn't block on an ~80 MB
  runtime download.

*Why:* questions are about "my recommendation" — top pick, why, what to buy — and that
context is small and changes every run. Scoping the vector DB to the recommendation keeps
retrieval relevant and avoids storing the whole gold layer.

---

## 11. Key decisions & fixes timeline

| When | Change | Why |
|---|---|---|
| During build | `load_re_sales.py` uploads all 3 platforms' full listings | Silver needs cross-platform dedupe |
| During build | `adj_close` back-adjustment, 63-day momentum, live-quotes liquidity | Real gaps in the source data (0 volume, short history) |
| During build | `io.read_table` + `add_metadata` wired into all 13 jobs | Gold jobs need to read published tables; lineage matters |
| During build | Fixed module-level `F.col()` bug in `gold_metal_roi`; `Column` import in `stock_scores` | Would have crashed at import time |
| 2026-08-01 | `asset_scores`: RE return = yield + 4% appreciation, RE vol = 10% (was 87% dispersion CV) | RE was wrongly the "riskiest, lowest-return" asset; optimizer avoided it |
| 2026-08-01 | Removed fragile `"pct" in label → /100` heuristic in `recommender.py` | Decimal units now guaranteed by the data layer |
| 2026-08-01 | Verdict banner + `best_specific_pick()` in the UI | Clear single answer: *invest in X, and specifically Y* |
| 2026-08-01 | RAG ingests only the recommendation (collection reset) | Vector DB scoped to "this recommendation", not the whole gold layer |
| 2026-08-01 | Dockerfile pre-seeds ChromaDB embedding model | No first-run stall on an 80 MB download |

---

## 12. Known limitations (be ready for these questions)

1. **FX is a one-day snapshot** — the same current EGP rate is applied across all of
   metals' 1968–2026 history (approximation, not point-in-time). Consequence:
   `roi_*_egp == roi_*_usd` for metals (the single rate cancels out).
2. **Real-estate return/vol are assumptions** (no price history) — clearly labeled in the
   table, tunable constants in `asset_scores.py`.
3. **Bayut is incomplete** — most Bayut sale rows lack a `location`, so they drop out in
   Silver; scraping was still in progress.
4. **Quality gate is scaffolded, not enforced** — `spark_jobs/quality/` has check suites
   and a (currently empty) `run_gate.py`; tables are written straight to `main`.
5. **Optimizer fallback** — low-risk mean-variance is infeasible (target vol < achievable),
   so it silently uses risk-parity weights that don't respect the single-asset cap.
6. **`api/` and `frontend/` are scaffolding** — only the Streamlit app is implemented.

---

## 13. How to run & verify

```bash
# Start the demo stack (core + chromadb + streamlit; no api/frontend builds needed)
docker compose up -d --build nessie-postgres nessie dremio chromadb streamlit

# Spark jobs run inside the jupyter container (demo scope does not include it)
docker compose up -d jupyter
docker compose exec -T jupyter python -m spark_jobs.gold.asset_scores   # (re)build a mart
```

| Service | URL |
|---|---|
| Streamlit app | http://localhost:8501 |
| Dremio | http://localhost:9047 |
| Nessie API | http://localhost:19120/api/v2 |
| Jupyter | http://localhost:8888 (token `egypt`) |
| Airflow | http://localhost:8082 (admin/admin) |

Verify end-to-end: run a recommendation (100k / low / long → verdict **Real Estate**,
best pick Port Fuad Land, EGP 75k) → it auto-ingests 5 recommendation docs into ChromaDB →
Ask AI answers from that context.

---

## 14. Presentation talking points

- **Problem:** scattered Egyptian market data → no single view of where to invest.
- **Architecture:** a proper lakehouse — Bronze (raw S3) → Silver (cleaned) → Gold
  (analytics marts) on Iceberg + Nessie, served by Dremio.
- **Engineering highlights:** back-adjustment math, cross-sectional scoring, an
  engine/dashboard data boundary enforced with `for_recommendation_use`, cross-asset
  comparison, and honest handling of assets with no price history.
- **The product:** one click → clear verdict + best specific pick + a grounded AI assistant
  scoped to your recommendation.
- **Honesty points:** the FX snapshot limitation, RE assumptions, and the quality-gate
  stub — show you know exactly where the edges are.
