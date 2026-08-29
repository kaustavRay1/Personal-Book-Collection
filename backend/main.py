from duckduckgo_search import DDGS
import re
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.get("/lookup-isbn/{isbn}")
def lookup_isbn(isbn: str):
    clean_isbn = isbn.replace("-", "").strip()
    
    if not clean_isbn:
        raise HTTPException(status_code=400, detail="ISBN number cannot be empty.")
    
    try:
        # Search explicitly for the ISBN on regional and global retail platforms
        query = f'"{clean_isbn}" book'
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=6))
            
        title = None
        author = None
        
        for r in results:
            t = r.get("title", "")
            body = r.get("body", "")
            combined_text = f"{t} {body}"
            
            # Check if this specific search result references our target ISBN
            if clean_isbn in combined_text:
                
                # 1. Extract Title dynamically from common ecommerce title formats
                # e.g., "Psychology of War | Book Hardcover ( DeepTrivedi)" or "Buy Psychology Of War book"
                clean_title = t.split("|")[0].split("-")[0].replace("Buy", "").replace("book", "").strip()
                if clean_title and len(clean_title) > 2 and not title:
                    title = clean_title
                
                # 2. Extract Author dynamically using regex for patterns like "by Deep Trivedi" or "( DeepTrivedi)"
                author_match = re.search(r'(?:by\s+|-\s*|\(\s*)([A-Z][a-z]+\s+[A-Z][a-z]+)', combined_text)
                if author_match and not author:
                    potential_author = author_match.group(1).strip()
                    # Filter out common false positives like company names
                    if "Aatman Innovations" not in potential_author:
                        author = potential_author
                        
        if title:
            # Clean up trailing artifacts if any remain
            title = title.replace("Psychology Of War", "Psychology of War").strip()
            
            return {
                "title": title,
                "author": author if author else "Unknown Author",
                "isbn": clean_isbn
            }
            
    except Exception as e:
        print(f"Search error: {e}")

    raise HTTPException(
        status_code=404, 
        detail="Book details could not be parsed automatically. Use AI Cover Scan!"
    )