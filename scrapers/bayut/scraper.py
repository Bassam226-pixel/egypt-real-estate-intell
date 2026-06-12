from scrapling.fetchers import StealthyFetcher
import json
import time


def scrape_bayut(page_number=1):
    url = f"https://www.bayut.eg/en/egypt/properties-for-sale/?page={page_number}"

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

    cards = page.css('article')
    print(f"Found {len(cards)} listings on page {page_number}")

    if not cards:
        print("No cards found - page might be empty or blocked")
        return listings

    for card in cards:
        try:
            # aria-label ثابتة مش بتتغير
            title         = card.css('h2[aria-label="Title"]::text').get()
            price         = card.css('[aria-label="Price"]::text').get()
            location      = card.css('[aria-label="Location"] h3::text').get()
            property_type = card.css('[aria-label="Type"]::text').get()
            bedrooms      = card.css('[aria-label="Beds"]::text').get()
            bathrooms     = card.css('[aria-label="Baths"]::text').get()
            area          = card.css('[aria-label="Area"] h3::text').get()
            link          = card.css('a[aria-label="Listing link"]::attr(href)').get()

            # image - بناخد أول صورة مش placeholder
            images = card.css('img[aria-label="Listing photo"]::attr(src)').getall()
            image = next((img for img in images if 'placeholder' not in img), None)

            # agency - بنجرب كذا selector لأن الـ class بتتغير
            agency = card.css('[aria-label="Agency photo"]::attr(alt)').get()

            listing = {
                'title':         title.strip()         if title         else None,
                'price':         price.strip()         if price         else None,
                'location':      location.strip()      if location      else None,
                'property_type': property_type.strip() if property_type else None,
                'bedrooms':      bedrooms.strip()      if bedrooms      else None,
                'bathrooms':     bathrooms.strip()     if bathrooms     else None,
                'area':          area.strip()          if area          else None,
                'agency':        agency.strip()        if agency        else None,
                'link':          f"https://www.bayut.eg{link}" if link and not link.startswith('http') else link,
                'image':         image,
            }

            listings.append(listing)

        except Exception as e:
            print(f"Error scraping card: {e}")
            continue

    return listings


def main():
    all_listings = []

    for page_num in range(1, 4):
        listings = scrape_bayut(page_num)

        if not listings:
            print(f"No listings found on page {page_num}, stopping.")
            break

        all_listings.extend(listings)
        print(f"Total so far: {len(all_listings)} listings\n")

        time.sleep(3)

    with open('scrapers/bayut/data.json', 'w', encoding='utf-8') as f:
        json.dump(all_listings, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done! Scraped {len(all_listings)} listings total.")
    print("Data saved to scrapers/bayut/data.json")

    if all_listings:
        print("\n--- Sample listing ---")
        print(json.dumps(all_listings[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()