"""
Google Maps Menu Image Extractor
Clean, reusable module following the same pattern as Magicpin.

Key steps:
1. Navigate to Google Maps URL
2. Click "Menu" tab
3. Scroll to load images
4. Extract image URLs (googleusercontent.com)
5. Upgrade to high resolution (=w2000)
6. Download with deduplication
"""
import asyncio
import hashlib
import os
from typing import Dict, Set
import httpx
from playwright.async_api import async_playwright

class GoogleMapsExtractor:
    def __init__(self, output_dir: str = "menu_images"):
        self.output_dir = output_dir
        self.seen_hashes: Set[str] = set()
        os.makedirs(output_dir, exist_ok=True)
    
    def _image_hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
    
    def _upgrade_quality(self, url: str) -> str:
        """Request high resolution version."""
        if "googleusercontent" in url:
            # Replace size params with larger ones
            base = url.split("=")[0]
            return base + "=w2000-h2000"
        return url
    
    async def _download_image(self, url: str, filename: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=20, follow_redirects=True)
                if response.status_code == 200 and len(response.content) > 10000:  # Skip tiny images
                    img_hash = self._image_hash(response.content)
                    if img_hash in self.seen_hashes:
                        print(f"   ⏭️  Duplicate skipped")
                        return False
                    self.seen_hashes.add(img_hash)
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    print(f"   ✅ {filename} ({len(response.content)//1024}KB)")
                    return True
        except Exception as e:
            print(f"   ❌ {e}")
        return False
    
    async def extract(self, url: str) -> Dict:
        print("\n" + "="*60)
        print("🗺️  GOOGLE MAPS MENU EXTRACTOR")
        print("="*60)
        
        result = {
            "source": "google_maps",
            "restaurant_name": "",
            "address": "",
            "image_urls": [],
            "downloaded_paths": [],
            "menu_text": "",
            "status": "failed"
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            try:
                # 1. Navigate
                print(f"\n1️⃣  Navigating to Google Maps...")
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)  # Wait for redirect
                
                # 2. Get restaurant name
                try:
                    await page.wait_for_selector("h1", timeout=15000)
                    result["restaurant_name"] = await page.locator("h1").first.inner_text()
                    print(f"   Restaurant: {result['restaurant_name']}")
                except:
                    pass
                
                # 3. Get address
                try:
                    addr = page.locator("button[data-item-id='address']").first
                    if await addr.count() > 0:
                        result["address"] = await addr.inner_text()
                        print(f"   Address: {result['address'][:50]}...")
                except:
                    pass
                
                # 4. Click Menu tab
                print("\n2️⃣  Looking for Menu tab...")
                menu_clicked = False
                for selector in ["button:has-text('Menu')", "[role='tab']:has-text('Menu')"]:
                    try:
                        btn = page.locator(selector).first
                        if await btn.count() > 0:
                            await btn.click()
                            await page.wait_for_timeout(3000)
                            menu_clicked = True
                            print(f"   ✅ Clicked Menu tab")
                            break
                    except:
                        continue
                
                if not menu_clicked:
                    print("   ⚠️  No Menu tab found, using Photos")
                
                # 5. Extract menu text if available
                try:
                    main_content = page.locator("div[role='main']")
                    result["menu_text"] = await main_content.inner_text()
                    print(f"   Got {len(result['menu_text'])} chars of text")
                except:
                    pass
                
                # 6. Scroll to load images
                print("\n3️⃣  Loading images...")
                for _ in range(5):
                    await page.mouse.wheel(0, 1000)
                    await page.wait_for_timeout(500)
                
                # 7. Extract image URLs
                print("\n4️⃣  Extracting image URLs...")
                all_images = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('img'))
                        .map(img => img.src)
                        .filter(src => src && src.includes('googleusercontent'))
                """)
                
                # Upgrade quality and deduplicate
                menu_images = []
                for img_url in all_images:
                    if "=w" in img_url or "=s" in img_url:  # Has size param
                        hq_url = self._upgrade_quality(img_url)
                        if hq_url not in menu_images:
                            menu_images.append(hq_url)
                
                result["image_urls"] = menu_images
                print(f"   Found {len(menu_images)} unique images")
                
                # 8. Download images
                print(f"\n5️⃣  Downloading high-res images...")
                for i, img_url in enumerate(menu_images[:20]):
                    filename = os.path.join(self.output_dir, f"gmaps_menu_{i+1}.jpg")
                    if await self._download_image(img_url, filename):
                        result["downloaded_paths"].append(filename)
                
                result["status"] = "success"
                print(f"\n✅ Downloaded {len(result['downloaded_paths'])} images to {self.output_dir}/")
                
            except Exception as e:
                print(f"\n❌ Error: {e}")
                result["error"] = str(e)
            finally:
                await browser.close()
        
        return result


if __name__ == "__main__":
    async def main():
        extractor = GoogleMapsExtractor(output_dir="gmaps_menus")
        result = await extractor.extract(
            "https://maps.app.goo.gl/LSyWKi4QK42MrJdi8"
        )
        print(f"\n📊 Final: {len(result['downloaded_paths'])} images saved")
        print(f"   Restaurant: {result['restaurant_name']}")
    
    asyncio.run(main())
