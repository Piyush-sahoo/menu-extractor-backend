from playwright.async_api import async_playwright
import asyncio
from typing import Dict, List, Any

class GoogleMapsScraper:
    async def scrape(self, url: str) -> Dict[str, Any]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            result = {
                "name": "",
                "address": "",
                "raw_html_menu": "",
                "image_urls": []
            }
            
            try:
                print(f"[GMaps] Navigating to {url}...")
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # Wait for redirect if it's a short URL
                await page.wait_for_timeout(3000)
                
                # Wait for main content
                try:
                    await page.wait_for_selector("h1", timeout=15000)
                except:
                    print("[GMaps] H1 not found, trying alternative...")
                
                # Extract name
                try:
                    name_el = page.locator("h1").first
                    result["name"] = await name_el.inner_text()
                    print(f"[GMaps] Found name: {result['name']}")
                except Exception as e:
                    print(f"[GMaps] Failed to get name: {e}")
                
                # Extract address
                try:
                    addr_el = page.locator("button[data-item-id='address']").first
                    if await addr_el.count() > 0:
                        result["address"] = await addr_el.inner_text()
                        print(f"[GMaps] Found address: {result['address']}")
                except Exception as e:
                    print(f"[GMaps] Address extraction failed: {e}")
                
                # Look for Menu tab - try multiple selectors
                menu_clicked = False
                menu_selectors = [
                    "button:has-text('Menu')",
                    "[role='tab']:has-text('Menu')",
                    "span:has-text('Menu')",
                ]
                
                for selector in menu_selectors:
                    try:
                        menu_btn = page.locator(selector).first
                        if await menu_btn.count() > 0 and await menu_btn.is_visible():
                            await menu_btn.click()
                            await page.wait_for_timeout(2000)
                            menu_clicked = True
                            print(f"[GMaps] Clicked Menu tab with selector: {selector}")
                            break
                    except Exception as e:
                        print(f"[GMaps] Selector {selector} failed: {e}")
                        continue
                
                if menu_clicked:
                    # Extract any text content from menu area
                    try:
                        menu_container = page.locator("div[role='main']")
                        result["raw_html_menu"] = await menu_container.inner_text()
                        print(f"[GMaps] Got menu text: {len(result['raw_html_menu'])} chars")
                    except:
                        pass
                    
                    # Scroll to load lazy images
                    for _ in range(3):
                        await page.mouse.wheel(0, 500)
                        await page.wait_for_timeout(500)
                
                # Collect all relevant images
                images = page.locator("img")
                count = await images.count()
                print(f"[GMaps] Found {count} images total")
                
                for i in range(count):
                    try:
                        src = await images.nth(i).get_attribute("src")
                        if src and "googleusercontent" in src and "=w" in src:
                            # Get higher resolution version
                            high_res = src.split("=w")[0] + "=w800"
                            result["image_urls"].append(high_res)
                    except:
                        continue
                
                print(f"[GMaps] Collected {len(result['image_urls'])} menu-relevant images")
                
            except Exception as e:
                print(f"[GMaps] Error: {e}")
                result["error"] = str(e)
            finally:
                await browser.close()
            
            return result
