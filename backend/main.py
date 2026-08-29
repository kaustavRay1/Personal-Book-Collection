from fastapi import FastAPI, UploadFile, File
import requests
from fastapi.middleware.cors import CORSMiddleware
import ocr_utils
from fastapi import HTTPException

app = FastAPI(title="OCR Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/lookup-isbn/{isbn}")
def lookup_isbn(isbn: str):
    # Clean up the ISBN string (remove dashes or spaces)
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
    
    # Extract authors list safely
    authors_list = book_info.get("authors", [])
    author = authors_list[0].get("name", "Unknown Author") if authors_list else "Unknown Author"
    
    return {
        "title": title,
        "author": author,
        "isbn": clean_isbn
    }