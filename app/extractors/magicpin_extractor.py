"""
Magicpin Menu Image Extractor - With Anti-Bot Bypass
"""
import asyncio
import hashlib
import os
from typing import Dict, Set
import httpx
from playwright.async_api import async_playwright

class MagicpinExtractor:
    def __init__(self, output_dir: str = "menu_images"):
        self.output_dir = output_dir
        self.seen_hashes: Set[str] = set()
        os.makedirs(output_dir, exist_ok=True)
    
    def _image_hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
    
    async def _download_image(self, url: str, filename: str) -> bool:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://magicpin.in/"
            }
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15, follow_redirects=True, headers=headers)
                if response.status_code == 200 and len(response.content) > 5000:
                    img_hash = self._image_hash(response.content)
                    if img_hash in self.seen_hashes:
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
        print("🍽️  MAGICPIN MENU EXTRACTOR")
        print("="*60)
        
        result = {
            "source": "magicpin",
            "restaurant_name": "",
            "image_urls": [],
            "downloaded_paths": [],
            "status": "failed"
        }
        
        async with async_playwright() as p:
            # Use more realistic browser context
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox'
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US"
            )
            page = await context.new_page()
            
            # Remove webdriver property
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            try:
                print(f"\n1️⃣  Navigating to {url[:50]}...")
                response = await page.goto(url, timeout=60000, wait_until="networkidle")
                print(f"   Status: {response.status}")
                
                await page.wait_for_timeout(3000)
                
                # Get name
                try:
                    title = await page.title()
                    result["restaurant_name"] = title.split("|")[0].strip()
                    print(f"   Restaurant: {result['restaurant_name']}")
                except:
                    pass
                
                # Scroll to load images
                print("\n2️⃣  Scrolling to load images...")
                for _ in range(5):
                    await page.mouse.wheel(0, 2000)
                    await page.wait_for_timeout(1000)
                
                # Extract images
                print("\n3️⃣  Extracting images...")
                all_images = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('img'))
                        .map(img => img.src || img.dataset.src)
                        .filter(src => src && src.length > 10)
                """)
                
                print(f"   Total images on page: {len(all_images)}")
                
                # Filter for content images
                menu_images = []
                for img_url in all_images:
                    if any(d in img_url for d in ["cdn.magicpin.com", "images.magicpin.in", "googleusercontent"]):
                        if not any(s in img_url for s in [".svg", "static/", "placeholder", "icon"]):
                            menu_images.append(img_url)
                
                menu_images = list(dict.fromkeys(menu_images))
                result["image_urls"] = menu_images
                print(f"   Menu images found: {len(menu_images)}")
                
                # Download
                print(f"\n4️⃣  Downloading images...")
                for i, img_url in enumerate(menu_images[:15]):
                    filename = os.path.join(self.output_dir, f"magicpin_{i+1}.jpg")
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
        extractor = MagicpinExtractor(output_dir="magicpin_menus")
        result = await extractor.extract(
            "https://magicpin.in/Bangalore/Sarjapur-Road/Restaurant/The-FishermanS-Wharf/store/6c66/menu/"
        )
        print(f"\n📊 Final: {len(result['downloaded_paths'])} images saved")
    
    asyncio.run(main())
