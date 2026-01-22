from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import Response
import uvicorn
import os
from dotenv import load_dotenv
from datetime import datetime
import time
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

load_dotenv()

app = FastAPI()

# Twilio Client for background messages
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(account_sid, auth_token)

@app.get("/")
async def root():
    return {"status": "Vyapar AI is running"}

async def handle_background_logic(sender: str, body: str, media_url: str, media_type: str, start_time: float):
    """
    Handles AI processing and business logic in the background.
    """
    try:
        # 1. Process with AI Agent
        import agent
        ai_response = agent.process_request(text_input=body, media_url=media_url, media_type=media_type)
        
        intent = ai_response.get("intent")
        data = ai_response.get("data", {})
        reply_msg = ai_response.get("reply_text", "AI response failed.")
        
        # 2. Execute Business Logic
        final_reply = reply_msg
        
        if intent == "create_invoice":
            import invoice_generator
            pdf_path = invoice_generator.generate_invoice_pdf(data)
            
            total = 0
            for item in data.get("items", []):
                qty = item.get("quantity") or 0
                price = item.get("price") or 0
                total += qty * price
                
            import database
            db_msg = database.create_transaction(
                data.get("customer_name", "Unknown"), 
                data.get("items", []), 
                total, 
                pdf_path
            )
            final_reply = f"{reply_msg}\n{db_msg}\nInvoice saved at: {pdf_path}"
            
        elif intent == "add_inventory":
            import database
            msgs = []
            for item in data.get("items", []):
                msg = database.add_inventory(item.get("name"), item.get("quantity"), item.get("price", 0))
                msgs.append(msg)
            final_reply = f"{reply_msg}\n" + "\n".join(msgs)
            
        elif intent == "query_ledger":
            import database
            summary = database.get_ledger_summary()
            final_reply = f"{reply_msg}\n{summary}"

        # 3. Send Response back via Twilio REST API
        # Twilio sandbox requires the 'from' to be 'whatsapp:+14155238886' usually
        twilio_from = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
        
        twilio_client.messages.create(
            body=final_reply,
            from_=twilio_from,
            to=sender
        )
        
        duration = time.time() - start_time
        print(f"--- [{datetime.now().strftime('%H:%M:%S')}] Request Processed in {duration:.2f}s ---")
        print(f"Sent reply to {sender}\n")

    except Exception as e:
        print(f"Error in background task: {e}")

@app.post("/whatsapp")
async def whatsapp_webhook(background_tasks: BackgroundTasks, request: Request):
    """
    Webhook for Twilio WhatsApp.
    Responds immediately to avoid 15s timeout.
    """
    form_data = await request.form()
    sender = form_data.get("From")
    body = form_data.get("Body", "").strip()
    media_url = form_data.get("MediaUrl0")
    media_type = form_data.get("MediaContentType0")

    start_time = time.time()
    print(f"\n--- [{datetime.now().strftime('%H:%M:%S')}] Incoming WhatsApp Request ---")
    print(f"From: {sender}")
    
    # Run the expensive logic in the background
    background_tasks.add_task(handle_background_logic, sender, body, media_url, media_type, start_time)
    
    # Respond with empty TwiML to satisfy Twilio immediately
    return Response(content=str(MessagingResponse()), media_type="application/xml")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
