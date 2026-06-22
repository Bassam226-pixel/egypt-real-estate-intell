# 📊 Egypt Real Estate — Collected Data Overview

This document explains the data collected so far across our three sources
(Aqarmap, PropertyFinder, Bayut), what each file contains, and what every
field means.

---

## ✅ Collection Status

| Source | Status | Pages Scraped | Notes |
|--------|--------|---------------|-------|
| **Aqarmap** | ✅ Done | 60 / 60 pages | Full run completed, `data.json` + `data_enriched.json` ready |
| **PropertyFinder** | ✅ Done | Full run | Both scraping and enrichment completed, `data.json` + `data_enriched.json` ready |
| **Bayut** | ⏳ Still scraping | In progress | Listing-page scraper done; data still being collected, no enrichment yet |

---

## 📁 Aqarmap — Data Files

We have 3 data files, each representing a different stage of collection:

### 1. `data_raw.json` — Bronze Layer (Raw Scraped Data)
Collected directly from Aqarmap listing pages across all **60 pages**.
**No cleaning, no translation** — exactly as it appears on the website.
Some titles and locations are in Arabic, some in English depending on
which version of the page was scraped.

**When to use it:** Only as a backup. If anything goes wrong in later
stages, we always have the original data here.

### 2. `data.json` — Bronze Layer (Translated Data)
Same as `data_raw.json` but titles and locations have been
**automatically translated to English** using Google Translate API.
This is the main input for the Silver Layer cleaning pipeline.

**Collection complete:** all 60 pages scraped successfully, with retry
logic in place for any page that returned an empty result on the first
attempt.

**When to use it:** This is our main working dataset before cleaning.

### 3. `data_enriched.json` — Enhanced Bronze Layer
A **sample of 300 listings** from `data.json`, enriched with extra details
collected from each listing's individual page (Stage 2 scraping).
Contains more fields like amenities, description, coordinates,
agent name, and full property details.

**When to use it:** For ML model training — richer features = better predictions.

---

## 📋 Aqarmap — Field Reference

### Fields present in ALL three files

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `listing_id` | String | Unique ID for the listing on Aqarmap | "7049522" |
| `property_type` | String or null | Type of property detected from title | "Apartment", "Villa", null |
| `title` | String | Listing title | "Apartment 190 M² in Bait El Watan" |
| `price` | String | Price as shown on site | "5,500,000 ج.م" or "1,800,000 EGP" |
| `location` | String | Area and sub-area | "New Cairo - Fifth Settlement / Group 113" |
| `bedrooms` | String | Number of bedrooms | "3" |
| `bathrooms` | String | Number of bathrooms | "2" |
| `area` | String | Property size with unit | "150 م² sqm" or "190 m²" |
| `price_per_sqm` | String | Price per square meter | "36,666 ج/م²" |
| `listing_level` | String or null | Listing tier on Aqarmap | "Premium", null |
| `listed_date` | String or null | When listing was posted | "Listed 3 days ago", null |
| `link` | String | Full URL to the listing page | "https://aqarmap.com.eg/..." |
| `image` | String | URL of listing thumbnail image | "https://img-1.aqarmap.com.eg/..." |
| `source` | String | Which platform data came from | "aqarmap" |
| `scraped_at` | DateTime | Timestamp when we collected it | "2026-06-22T19:37:24" |

### Extra fields in `data_enriched.json` only
These come from Stage 2 scraping (individual listing pages)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `subtitle` | String | Arabic subtitle from listing page | "شقة سوبر لوكس ٩٦ متر..." |
| `full_title` | String | Full Arabic title | "شقة سوبر لوكس ٩٦ متر..." |
| `amenities` | List | Property amenities (translated) | ["Security", "Elevator", "Balcony"] |
| `description` | String | Listing description in English | "Super luxurious finished apartment..." |
| `full_location` | String | Sub-location / compound name | "مجموعة 113" |
| `agent_name` | String or null | Name of selling agent | "Dalia Alaa", null |
| `broker_name` | String or null | Name of broker company | "Assets Real Estate", null |
| `price_full` | Integer | Price as a clean number | 5000000 |
| `property_type_full` | String | Arabic property type from page | "شقق", "مكاتب" |
| `bedrooms_full` | Integer | Bedrooms as integer | 2 |
| `bathrooms_full` | Integer | Bathrooms as integer | 2 |
| `property_size_full` | String | Clean size string | "96 sqm" |
| `latitude` | Float | GPS latitude coordinate | 30.074 |
| `longitude` | Float | GPS longitude coordinate | 31.654 |

---

## 📁 PropertyFinder — Data Files

PropertyFinder collection is **fully complete** — both the base listing
scrape and the detail-page enrichment have finished running.

### 1. `data.json` — Base Listings
Collected from PropertyFinder's search result pages. Unlike Aqarmap,
PropertyFinder's site is English-only by default, so **no translation
step was needed** for this source.

### 2. `data_enriched.json` — Enriched Listings
Each listing's individual detail page was visited to pull richer fields:
project information (developer, delivery date), regulatory reference,
full amenities list, and agent/broker details.

---

## 📋 PropertyFinder — Field Reference

### Fields present in `data.json`

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `listing_id` | String | Unique ID for the listing | "83988226" |
| `property_type` | String | Property type from the card | "Apartment" |
| `title` | String | Listing title | "Apartment double view with lowest dp" |
| `price` | String | Price with currency | "5,900,000 EGP" |
| `location` | String | Full location string | "Mountain View iCity, 5th Settlement..." |
| `bedrooms` | String | Number of bedrooms | "3" |
| `bathrooms` | String | Number of bathrooms | "3" |
| `area` | String | Property size | "165 sqm" |
| `price_per_sqm` | String | Price per square meter | "35,757 EGP/sqm" |
| `listing_level` | String | Listing tier | "Premium" |
| `listed_date` | String | Relative posting date | "Listed 3 days ago" |
| `link` | String | Full URL to the listing | "https://www.propertyfinder.eg/..." |
| `image` | String | Thumbnail image URL | "https://static.shared.propertyfinder.eg/..." |
| `source` | String | Platform name | "propertyfinder" |
| `scraped_at` | DateTime | Timestamp of collection | "2026-06-21T21:12:30" |

### Extra fields in `data_enriched.json` only

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `property_type_full` | String | Property type from detail page | "Villa" |
| `property_size_full` | String | Size with both units | "2,260 sqft / 210 sqm" |
| `bedrooms_full` | String | Bedrooms, with extras noted | "4 + Maid" |
| `bathrooms_full` | String | Bathrooms from detail page | "3" |
| `available_from` | String | Delivery / availability date | "18 Jun 2026" |
| `price_full` | String | Price without currency suffix | "8,300,000" |
| `subtitle` | String | Page subtitle | "VILLA FOR SALE IN MOUNTAIN VIEW..." |
| `full_title` | String | Full listing title | "Ready to move finished Villa..." |
| `description` | String | Listing description | "Ready-to-Move Fully Finished Villa..." |
| `amenities` | List | Property amenities | ["Covered Parking", "Shared Pool", ...] |
| `project_name` | String | Compound / project name | "Mountain View October Park" |
| `project_status` | String | Construction status | "Under Construction", "First Sale" |
| `developer` | String | Developer name | "Mountain View" |
| `delivery_date` | String | Project delivery quarter | "Q4 2023" |
| `full_location` | String | Location from detail page | "Mountain View October Park, 6th District..." |
| `agent_name` | String | Selling agent name | "Dina El sayed" |
| `broker_name` | String | Broker company name | "Property Hills..." |
| `regulatory_reference` | String | Official regulatory ID | "CPAASRYKZYKJ6MAR10ZNRSET7W" |

---

## 📁 Bayut — Status

🚧 **Bayut is still being scraped.** The base listing scraper (search
result pages) is built and running, but the full dataset hasn't finished
collecting yet, and **no detail-page enrichment has started** for this
source. This section of the document will be updated once collection
is complete, with the same Field Reference structure as Aqarmap and
PropertyFinder above.

---

## ⚠️ Known Data Issues

| Issue | Where | How it will be fixed |
|-------|-------|---------------------|
| `area` field has mixed units ("م² sqm", "m²") | Aqarmap files | Cleaned in Silver Layer |
| `price` has Arabic currency symbol "ج.م" | Aqarmap `data_raw.json` | Standardized in Silver Layer |
| `property_type` is null for many listings | Aqarmap files | Detected from title in Silver Layer |
| `location` has Arabic text in some rows | Aqarmap `data_raw.json` | Translated in `data.json` |
| `amenities` are in Arabic in data_raw.json | Aqarmap `data_raw.json` | Translated in `data_enriched.json` |
| `area_m2` is null for Project listings | Aqarmap files | Handled with Imputation in ML pipeline |
| Mixed Arabic/English in same field | Aqarmap `data_raw.json` | Unified in `data.json` via translation |
| `property_type` / `bedrooms_full` redundant with base fields | PropertyFinder `data_enriched.json` | Will be reconciled in Silver Layer (detail-page values take priority) |

---

## 📊 Data Volume

| File | Approx. Records | Notes |
|------|----------------|-------|
| Aqarmap `data_raw.json` | ~1,400–1,500 | Full 60-page scrape, raw |
| Aqarmap `data.json` | ~1,400–1,500 | Same + translated |
| Aqarmap `data_enriched.json` | ~300 | Sample with extra details |
| PropertyFinder `data.json` | Full scrape complete | Count to confirm from actual file |
| PropertyFinder `data_enriched.json` | Full enrichment complete | Count to confirm from actual file |
| Bayut `data.json` | In progress | Not yet final |


