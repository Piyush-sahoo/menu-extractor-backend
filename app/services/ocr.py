"""
OCR Service using Google Vision API.
PARALLEL PROCESSING: Downloads and OCRs images concurrently for speed.
"""
from typing import List, Dict, Any, Tuple
import asyncio
import httpx
from google.cloud import vision

class OcrService:
    def __init__(self):
        self.client = None
    
    def _get_client(self):
        """Lazy load Vision client."""
        if not self.client:
            import os
            import json
            from google.oauth2 import service_account
            
            # Check for credentials in env var (for cloud deployment)
            creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_json:
                try:
                    info = json.loads(creds_json)
                    creds = service_account.Credentials.from_service_account_info(info)
                    self.client = vision.ImageAnnotatorClient(credentials=creds)
                    print("[OCR] Using credentials from GOOGLE_CREDENTIALS_JSON env var")
                except Exception as e:
                    print(f"[OCR] Failed to load credentials from env var: {e}")
                    # Fallback to default (file path)
                    self.client = vision.ImageAnnotatorClient()
            else:
                self.client = vision.ImageAnnotatorClient()
        return self.client

    async def _download_image(self, url: str, index: int) -> Tuple[int, bytes]:
        """Download image from URL. Returns (index, bytes)."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 5000:
                    print(f"[OCR] Downloaded image {index+1}: {len(resp.content)//1024}KB")
                    return (index, resp.content)
        except Exception as e:
            print(f"[OCR] Download error {index+1}: {e}")
        return (index, None)

    def _ocr_image_from_url(self, url: str, index: int) -> Tuple[int, str]:
        """Run OCR directly on image URL. Returns (index, text)."""
        try:
            client = self._get_client()
            image = vision.Image()
            image.source.image_uri = url
            
            response = client.text_detection(image=image)
            texts = response.text_annotations
            
            if texts:
                text = texts[0].description
                print(f"[OCR] Image {index+1}: {len(text)} chars")
                # text_detection might return 0 len string
                return (index, text)
            else:
                print(f"[OCR] Image {index+1}: no text")
                return (index, "")
        except Exception as e:
            print(f"[OCR] OCR error {index+1}: {e}")
            return (index, "")

    async def process_images(self, image_urls: List[str]) -> Dict[str, Any]:
        """
        PARALLEL PROCESSING (DIRECT URL):
        Passes URLs directly to Google Vision API, skipping local download.
        """
        if not image_urls:
            return {"source": "google_vision", "items": [], "combined_text": ""}
            
        print(f"[OCR] Processing {len(image_urls)} images via Direct URL...")
        
        # Run OCR in parallel using thread pool
        # We process ALL images in parallel since we don't need to download them first
        loop = asyncio.get_event_loop()
        ocr_tasks = [
            loop.run_in_executor(None, self._ocr_image_from_url, url, i)
            for i, url in enumerate(image_urls)
        ]
        
        ocr_results = await asyncio.gather(*ocr_tasks)
        
        # Combine results in order
        items = []
        all_text = []
        for i, text in sorted(ocr_results, key=lambda x: x[0]):
            if text:
                items.append({"raw_text": text, "image_index": i})
                all_text.append(text)
        
        combined_text = "\n\n---\n\n".join(all_text)
        print(f"[OCR] Done: {len(combined_text)} chars from {len(items)} images")
        
        return {
            "source": "google_vision",
            "items": items,
            "combined_text": combined_text
        }
