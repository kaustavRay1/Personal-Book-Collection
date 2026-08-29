import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from duckduckgo_search import DDGS
import ocr_utils

app = FastAPI(title="Personal Book Collection Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/extract-text/")
async def extract_text(file: UploadFile = File(...)):
    contents = await file.read()
    return ocr_utils.extract_book_info(contents)

@app.get("/lookup-isbn/{isbn}")
def lookup_isbn(isbn: str):
    clean_isbn = isbn.replace("-", "").strip()
    
    if not clean_isbn:
        raise HTTPException(status_code=400, detail="ISBN number cannot be empty.")
    
    # --- Strategy: Web Search Engine Fallback ---
    try:
        query = f"book ISBN {clean_isbn}"
        with DDGS() as ddgs:
            # Fetch top web search results
            results = list(ddgs.text(query, max_results=3))
            
        if results:
            # Extract title from the search result title/snippet
            best_match = results[0]
            raw_title = best_match.get("title", "Unknown Title")
            snippet = best_match.get("body", "")
            
            # Clean up typical search title clutter (e.g., "Buy Book Name Online at Low Prices... - Amazon")
            title = raw_title.split("-")[0].split("|")[0].strip()
            
            return {
                "title": title if title else "Unknown Title",
                "author": f"Found via Web Search (Ref: {clean_isbn})",
                "isbn": clean_isbn
            }
            
    except Exception as e:
        print(f"Search engine fallback error: {e}")

    # If web search yields nothing
    raise HTTPException(
        status_code=404, 
        detail="Book not found via web search. Use AI Cover Scan to add it instantly!"
    )