import os
import json
from google import genai
from google.genai import types
from PIL import Image
import io
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

client = genai.Client()

def extract_book_info(image_bytes: bytes) -> dict:
    try:
        # Load image without thumbnail restriction
        image = Image.open(io.BytesIO(image_bytes))

        # Standard prompt to extract book details
        prompt = "Extract the book title and author from this cover image. Return as a JSON object with keys 'title' and 'author'."

        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=[image, prompt]
        )
        
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        
        data = json.loads(raw_text.strip())
        title = data.get("title", "").strip()
        author = data.get("author", "").strip()
        
        # Check if the AI returned empty or unknown values and show as an error
        if not title or title.lower() == "unknown" or not author or author.lower() == "unknown":
            raise HTTPException(
                status_code=400, 
                detail="Could not clearly read book title or author from the image. Please try taking a clearer photo or enter details manually."
            )
        
        return {
            "status": "success",
            "title": title.title(),
            "author": author.title(),
            "source": "AI Cover Scan"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"AI Extraction Error: {e}")
        raise HTTPException(
            status_code=400, 
            detail="Failed to process book cover image. Please try again or use manual entry."
        )