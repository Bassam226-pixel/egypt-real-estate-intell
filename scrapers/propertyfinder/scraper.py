from scrapling.fetchers import StealthyFetcher
import json
import time

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
    
    if not cards:
        print("No cards found - page might be empty or blocked")
        return listings
    
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
            
            listing = {
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
            }
            
            listings.append(listing)
            
        except Exception as e:
            print(f"Error scraping card: {e}")
            continue
    
    return listings


def main():
    all_listings = []
    
    for page_num in range(1, 4):
        listings = scrape_propertyfinder(page_num)
        
        if not listings:
            print(f"No listings found on page {page_num}, stopping.")
            break
        
        all_listings.extend(listings)
        print(f"Total so far: {len(all_listings)} listings\n")
        
        time.sleep(3)
    
    with open('propertyfinder_data.json', 'w', encoding='utf-8') as f:
        json.dump(all_listings, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Done! Scraped {len(all_listings)} listings total.")
    print("Data saved to propertyfinder_data.json")
    
    if all_listings:
        print("\n--- Sample listing ---")
        print(json.dumps(all_listings[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()