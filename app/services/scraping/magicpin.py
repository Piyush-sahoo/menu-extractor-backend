import logging
from typing import Dict, Any
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class MagicpinScraper:
    async def scrape(self, restaurant_name: str, location: str = "") -> Dict[str, Any]:
        """
        1. Search Magicpin.
        2. Go to /menu section.
        3. Extract images.
        """
        print(f"Magicpin: Searching for {restaurant_name}...")
        results = {
            "source": "magicpin",
            "image_urls": [],
            "status": "failed",
            "menu_url": ""
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # 1. Google Search
                query = f"magicpin {restaurant_name} {location}"
                await page.goto(f"https://www.google.com/search?q={query}")
                
                link_locator = page.locator("a[href*='magicpin.in']").first
                
                if await link_locator.count() > 0:
                    mp_url = await link_locator.get_attribute("href")
                    # Magicpin menu is usually at /menu or in a section
                    print(f"Found Magicpin URL: {mp_url}")
                    results["menu_url"] = mp_url
                    
                    await page.goto(mp_url, wait_until="domcontentloaded")
                    
                    # 2. Look for Menu Images
                    # Magicpin typically puts them in a grid.
                    # Look for images with 'media/restaurant/menu' in path
                    
                    # Scroll to trigger loads
                    await page.mouse.wheel(0, 1000)
                    await page.wait_for_timeout(1000)
                    
                    images = page.locator("img")
                    count = await images.count()
                    
                    for i in range(count):
                        src = await images.nth(i).get_attribute("src")
                        if src and "/menu/" in src:
                             results["image_urls"].append(src)
                             
                    # If we found direct menu images
                    if results["image_urls"]:
                        results["status"] = "success"

                else:
                    print("No Magicpin link found.")
                    
            except Exception as e:
                print(f"Magicpin Scrape Error: {e}")
            finally:
                await browser.close()
                
        return results
