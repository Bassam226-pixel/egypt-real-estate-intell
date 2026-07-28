# Data Pipeline — Bronze → Silver → Gold

Medallion architecture on AWS S3 + Nessie (Iceberg catalog) + Spark (local mode, run
inside the `jupyter` container — see `docker-compose.yml`). Bronze lands raw files in
S3; Silver reads those raw files directly and writes cleaned Iceberg tables; Gold reads
Silver (and sometimes other Gold) tables and writes analytics marts. Every Silver/Gold
table also carries `_ingested_at` (job run timestamp) and `_source_file` (lineage —
which raw file(s) or upstream table(s) it was built from), via `common/io.py`'s
`add_metadata()`.

---

## Bronze — `ingestion/loaders/` (raw files → `s3://<bucket>/raw/...`)

Bronze here is intentionally dumb: each loader just copies a local file to S3 via
`s3_upload.upload_raw()` (a plain `boto3` `upload_file`, no Spark, no schema). No
Iceberg `bronze.*` tables exist — Silver reads straight from `raw/` via
`common/io.py`'s `read_csv`/`read_json`.

| Loader | Uploads | S3 key(s) |
|---|---|---|
| `load_stocks.py` | `data/Egx Stocks data/{batch_eod_all_stocks,fundamentals_all,live_quotes_all}.csv` | `raw/batch_eod_all_stocks.csv`, `raw/fundamentals_all.csv`, `raw/live_quotes_all.csv` |
| `load_egx_index.py` | `EGX30_index.csv` | `raw/EGX30_index.csv` |
| `load_metals.py` | `data/Gold/{authority_prices,spot_prices}.csv` | `raw/authority_prices.csv`, `raw/spot_prices.csv` |
| `load_fx.py` | `data/Gold/currency_rates.csv` | `raw/currency_rates.csv` |
| `load_re_sales.py` | `data/{aqarmap,propertyfinder,bayut}/*_data.json` | `raw/aqarmap_data.json`, `raw/propertyfinder_data.json`, `raw/bayut_data.json` |
| `load_re_rentals.py` | `data/rental data/rental_listings.csv` | `raw/rental_listings.csv` |

**Fix applied:** `load_re_sales.py` originally only uploaded
`propertyfinder_data_enriched.json` (a 300-row enrichment sample). Since Silver's
`clean_re_sales.py` needs to dedupe across all 3 sale platforms, it now uploads the
full base listing files from all three sources (1199 + 1250 + 107 rows).

---

## Silver — `spark_jobs/silver/` (raw → cleaned Iceberg tables)

None of these depend on another Silver table being written first — each reads raw
files directly (or, for FX-dependent conversions, imports a function from
`clean_fx.py` directly rather than reading its published table, so ordering between
Silver jobs never matters).

### `clean_stocks_eod.py` → `silver.stock_eod`
From `batch_eod_all_stocks.csv`. Strips the `.CA` suffix into `ticker`. Computes
`adj_close` via a proper split/dividend back-adjustment (log-sum-exp over a forward
window, since Spark has no running-product window aggregate) and `daily_return` =
`close / prev_close - 1`. In the current data, `Dividends`/`Stock_Splits` are always
0, so `adj_close == close`, but the logic is correct if that ever changes.

### `clean_fx.py` → `silver.fx_rates`
From `currency_rates.csv`, filtered to EGP + a majors list (`USD, EUR, GBP, JPY, CHF,
CNY, SAR, AED`). The source is a same-day double-scrape (two timestamps ~25s apart);
collapsed to one rate per currency per day (latest wins). Exposes
`latest_egp_rate(spark)`, reused by `clean_metals.py` and `clean_re_rentals.py` for
USD→EGP conversion (`EGP = USD / rate_EGP`, since `rate` = USD value of 1 unit of
that currency — verified against the data: `USD` rate is exactly `1.0`, `SAR` is
`0.2667` ≈ 1/3.75, the real SAR peg).

### `clean_metals.py` → `silver.metals`
Unions two shapes into one table (`kind = 'history' | 'spot'`):
- **history**, from `authority_prices.csv` (1968–2026, LBMA am/pm fixes + silver's
  single daily print).
- **spot**, from `spot_prices.csv`, collapsed to the latest timestamp per metal
  (same double-scrape pattern as FX).

Both get a `price_egp` column via the single EGP rate from `clean_fx.latest_egp_rate()`.
**Known limitation:** `currency_rates.csv` is a one-day snapshot, so the *same*
current EGP rate is applied across the full 1968–2026 history — a best-effort
approximation, not point-in-time-accurate FX.

### `clean_fundamentals.py` → `silver.fundamentals` + `silver.stock_quotes` + `silver.egx30_index`
One file, three outputs (matches the task's own grouping):
- **fundamentals**, from `fundamentals_all.csv`: typed columns, plus `roe_proxy` =
  `price_to_book / trailing_pe` (the P/B ÷ P/E identity: `(Price/BVPS)/(Price/EPS) =
  EPS/BVPS = ROE`), sidestepping the fact that book value / shares outstanding aren't
  in this feed.
- **stock_quotes**, from `live_quotes_all.csv`: the live single-snapshot quote per
  ticker (real, non-zero `volume`).
- **egx30_index**, from `EGX30_index.csv`: typed OHLCV + `daily_return`.

### `clean_re_sales.py` → `silver.re_sales`
Combines `aqarmap_data.json` + `propertyfinder_data.json` + `bayut_data.json`.
Per-source normalization:
- `listing_id` parsed from the **link** (not the source's own ID field — Bayut
  doesn't have one), via a per-platform regex (`/listing/(\d+)-`, `-(\d+)\.html$`,
  `details-(\d+)\.html$`).
- `price_egp` / `area_sqm` parsed by stripping non-digits / extracting the leading
  number from strings like `"32,900,000 ج.م"`, `"194 م² sqm"`, `"430 Sq. M."`.
- `district`: Aqarmap's `location` is `"District / Sub-area"` (first segment). Bayut
  and PropertyFinder's `location` is comma-separated, most-specific-first, ending in
  the governorate/region — so the **second-to-last** segment is used as the district
  proxy.
- Rows without a district, or with non-positive price/area, are dropped (`district`
  is a hard requirement per the task). Bayut's `location` is null on more than half
  its rows, so most Bayut sale listings never make it into `silver.re_sales` — that's
  a real gap in that source (per `data_overview.md`, Bayut scraping is still
  incomplete), not a bug.
- Deduped on `(district, bedrooms, price_egp, area_sqm)` — there's no ID shared
  across the 3 platforms, so `listing_id` alone can't detect a listing posted on two
  sites.
- `price_per_sqm_egp` = `price_egp / area_sqm`.

### `clean_re_rentals.py` → `silver.re_rentals`
From `rental_listings.csv` (420 rows, already source-tagged/combined upstream).
- `monthly_rent_egp`: normalizes `period` (`monthly` vs `yearly` ÷ 12), and converts
  the ~56/420 USD-denominated rows to EGP via `clean_fx.latest_egp_rate()` (found
  while validating the data — mixing USD and EGP rents unconverted would have
  silently corrupted every downstream district rent average).
- Requires `district` **and** `latitude`/`longitude` (per task); ~59/420 rows are
  missing district and get dropped, leaving the ~361-row "medium confidence" set the
  task's delta notes describe.
- `for_recommendation_use = false`, tagged here at Silver so the engine/dashboard
  boundary (real rentals never feed the recommendation engine — only sales do)
  survives every downstream join, all the way to a future quality-gate check.
- Deduped on `listing_id` (20/420 rows were exact full-row duplicates, e.g. the same
  Bayut listing appearing twice).

---

## Gold — `spark_jobs/gold/` (Silver/Gold → analytics marts)

Run in this order — later ones read earlier ones' *written* Iceberg tables via
`io.read_table()` (except where noted, some re-derive from a function import instead,
which avoids that ordering dependency):

```
stock_returns_vol → stock_scores
gold_metal_roi
re_sale_metrics → re_district_metrics
                              ↘
stock_returns_vol + gold_metal_roi + re_sales + re_district_metrics → asset_scores
egx30_index + metals + fx_rates → market_snapshot
```

### `stock_returns_vol.py` → `gold.stock_returns_vol`
Full daily panel per ticker (not just latest date). `momentum_3m` = 63-trading-day
return (`ret_63` on `adj_close`) — **not** the skeleton's original 126-day/6-month lag,
because the EOD history is only ~123 trading days; a 126-day lag would be all-null.
`vol_90d` = stdev of daily returns over a trailing 90-trading-day window, annualized
(`× √252`).

### `stock_scores.py` → `gold.stock_scores`
Cross-sectional (all-tickers) min-max normalization to a 0–1 score for `norm_roe`,
`div_yield_score`, and `vol_score` (inverted — lower volatility scores higher).
`momentum_3m` passes through raw/unscored (matches how the task lists it without a
`_score` suffix). `liquidity_score` is normalized `dollar_volume_latest` = `volume ×
close` **from `silver.stock_quotes`**, not `stock_eod` — the historical EOD file's
`Volume` column is `0` for every one of its 1230 rows (a real gap in that scrape), so
a rolling average from it would always be zero; the live quotes snapshot has real
volume.

### `gold_metal_roi.py` → `gold.gold_metal_roi`
Trailing 1/3/5/10-yr ROI for gold and silver, in both USD and EGP, via an as-of join
(nearest available price on or before `latest_date - N years` — the 1968–2026 history
isn't perfectly continuous day-to-day). Exposes `daily_metal_prices()`, reused by
`asset_scores.py`. **Note:** because of the single-FX-snapshot limitation in
`clean_metals.py`, `roi_*_egp` comes out numerically identical to `roi_*_usd` (the one
EGP rate scales both the numerator and denominator the same way, so it cancels) — this
is a direct, expected consequence of that data limitation, not a bug.

### `re_sale_metrics.py` → `gold.re_sale_metrics` (**engine-eligible**)
District-level aggregates from `silver.re_sales`: `avg_price_per_sqm_egp`,
`median_price_per_sqm_egp`, min/max, `avg_area_sqm`, `listing_count`. Districts with
fewer than 3 listings are dropped (don't let one noisy listing set a district's
recommended price/m²). Tagged `for_recommendation_use = true`. **Deliberately has zero
rent/yield columns** — that's the whole point of the split from the dashboard mart.

### `re_district_metrics.py` → `gold.re_district_metrics` (**dashboard-only**)
Imports and reuses `re_sale_metrics()`'s aggregation, joins in a rental aggregate
(`avg_rent_per_sqm_egp` from `silver.re_rentals`, districts with <2 rental listings
dropped), and computes `gross_yield_pct` = `(avg_rent_per_sqm_egp × 12 /
avg_price_per_sqm_egp) × 100`. Inner join — a district only appears here if it has
*both* a sale and a rental read. Tagged `for_recommendation_use = false`.

### `asset_scores.py` → `gold.asset_scores`
Cross-asset comparison: stocks vs. gold vs. silver vs. real estate. Stocks and metals
have genuine daily price history, so their `roi_proxy`/`vol_proxy` are a real trailing
return (equal-weight average of `momentum_3m` across tickers for stocks;
`roi_1yr_egp` for each metal) and time-series volatility (equal-weight `vol_90d`
average for stocks; a fresh 90-day annualized vol computed from
`daily_metal_prices()` for each metal — `gold_metal_roi.py` doesn't compute vol at
all, so this is done here). **Real estate listings are a single snapshot with no
price history at all**, so it can't have a real ROI/vol — instead it borrows the
average district `gross_yield_pct` as its "return" proxy and the cross-sectional
coefficient of variation of `price_per_sqm_egp` across all listings as its "risk"
proxy. Every row carries a `*_label` column spelling out what its numbers actually
mean, since it's explicitly *not* the same statistic across rows.

### `market_snapshot.py` → `gold.market_snapshot`
EGX30 index, metal spot prices, and FX rates don't share a natural wide-table shape
(different entities, different metrics, different units), so this is a tidy long
"fact table" — `(category, symbol, metric, value, unit, as_of_date)` — built via
Spark SQL's `stack()` function, rather than one sparse, null-filled row per date.

---

## `spark_jobs/common/` additions

- **`io.read_table(spark, layer, table)`** — added; was missing. Every Gold job needs
  to read an already-published Silver/Gold Iceberg table (`spark.table("nessie.<layer>.<table>")`),
  and only raw-file reads + table writes existed before.
- **`io.add_metadata(df, source_file)`** — already existed but was unused by every
  job; now called in all 13 `run()` functions, right before the final
  `write_table()` (not inside the reusable transform functions some jobs import from
  each other, so lineage columns from an inner call can't get silently overwritten by
  an outer one).

---

## Real bugs found while actually running these against the live Nessie/S3 stack

1. **`stock_scores.py`**: `_min_max_normalize(column: str) -> F.Column` — `Column`
   isn't an attribute of `pyspark.sql.functions`; it lives in `pyspark.sql`. Would
   have raised `AttributeError` at import time. Fixed to `from pyspark.sql import
   Column`.
2. **`gold_metal_roi.py`**: `_SESSION_PRIORITY = F.when(F.col("session")...)` was a
   **module-level** constant — evaluated at import time, before any SparkSession
   exists. `F.col()` needs an active `SparkContext` under the hood, so importing the
   module crashed with `AssertionError: assert SparkContext._active_spark_context is
   not None`. Fixed by building the expression inside the function that uses it.
3. **`stock_scores.py`** liquidity: not a code bug so much as a wrong data source —
   see `stock_scores.py` above (`stock_eod.volume` is always 0; switched to
   `stock_quotes.volume`).
