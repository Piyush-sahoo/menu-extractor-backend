import os
# Suppress deprecation warning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

import json
import logging
import asyncio
from typing import Dict, Any, List
import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

MENU_SCHEMA = '''{"vegetarian": {"starters": [...], "main_course": [...], "rice_and_biryani": [...], "breads": [...], "desserts": [...], "beverages": [...]}, "non_vegetarian": {"starters": [...], "main_course": [...], "seafood": [...], "rice_and_biryani": [...], "desserts": [...], "beverages": []}}
{{ ... }}'''

PARSE_PROMPT = """Parse this menu text into JSON. RESTAURANT: {restaurant_name}

MENU TEXT:
{text}

OUTPUT FORMAT: {schema}

RULES:
1. VEG: Paneer, Vegetables, Dal, Rice | NON-VEG: Chicken, Mutton, Fish, Prawns, Egg
2. Categories: starters, main_course, seafood, rice_and_biryani, breads, desserts, beverages
3. Cuisine: North Indian, South Indian, Chinese, Italian, Thai, Goan, Continental
4. Prices: If one price, use "full", set "half" to "NA". If no price, both "NA"
5. spicy=true if has chili/masala. bestseller=true if marked special

RETURN ONLY VALID JSON."""

class NormalizerService:
    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            logger.warning("GEMINI_API_KEY not found.")
            self.model = None

    async def normalize(self, raw_text: str, restaurant_name: str = "") -> Dict[str, Any]:
        """Parse OCR text into structured menu JSON with parallel chunking."""
        if not self.model:
            return {"error": "Gemini not configured"}
        if not raw_text or len(raw_text) < 50:
            return {"error": "Insufficient text"}

        # Split into chunks and process in parallel
        chunks = self._split_text(raw_text, chunk_size=2000)
        print(f"[Normalizer] Processing {len(chunks)} chunks in PARALLEL...")
        
        # Process all chunks in parallel
        tasks = [self._parse_chunk(chunk, restaurant_name, i) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Merge all results
        combined_menu = {
            "vegetarian": {"starters": [], "main_course": [], "rice_and_biryani": [], "breads": [], "desserts": [], "beverages": []},
            "non_vegetarian": {"starters": [], "main_course": [], "seafood": [], "rice_and_biryani": [], "desserts": [], "beverages": []}
        }
        
        for result in results:
            if isinstance(result, dict) and "menu" in result:
                self._merge_menus(combined_menu, result["menu"])
        
        items_count = self._count_items(combined_menu)
        print(f"[Normalizer] Total: {items_count} items from {len(chunks)} chunks")
        
        return {"menu": combined_menu, "items_count": items_count, "chunks": len(chunks)}

    async def _parse_chunk(self, text: str, restaurant_name: str, chunk_idx: int) -> Dict[str, Any]:
        """Parse a single chunk of text."""
        prompt = PARSE_PROMPT.format(
            restaurant_name=restaurant_name,
            text=text,
            schema=MENU_SCHEMA
        )
        
        try:
            response = await self.model.generate_content_async(prompt)
            cleaned = response.text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            
            parsed = json.loads(cleaned)
            items = self._count_items(parsed)
            print(f"[Normalizer] Chunk {chunk_idx+1}: {items} items")
            return {"menu": parsed}
        except Exception as e:
            print(f"[Normalizer] Chunk {chunk_idx+1} error: {e}")
            return {"error": str(e)}

    def _split_text(self, text: str, chunk_size: int = 2000) -> List[str]:
        """Split text into chunks at paragraph breaks."""
        chunks = []
        current = ""
        for para in text.split("\n\n"):
            if len(current) + len(para) < chunk_size:
                current += para + "\n\n"
            else:
                if current:
                    chunks.append(current.strip())
                current = para + "\n\n"
        if current:
            chunks.append(current.strip())
        return chunks if chunks else [text[:chunk_size]]

    def _merge_menus(self, target: Dict, source: Dict):
        """Merge source menu into target."""
        for veg_type in ["vegetarian", "non_vegetarian"]:
            if veg_type in source:
                for category, items in source[veg_type].items():
                    if isinstance(items, list) and category in target[veg_type]:
                        target[veg_type][category].extend(items)

    def _count_items(self, menu: Dict) -> int:
        """Count total items."""
        count = 0
        for veg_type in ["vegetarian", "non_vegetarian"]:
            if veg_type in menu:
                for items in menu[veg_type].values():
                    if isinstance(items, list):
                        count += len(items)
        return count
