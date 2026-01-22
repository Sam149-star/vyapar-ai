import os
import google.generativeai as genai
import requests
from dotenv import load_dotenv
import json
import time
from datetime import datetime

load_dotenv()

# Configure Gemini
GENAI_API_KEY = os.getenv("GENAI_API_KEY")
if not GENAI_API_KEY:
    print("Error: GENAI_API_KEY not found in .env")

genai.configure(api_key=GENAI_API_KEY, transport='rest')

# Generation Config to force JSON response
generation_config = {
    "temperature": 0.4,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

def download_media(media_url):
    """
    Downloads media from Twilio URL.
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Downloading media from {media_url}...")
    try:
        # Try without auth first
        response = requests.get(media_url, timeout=10)
        if response.status_code != 200:
            sid = os.getenv("TWILIO_ACCOUNT_SID")
            token = os.getenv("TWILIO_AUTH_TOKEN")
            if sid and token:
                response = requests.get(media_url, auth=(sid, token), timeout=10)
        
        if response.status_code == 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Download successful.")
            return response.content
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Failed to download: {response.status_code}")
            return None
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Download error: {e}")
        return None

def upload_to_gemini(file_bytes, mime_type="audio/ogg"):
    """
    Uploads file bytes to Gemini File API.
    """
    # Save to temp file first (Gemini SDK likes paths or file-like objects)
    temp_filename = f"temp_{int(time.time())}.bin"
    with open(temp_filename, "wb") as f:
        f.write(file_bytes)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Uploading to Gemini (MIME: {mime_type})...")
    clean_mime = mime_type.split(";")[0].strip()
    
    try:
        myfile = genai.upload_file(temp_filename, mime_type=clean_mime)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Upload initiated: {myfile.name}")
        
        # Check if the file is ready
        while myfile.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(1) # Faster poll
            myfile = genai.get_file(myfile.name)
        
        if myfile.state.name == "FAILED":
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Gemini file state FAILED: {myfile.state}")
            raise Exception("Gemini file processing failed.")

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] File {myfile.name} is {myfile.state.name}")
        
        if myfile.state.name == "FAILED":
            print(f"Gemini file state FAILED: {myfile.state}")
            raise Exception("Gemini file processing failed.")

        print(f"\nFile {myfile.name} is now {myfile.state.name}")
        
        # Cleanup local file
        os.remove(temp_filename)
        return myfile
    except Exception as e:
        print(f"Gemini Upload Error: {e}")
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return None

def process_request(text_input=None, media_url=None, media_type=None):
    """
    Main entry point.
    Determines intent and extracts data using Gemini.
    Returns: JSON object with 'intent' and 'data'.
    """
    prompt_text = """
    You are an ERP Assistant for a small Indian business shopkeeper.
    Your job is to extract structured data from the user's input (Text, Audio, or Image).

    POSSIBLE INTENTS:
    1. "create_invoice": User is selling something. Extract customer name, items (name, quantity, price), and total.
    2. "add_inventory": User is buying stock or counting stock. Extract items and quantities.
    3. "query_ledger": User is asking a question about sales, stock, or balance.

    OUTPUT FORMAT (JSON):
    {
      "intent": "create_invoice" | "add_inventory" | "query_ledger" | "unknown",
      "data": {
        "customer_name": "string (or null)",
        "items": [{"name": "string", "quantity": number, "price": number or null}],
        "query_text": "string (for query_ledger)"
      },
      "reply_text": "A specialized, short, friendly Hinglish response acknowledging the action. If a price is missing, politely ask for it."
    }
    
    Start now. Output ONLY a valid JSON object. No other text.
    """

    content_parts = [prompt_text]

    if text_input:
        content_parts.append(f"User Text Input: {text_input}")
    
    if media_url:
        print(f"Detected media URL: {media_url} (Type: {media_type})")
        file_bytes = download_media(media_url)
        if file_bytes:
            print(f"Downloaded {len(file_bytes)} bytes.")
            gemini_file = upload_to_gemini(file_bytes, mime_type=media_type)
            if gemini_file:
                content_parts.append(gemini_file)
                print("Added media to Gemini payload.")
            else:
                print("Failed to upload/ready media to Gemini.")
                return {"intent": "error", "reply_text": "Audio processing failed at upload."}
        else:
            print("Failed to download media bytes.")
            return {"intent": "error", "reply_text": "Failed to download media."}

    print("Sending to Gemini...")
    try:
        response = model.generate_content(content_parts)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "").strip()
        print("Gemini Response:", cleaned_text)
        return json.loads(cleaned_text)
    except Exception as e:
        import traceback
        print(f"Gemini/JSON Error: {e}")
        traceback.print_exc()
        return {"intent": "error", "reply_text": "AI processing failed."}
