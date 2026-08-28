import os
import json
from google import genai
from google.genai import types
from PIL import Image
import io
from dotenv import load_dotenv

load_dotenv()

client = genai.Client()

def extract_book_info(image_bytes: bytes) -> dict:
    try:
        # Convert raw bytes into a PIL image for the model
        image = Image.open(io.BytesIO(image_bytes))

        # Ask Gemini to extract the book info and return strict JSON
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=[
                image,
                "Analyze this book cover image. Extract the book title and the author's name. Return ONLY a valid JSON object with the keys 'title' and 'author'. Do not include markdown formatting like ```json."
            ]
        )
        
        # Parse the JSON text returned by the AI
        raw_text = response.text.strip()
        # Clean up any accidental markdown blocks if the model includes them
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        
        data = json.loads(raw_text.strip())
        
        return {
            "title": data.get("title", "Unknown Title").title(),
            "author": data.get("author", "Unknown Author").title()
        }
    except Exception as e:
        print(f"AI Extraction Error: {e}")
        return {
            "title": "Unknown Title",
            "author": "Unknown Author"
        }