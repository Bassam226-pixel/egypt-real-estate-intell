from scrapling.fetchers import StealthyFetcher
import json
import time


def scrape_listing_details(url):
    """Visit a single listing page and extract extra details"""

    print(f"Scraping details: {url}")

    try:
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            disable_resources=True,
        )

        details = {}

        # Core property details panel (Property Type, Property Size, Bedrooms, Bathrooms, Available from)
        details['property_type_full'] = page.css('[data-testid="property-details-type"]::text').get()
        details['property_size_full'] = page.css('[data-testid="property-details-size"]::text').get()
        details['bedrooms_full']      = page.css('[data-testid="property-details-bedrooms"]::text').get()
        details['bathrooms_full']     = page.css('[data-testid="property-details-bathrooms"]::text').get()
        details['available_from']     = page.css('[data-testid="property-details-rental-availability-date"]::text').get()

        # Price (full price block from the detail page header)
        details['price_full'] = page.css('[data-testid="property-price-value"]::text').get()

        # Title / Subtitle
        details['subtitle'] = page.css('.styles_desktop_subtitle__XntGT::text').get()
        details['full_title'] = page.css('h1.styles_desktop_title__j0uNx::text').get()

        # Description
        details['description'] = page.css('[data-testid="dynamic-sanitize-html"]::text').get()

        # Amenities
        amenities = page.css('[data-testid^="amenity-"] p.styles_text__IlyiW::text').getall()
        details['amenities'] = [a.strip() for a in amenities if a.strip()]

        # Project information (if off-plan/new project)
        details['project_name']     = page.css('.styles_desktop_project-information__card-title__Rx6gS::text').get()
        details['project_status']  = page.css('[data-testid="tag"]::text').get()
        details['developer']       = page.css('[data-testid="project-information-developer-link"]::text').get()
        details['delivery_date']   = page.css('[data-testid="delivery-date"] + p::text').get()

        # Location
        details['full_location'] = page.css('.styles-module_map__title__M2mBC::text').get()

        # Agent / Broker
        details['agent_name']  = page.css('[data-testid="property-detail-agent-name"]::text').get()
        details['broker_name'] = page.css('[data-testid="property-detail-broker-name"]::text').get()

        # Regulatory reference + listed date
        details['regulatory_reference'] = page.css('[data-testid="property-regulatory-reference"]::text').get()

        # Clean up Nones/empty strings into stripped values
        for key, value in details.items():
            if isinstance(value, str):
                details[key] = value.strip() or None

        return details

    except Exception as e:
        print(f"Error scraping listing details: {e}")
        return {}


def enrich_listings(input_file='scrapers/propertyfinder/data.json',
                     output_file='scrapers/propertyfinder/data_enriched.json',
                     sample_size=300,
                     delay=3):
    """Take base listings and enrich a sample of them with full details"""

    with open(input_file, 'r', encoding='utf-8') as f:
        listings = json.load(f)

    # Take only a sample — enriching everything is too slow/risky
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