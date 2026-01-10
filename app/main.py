import os
from dotenv import load_dotenv

# Load .env file FIRST before any other imports
load_dotenv()

# Set Google credentials explicitly
creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if creds_path:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    print(f"[STARTUP] Google credentials: {creds_path}")

from fastapi import FastAPI
from app.api.v1.endpoints import router as api_router

app = FastAPI(title="Menu Extractor API")

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    print("[STARTUP] Menu Extractor API started")
    print(f"[STARTUP] SERPAPI_KEY: {'SET' if os.getenv('SERPAPI_KEY') else 'NOT SET'}")
    print(f"[STARTUP] GEMINI_API_KEY: {'SET' if os.getenv('GEMINI_API_KEY') else 'NOT SET'}")
    print(f"[STARTUP] GOOGLE_CREDS: {'SET' if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') else 'NOT SET'}")
