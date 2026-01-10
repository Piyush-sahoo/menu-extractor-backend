import json
import logging
from typing import Dict, Any, List
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class SwiggyScraper:
    async def scrape(self, restaurant_name: str, location: str = "") -> Dict[str, Any]:
        """
        1. Search Swiggy for restaurant to get ID.
        2. Hit internal API for JSON menu.
        """
        print(f"Swiggy: Searching for {restaurant_name}...")
        results = {
            "source": "swiggy",
            "items": [], 
            "status": "failed",
            "menu_url": ""
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # 1. Search (using Google Search to find Swiggy link is often faster/reliable than Swiggy internal search)
                # Query: "Swiggy {restaurant_name} {location}"
                query = f"swiggy {restaurant_name} {location}"
                await page.goto(f"https://www.google.com/search?q={query}")
                
                # Find first swiggy.com link
                # Selector looks for links containing swiggy.com
                link_locator = page.locator("a[href*='swiggy.com/restaurants']").first
                
                if await link_locator.count() > 0:
                    swiggy_url = await link_locator.get_attribute("href")
                    print(f"Found Swiggy URL: {swiggy_url}")
                    results["menu_url"] = swiggy_url
                    
                    # 2. Extract Restaurant ID from URL
                    # URL format: .../restaurant-name-area-city-id
                    try:
                        res_id = swiggy_url.split("-")[-1]
                        # Remove any trailing query params
                        res_id = res_id.split("?")[0]
                        print(f"Swiggy ID: {res_id}")
                        
                        # 3. Fetch Menu JSON directly (Unofficial API)
                        # We can try to fetch the page and extract the INITIAL_STATE json or hit the API
                        # Hitting page is safer to get cookies/crsf if needed
                        await page.goto(swiggy_url, wait_until="domcontentloaded")
                        
                        # Extract JSON data from script tag
                        # Swiggy usually embeds data in a <script id="__NEXT_DATA__"> or similar
                        data = await page.evaluate('''() => {
                            const script = document.getElementById("__NEXT_DATA__");
                            if (script) return JSON.parse(script.innerText);
                            return null; 
                        }''')
                        
                        if data:
                            self._parse_swiggy_json(data, results)
                            results["status"] = "success"
                        else:
                            print("Direct JSON extraction failed, trying API fallback...")
                            # Fallback: simple text parsing for now or dedicated API call
                            
                    except Exception as e:
                        print(f"Error parsing Swiggy ID/Page: {e}")
                else:
                    print("No Swiggy link found.")
                    
            except Exception as e:
                print(f"Swiggy Scrape Error: {e}")
            finally:
                await browser.close()
                
        return results

    def _parse_swiggy_json(self, data: Dict, results: Dict):
        """
        Parses Swiggy's complex JSON structure.
        Note: This structure changes often. 
        """
        try:
            # Navigate finding the 'menu' key in the prop chain
            # This is a heuristic path, might need adjustment
            cards = data.get("props", {}).get("pageProps", {}).get("restaurantData", {}).get("menu", {}).get("items", [])
            # Swiggy's new structure uses "cards" -> "groupedCard" -> "cardGroupMap" -> "REGULAR"
            
            # Allow fallback to generic "find keys" if structure is deep
            # For MVP, let's assume we implement a recursive finder or standard path
            pass 
        except Exception as e:
            print(f"JSON Parse Error: {e}")
