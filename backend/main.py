import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    
    headers = {"User-Agent": "PersonalBookCollectionApp/1.0 (contact@example.com)"}
    
    # --- Tier 1: Direct ISBN Search Index ---
    tier1_url = f"https://openlibrary.org/search.json?isbn={clean_isbn}"
    response = requests.get(tier1_url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        docs = data.get("docs", [])
        if docs:
            best_match = docs[0]
            return {
                "title": best_match.get("title", "Unknown Title"),
                "author": best_match.get("author_name", ["Unknown Author"])[0],
                "isbn": clean_isbn
            }
            
    # --- Tier 2: Regional / Full-Text Fallback Index ---
    # Catches regional press and alternative database entries that lack a primary strict key
    tier2_url = f"https://openlibrary.org/search.json?q={clean_isbn}"
    fallback_response = requests.get(tier2_url, headers=headers)
    
    if fallback_response.status_code == 200:
        fallback_data = fallback_response.json()
        fallback_docs = fallback_data.get("docs", [])
        if fallback_docs:
            best_match = fallback_docs[0]
            authors_list = best_match.get("author_name", ["Unknown Author"])
            return {
                "title": best_match.get("title", "Unknown Title"),
                "author": authors_list[0] if authors_list else "Unknown Author",
                "isbn": clean_isbn
            }
            
    # If both tiers fail to match the regional print
    raise HTTPException(
        status_code=404, 
        detail="Regional book edition not found. Use AI Cover Scan to capture it instantly!"
    )