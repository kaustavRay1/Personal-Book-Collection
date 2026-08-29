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
    """Queries Open Library public database using a clean ISBN number."""
    clean_isbn = isbn.replace("-", "").strip()
    
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"
    response = requests.get(url)
    
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Could not reach book database.")
        
    data = response.json()
    book_key = f"ISBN:{clean_isbn}"
    
    if book_key not in data:
        raise HTTPException(status_code=404, detail="Book not found for this ISBN.")
        
    book_info = data[book_key]
    title = book_info.get("title", "Unknown Title")
    
    authors_list = book_info.get("authors", [])
    author = authors_list[0].get("name", "Unknown Author") if authors_list else "Unknown Author"
    
    return {
        "title": title,
        "author": author,
        "isbn": clean_isbn
    }