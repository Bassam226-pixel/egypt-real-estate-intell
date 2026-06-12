from scrapling.fetchers import StealthyFetcher
import json
import time

def scrape_aqarmap(page_number=1):
    url = f"https://aqarmap.com.eg/en/for-sale/property-type/?page={page_number}"
    
    print(f"Scraping page {page_number}...")
    
    page = StealthyFetcher.fetch(
        url,
        headless=True,
        network_idle=True,
    )
    
    listings = []
    cards = page.css('article.listing-card')
    print(f"Found {len(cards)} listings")
    
    for card in cards:
        try:
            price = card.css('data.text-title-5::text').get()
            title = card.css('h2::text').get()
            location = card.css('a.hover\\:underline::text').get()

            # سحب الـ specs بذكاء
            area = None
            bedrooms = None
            bathrooms = None

            specs_items = card.css('ul.flex li span::text').getall()
            specs_items = [s.strip() for s in specs_items if s.strip()]

            for value in specs_items:
                if 'م²' in value or 'm²' in value:
                    area = value
                elif value.isdigit():
                    if bedrooms is None:
                        bedrooms = value
                    elif bathrooms is None:
                        bathrooms = value

            link = card.css('a::attr(href)').get()
            
            listing = {
                'price': price,
                'title': title,
                'location': location,
                'area_m2': area,
                'bedrooms': bedrooms,
                'bathrooms': bathrooms,
                'link': f"https://aqarmap.com.eg{link}" if link else None
            }
            
            listings.append(listing)
            
        except Exception as e:
            print(f"Error scraping card: {e}")
            continue
    
    return listings


def main():
    all_listings = []
    
    for page_num in range(1, 4):
        listings = scrape_aqarmap(page_num)
        all_listings.extend(listings)
        time.sleep(3)
    
    with open('scrapers/aqarmap/data.json', 'w', encoding='utf-8') as f:
        json.dump(all_listings, f, ensure_ascii=False, indent=2)
    
    print(f"Total listings scraped: {len(all_listings)}")
    print("Data saved to scrapers/aqarmap/data.json")


if __name__ == "__main__":
    main()