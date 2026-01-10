import logging
from typing import Dict, Any
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class ZomatoScraper:
    async def scrape(self, restaurant_name: str, location: str = "") -> Dict[str, Any]:
        """
        1. Search Zomato.
        2. Go to /menu.
        3. Extract all image URLs from the gallery.
        """
        print(f"Zomato: Searching for {restaurant_name}...")
        results = {
            "source": "zomato",
            "image_urls": [],
            "status": "failed",
            "menu_url": ""
        }
        
        async with async_playwright() as p:
            # Zomato has heavy bot detection. Stealth plugin needed in prod.
            # Here we try with standard browser.
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                # 1. Google Search for Zomato Link (To bypass internal search)
                query = f"zomato {restaurant_name} {location} menu"
                await page.goto(f"https://www.google.com/search?q={query}")
                
                link_locator = page.locator("a[href*='zomato.com'][href*='/menu']").first
                
                if await link_locator.count() > 0:
                    menu_url = await link_locator.get_attribute("href")
                    print(f"Found Zomato Menu URL: {menu_url}")
                    results["menu_url"] = menu_url
                    
                    await page.goto(menu_url, wait_until="domcontentloaded")
                    
                    # 2. Extract Images
                    # Zomato menu pages have a specific grid.
                    # We look for img tags within the menu container
                    # Heuristic: images with 'zomato' in src and dimensions
                    
                    # Wait for lazy load
                    await page.mouse.wheel(0, 1000)
                    await page.wait_for_timeout(2000)

                    images = page.locator("div#menu-gallery img") # Varies, generic selector
                    # Fallback generic
                    if await images.count() == 0:
                         images = page.locator("img")

                    count = await images.count()
                    for i in range(count):
                        src = await images.nth(i).get_attribute("src")
                        if src and "zomato" in src and "menus" in src:
                             # usually 'thumb' is in url, we want full size
                             # simple text replace often works for zomato: /thumb/ -> /original/ or remove params
                             hq_src = src.split("?")[0] 
                             results["image_urls"].append(hq_src)
                    
                    if results["image_urls"]:
                        results["status"] = "success"
                        
                else:
                    print("No Zomato Menu link found.")
                    
            except Exception as e:
                print(f"Zomato Scrape Error: {e}")
            finally:
                await browser.close()
                
        return results
