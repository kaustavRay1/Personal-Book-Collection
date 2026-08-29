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
    
    # Strategy 1: Direct ISBN Match (Best for standard Western & major global releases)
    url_direct = f"https://openlibrary.org/search.json?isbn={clean_isbn}"
    res_direct = requests.get(url_direct, headers=headers)
    
    if res_direct.status_code == 200:
        docs = res_direct.json().get("docs", [])
        if docs:
            match = docs[0]
            return {
                "title": match.get("title", "Unknown Title"),
                "author": match.get("author_name", ["Unknown Author"])[0],
                "isbn": clean_isbn
            }
            
    # Strategy 2: Full-Text Broad Query Match (Crucial for regional/Indian prints & alternative records)
    url_broad = f"https://openlibrary.org/search.json?q={clean_isbn}"
    res_broad = requests.get(url_broad, headers=headers)
    
    if res_broad.status_code == 200:
        docs = res_broad.json().get("docs", [])
        if docs:
            match = docs[0]
            authors_list = match.get("author_name", ["Unknown Author"])
            return {
                "title": match.get("title", "Unknown Title"),
                "author": authors_list[0] if authors_list else "Unknown Author",
                "isbn": clean_isbn
            }
            
    # Strategy 3: Direct Edition Path Lookup (Fallback for localized metadata files)
    url_edition = f"https://openlibrary.org/isbn/{clean_isbn}.json"
    res_edition = requests.get(url_edition, headers=headers)
    
    if res_edition.status_code == 200:
        data = res_edition.json()
        title = data.get("title", "Unknown Title")
        author = "Unknown Author"
        authors_ref = data.get("authors", [])
        if authors_ref and "key" in authors_ref[0]:
            author_res = requests.get(f"https://openlibrary.org{authors_ref[0]['key']}.json", headers=headers)
            if author_res.status_code == 200:
                author = author_res.json().get("name", "Unknown Author")
        return {
            "title": title,
            "author": author,
            "isbn": clean_isbn
        }

    # If all three lookup strategies fail to find the book
    raise HTTPException(
        status_code=404, 
        detail="Book not found for this ISBN. You can use AI Cover Scan to add it manually!"
    )