"""
Menu Extraction Pipeline
Uses SerpAPI for image extraction + Google Vision for OCR + Gemini for normalization.
"""
import asyncio
from typing import Dict, Any, List
from app.services.serpapi_service import SerpAPIService
from app.services.ocr import OcrService
from app.services.normalizer import NormalizerService
from app.services.cache import CacheService

class ExtractionPipeline:
    """
    Complete menu extraction pipeline:
    1. SerpAPI → Get menu images from Google Maps
    2. Vision OCR → Extract text from images
    3. Gemini → Normalize into structured JSON
    """
    
    def __init__(self):
        self.serpapi = SerpAPIService()
        self.ocr_service = OcrService()
        self.normalizer = NormalizerService()
        self.cache = CacheService()
    
    def _parse_restaurant_from_url(self, url: str) -> tuple[str, str]:
        """Extract restaurant name and location from Google Maps URL."""
        # Example: https://maps.google.com/maps/place/Restaurant+Name+Location
        import re
        
        # Try to extract from URL path
        if "/place/" in url:
            path = url.split("/place/")[1].split("/")[0].split("?")[0]
            # Replace + and - with spaces
            name = path.replace("+", " ").replace("-", " ")
            return name, ""
        
        return "", ""
    
    async def run(
        self, 
        google_maps_url: str = "",
        restaurant_name: str = "",
        location: str = ""
    ) -> Dict[str, Any]:
        """
        Run the complete extraction pipeline.
        
        Args:
            google_maps_url: Google Maps URL (optional if name+location provided)
            restaurant_name: Restaurant name (optional if URL provided)
            location: Location/city (optional)
        
        Returns:
            Structured menu data with items, prices, categories
        """
        print(f"[Pipeline] Starting extraction...")
        
        # Check cache first
        cache_key = google_maps_url or f"{restaurant_name}_{location}"
        cached = await self.cache.get_menu(cache_key)
        if cached:
            print(f"[Pipeline] Cache hit!")
            return cached
        
        # Parse URL if needed
        if google_maps_url and not restaurant_name:
            restaurant_name, location = self._parse_restaurant_from_url(google_maps_url)
        
        if not restaurant_name:
            return {"error": "Restaurant name or URL required", "menu_items": []}
        
        # Step 1: Get menu images via SerpAPI
        print(f"[Pipeline] Step 1: SerpAPI extraction...")
        serpapi_result = await self.serpapi.extract_menu_images(
            restaurant_name=restaurant_name,
            location=location,
            max_images=10
        )
        
        if "error" in serpapi_result and "image_urls" not in serpapi_result:
            return serpapi_result
        
        restaurant_info = serpapi_result.get("restaurant", {})
        image_urls = serpapi_result.get("image_urls", [])
        
        if not image_urls:
            return {
                "restaurant": restaurant_info,
                "menu_items": [],
                "error": "No menu images found",
                "source": "serpapi"
            }
        
        # Step 2: OCR on images
        print(f"[Pipeline] Step 2: OCR on {len(image_urls)} images...")
        ocr_result = await self.ocr_service.process_images(image_urls)
        
        ocr_texts = []
        if "items" in ocr_result:
            ocr_texts = [item.get("raw_text", "") for item in ocr_result["items"]]
        
        combined_text = "\n\n".join(ocr_texts)
        print(f"[Pipeline] OCR extracted {len(combined_text)} characters")
        
        # Step 3: Normalize with Gemini
        print(f"[Pipeline] Step 3: Gemini normalization...")
        raw_data = {
            "restaurant_info": restaurant_info,
            "scraped_fragments": [{"source": "ocr", "raw_text": combined_text}]
        }
        
        normalized_menu = await self.normalizer.normalize(raw_data)
        
        # Build final result
        result = {
            "restaurant": restaurant_info,
            "menu_items": normalized_menu,
            "sources": ["serpapi", "google_vision", "gemini"],
            "images_processed": len(image_urls)
        }
        
        # Save to cache
        await self.cache.set_menu(cache_key, result)
        
        print(f"[Pipeline] Complete! {len(normalized_menu)} menu items extracted")
        return result
