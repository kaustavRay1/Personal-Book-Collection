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
        # Load image and resize it to save visual tokens (covers don't need 4K resolution)
        image = Image.open(io.BytesIO(image_bytes))
        image.thumbnail((800, 800))

        # Ultra-short prompt to save input tokens
        prompt = 'Extract title and author. Return JSON only: {"title": "", "author": ""}'

        response = client.models.generate_content(
            model='gemini-3s.5-flash',
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                max_output_tokens=100,
                temperature=0.0
            )
        )
        
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        
        data = json.loads(raw_text.strip())
        title = data.get("title", "").strip()
        author = data.get("author", "").strip()
        
        # Check if the AI returned empty or unknown values
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