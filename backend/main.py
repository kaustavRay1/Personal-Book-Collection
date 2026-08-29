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
    
    # ==========================================
    # PRIMARY SOURCE: Open Library (Global + Regional)
    # ==========================================
    try:
        ol_url = f"https://openlibrary.org/search.json?isbn={clean_isbn}"
        res = requests.get(ol_url, headers=headers)
        
        if res.status_code == 200:
            docs = res.json().get("docs", [])
            if not docs:
                broad_res = requests.get(f"https://openlibrary.org/search.json?q={clean_isbn}", headers=headers)
                if broad_res.status_code == 200:
                    docs = broad_res.json().get("docs", [])
            
            if docs:
                match = docs[0]
                authors_list = match.get("author_name", ["Unknown Author"])
                return {
                    "title": match.get("title", "Unknown Title"),
                    "author": authors_list[0] if authors_list else "Unknown Author",
                    "isbn": clean_isbn,
                    "source": "Open Library"
                }
    except Exception as e:
        print(f"Open Library lookup error: {e}")

    # ==========================================
    # BACKUP SOURCE: Google Books API
    # ==========================================
    try:
        gb_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_isbn}"
        gb_res = requests.get(gb_url)
        
        if gb_res.status_code == 200:
            gb_data = gb_res.json()
            if gb_data.get("totalItems", 0) > 0:
                volume_info = gb_data["items"][0].get("volumeInfo", {})
                authors = volume_info.get("authors", ["Unknown Author"])
                return {
                    "title": volume_info.get("title", "Unknown Title"),
                    "author": authors[0] if authors else "Unknown Author",
                    "isbn": clean_isbn,
                    "source": "Google Books"
                }
                
        # Handle Rate Limit Exceeded (429) with explicit retry time instructions
        elif gb_res.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Google Books API rate limit exceeded.",
                    "retry_after_seconds": 60,
                    "message": "Google Books quota reached. Please retry in 60 seconds or use AI Cover Scan."
                }
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Google Books fallback error: {e}")

    # ==========================================
    # FINAL FALLBACK: Not Found
    # ==========================================
    raise HTTPException(
        status_code=404, 
        detail="Book not found in public databases. Use AI Cover Scan to add it!"
    )