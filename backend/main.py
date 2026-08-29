import re
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import ocr_utils  # Contains your Gemini/OCR extraction logic

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
    """Extracts book title and author from a cover image or ISBN snapshot using AI/OCR."""
    contents = await file.read()
    return ocr_utils.extract_book_info(contents)

@app.get("/lookup-isbn/{isbn}")
def lookup_isbn(isbn: str):
    clean_isbn = isbn.replace("-", "").strip()
    
    # Use Open Library Search API instead of strict bibkeys
    url = f"https://openlibrary.org/search.json?q={clean_isbn}"
    response = requests.get(url)
    
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Could not reach book database.")
        
    data = response.json()
    docs = data.get("docs", [])
    
    if not docs:
        raise HTTPException(status_code=404, detail="Book not found for this ISBN.")
        
    # Grab the first matching book from search results
    best_match = docs[0]
    title = best_match.get("title", "Unknown Title")
    
    authors_list = best_match.get("author_name", ["Unknown Author"])
    author = authors_list[0] if authors_list else "Unknown Author"
    
    return {
        "title": title,
        "author": author,
        "isbn": clean_isbn
    }