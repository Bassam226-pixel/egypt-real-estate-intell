from scrapling.fetchers import StealthyFetcher
from deep_translator import GoogleTranslator
import json
import time
import re


def translate_text(text):
    if not text:
        return text
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except Exception:
        return text


def extract_json_ld(page):
    """Extract the RealEstateListing schema block, which holds clean structured data"""
    scripts = page.css('script[type="application/ld+json"]::text').getall()

    for script in scripts:
        try:
            data = json.loads(script)
        except Exception:
            continue

        graph = data.get('@graph') if isinstance(data, dict) else None
        if not graph:
            continue

        for node in graph:
            if node.get('@type') == 'RealEstateListing':
                return node

    return None


def scrape_listing_details(url):
    """Visit a single listing page and extract extra details, matching the
    richness of the PropertyFinder enrichment fields."""

    print(f"Scraping details: {url}")

    try:
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            disable_resources=True,
        )

        details = {}

        # ---- Title / subtitle ----
        details['subtitle'] = page.css('h1::text').get()
        details['full_title'] = page.css('h1::text').get()
        if details['subtitle']:
            details['subtitle'] = details['subtitle'].strip()
        if details['full_title']:
            details['full_title'] = details['full_title'].strip()

        # ---- Listing Details table (Floor / View / Year Built / Payment Method / Seller Type / Price per m2 / Listing ID) ----
        detail_rows = page.css('section#details div.flex.px-1\\.5x.py-2x.gap-2x')

        for row in detail_rows:
            label = row.css('h4::text').get()
            value = row.css('span::text').get()

            if label and value:
                label = label.strip()
                value = value.strip()

                if label == 'Floor':
                    details['floor'] = value
                elif label == 'View':
                    details['view'] = translate_text(value)
                elif label == 'Year Built':
                    details['year_built'] = value
                elif label == 'Payment Method':
                    details['payment_method'] = value
                elif label == 'Seller Type':
                    details['seller_type'] = value
                elif label == 'Price Per Meter':
                    details['price_per_m2'] = value
                elif label == 'Listing ID':
                    details['regulatory_reference'] = value

        # ---- Amenities (visible list, Arabic on AR pages / English on EN pages) ----
        amenities = page.css('section#amenities span.flex-1::text').getall()
        details['amenities'] = [translate_text(a.strip()) for a in amenities if a.strip()]

        # ---- Description ----
        desc_text = page.css('div[style*="overflow"] span::text').get()
        details['description'] = translate_text(desc_text.strip()) if desc_text else None

        # ---- Location ----
        details['full_location'] = page.css('a[href*="/for-sale/"] p.text-body-2::text').get()
        if details['full_location']:
            details['full_location'] = details['full_location'].strip()

        # ---- Agent / Broker ----
        details['agent_name'] = page.css('a[href^="/en/user/"] p.text-title-5::text').get()
        if details['agent_name']:
            details['agent_name'] = details['agent_name'].strip()
        details['broker_name'] = details['agent_name']

        # ---- Structured data (schema.org JSON-LD) — most reliable source ----
        schema = extract_json_ld(page)
        if schema:
            offer = schema.get('offers', {})
            item = schema.get('itemOffered', {})
            address = item.get('address', {})
            geo = item.get('geo', {})

            details['price_full'] = offer.get('price')
            details['property_type_full'] = item.get('@type')
            details['bedrooms_full'] = item.get('numberOfRooms')
            details['bathrooms_full'] = item.get('numberOfBathroomsTotal')

            floor_size = item.get('floorSize', {})
            if floor_size.get('value'):
                details['property_size_full'] = f"{floor_size['value']} sqm"

            details['full_location'] = details['full_location'] or address.get('streetAddress')

            if geo.get('latitude') and geo.get('longitude'):
                details['latitude'] = geo['latitude']
                details['longitude'] = geo['longitude']

            # Amenities from schema are already clean English labels
            amenity_features = item.get('amenityFeature', [])
            schema_amenities = [
                a['name'].replace('_', ' ').title()
                for a in amenity_features
                if a.get('value')
            ]
            if schema_amenities:
                details['amenities'] = schema_amenities

        # Clean up empty strings to None
        for key, value in details.items():
            if isinstance(value, str) and not value.strip():
                details[key] = None

        return details

    except Exception as e:
        print(f"Error scraping listing details: {e}")
        return {}


def enrich_listings(input_file='scrapers/aqarmap/data.json',
                     output_file='scrapers/aqarmap/data_enriched.json',
                     sample_size=300,
                     delay=3):
    """Take base listings and enrich a sample of them with full details"""

    with open(input_file, 'r', encoding='utf-8') as f:
        listings = json.load(f)

    # Take only a sample — enriching all 12k+ listings is too slow/risky
    sample = listings[:sample_size]
    print(f"Enriching {len(sample)} listings out of {len(listings)} total.")

    enriched_listings = []

    for i, listing in enumerate(sample):
        print(f"\nProcessing {i+1}/{len(sample)}")

        if not listing.get('link'):
            print("No link found, skipping details.")
            enriched_listings.append(listing)
            continue

        details = scrape_listing_details(listing['link'])
        listing.update(details)
        enriched_listings.append(listing)

        if (i + 1) % 20 == 0:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(enriched_listings, f, ensure_ascii=False, indent=2)
            print(f"Progress saved at {i+1} listings.")

        time.sleep(delay)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(enriched_listings, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Enriched {len(enriched_listings)} listings.")
    print(f"Saved to {output_file}")


if __name__ == "__main__":
    enrich_listings()