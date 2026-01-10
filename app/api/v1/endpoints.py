from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import traceback
import re

router = APIRouter()

class MenuRequest(BaseModel):
    restaurant_name: Optional[str] = None
    location: Optional[str] = ""
    google_maps_url: Optional[str] = None  # Pass URL directly

@router.post("/extract-menu")
async def extract_menu(request: MenuRequest):
    """
    Full extraction with structured veg/non-veg menu output.
    Saves to MongoDB (30-day TTL) and caches in Redis (1-hour TTL).
    """
    try:
        from app.services.serpapi_service import SerpAPIService
        from app.services.ocr import OcrService
        from app.services.normalizer import NormalizerService
        from app.services.cache import CacheService
        from app.services.mongo_service import MongoService
        
        cache = None
        cache_key = f"{request.restaurant_name}_{request.location}" if request.restaurant_name else None
        
        # Check Redis cache first (1-hour TTL) - only if name provided
        if cache_key:
            cache = CacheService()
            cached = await cache.get_menu(cache_key)
            if cached and cached.get("menu") and cached.get("meta", {}).get("items_count", 0) > 0:
                return {**cached, "source": "cache"}
        
        # Check MongoDB (30-day TTL) - only if name provided
        mongo = MongoService()
        if request.restaurant_name:
            try:
                stored = await mongo.get_menu(request.restaurant_name, request.location)
                # Only use stored data if menu has items
                has_items = False
                if stored and stored.get("menu"):
                    menu = stored.get("menu", {})
                    for veg_type in ["vegetarian", "non_vegetarian"]:
                        if veg_type in menu:
                            for items in menu[veg_type].values():
                                if isinstance(items, list) and len(items) > 0:
                                    has_items = True
                                    break
                if stored and has_items:
                    # Refresh Redis cache (fail silently if redis down)
                    if cache_key and cache:
                        try:
                            await cache.set_menu(cache_key, {
                                "restaurant": stored["restaurant_info"],
                                "menu": stored["menu"],
                                "meta": stored["meta"]
                            })
                        except: pass
                    return {
                        "restaurant": stored["restaurant_info"],
                        "menu": stored["menu"],
                        "meta": stored["meta"],
                        "source": "mongodb"
                    }
            except Exception as e:
                print(f"[Warning] MongoDB read failed: {e}")
        
        import time
        timings = {}
        
        print(f"[API] Fresh extraction for: {request.restaurant_name}")
        
        # Step 1: SerpAPI - Get restaurant info and menu images
        t1 = time.time()
        serpapi = SerpAPIService()
        serp_result = await serpapi.extract_menu_images(
            restaurant_name=request.restaurant_name,
            location=request.location or "",
            max_images=0,  # Get ALL menu images
            google_maps_url=request.google_maps_url
        )
        timings["serpapi"] = round(time.time() - t1, 1)
        print(f"[TIMING] SerpAPI: {timings['serpapi']}s")
        
        if "error" in serp_result and not serp_result.get("image_urls"):
            raise HTTPException(status_code=404, detail=serp_result.get("error"))
        
        restaurant = serp_result.get("restaurant", {})
        image_urls = serp_result.get("image_urls", [])
        print(f"[API] Got {len(image_urls)} menu images")
        
        # Step 2: OCR - Extract text from menu images (parallel, max 10)
        t2 = time.time()
        ocr = OcrService()
        ocr_result = await ocr.process_images(image_urls[:10])  # Limit to 10 for speed
        timings["ocr"] = round(time.time() - t2, 1)
        print(f"[TIMING] OCR: {timings['ocr']}s for {len(image_urls)} images")
        
        combined_text = ocr_result.get("combined_text", "")
        print(f"[API] OCR extracted {len(combined_text)} chars")
        
        if not combined_text:
            return {
                "restaurant": restaurant,
                "menu": None,
                "error": "No text extracted from menu images",
                "meta": {"sources": ["serpapi", "google_vision"], "timings": timings}
            }
        
        # Step 3: Normalize - Structure the menu with Gemini
        t3 = time.time()
        normalizer = NormalizerService()
        normalized = await normalizer.normalize(
            raw_text=combined_text,
            restaurant_name=restaurant.get("name", request.restaurant_name)
        )
        timings["gemini"] = round(time.time() - t3, 1)
        print(f"[TIMING] Gemini: {timings['gemini']}s")
        
        menu = normalized.get("menu")
        meta = {
            "sources": ["serpapi", "google_vision", "gemini"],
            "images_processed": len(image_urls),
            "ocr_chars": len(combined_text),
            "items_count": normalized.get("items_count", 0),
            "timings": timings
        }
        
        # Save to MongoDB (30-day TTL)
        final_name = restaurant.get("name") or request.restaurant_name or "Unknown"
        final_location = request.location or restaurant.get("address") or ""
        
        try:
            await mongo.save_menu(
                restaurant_name=final_name,
                location=final_location,
                restaurant_info=restaurant,
                menu=menu,
                meta=meta
            )
        except Exception as e:
            print(f"[Warning] MongoDB save failed: {e}")
        
        # Cache in Redis (1-hour TTL)
        response_data = {
            "restaurant": restaurant,
            "menu": menu,
            "meta": meta
        }
        
        # Ensure we have a cache service and key
        if not cache_key:
            cache_key = f"{final_name}_{final_location}"
        
        if not cache:
            cache = CacheService()
            
        try:
            await cache.set_menu(cache_key, response_data)
        except Exception as e:
            print(f"[Warning] Redis cache failed: {e}")
        
        print(f"[API] Saved to MongoDB and cached in Redis")
        
        return {**response_data, "source": "fresh"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/menus")
async def list_menus(limit: int = 100, skip: int = 0):
    """List all stored menus from MongoDB."""
    try:
        from app.services.mongo_service import MongoService
        mongo = MongoService()
        menus = await mongo.get_all_menus(limit=limit, skip=skip)
        count = await mongo.get_menu_count()
        return {
            "total": count,
            "menus": menus
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/menus/{restaurant_name}")
async def get_menu(restaurant_name: str, location: str = ""):
    """Get a specific menu from MongoDB."""
    try:
        from app.services.mongo_service import MongoService
        mongo = MongoService()
        menu = await mongo.get_menu(restaurant_name, location)
        if not menu:
            raise HTTPException(status_code=404, detail="Menu not found")
        return menu
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/menus/{restaurant_name}")
async def delete_menu(restaurant_name: str, location: str = ""):
    """Delete a menu from MongoDB and Redis cache."""
    try:
        from app.services.mongo_service import MongoService
        from app.services.cache import CacheService
        
        mongo = MongoService()
        cache = CacheService()
        
        deleted = await mongo.delete_menu(restaurant_name, location)
        await cache.delete(f"{restaurant_name}_{location}")
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Menu not found")
        
        return {"message": f"Menu for {restaurant_name} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/extract-simple")
async def extract_simple(request: MenuRequest):
    """Simple extraction - returns OCR text without Gemini normalization."""
    try:
        from app.services.serpapi_service import SerpAPIService
        from app.services.ocr import OcrService
        
        serpapi = SerpAPIService()
        serp_result = await serpapi.extract_menu_images(
            restaurant_name=request.restaurant_name,
            location=request.location or "",
            max_images=0  # Get ALL menu images
        )
        
        if "error" in serp_result and not serp_result.get("image_urls"):
            return {"error": serp_result.get("error"), "restaurant": None}
        
        restaurant = serp_result.get("restaurant", {})
        image_urls = serp_result.get("image_urls", [])
        
        ocr = OcrService()
        ocr_result = await ocr.process_images(image_urls[:3])
        combined_text = ocr_result.get("combined_text", "")
        
        return {
            "restaurant": restaurant,
            "images_processed": len(image_urls),
            "ocr_chars": len(combined_text),
            "ocr_text_sample": combined_text[:1000] if combined_text else "",
            "sources": ["serpapi", "google_vision"]
        }
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
