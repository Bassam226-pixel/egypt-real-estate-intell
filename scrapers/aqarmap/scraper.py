from scrapling.fetchers import StealthyFetcher
from deep_translator import GoogleTranslator
import json
import time
from datetime import datetime


def translate_text(text):
    """Translate Arabic text to English, return original if translation fails"""
    if not text:
        return text
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return translated
    except Exception:
        return text


def extract_property_type(card, title):
    """Try to get property type from the breadcrumb link first, fallback to title keywords"""
    breadcrumb_links = card.css('a::attr(href)').getall()

    type_keywords = [
        'apartment', 'villa', 'duplex', 'penthouse', 'townhouse',
        'studio', 'chalet', 'twin-house', 'shop', 'office', 'clinic',
        'land', 'building', 'farm', 'warehouse'
    ]

    for href in breadcrumb_links:
        if href:
            href_lower = href.lower()
            for keyword in type_keywords:
                if keyword in href_lower:
                    return keyword.replace('-', ' ').title()

    if title:
        title_lower = title.lower()
        for keyword in type_keywords:
            if keyword in title_lower:
                return keyword.replace('-', ' ').title()

    return None


def scrape_aqarmap(page_number=1, retries=3):
    url = f"https://aqarmap.com.eg/en/for-sale/property-type/?page={page_number}"

    print(f"Scraping page {page_number}...")

    cards = []
    page = None

    for attempt in range(1, retries + 1):
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
        )

        cards = page.css('article.listing-card')

        # Fallback selectors in case markup differs on some pages
        if len(cards) == 0:
            cards = page.css('article[aria-labelledby^="listing-"]')
        if len(cards) == 0:
            cards = page.css('article')

        print(f"Attempt {attempt}: Found {len(cards)} listings")

        if len(cards) > 0:
            break

        # Page came back empty - could be bot detection / blocked / rate limited,
        # OR the card markup differs on this page. Print diagnostics either way.
        title_tag = page.css('title::text').get()
        print(f"Empty page. <title>: {title_tag}")

        try:
            page_text = page.body.decode('utf-8', errors='ignore') if isinstance(page.body, bytes) else str(page.body)
        except Exception:
            page_text = str(page)

        print(f"Page length: {len(page_text)} chars")

        # Check if any article tags exist at all, even without the listing-card class
        all_articles = page.css('article')
        print(f"Total <article> tags found (any class): {len(all_articles)}")
        if all_articles:
            print(f"First article class attr: {all_articles[0].css('::attr(class)').get()}")

        if attempt < retries:
            wait_time = 8 * attempt
            print(f"Retrying in {wait_time}s...")
            time.sleep(wait_time)

    if len(cards) == 0:
        return None

    listings = []

    for card in cards:
        try:
            price_value   = card.css('data.text-title-5::text').get()
            price_per_sqm = card.css('span.text-caption-1.text-gray__dark_1::text').get()
            title         = card.css('h2::text').get()
            location_parts = card.css('a.hover\\:underline::text').getall()
            location = ' / '.join(p.strip() for p in location_parts if p.strip())
            link = card.css('a::attr(href)').get()

            listing_id = None
            if link:
                try:
                    listing_id = link.split('/listing/')[1].split('-')[0]
                except Exception:
                    listing_id = link

            # Specs are identified by icon class names (size-icon, bedroom-icon,
            # bathroom-icon), which are more stable across card layout variants
            # than compound utility-class chains.
            area = None
            bedrooms = None
            bathrooms = None

            size_li = card.css('li:has(i.size-icon)')
            bedroom_li = card.css('li:has(i.bedroom-icon)')
            bathroom_li = card.css('li:has(i.bathroom-icon)')

            if size_li:
                area_val = size_li[0].css('span::text').get()
                if area_val:
                    area_val = area_val.strip()
                    area = area_val if 'm' in area_val.lower() else f"{area_val} sqm"

            if bedroom_li:
                bedrooms = bedroom_li[0].css('span::text').get()
                if bedrooms:
                    bedrooms = bedrooms.strip()

            if bathroom_li:
                bathrooms = bathroom_li[0].css('span::text').get()
                if bathrooms:
                    bathrooms = bathrooms.strip()

            # Fallback: if the :has() pseudo-class isn't supported by the parser,
            # fall back to positional order (area, bedrooms, bathrooms).
            if not (size_li or bedroom_li or bathroom_li):
                spec_items = card.css('ul.flex.items-center.gap-x-2x li') or card.css('ul li')
                if len(spec_items) >= 1:
                    area_val = spec_items[0].css('span::text').get()
                    if area_val:
                        area = f"{area_val.strip()} sqm"
                if len(spec_items) >= 2:
                    bedrooms = spec_items[1].css('span::text').get()
                    if bedrooms:
                        bedrooms = bedrooms.strip()
                if len(spec_items) >= 3:
                    bathrooms = spec_items[2].css('span::text').get()
                    if bathrooms:
                        bathrooms = bathrooms.strip()

            property_type = extract_property_type(card, title)

            listing = {
                'listing_id':    listing_id,
                'property_type': property_type,
                'title':         title.strip() if title else None,
                'price':         price_value.strip() if price_value else None,
                'location':      location if location else None,
                'bedrooms':      bedrooms,
                'bathrooms':     bathrooms,
                'area':          area,
                'price_per_sqm': price_per_sqm.replace('–', '').strip() if price_per_sqm else None,
                'listing_level': None,
                'listed_date':   None,
                'link':          f"https://aqarmap.com.eg{link}" if link else None,
                'image':         card.css('img::attr(src)').get(),
                'source':        'aqarmap',
                'scraped_at':    datetime.now().isoformat()
            }

            listings.append(listing)

        except Exception as e:
            print(f"Error scraping card: {e}")
            continue

    return listings


def translate_listings(listings):
    """Translate title and location for all listings, unify language to English"""
    print(f"\nTranslating {len(listings)} listings to English...")

    for i, listing in enumerate(listings):
        listing['title'] = translate_text(listing.get('title'))
        listing['location'] = translate_text(listing.get('location'))
        listing['property_type'] = translate_text(listing.get('property_type'))

        if (i + 1) % 50 == 0:
            print(f"Translated {i+1}/{len(listings)}")
            with open('scrapers/aqarmap/data.json', 'w', encoding='utf-8') as f:
                json.dump(listings, f, ensure_ascii=False, indent=2)

        time.sleep(0.3)

    print("Translation done.")
    return listings


def main():
    all_listings = []
    page_num = 1
    max_pages = 60

    while page_num <= max_pages:
        listings = scrape_aqarmap(page_num)

        if listings is None or len(listings) == 0:
            print(f"No more listings found. Stopping at page {page_num}.")
            break

        all_listings.extend(listings)
        page_num += 1

        if page_num % 10 == 0:
            with open('scrapers/aqarmap/data_raw.json', 'w', encoding='utf-8') as f:
                json.dump(all_listings, f, ensure_ascii=False, indent=2)
            print(f"Progress saved: {len(all_listings)} listings so far.")

        time.sleep(5)

    print(f"\nScraping done. Total listings before translation: {len(all_listings)}")

    with open('scrapers/aqarmap/data_raw.json', 'w', encoding='utf-8') as f:
        json.dump(all_listings, f, ensure_ascii=False, indent=2)

    all_listings = translate_listings(all_listings)

    with open('scrapers/aqarmap/data.json', 'w', encoding='utf-8') as f:
        json.dump(all_listings, f, ensure_ascii=False, indent=2)

    print(f"\nTotal listings scraped: {len(all_listings)}")
    print("Data saved to scrapers/aqarmap/data.json")


if __name__ == "__main__":
    main()