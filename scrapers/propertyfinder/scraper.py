from scrapling.fetchers import StealthyFetcher
import json
import time
from datetime import datetime


def scrape_propertyfinder(page_number=1):
    url = f"https://www.propertyfinder.eg/en/buy/properties-for-sale.html?page={page_number}"

    print(f"Scraping page {page_number}...")

    page = StealthyFetcher.fetch(
        url,
        headless=True,
        network_idle=True,
        disable_resources=True,
        google_search=True,
        timeout=60000,
    )

    listings = []

    cards = page.css('[data-testid="property-card"]')
    print(f"Found {len(cards)} listings on page {page_number}")

    if len(cards) == 0:
        return None

    for card in cards:
        try:
            property_type = card.css('[data-testid="property-card-type"] span::text').get()
            title         = card.css('h3::text').get()
            price         = card.css('[data-testid="property-card-price"] p::text').get()
            location      = card.css('[data-testid="property-card-location"] p::text').get()

            bedrooms      = card.css('[data-testid="property-card-spec-bedroom"]::text').get()
            bathrooms     = card.css('[data-testid="property-card-spec-bathroom"]::text').get()
            area          = card.css('[data-testid="property-card-spec-area"]::text').get()
            price_per_sqm = card.css('[data-testid="property-card-spec-price-per-area"]::text').get()

            listing_level = card.css('[class*="listing-level"]::text').get()
            listed_date   = card.css('[class*="publish-info"]::text').get()
            link          = card.css('[data-testid="property-card-link"]::attr(href)').get()
            image         = card.css('[data-testid="gallery-picture"]:not([data-testid="webp-placeholder"])::attr(src)').get()

            listing_id = None
            if link:
                try:
                    listing_id = link.rstrip('.html').split('-')[-1]
                except Exception:
                    listing_id = link

            listing = {
                'listing_id':    listing_id,
                'property_type': property_type.strip() if property_type else None,
                'title':         title.strip()         if title         else None,
                'price':         price.strip()         if price         else None,
                'location':      location.strip()      if location      else None,
                'bedrooms':      bedrooms.strip()      if bedrooms      else None,
                'bathrooms':     bathrooms.strip()     if bathrooms     else None,
                'area':          area.strip()          if area          else None,
                'price_per_sqm': price_per_sqm.strip() if price_per_sqm else None,
                'listing_level': listing_level.strip() if listing_level else None,
                'listed_date':   listed_date.strip()   if listed_date   else None,
                'link':          link,
                'image':         image,
                'source':        'propertyfinder',
                'scraped_at':    datetime.now().isoformat()
            }

            listings.append(listing)

        except Exception as e:
            print(f"Error scraping card: {e}")
            continue

    return listings


def main():
    all_listings = []
    page_num = 1
    max_pages = 50  # limited run, not the whole site

    while page_num <= max_pages:
        listings = scrape_propertyfinder(page_num)

        if listings is None or len(listings) == 0:
            print(f"No more listings found. Stopping at page {page_num}.")
            break

        all_listings.extend(listings)
        page_num += 1

        if page_num % 10 == 0:
            with open('scrapers/propertyfinder/data_raw.json', 'w', encoding='utf-8') as f:
                json.dump(all_listings, f, ensure_ascii=False, indent=2)
            print(f"Progress saved: {len(all_listings)} listings so far.")

        time.sleep(3)

    print(f"\nScraping done. Total listings: {len(all_listings)}")

    with open('scrapers/propertyfinder/data.json', 'w', encoding='utf-8') as f:
        json.dump(all_listings, f, ensure_ascii=False, indent=2)

    print("Data saved to scrapers/propertyfinder/data.json")


if __name__ == "__main__":
    main()