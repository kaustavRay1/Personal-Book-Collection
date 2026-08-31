import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import cv2
import numpy as np
import ocr_utils

app = FastAPI(title="Personal Book Collection Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ManualBookCreate(BaseModel):
    title: str
    author: str
    isbn: str = "N/A"

@app.post("/scan-barcode/")
async def scan_barcode(file: UploadFile = File(...)):
    """Dedicated ISBN Barcode Scanner: Preprocesses image to extract book ISBN-13 or ISBN-10 barcodes."""
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file uploaded.")
            
        detector = cv2.barcode.BarcodeDetector()
        
        # Pass 1: Try decoding on a grayscale version for higher edge-contrast detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        retval, decoded_info, decoded_type = detector.detectAndDecode(gray)
        
        # Pass 2: Fallback to color image if grayscale scan doesn't catch it
        if not retval or not decoded_info:
            retval, decoded_info, decoded_type = detector.detectAndDecode(img)
        
        isbn_number = None
        if retval and decoded_info is not None:
            if isinstance(decoded_info, np.ndarray):
                codes = decoded_info.flatten().tolist()
            elif isinstance(decoded_info, (list, tuple)):
                codes = list(decoded_info)
            else:
                codes = [str(decoded_info)]
            
            for code in codes:
                if code:
                    clean_code = str(code).strip()
                    # Strictly validate standard book ISBN formats (ISBN-13 starting with 978/979 or ISBN-10)
                    if (clean_code.startswith(("978", "979")) and len(clean_code) == 13) or len(clean_code) == 10:
                        isbn_number = clean_code
                        break
                        
        if not isbn_number:
            raise HTTPException(
                status_code=400, 
                detail="No valid book ISBN barcode found. Try holding the camera steadier or use AI Cover Scan."
            )
            
        return {
            "status": "success",
            "isbn": isbn_number,
            "message": "ISBN barcode scanned successfully!"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ [DEBUG] Server error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error during barcode scan: {str(e)}")
    
@app.post("/extract-text/")
async def extract_text(file: UploadFile = File(...)):
    """AI Cover Scan: Extracts title and author directly from a photo of the book cover/text."""
    contents = await file.read()
    return ocr_utils.extract_book_info(contents)

@app.post("/add-manual-book/")
def add_manual_book(book: ManualBookCreate):
    """Manual Insert: Allows user to manually type book details."""
    if not book.title.strip() or not book.author.strip():
        raise HTTPException(status_code=400, detail="Title and author cannot be empty.")
    
    return {
        "status": "success",
        "message": "Book added manually!",
        "book": {
            "title": book.title,
            "author": book.author,
            "isbn": book.isbn,
            "source": "Manual Entry"
        }
    }

@app.get("/lookup-isbn/{isbn}")
def lookup_isbn(isbn: str):
    """ISBN Text Lookup: Open Library -> Google Books (No AI Fallbacks)."""
    clean_isbn = isbn.replace("-", "").strip()
    
    if not clean_isbn:
        raise HTTPException(status_code=400, detail="ISBN number cannot be empty.")
    
    headers = {"User-Agent": "PersonalBookCollectionApp/1.0 (contact@example.com)"}
    
    # 1. Primary Source: Open Library
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

    # 2. Secondary Source: Google Books API
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
                    "author": authors_list[0] if (authors_list := authors) else "Unknown Author",
                    "isbn": clean_isbn,
                    "source": "Google Books"
                }
                
        elif gb_res.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Google Books API rate limit exceeded.",
                    "retry_after_seconds": 60,
                    "message": "Google Books quota reached. Please use AI Cover Scan or insert manually."
                }
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Google Books lookup error: {e}")

    # Final Fallback if not found in public catalogs
    raise HTTPException(
        status_code=404, 
        detail="Book not found in public databases. Use AI Cover Scan or insert manually."
    )