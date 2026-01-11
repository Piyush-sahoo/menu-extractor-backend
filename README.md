# Menu Extractor API 🍽️

> Extract structured menu data from any restaurant using Google Maps photos, Vision OCR, and Gemini AI.

## 📈 Performance Comparison

| Version | Total Time | OCR | Gemini | Speedup |
|---------|------------|-----|--------|--------|
| v1 (Sequential) | 120s | 36s | 81s | 1x |
| v2 (Parallel OCR) | 90s | 18s | 70s | 1.3x |
| v3 (Parallel Gemini) | 60s | 18s | 35s | 2x |
| **v4 (Full Parallel)** | **32s** | **16s** | **8s** | **4x** 🚀 |

**From 2 minutes to 30 seconds — 4x faster!** 🔥

---

## ⚡ Current Performance

| Metric | Time |
|--------|------|
| **Total Extraction** | **~30 seconds** |
| SerpAPI | 5s |
| OCR (10 images parallel) | 16s |
| Gemini (parallel chunks) | 8s |

---

## 🔬 Why SerpAPI? (The Journey)

We explored multiple approaches before settling on SerpAPI:

| Approach | Problem | Outcome |
|----------|---------|----------|
| **Zomato API** | Rate limiting + Blocked scraping | ❌ Blocked |
| **Swiggy API** | Rate limiting + Anti-bot protection | ❌ Blocked |
| **MagicPin** | Rate limiting + CAPTCHA | ❌ Blocked |
| **Direct Google Maps** | Rate limiting on images | ❌ Blocked |
| **Zomato MCP** | Added latency (~10s overhead) | ❌ Too slow |
| **SerpAPI** | Reliable, no rate limits, fast | ✅ **Winner** |

**SerpAPI** provides direct access to Google Maps photos without rate limiting, making it the most reliable and fastest option for production use.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MENU EXTRACTOR API                           │
│                      (FastAPI + Python 3.11)                        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
          ┌─────────────────┐         ┌─────────────────┐
          │   Redis Cache   │         │    MongoDB      │
          │   (1 hour TTL)  │         │  (30 day TTL)   │
          └─────────────────┘         └─────────────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  ▼
                    ┌─────────────────────────┐
                    │     FRESH EXTRACTION    │
                    └─────────────────────────┘
                                  │
           ┌──────────────────────┼──────────────────────┐
           ▼                      ▼                      ▼
   ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
   │   STEP 1      │     │   STEP 2      │     │   STEP 3      │
   │   SerpAPI     │────▶│    OCR        │────▶│   Gemini      │
   │   (5 sec)     │     │  (16 sec)     │     │  (8 sec)      │
   └───────────────┘     └───────────────┘     └───────────────┘
         │                      │                      │
         ▼                      ▼                      ▼
   ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
   │ Google Maps   │     │ Google Vision │     │ Gemini Flash  │
   │ Photos API    │     │ API (Parallel)│     │ (Parallel)    │
   └───────────────┘     └───────────────┘     └───────────────┘
```

---

## 📊 Data Flow

```
Restaurant Name + Location
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: SerpAPI (5 sec)                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Search Google Maps for restaurant                │    │
│  │ 2. Get data_id for restaurant                       │    │
│  │ 3. Fetch "Menu" category photos (CgIYIQ)            │    │
│  │ 4. Return: restaurant info + 10-20 image URLs       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼ [10 image URLs]
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: OCR - PARALLEL (16 sec for 10 images)              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │    │
│  │  │IMG 1│ │IMG 2│ │IMG 3│ │IMG 4│ │IMG 5│ ...       │    │
│  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘           │    │
│  │     │       │       │       │       │               │    │
│  │     └───────┴───────┴───┬───┴───────┘               │    │
│  │                         ▼                            │    │
│  │              asyncio.gather() - PARALLEL             │    │
│  │                         │                            │    │
│  │     ┌───────┬───────┬───┴───┬───────┬───────┐       │    │
│  │     ▼       ▼       ▼       ▼       ▼       ▼       │    │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │    │
│  │  │VISION│ │VISION│ │VISION│ │VISION│ │VISION│ ...   │    │
│  │  │ API │ │ API │ │ API │ │ API │ │ API │           │    │
│  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘           │    │
│  │     └───────┴───────┴───┬───┴───────┘               │    │
│  │                         ▼                            │    │
│  │              Combined OCR Text (~10k chars)          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼ [Combined text ~10k chars]
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: GEMINI - PARALLEL CHUNKING (8 sec)                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Split into 5000 char chunks                │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                │    │
│  │  │ Chunk 1 │ │ Chunk 2 │ │ Chunk 3 │                │    │
│  │  └────┬────┘ └────┬────┘ └────┬────┘                │    │
│  │       │           │           │                      │    │
│  │       └───────────┼───────────┘                      │    │
│  │                   ▼                                  │    │
│  │        asyncio.gather() - PARALLEL                   │    │
│  │                   │                                  │    │
│  │       ┌───────────┼───────────┐                      │    │
│  │       ▼           ▼           ▼                      │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                │    │
│  │  │ Gemini  │ │ Gemini  │ │ Gemini  │                │    │
│  │  │  API    │ │  API    │ │  API    │                │    │
│  │  └────┬────┘ └────┬────┘ └────┬────┘                │    │
│  │       │           │           │                      │    │
│  │       └───────────┼───────────┘                      │    │
│  │                   ▼                                  │    │
│  │         Merge all JSON results                       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  OUTPUT: Structured Menu JSON                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ {                                                    │    │
│  │   "vegetarian": {                                    │    │
│  │     "starters": [...],                               │    │
│  │     "main_course": [...]                             │    │
│  │   },                                                 │    │
│  │   "non_vegetarian": {                                │    │
│  │     "starters": [...],                               │    │
│  │     "seafood": [...]                                 │    │
│  │   }                                                  │    │
│  │ }                                                    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Ways to Make OCR Faster

| Optimization | Impact | Status |
|-------------|--------|--------|
| **Parallel image downloads** | 3x faster | ✅ Done |
| **Parallel Vision API calls** | 5x faster | ✅ Done |
| **First 10 popular/recent images** | 2x faster (covers most menu data) | ✅ Done |

### Current OCR Implementation:

```python
# Parallel download + parallel OCR
async def process_images(image_urls):
    # Step 1: Download ALL images in parallel
    download_tasks = [download_image(url) for url in image_urls[:10]]
    images = await asyncio.gather(*download_tasks)
    
    # Step 2: Run OCR in parallel using thread pool
    ocr_tasks = [run_executor(vision_api, img) for img in images]
    texts = await asyncio.gather(*ocr_tasks)
    
    return combined_text
```

---

## 📁 Project Structure

```
menu_extractor/
├── app/
│   ├── api/v1/
│   │   └── endpoints.py      # API routes
│   ├── core/
│   │   └── config.py         # Settings
│   ├── models/
│   │   └── response.py       # Pydantic models
│   └── services/
│       ├── serpapi_service.py  # Google Maps extraction
│       ├── ocr.py              # Vision API (parallel)
│       ├── normalizer.py       # Gemini AI (parallel chunks)
│       ├── cache.py            # Redis (1h TTL)
│       └── mongo_service.py    # MongoDB (30d TTL)
├── docker-compose.yml        # MongoDB + Redis
├── requirements.txt
└── .env
```

---

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/extract-menu` | Extract menu (with caching) |
| POST | `/api/v1/extract-simple` | Quick OCR (no Gemini) |
| GET | `/api/v1/menus` | List all stored menus |
| GET | `/api/v1/menus/{name}` | Get specific menu |
| DELETE | `/api/v1/menus/{name}` | Delete menu |

### Example Request:
```bash
curl -X POST "http://localhost:8000/api/v1/extract-menu" \
  -H "Content-Type: application/json" \
  -d '{"restaurant_name": "MTR", "location": "Jayanagar Bangalore"}'
```

### Example Response:
```json
{
  "restaurant": {
    "name": "MTR",
    "rating": 4.5,
    "reviews": 12345
  },
  "menu": {
    "vegetarian": {
      "starters": [
        {"name": "Masala Dosa", "prices": {"half": 80, "full": 150}}
      ]
    }
  },
  "meta": {
    "items_count": 45,
    "timings": {"serpapi": 5.2, "ocr": 15.8, "gemini": 7.7}
  }
}
```

---

### 🐳 Production / Docker Quick Start (Recommended)

1. **Clone the repo**
   ```bash
   git clone https://github.com/Piyush-sahoo/menu-extractor-backend
   cd menu_extractor-backend
   ```

2. **Configure Environment**
   - Copy `.env.example` to `.env`
   - Add your keys (SERPAPI_KEY, GEMINI_API_KEY)
   - **Important**: For Google Cloud Vision, paste your JSON key content into `GOOGLE_CREDENTIALS_JSON` in `.env`.

3. **Run Everything**
   ```bash
   docker-compose up --build -d
   ```
   The API will start at `http://localhost:8000`.

### 🛠️ Local Development (Manual Setup)

1. **Setup Python**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run Databases**
   ```bash
   docker-compose up -d mongo redis
   ```

3. **Run Server**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

---

## 📈 Performance Comparison

| Version | Total Time | OCR | Gemini | Speedup |
|---------|------------|-----|--------|--------|
| v1 (Sequential) | 120s | 36s | 81s | 1x |
| v2 (Parallel OCR) | 90s | 18s | 70s | 1.3x |
| v3 (Parallel Gemini) | 60s | 18s | 35s | 2x |
---

## 🔮 Future Parallelization Ideas

| Idea | Potential Impact | Complexity |
|------|-----------------|------------|
| **Overlap OCR + Gemini** | Start Gemini on first chunk while OCR continues | ~15% faster | Medium |
| **Batch Vision API** | Send multiple images in single request | ~20% faster | Low |
| **Stream Gemini responses** | Use streaming to start processing earlier | ~10% faster | Medium |
| **Prefetch popular restaurants** | Background job to cache top restaurants | Instant for cached | High |
| **Parallel cache + DB check** | Check Redis and MongoDB simultaneously | ~1s faster | Low |
