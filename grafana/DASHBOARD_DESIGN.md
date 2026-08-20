# Dashboard Design Guide

> ⚠️ **Stale — do not use the SQL/schema below.** This document predates the current Gold-layer
> schema and describes tables/columns that don't exist in this repo (e.g. `gold.stock_performance`
> with embedded sma/rsi/macd, `gold.stock_fundamentals_enriched`, `gold.commodity_trends`,
> `gold.currency_matrix`, `gold.real_estate_analytics`, `gold.portfolio_summary`). The real,
> working queries are the ones in `grafana/dashboards/*.json` — treat those JSON files as the
> source of truth for schema and panel design, not this document. This file needs a full
> regeneration against the actual schema (see `spark_jobs/gold/*.py` and
> `scripts/export_to_postgres.py`) before it can be trusted again.

This document provides a comprehensive reference for all dashboard structures, visualizations, and KPIs for the Egypt Investment Analytics project.

---

## Table of Contents

1. [Gold Layer Tables](#1-gold-layer-tables)
2. [Visualizations by Domain](#2-visualizations-by-domain)
3. [Dashboard Structure Recommendations](#3-dashboard-structure-recommendations)
4. [Key Performance Indicators (KPIs)](#4-key-performance-indicators-kpis)
5. [Implementation Guide](#5-implementation-guide)

---

## 1. Gold Layer Tables

The Gold layer contains business-level aggregations and enriched tables consumed by dashboards.

### 1.1 `gold.stock_performance`

Enriched stock data with calculated metrics for technical analysis.

| Column | Type | Description |
|--------|------|-------------|
| symbol | String | Stock ticker (e.g., "COMI.CA") |
| date | Date | Trading date |
| open | Double | Opening price (EGP) |
| high | Double | Day high (EGP) |
| low | Double | Day low (EGP) |
| close | Double | Closing price (EGP) |
| volume | Long | Trading volume |
| change_pct | Double | Daily percentage change |
| sma_20 | Double | 20-day Simple Moving Average |
| sma_50 | Double | 50-day Simple Moving Average |
| ema_12 | Double | 12-day Exponential Moving Average |
| ema_26 | Double | 26-day Exponential Moving Average |
| rsi | Double | Relative Strength Index (14-day) |
| macd | Double | MACD Line |
| macd_signal | Double | MACD Signal Line |
| macd_hist | Double | MACD Histogram |
| volatility_20 | Double | 20-day Rolling Volatility |
| ytd_return | Double | Year-to-Date Return |
| _ingested_at | Timestamp | Ingestion timestamp |

### 1.2 `gold.stock_fundamentals_enriched`

Company fundamentals with calculated ratios and rankings.

| Column | Type | Description |
|--------|------|-------------|
| symbol | String | Stock ticker |
| company_name | String | Company name |
| sector | String | Business sector |
| industry | String | Industry sub-sector |
| market_cap_egp | Double | Market cap in EGP |
| market_cap_rank | Integer | Rank by market cap |
| trailing_pe | Double | Trailing P/E ratio |
| forward_pe | Double | Forward P/E ratio |
| pe_sector_avg | Double | Sector average P/E |
| price_to_book | Double | Price-to-book ratio |
| eps | Double | Earnings per share |
| dividend_yield | Double | Dividend yield |
| dividend_yield_rank | Integer | Rank by dividend yield |
| beta | Double | Beta (volatility vs. market) |
| week52_high | Double | 52-week high |
| week52_low | Double | 52-week low |
| week52_position | Double | Current price position in 52-week range (0-100%) |
| employees | Integer | Number of employees |
| revenue_growth | Double | Revenue growth rate |
| profit_margin | Double | Profit margin |
| _ingested_at | Timestamp | Ingestion timestamp |

### 1.3 `gold.commodity_trends`

Gold and silver historical trends with rolling statistics.

| Column | Type | Description |
|--------|------|-------------|
| date | Date | Price date |
| metal | String | "GOLD" or "SILVER" |
| price_usd | Double | Price in USD per gram |
| sma_30 | Double | 30-day Simple Moving Average |
| sma_90 | Double | 90-day Simple Moving Average |
| sma_365 | Double | 365-day Simple Moving Average |
| volatility_30 | Double | 30-day Rolling Volatility |
| volatility_90 | Double | 90-day Rolling Volatility |
| monthly_return | Double | Monthly percentage change |
| yearly_return | Double | Yearly percentage change |
| gold_silver_ratio | Double | Gold/Silver price ratio (gold only) |
| _ingested_at | Timestamp | Ingestion timestamp |

### 1.4 `gold.currency_matrix`

Currency pairs with relative strength analysis.

| Column | Type | Description |
|--------|------|-------------|
| snapshot_time | Timestamp | Rate snapshot time |
| currency | String | Currency code (USD, EUR, GBP, JPY, CNY, SAR, AED, EGP, CHF, CAD) |
| rate_vs_usd | Double | Exchange rate vs USD |
| daily_change | Double | Daily change percentage |
| weekly_change | Double | Weekly change percentage |
| monthly_change | Double | Monthly change percentage |
| volatility_30 | Double | 30-day Rolling Volatility |
| strength_index | Double | Relative strength index (0-100) |
| _ingested_at | Timestamp | Ingestion timestamp |

### 1.5 `gold.real_estate_analytics`

Property metrics with location and developer aggregations.

| Column | Type | Description |
|--------|------|-------------|
| listing_id | String | Unique listing ID |
| property_type | String | Property type |
| location | String | Location |
| full_location | String | Full location detail |
| bedrooms | Integer | Number of bedrooms |
| bathrooms | Integer | Number of bathrooms |
| area_sqm | Double | Area in square meters |
| price_egp | Double | Price in EGP |
| price_per_sqm | Double | Price per sqm |
| price_usd | Double | Price in USD (calculated) |
| project_name | String | Compound/project name |
| project_status | String | Construction status |
| developer | String | Developer name |
| delivery_date | String | Delivery quarter |
| amenities_count | Integer | Number of amenities |
| location_avg_price | Double | Average price in location |
| location_avg_price_sqm | Double | Average price per sqm in location |
| price_vs_location_avg | Double | Price vs location average (%) |
| _ingested_at | Timestamp | Ingestion timestamp |

### 1.6 `gold.portfolio_summary`

Cross-asset class performance comparison.

| Column | Type | Description |
|--------|------|-------------|
| date | Date | Date |
| asset_class | String | "EQUITIES", "COMMODITIES", "CURRENCIES", "REAL_ESTATE" |
| total_value | Double | Total portfolio value |
| daily_return | Double | Daily return percentage |
| weekly_return | Double | Weekly return percentage |
| monthly_return | Double | Monthly return percentage |
| ytd_return | Double | Year-to-date return |
| volatility | Double | Rolling volatility |
| sharpe_ratio | Double | Sharpe ratio |
| max_drawdown | Double | Maximum drawdown |
| _ingested_at | Timestamp | Ingestion timestamp |

### 1.7 Data Relationships

| Relationship | Join Key | Description |
|---|---|---|
| stock_performance ↔ stock_fundamentals_enriched | `symbol` | Stock price history joined with company fundamentals |
| commodity_trends ↔ currency_matrix | `date` | Gold/silver prices in different currencies |
| real_estate_analytics ↔ currency_matrix | `snapshot_time` | Real estate prices in USD equivalent |
| portfolio_summary ↔ all tables | `date` | Aggregated performance across all asset classes |

---

## 2. Visualizations by Domain

### 2.1 Equities Dashboard

| # | Visualization | Type | Purpose | Data Source | Key Metrics |
|---|---------------|------|---------|-------------|-------------|
| 1 | Stock Price Time Series | Line chart | Track historical prices | gold.stock_performance | Price, % Change, Volume |
| 2 | Candlestick Chart | OHLCV | Detailed price action | gold.stock_performance | High, Low, Open, Close |
| 3 | Stock Performance Comparison | Multi-line | Compare stocks vs EGX30 | gold.stock_performance | Relative Return, Beta |
| 4 | Volume Analysis | Bar chart | Trading activity | gold.stock_performance | Daily Volume, Avg Volume |
| 5 | Moving Averages (SMA/EMA) | Overlay lines | Trend identification | gold.stock_performance | MA Crossovers |
| 6 | RSI/MACD Indicators | Subplots | Momentum analysis | gold.stock_performance | Overbought/Oversold |
| 7 | Stock Correlation Matrix | Heatmap | Portfolio diversification | gold.stock_performance | Correlation Coefficient |
| 8 | Sector Distribution | Pie/Donut | Portfolio allocation | gold.stock_fundamentals_enriched | % by Sector |
| 9 | Market Cap Ranking | Horizontal bar | Company size comparison | gold.stock_fundamentals_enriched | Market Cap (EGP) |
| 10 | P/E Ratio Comparison | Bar chart | Valuation comparison | gold.stock_fundamentals_enriched | Trailing/Forward P/E |
| 11 | Dividend Yield Scatter | Scatter plot | Income vs Growth | gold.stock_fundamentals_enriched | Yield vs P/E |
| 12 | 52-Week Range | Bullet chart | Current price position | gold.stock_fundamentals_enriched | % from 52W High/Low |

#### Visualization Details

**1. Stock Price Time Series**
```sql
SELECT date, symbol, close 
FROM gold.stock_performance 
WHERE symbol IN ('COMI.CA', 'HRHO.CA', 'ETEL.CA', 'TMGH.CA', 'SWDY.CA') 
ORDER BY date
```
- **Chart Type**: Time series line chart
- **X-Axis**: Date
- **Y-Axis**: Price (EGP)
- **Legend**: Stock symbols
- **Interactions**: Zoom, pan, tooltip with details

**2. Candlestick Chart**
```sql
SELECT date, open, high, low, close, volume 
FROM gold.stock_performance 
WHERE symbol = 'COMI.CA' 
ORDER BY date
```
- **Chart Type**: Candlestick with volume bars
- **Colors**: Green for bullish, Red for bearish
- **Volume**: Bar chart below candlesticks

**3. Stock Performance Comparison**
```sql
SELECT date, symbol, 
       (close / FIRST_VALUE(close) OVER (PARTITION BY symbol ORDER BY date) - 1) * 100 as cumulative_return
FROM gold.stock_performance 
WHERE symbol IN ('COMI.CA', 'HRHO.CA', 'ETEL.CA')
ORDER BY date
```
- **Chart Type**: Multi-line chart
- **Normalization**: All stocks start at 0% for comparison
- **Reference Line**: EGX30 index performance

**4. Volume Analysis**
```sql
SELECT date, volume, 
       AVG(volume) OVER (ORDER BY date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as avg_volume_20
FROM gold.stock_performance 
WHERE symbol = 'COMI.CA' 
ORDER BY date
```
- **Chart Type**: Bar chart with moving average overlay
- **Colors**: Volume bars colored by price change direction

**5. Moving Averages**
```sql
SELECT date, close, sma_20, sma_50, ema_12, ema_26
FROM gold.stock_performance 
WHERE symbol = 'COMI.CA' 
ORDER BY date
```
- **Chart Type**: Line chart with multiple overlays
- **Signals**: Highlight crossovers (Golden Cross, Death Cross)

**6. RSI/MACD Indicators**
```sql
SELECT date, rsi, macd, macd_signal, macd_hist
FROM gold.stock_performance 
WHERE symbol = 'COMI.CA' 
ORDER BY date
```
- **Chart Type**: Subplot below main price chart
- **RSI Zones**: Overbought (>70), Oversold (<30)
- **MACD**: Histogram with signal line crossovers

**7. Stock Correlation Matrix**
```sql
SELECT a.symbol as symbol_a, b.symbol as symbol_b,
       CORR(a.close, b.close) as correlation
FROM gold.stock_performance a
JOIN gold.stock_performance b ON a.date = b.date AND a.symbol < b.symbol
GROUP BY a.symbol, b.symbol
```
- **Chart Type**: Heatmap
- **Color Scale**: Red (-1) to Blue (1)
- **Tooltip**: Correlation coefficient

**8. Sector Distribution**
```sql
SELECT sector, COUNT(*) as count
FROM gold.stock_fundamentals_enriched
GROUP BY sector
```
- **Chart Type**: Donut chart
- **Labels**: Sector names with percentages
- **Center Text**: Total count

**9. Market Cap Ranking**
```sql
SELECT symbol, market_cap_egp
FROM gold.stock_fundamentals_enriched
ORDER BY market_cap_egp DESC
```
- **Chart Type**: Horizontal bar chart
- **Sorting**: Descending by market cap
- **Labels**: EGP values with B/M suffixes

**10. P/E Ratio Comparison**
```sql
SELECT symbol, trailing_pe, forward_pe, pe_sector_avg
FROM gold.stock_fundamentals_enriched
ORDER BY trailing_pe DESC
```
- **Chart Type**: Grouped bar chart
- **Reference Line**: Sector average P/E
- **Tooltip**: Both trailing and forward P/E

**11. Dividend Yield Scatter**
```sql
SELECT symbol, dividend_yield, trailing_pe, market_cap_egp
FROM gold.stock_fundamentals_enriched
WHERE dividend_yield > 0
```
- **Chart Type**: Scatter plot
- **X-Axis**: P/E Ratio
- **Y-Axis**: Dividend Yield
- **Bubble Size**: Market cap
- **Tooltip**: Company details

**12. 52-Week Range**
```sql
SELECT symbol, close, week52_high, week52_low, week52_position
FROM gold.stock_fundamentals_enriched
```
- **Chart Type**: Bullet chart
- **Range**: 52-week low to high
- **Marker**: Current price position
- **Colors**: Green (near high), Red (near low)

---

### 2.2 Commodities Dashboard

| # | Visualization | Type | Purpose | Data Source | Key Metrics |
|---|---------------|------|---------|-------------|-------------|
| 1 | Gold Price Historical | Area chart | Long-term gold trend | gold.commodity_trends | Price (USD/g), % Change |
| 2 | Silver Price Historical | Area chart | Long-term silver trend | gold.commodity_trends | Price (USD/g), % Change |
| 3 | Gold/Silver Ratio | Line chart | Relative value | gold.commodity_trends | Ratio Value |
| 4 | Spot vs Historical | Dual-axis | Current vs historical context | gold.commodity_trends + silver.spot_prices | Spot Price, Historical Avg |
| 5 | Precious Metals Comparison | Multi-bar | Compare all metals | silver.spot_prices | Gold, Silver, Platinum, Palladium |
| 6 | Commodity Volatility | Line chart | Risk assessment | gold.commodity_trends | Rolling Volatility |
| 7 | Gold Price Distribution | Histogram | Price range analysis | gold.commodity_trends | Mean, Median, Std Dev |
| 8 | Monthly/Yearly Returns | Bar chart | Seasonal patterns | gold.commodity_trends | Avg Monthly Return |

#### Visualization Details

**1. Gold Price Historical**
```sql
SELECT date, price_usd, sma_30, sma_90, sma_365
FROM gold.commodity_trends 
WHERE metal = 'GOLD' 
ORDER BY date
```
- **Chart Type**: Area chart with moving average overlays
- **Y-Axis**: Price (USD/g)
- **Reference Lines**: 30-day, 90-day, 365-day MAs

**2. Silver Price Historical**
```sql
SELECT date, price_usd, sma_30, sma_90
FROM gold.commodity_trends 
WHERE metal = 'SILVER' 
ORDER BY date
```
- **Chart Type**: Area chart
- **Color**: Silver/gray theme

**3. Gold/Silver Ratio**
```sql
SELECT date, gold_silver_ratio
FROM gold.commodity_trends 
WHERE metal = 'GOLD' AND gold_silver_ratio IS NOT NULL
ORDER BY date
```
- **Chart Type**: Line chart
- **Reference Lines**: Historical average (80), Extreme levels (40, 120)
- **Interpretation**: High ratio = Gold overvalued vs Silver

**4. Spot vs Historical**
```sql
SELECT 
  g.date, 
  g.price_usd as historical_price,
  s.price as spot_price,
  AVG(g.price_usd) OVER (ORDER BY g.date ROWS BETWEEN 365 PRECEDING AND CURRENT ROW) as avg_1y
FROM gold.commodity_trends g
CROSS JOIN silver.spot_prices s
WHERE g.metal = 'GOLD'
ORDER BY g.date DESC
LIMIT 1
```
- **Chart Type**: Dual-axis comparison
- **Left Axis**: Historical price trend
- **Right Axis**: Current spot price

**5. Precious Metals Comparison**
```sql
SELECT metal, price, change, change_pct
FROM silver.spot_prices
WHERE metal IN ('GOLD', 'SILVER', 'PLATINUM', 'PALLADIUM')
```
- **Chart Type**: Grouped bar chart
- **Metrics**: Price and % Change
- **Colors**: Distinct for each metal

**6. Commodity Volatility**
```sql
SELECT date, volatility_30, volatility_90
FROM gold.commodity_trends 
WHERE metal = 'GOLD' 
ORDER BY date
```
- **Chart Type**: Line chart
- **Comparison**: Short-term vs long-term volatility
- **Thresholds**: High (>30%), Low (<15%)

**7. Gold Price Distribution**
```sql
SELECT price_usd, COUNT(*) as frequency
FROM gold.commodity_trends 
WHERE metal = 'GOLD'
GROUP BY price_usd
ORDER BY price_usd
```
- **Chart Type**: Histogram
- **Bins**: Price ranges
- **Overlay**: Mean, median lines
- **Statistics**: Mean, median, std dev in tooltip

**8. Monthly/Yearly Returns**
```sql
SELECT 
  DATE_TRUNC('month', date) as month,
  AVG(monthly_return) as avg_monthly_return
FROM gold.commodity_trends 
WHERE metal = 'GOLD'
GROUP BY DATE_TRUNC('month', date)
ORDER BY month
```
- **Chart Type**: Bar chart
- **Colors**: Green for positive, Red for negative
- **Reference Line**: Zero line

---

### 2.3 Currencies Dashboard

| # | Visualization | Type | Purpose | Data Source | Key Metrics |
|---|---------------|------|---------|-------------|-------------|
| 1 | Exchange Rate Trends | Multi-line | Currency movements | gold.currency_matrix | Rate vs USD, % Change |
| 2 | Currency Heatmap | Matrix | Relative strength | gold.currency_matrix | % Change (1W, 1M, 3M) |
| 3 | EGP Strength Index | Gauge/Indicator | Egyptian Pound health | gold.currency_matrix | EGP/USD Rate |
| 4 | Currency Correlation | Scatter matrix | Cross-currency relationships | gold.currency_matrix | Correlation |
| 5 | Volatility by Currency | Bar chart | Risk comparison | gold.currency_matrix | Annualized Volatility |
| 6 | Currency vs Gold | Dual-axis | Safe haven analysis | gold.currency_matrix + gold.commodity_trends | Correlation Coefficient |

#### Visualization Details

**1. Exchange Rate Trends**
```sql
SELECT snapshot_time, currency, rate_vs_usd
FROM gold.currency_matrix
WHERE currency IN ('USD', 'EUR', 'GBP', 'JPY')
ORDER BY snapshot_time
```
- **Chart Type**: Multi-line chart
- **Y-Axis**: Exchange rate
- **Normalization**: Indexed to 100 for comparison

**2. Currency Heatmap**
```sql
SELECT currency, 
       daily_change,
       weekly_change,
       monthly_change
FROM gold.currency_matrix
WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM gold.currency_matrix)
```
- **Chart Type**: Matrix heatmap
- **Rows**: Currencies
- **Columns**: Time periods (1D, 1W, 1M)
- **Colors**: Green (strength) to Red (weakness)

**3. EGP Strength Index**
```sql
SELECT rate_vs_usd, strength_index
FROM gold.currency_matrix
WHERE currency = 'EGP' AND snapshot_time = (SELECT MAX(snapshot_time) FROM gold.currency_matrix)
```
- **Chart Type**: Gauge/Indicator
- **Range**: 0-100
- **Zones**: Weak (0-30), Neutral (30-70), Strong (70-100)
- **Current Value**: EGP/USD rate

**4. Currency Correlation**
```sql
SELECT a.currency as currency_a, b.currency as currency_b,
       CORR(a.rate_vs_usd, b.rate_vs_usd) as correlation
FROM gold.currency_matrix a
JOIN gold.currency_matrix b ON a.snapshot_time = b.snapshot_time AND a.currency < b.currency
GROUP BY a.currency, b.currency
```
- **Chart Type**: Scatter matrix / Heatmap
- **Purpose**: Identify correlated currencies for diversification

**5. Volatility by Currency**
```sql
SELECT currency, volatility_30
FROM gold.currency_matrix
WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM gold.currency_matrix)
ORDER BY volatility_30 DESC
```
- **Chart Type**: Horizontal bar chart
- **Sorting**: Descending by volatility
- **Colors**: Red (high volatility) to Green (low volatility)

**6. Currency vs Gold**
```sql
SELECT 
  c.snapshot_time,
  c.rate_vs_usd as egp_usd,
  g.price_usd as gold_price,
  CORR(c.rate_vs_usd, g.price_usd) OVER (ORDER BY c.snapshot_time ROWS BETWEEN 90 PRECEDING AND CURRENT ROW) as rolling_correlation
FROM gold.currency_matrix c
JOIN gold.commodity_trends g ON c.snapshot_time = g.date
WHERE c.currency = 'EGP' AND g.metal = 'GOLD'
ORDER BY c.snapshot_time
```
- **Chart Type**: Dual-axis chart
- **Left Axis**: EGP/USD rate
- **Right Axis**: Gold price
- **Correlation**: Rolling correlation overlay

---

### 2.4 Real Estate Dashboard

| # | Visualization | Type | Purpose | Data Source | Key Metrics |
|---|---------------|------|---------|-------------|-------------|
| 1 | Price Distribution | Histogram | Market pricing | gold.real_estate_analytics | Median, Avg Price |
| 2 | Price per Sqm by Location | Bar chart | Location valuation | gold.real_estate_analytics | EGP/sqm |
| 3 | Property Type Mix | Pie chart | Market composition | gold.real_estate_analytics | % Apartments, Villas, etc. |
| 4 | Bedroom Distribution | Bar chart | Inventory analysis | gold.real_estate_analytics | Count by Bedrooms |
| 5 | Developer Market Share | Treemap | Developer analysis | gold.real_estate_analytics | # Listings, Avg Price |
| 6 | Project Status | Stacked bar | Pipeline health | gold.real_estate_analytics | Under Construction, Ready |
| 7 | Price vs Area Scatter | Scatter | Size-price relationship | gold.real_estate_analytics | Correlation |
| 8 | Location Price Map | Geographic | Spatial analysis | gold.real_estate_analytics | Avg Price by Area |
| 9 | Amenity Analysis | Word cloud/Frequency | Feature popularity | gold.real_estate_analytics | Top Amenities |
| 10 | Delivery Timeline | Gantt/Timeline | Project pipeline | gold.real_estate_analytics | Upcoming Deliveries |

#### Visualization Details

**1. Price Distribution**
```sql
SELECT 
  CASE 
    WHEN price_egp < 1000000 THEN 'Under 1M'
    WHEN price_egp < 2000000 THEN '1M - 2M'
    WHEN price_egp < 5000000 THEN '2M - 5M'
    WHEN price_egp < 10000000 THEN '5M - 10M'
    ELSE 'Over 10M'
  END as price_range,
  COUNT(*) as count
FROM gold.real_estate_analytics
GROUP BY price_range
ORDER BY MIN(price_egp)
```
- **Chart Type**: Histogram
- **Bins**: Price ranges
- **Statistics**: Mean, median, mode in tooltip

**2. Price per Sqm by Location**
```sql
SELECT location, AVG(price_per_sqm) as avg_price_sqm
FROM gold.real_estate_analytics
GROUP BY location
ORDER BY avg_price_sqm DESC
LIMIT 20
```
- **Chart Type**: Horizontal bar chart
- **Sorting**: Descending by average price
- **Labels**: EGP/sqm values

**3. Property Type Mix**
```sql
SELECT property_type, COUNT(*) as count
FROM gold.real_estate_analytics
GROUP BY property_type
```
- **Chart Type**: Donut chart
- **Labels**: Property type names with percentages
- **Center Text**: Total listings

**4. Bedroom Distribution**
```sql
SELECT bedrooms, COUNT(*) as count
FROM gold.real_estate_analytics
GROUP BY bedrooms
ORDER BY bedrooms
```
- **Chart Type**: Bar chart
- **X-Axis**: Number of bedrooms
- **Y-Axis**: Count of listings

**5. Developer Market Share**
```sql
SELECT developer, 
       COUNT(*) as listing_count,
       AVG(price_egp) as avg_price
FROM gold.real_estate_analytics
WHERE developer IS NOT NULL
GROUP BY developer
ORDER BY listing_count DESC
```
- **Chart Type**: Treemap
- **Size**: Number of listings
- **Color**: Average price
- **Tooltip**: Developer name, count, avg price

**6. Project Status**
```sql
SELECT project_status, COUNT(*) as count
FROM gold.real_estate_analytics
GROUP BY project_status
```
- **Chart Type**: Stacked bar chart
- **Categories**: Under Construction, First Sale, Ready to Move
- **Colors**: Distinct for each status

**7. Price vs Area Scatter**
```sql
SELECT area_sqm, price_egp, property_type, location
FROM gold.real_estate_analytics
WHERE area_sqm > 0 AND price_egp > 0
```
- **Chart Type**: Scatter plot
- **X-Axis**: Area (sqm)
- **Y-Axis**: Price (EGP)
- **Color**: Property type
- **Tooltip**: Property details
- **Trend Line**: Linear regression

**8. Location Price Map**
```sql
SELECT location, 
       AVG(price_egp) as avg_price,
       AVG(price_per_sqm) as avg_price_sqm,
       COUNT(*) as listing_count
FROM gold.real_estate_analytics
GROUP BY location
```
- **Chart Type**: Geographic map
- **Markers**: Circles sized by count
- **Color**: Average price (heatmap)
- **Popup**: Location details

**9. Amenity Analysis**
```sql
SELECT amenity, COUNT(*) as frequency
FROM (
  SELECT UNNEST(STRING_TO_ARRAY(amenities, ',')) as amenity
  FROM gold.real_estate_analytics
  WHERE amenities IS NOT NULL
)
GROUP BY amenity
ORDER BY frequency DESC
LIMIT 20
```
- **Chart Type**: Word cloud or horizontal bar chart
- **Size**: Frequency
- **Tooltip**: Amenity name and count

**10. Delivery Timeline**
```sql
SELECT project_name, delivery_date, developer, price_egp
FROM gold.real_estate_analytics
WHERE delivery_date IS NOT NULL
ORDER BY delivery_date
```
- **Chart Type**: Timeline/Gantt chart
- **Projects**: Listed by delivery date
- **Colors**: By developer or project status

---

### 2.5 Cross-Asset Portfolio Dashboard

| # | Visualization | Type | Purpose | Data Source | Key Metrics |
|---|---------------|------|---------|-------------|-------------|
| 1 | Asset Class Performance | Multi-line | Compare returns | gold.portfolio_summary | Equities vs Commodities vs RE |
| 2 | Portfolio Allocation | Donut chart | Diversification | gold.portfolio_summary | % by Asset Class |
| 3 | Risk-Return Scatter | Scatter | Efficient frontier | gold.portfolio_summary | Return vs Volatility |
| 4 | Correlation Matrix | Heatmap | Cross-asset correlations | gold.portfolio_summary | Correlation Coefficient |
| 5 | Drawdown Analysis | Area chart | Risk visualization | gold.portfolio_summary | Max Drawdown |
| 6 | Sharpe Ratio Comparison | Bar chart | Risk-adjusted returns | gold.portfolio_summary | Sharpe Ratio |
| 7 | Monthly Returns Heatmap | Calendar | Seasonal patterns | gold.portfolio_summary | Monthly % Returns |

#### Visualization Details

**1. Asset Class Performance**
```sql
SELECT date, asset_class, ytd_return
FROM gold.portfolio_summary
WHERE asset_class IN ('EQUITIES', 'COMMODITIES', 'REAL_ESTATE')
ORDER BY date
```
- **Chart Type**: Multi-line chart
- **Normalization**: All start at 0%
- **Reference Line**: Zero line

**2. Portfolio Allocation**
```sql
SELECT asset_class, SUM(total_value) as total_value
FROM gold.portfolio_summary
WHERE date = (SELECT MAX(date) FROM gold.portfolio_summary)
GROUP BY asset_class
```
- **Chart Type**: Donut chart
- **Labels**: Asset class names with percentages
- **Center Text**: Total portfolio value

**3. Risk-Return Scatter**
```sql
SELECT asset_class, 
       AVG(daily_return) * 252 as annual_return,
       STDDEV(daily_return) * SQRT(252) as annual_volatility
FROM gold.portfolio_summary
GROUP BY asset_class
```
- **Chart Type**: Scatter plot
- **X-Axis**: Annualized Volatility
- **Y-Axis**: Annualized Return
- **Bubble Size**: Total value
- **Quadrants**: High return/low risk (ideal)

**4. Correlation Matrix**
```sql
SELECT a.asset_class as asset_a, b.asset_class as asset_b,
       CORR(a.daily_return, b.daily_return) as correlation
FROM gold.portfolio_summary a
JOIN gold.portfolio_summary b ON a.date = b.date AND a.asset_class < b.asset_class
GROUP BY a.asset_class, b.asset_class
```
- **Chart Type**: Heatmap
- **Color Scale**: Red (-1) to Blue (1)
- **Purpose**: Diversification analysis

**5. Drawdown Analysis**
```sql
SELECT date, asset_class,
       (total_value / MAX(total_value) OVER (PARTITION BY asset_class ORDER BY date) - 1) * 100 as drawdown
FROM gold.portfolio_summary
ORDER BY date
```
- **Chart Type**: Area chart
- **Y-Axis**: Drawdown percentage
- **Colors**: Red for drawdowns
- **Annotation**: Maximum drawdown points

**6. Sharpe Ratio Comparison**
```sql
SELECT asset_class, sharpe_ratio
FROM gold.portfolio_summary
WHERE date = (SELECT MAX(date) FROM gold.portfolio_summary)
ORDER BY sharpe_ratio DESC
```
- **Chart Type**: Horizontal bar chart
- **Reference Line**: Sharpe ratio of 1 (acceptable)
- **Colors**: Green (>1), Yellow (0.5-1), Red (<0.5)

**7. Monthly Returns Heatmap**
```sql
SELECT 
  DATE_TRUNC('month', date) as month,
  asset_class,
  SUM(daily_return) * 100 as monthly_return
FROM gold.portfolio_summary
GROUP BY month, asset_class
```
- **Chart Type**: Calendar heatmap
- **Rows**: Months
- **Columns**: Asset classes
- **Colors**: Green (positive) to Red (negative)

---

## 3. Dashboard Structure Recommendations

### 3.1 Executive Summary Dashboard

**Purpose**: High-level overview for quick decision-making

**Target Audience**: Executives, portfolio managers

**Refresh Rate**: Real-time or daily

#### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  KPI Cards (4x)                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Total   │ │ Daily   │ │ YTD     │ │ Top     │           │
│  │ Value   │ │ Change  │ │ Return  │ │ Gainer  │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
├─────────────────────────────────────────────────────────────┤
│  Mini Charts (4x)                                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ EGX30   │ │ Gold    │ │ EGP/USD │ │ Real    │           │
│  │ Chart   │ │ Chart   │ │ Chart   │ │ Estate  │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
├─────────────────────────────────────────────────────────────┤
│  Top Movers Table              │ Market Status               │
│  ┌─────────────────────────┐   │ ┌─────────────────────┐    │
│  │ Symbol │ Change │ Vol   │   │ │ EGX: Open/Closed    │    │
│  │ COMI   │ +2.5%  │ 1.2M │   │ │ Commodities: Active │    │
│  │ HRHO   │ -1.2%  │ 850K │   │ │ FX: Trading         │    │
│  └─────────────────────────┘   │ └─────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

#### Components

1. **KPI Cards**
   - Total Portfolio Value (EGP)
   - Daily Change (%)
   - YTD Return (%)
   - Top Gainer/Loser

2. **Mini Charts**
   - EGX30 Index (sparkline)
   - Gold Price (sparkline)
   - EGP/USD Rate (sparkline)
   - Real Estate Index (sparkline)

3. **Top Movers Table**
   - Top 5 gainers
   - Top 5 losers
   - Volume leaders

4. **Market Status**
   - Trading hours
   - Market sentiment indicator
   - News alerts

---

### 3.2 Equities Deep Dive Dashboard

**Purpose**: Detailed stock analysis for equity investors

**Target Audience**: Stock traders, equity analysts

**Refresh Rate**: Real-time

#### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Stock Selector ──────────────────────────────────────────┐  │
│  [COMI.CA ▼] [Date Range: Last 30 days ▼] [Compare: +]   │  │
├─────────────────────────────────────────────────────────────┤
│  Price Chart (Main)                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │         Candlestick/Line Chart               │   │   │
│  │  │         with Moving Averages                 │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │         Volume Bars                          │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Technical Indicators                                        │
│  ┌──────────────────────┐ ┌──────────────────────┐          │
│  │  RSI Chart           │ │  MACD Chart          │          │
│  │  [Overbought: 70]    │ │  [Signal Crossovers] │          │
│  │  [Oversold: 30]      │ │                      │          │
│  └──────────────────────┘ └──────────────────────┘          │
├─────────────────────────────────────────────────────────────┤
│  Fundamentals Panel          │ Performance Metrics           │
│  ┌─────────────────────────┐ │ ┌─────────────────────┐      │
│  │ Company: Commercial     │ │ │ P/E: 12.5           │      │
│  │ Intl Bank               │ │ │ EPS: 4.2 EGP        │      │
│  │ Sector: Financials      │ │ │ Div Yield: 2.1%     │      │
│  │ Market Cap: 85.2B EGP   │ │ │ Beta: 1.2           │      │
│  │ 52W Range: 45-68 EGP    │ │ │ 52W Position: 72%   │      │
│  └─────────────────────────┘ │ └─────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

#### Components

1. **Stock Selector**
   - Dropdown for stock selection
   - Date range picker
   - Compare mode toggle

2. **Price Chart**
   - Candlestick or line chart
   - Moving average overlays (SMA 20, 50; EMA 12, 26)
   - Volume bars below
   - Zoom and pan controls

3. **Technical Indicators**
   - RSI with overbought/oversold zones
   - MACD with signal line and histogram
   - Bollinger Bands (optional)

4. **Fundamentals Panel**
   - Company information
   - Key financial ratios
   - Valuation metrics

5. **Performance Metrics**
   - Returns (daily, weekly, monthly, YTD)
   - Risk metrics (volatility, beta)
   - 52-week position

---

### 3.3 Commodities & Currencies Dashboard

**Purpose**: Macro analysis for commodities and forex

**Target Audience**: Macro analysts, forex traders

**Refresh Rate**: Real-time

#### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Commodities Section                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Gold Price Chart (with MA overlays)                │   │
│  │  [Current: $65.2/g] [Change: +0.5%]                │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Silver Price Chart │ Gold/Silver Ratio │ Spot Tab  │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Currencies Section                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Exchange Rate Matrix (Heatmap)                     │   │
│  │  ┌─────┬─────┬─────┬─────┬─────┬─────┐             │   │
│  │  │ USD │ EUR │ GBP │ JPY │ CNY │ EGP │             │   │
│  │  ├─────┼─────┼─────┼─────┼─────┼─────┤             │   │
│  │  │ 1.0 │ 0.9 │ 0.8 │ 145 │ 7.2 │ 50.5│             │   │
│  │  └─────┴─────┴─────┴─────┴─────┴─────┘             │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  EGP Strength Gauge │ Currency Volatility Bars      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### Components

1. **Gold Price Chart**
   - Historical price with moving averages
   - Current price and daily change
   - Key support/resistance levels

2. **Silver Price Chart**
   - Similar to gold chart
   - Silver-specific indicators

3. **Gold/Silver Ratio**
   - Historical ratio chart
   - Mean reversion signals

4. **Exchange Rate Matrix**
   - Heatmap showing all currency pairs
   - Color-coded by change (1D, 1W, 1M)

5. **EGP Strength Gauge**
   - Visual gauge of EGP strength
   - Current rate and trend

6. **Currency Volatility**
   - Bar chart of volatility by currency
   - Risk comparison

---

### 3.4 Real Estate Analytics Dashboard

**Purpose**: Property market intelligence

**Target Audience**: Real estate investors, analysts

**Refresh Rate**: Daily or weekly

#### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Filters ─────────────────────────────────────────────────┐  │
│  [Location ▼] [Property Type ▼] [Price Range ▼] [Bedrooms] │  │
├─────────────────────────────────────────────────────────────┤
│  Market Overview KPIs                                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Median  │ │ Avg     │ │ Total   │ │ Price   │           │
│  │ Price   │ │ $/sqm   │ │ Listings│ │ Trend   │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
├─────────────────────────────────────────────────────────────┤
│  Location Analysis                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Price per Sqm by Location (Bar Chart)              │   │
│  │  [Top 10 locations by avg price]                    │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Property Analysis                                           │
│  ┌──────────────────────┐ ┌──────────────────────┐          │
│  │ Price Distribution   │ │ Property Type Mix     │          │
│  │ (Histogram)          │ │ (Donut Chart)         │          │
│  └──────────────────────┘ └──────────────────────┘          │
├─────────────────────────────────────────────────────────────┤
│  Developer Analysis                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Developer Market Share (Treemap)                   │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Listings Table                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ID │ Type │ Location │ Beds │ Area │ Price │ $/sqm │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### Components

1. **Filters**
   - Location dropdown
   - Property type selector
   - Price range slider
   - Bedroom count

2. **Market Overview KPIs**
   - Median price
   - Average price per sqm
   - Total listings
   - Price trend (arrow up/down)

3. **Location Analysis**
   - Bar chart of price per sqm by location
   - Top 10 locations

4. **Property Analysis**
   - Price distribution histogram
   - Property type donut chart
   - Bedroom distribution

5. **Developer Analysis**
   - Treemap of developer market share
   - Size by listing count
   - Color by average price

6. **Listings Table**
   - Sortable/filterable table
   - Key property details
   - Links to full listings

---

### 3.5 Risk & Performance Dashboard

**Purpose**: Portfolio risk management

**Target Audience**: Risk managers, portfolio managers

**Refresh Rate**: Daily

#### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Portfolio Summary KPIs                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Total   │ │ Sharpe  │ │ Max     │ │ VaR     │           │
│  │ Return  │ │ Ratio   │ │ Drawdown│ │ (95%)   │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
├─────────────────────────────────────────────────────────────┤
│  Asset Class Performance                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Multi-line chart: Equities vs Commodities vs RE    │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Risk Analysis                                               │
│  ┌──────────────────────┐ ┌──────────────────────┐          │
│  │ Drawdown Chart       │ │ Volatility Chart     │          │
│  │ (Area chart)         │ │ (Line chart)         │          │
│  └──────────────────────┘ └──────────────────────┘          │
├─────────────────────────────────────────────────────────────┤
│  Correlation Analysis                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Cross-Asset Correlation Matrix (Heatmap)           │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Risk-Return Analysis                                        │
│  ┌──────────────────────┐ ┌──────────────────────┐          │
│  │ Risk-Return Scatter  │ │ Sharpe Ratio Bars    │          │
│  │ (Efficient Frontier) │ │ (Comparison)         │          │
│  └──────────────────────┘ └──────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

#### Components

1. **Portfolio Summary KPIs**
   - Total return (MTD, YTD)
   - Sharpe ratio
   - Maximum drawdown
   - Value at Risk (95%)

2. **Asset Class Performance**
   - Multi-line chart comparing returns
   - Normalized to 100

3. **Risk Analysis**
   - Drawdown chart (area)
   - Volatility chart (line)

4. **Correlation Analysis**
   - Heatmap of cross-asset correlations
   - Diversification benefits

5. **Risk-Return Analysis**
   - Scatter plot (efficient frontier)
   - Sharpe ratio comparison bars

---

## 4. Key Performance Indicators (KPIs)

### 4.1 Equities KPIs

| KPI | Formula | Target | Alert Threshold |
|-----|---------|--------|-----------------|
| Daily Return | (Close - Previous Close) / Previous Close | > 0% | < -5% |
| Weekly Return | (Close - Close 5 days ago) / Close 5 days ago | > 0% | < -10% |
| Monthly Return | (Close - Close 20 days ago) / Close 20 days ago | > 0% | < -15% |
| YTD Return | (Close - Close at year start) / Close at year start | > 10% | < 0% |
| Volume vs Avg | Volume / 20-day Average Volume | 0.8 - 1.2 | > 2.0 or < 0.5 |
| P/E Ratio | Market Price / EPS | Sector Average | > 2x Sector Avg |
| Dividend Yield | Annual Dividend / Price | > 2% | < 1% |
| 52-Week Position | (Price - 52W Low) / (52W High - 52W Low) | > 50% | < 20% |
| RSI (14-day) | 100 - (100 / (1 + RS)) | 30-70 | > 70 or < 30 |
| Beta | Covariance(Stock, Market) / Variance(Market) | 0.8-1.2 | > 1.5 |

### 4.2 Commodities KPIs

| KPI | Formula | Target | Alert Threshold |
|-----|---------|--------|-----------------|
| Gold/Silver Ratio | Gold Price / Silver Price | 60-80 | > 100 or < 50 |
| Spot vs Historical | (Spot Price - 30-day Avg) / 30-day Avg | ±5% | > 10% |
| Volatility (30-day) | STDDEV(Daily Returns) * SQRT(365) | 15-25% | > 40% |
| Monthly Return | (Price - Price 30 days ago) / Price 30 days ago | > 0% | < -10% |
| Yearly Return | (Price - Price 365 days ago) / Price 365 days ago | > 5% | < -15% |

### 4.3 Currencies KPIs

| KPI | Formula | Target | Alert Threshold |
|-----|---------|--------|-----------------|
| EGP/USD Rate | Current Exchange Rate | Stable | > 55 or < 45 |
| Daily Change | (Rate - Previous Rate) / Previous Rate | ±0.5% | > 2% |
| Weekly Change | (Rate - Rate 7 days ago) / Rate 7 days ago | ±2% | > 5% |
| Monthly Change | (Rate - Rate 30 days ago) / Rate 30 days ago | ±5% | > 10% |
| Volatility (30-day) | STDDEV(Daily Changes) * SQRT(365) | < 10% | > 20% |
| Strength Index | Normalized strength vs basket | 50 | < 30 or > 70 |

### 4.4 Real Estate KPIs

| KPI | Formula | Target | Alert Threshold |
|-----|---------|--------|-----------------|
| Median Price | PERCENTILE(Price, 0.5) | Stable | > 10% change |
| Avg Price per Sqm | AVG(Price / Area) | Growing | < 0% growth |
| Total Listings | COUNT(*) | Growing | < 0% growth |
| Price Appreciation | (Current Median - Previous Median) / Previous Median | > 5% | < 0% |
| Inventory Levels | COUNT(*) by Status | Balanced | > 20% oversupply |
| Days on Market | AVG(Current Date - Listed Date) | < 90 days | > 180 days |

### 4.5 Portfolio KPIs

| KPI | Formula | Target | Alert Threshold |
|-----|---------|--------|-----------------|
| Total Return | (Current Value - Initial Value) / Initial Value | > 10% | < 0% |
| Sharpe Ratio | (Return - Risk-Free Rate) / Volatility | > 1.0 | < 0.5 |
| Maximum Drawdown | MIN((Price - Peak) / Peak) | > -10% | < -20% |
| VaR (95%) | PERCENTILE(Returns, 0.05) | > -2% | < -5% |
| Diversification Score | 1 - AVG(Correlation Matrix) | > 0.7 | < 0.5 |
| Beta | Covariance(Portfolio, Market) / Variance(Market) | 0.8-1.2 | > 1.5 |

---

## 5. Implementation Guide

### 5.1 Dashboard JSON Structure

Each dashboard JSON file follows this structure:

```json
{
  "dashboard": {
    "id": null,
    "uid": "unique-dashboard-id",
    "title": "Dashboard Title",
    "tags": ["tag1", "tag2"],
    "timezone": "Africa/Cairo",
    "panels": [...],
    "templating": {...},
    "time": {...}
  }
}
```

### 5.2 Panel Types

| Panel Type | Grafana Type | Use Case |
|------------|--------------|----------|
| Time Series | `timeseries` | Historical data, trends |
| Bar Chart | `barchart` | Comparisons, rankings |
| Stat | `stat` | Single values, KPIs |
| Pie Chart | `piechart` | Distribution, composition |
| Heatmap | `heatmap` | Correlation, intensity |
| Scatter | `scatterplot` | Relationships, clusters |
| Table | `table` | Detailed data, lists |
| Gauge | `gauge` | Single values with ranges |
| Text | `text` | Markdown, annotations |

### 5.3 SQL Query Templates

**Time Series Query**
```sql
SELECT date, value
FROM gold.table
WHERE symbol = '$symbol'
ORDER BY date
```

**Aggregation Query**
```sql
SELECT category, COUNT(*) as count, AVG(value) as avg_value
FROM gold.table
GROUP BY category
ORDER BY avg_value DESC
```

**Correlation Query**
```sql
SELECT a.category as cat_a, b.category as cat_b,
       CORR(a.value, b.value) as correlation
FROM gold.table a
JOIN gold.table b ON a.date = b.date AND a.category < b.category
GROUP BY a.category, b.category
```

### 5.4 Color Schemes

**Equities**
- Primary: `#0066CC` (Blue)
- Positive: `#00CC66` (Green)
- Negative: `#CC3333` (Red)
- Neutral: `#666666` (Gray)

**Commodities**
- Gold: `#FFD700`
- Silver: `#C0C0C0`
- Platinum: `#E5E4E2`
- Palladium: `#CED0CE`

**Currencies**
- USD: `#002868`
- EUR: `#003399`
- GBP: `#C8102E`
- EGP: `#CE1126`

**Real Estate**
- Apartments: `#4472C4`
- Villas: `#70AD47`
- Townhouses: `#FFC000`
- Land: `#5B9BD5`

### 5.5 Screenshot Configuration

**Full Dashboard Screenshot**
```bash
curl -u admin:admin \
  "http://localhost:3000/render/d/<DASHBOARD_UID>?orgId=1&from=now-30d&to=now&width=1920&height=1080" \
  -o dashboard.png
```

**Panel Screenshot**
```bash
curl -u admin:admin \
  "http://localhost:3000/render/d/<DASHBOARD_UID>?orgId=1&panelId=<PANEL_ID>&width=800&height=400" \
  -o panel.png
```

**Scheduled Screenshots (Cron)**
```bash
# Daily screenshot at 6 AM
0 6 * * * python /path/to/screenshot_utility.py --action capture-all --output /path/to/screenshots/
```

---

## Appendix A: Stock Universe

| Symbol | Company | Sector | Industry |
|--------|---------|--------|----------|
| COMI.CA | Commercial International Bank | Financials | Banking |
| HRHO.CA | EFG Holding | Financials | Holding |
| ETEL.CA | Telecom Egypt | Communication | Telecom |
| TMGH.CA | Talaat Moustafa Group | Real Estate | Development |
| SWDY.CA | El Sewedy Electric | Industrials | Electrical |
| ORAS.CA | Orascom Construction | Industrials | Construction |
| EAST.CA | Eastern Company | Consumer Staples | Tobacco |
| CLHO.CA | Cleopatra Hospital | Healthcare | Hospital |
| PHDC.CA | Palm Hills | Real Estate | Development |
| AUTO.CA | GB Auto | Consumer Discretionary | Automotive |

---

## Appendix B: Currency Universe

| Currency | Description | Relevance |
|----------|-------------|-----------|
| USD | US Dollar | Base currency, global reserve |
| EUR | Euro | Major trading partner |
| GBP | British Pound | Major trading partner |
| JPY | Japanese Yen | Safe haven |
| CNY | Chinese Yuan | Growing trade partner |
| SAR | Saudi Riyal | Regional, oil-linked |
| AED | UAE Dirham | Regional, trade hub |
| EGP | Egyptian Pound | Local currency |
| CHF | Swiss Franc | Safe haven |
| CAD | Canadian Dollar | Commodity currency |

---

## Appendix C: Real Estate Metrics

| Metric | Description | Calculation |
|--------|-------------|-------------|
| Price per Sqm | Price divided by area | Price / Area (sqm) |
| Location Average | Average price in location | AVG(Price) WHERE Location = X |
| Price vs Location | Price relative to location average | (Price - Location Avg) / Location Avg |
| Amenity Count | Number of amenities | COUNT(Amenities) |
| Developer Score | Developer reputation score | Based on listing count and avg price |

---

*Document Version: 1.0*
*Last Updated: July 30, 2026*
*Author: Egypt Investment Analytics Team*