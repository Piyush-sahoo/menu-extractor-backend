"""
SerpAPI Menu Extraction Service
Uses Google Maps API via SerpAPI to get menu images.
"""
import os
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from serpapi import GoogleSearch

class SerpAPIService:
    """
    Extracts menu images from Google Maps using SerpAPI.
    No browser required - hosting-friendly!
    """
    
    def __init__(self, api_key: Optional[str] = None):
        from app.core.config import settings
        self.api_key = api_key or settings.SERPAPI_KEY or os.getenv("SERPAPI_KEY")
        if not self.api_key:
            raise ValueError("SERPAPI_KEY not found in environment")
    
    def _search_restaurant(self, restaurant_name: str, location: str = "") -> Optional[Dict]:
        """Search Google Maps for restaurant and get data_id."""
        query = f"{restaurant_name} {location}".strip()
        
        params = {
            "engine": "google_maps",
            "q": query,
            "type": "search",
            "api_key": self.api_key
        }
        
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Check place_results (single exact match)
        if "place_results" in results:
            return results["place_results"]
        
        # Fallback to local_results (list of matches)
        if "local_results" in results and len(results["local_results"]) > 0:
            return results["local_results"][0]
        
        return None
    
    def _get_menu_photos(self, data_id: str) -> List[Dict]:
        """Get photos from the Menu category."""
        params = {
            "engine": "google_maps_photos",
            "data_id": data_id,
            "api_key": self.api_key,
            "category_id": "CgIYIQ"  # Menu category
        }
        
        search = GoogleSearch(params)
        results = search.get_dict()
        
        return results.get("photos", [])
    
    async def _download_image(self, url: str) -> Optional[bytes]:
        """Download image and return bytes."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 10000:
                    return resp.content
        except Exception as e:
            print(f"[SerpAPI] Image download error: {e}")
        return None
    
    async def extract_menu_images(
        self, 
        restaurant_name: Optional[str] = None, 
        location: str = "",
        max_images: int = 0,  # 0 = get ALL images
        google_maps_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main extraction method.
        Returns restaurant info and list of image URLs.
        max_images: 0 means get all available menu images
        """
        search_query = google_maps_url if google_maps_url else f"{restaurant_name} {location}"
        print(f"[SerpAPI] Searching: {search_query[:50]}...")
        
        # Step 1: Search for restaurant
        # If URL is provided, we pass it as the query to find the specific place
        place = self._search_restaurant(search_query, "")  # No location needed if URL or full query used
        
        if not place:
            return {
                "error": "Restaurant not found on Google Maps",
                "source": "serpapi"
            }
        
        # Use found name if original not provided (e.g. only URL given)
        final_name = place.get("title", restaurant_name or "Unknown Restaurant")
        restaurant_info = {
            "name": final_name,
            "address": place.get("address", ""),
            "rating": place.get("rating"),
            "reviews": place.get("reviews"),
            "phone": place.get("phone", ""),
            "data_id": place.get("data_id")
        }
        
        print(f"[SerpAPI] Found: {restaurant_info['name']} (Rating: {restaurant_info['rating']})")
        
        # Step 2: Get menu photos
        data_id = place.get("data_id")
        if not data_id:
            return {
                "restaurant": restaurant_info,
                "image_urls": [],
                "error": "No data_id found",
                "source": "serpapi"
            }
        
        photos = self._get_menu_photos(data_id)
        print(f"[SerpAPI] Found {len(photos)} menu photos (extracting ALL)")
        
        # Step 3: Extract ALL image URLs (no limit)
        image_urls = []
        photos_to_process = photos if max_images == 0 else photos[:max_images]
        for photo in photos_to_process:
            url = photo.get("image", "")
            if url:
                image_urls.append(url)
        
        print(f"[SerpAPI] Returning {len(image_urls)} image URLs")
        
        return {
            "restaurant": restaurant_info,
            "image_urls": image_urls,
            "source": "serpapi"
        }
