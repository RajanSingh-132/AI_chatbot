from fastapi import APIRouter, HTTPException
from prompt import format_response
from services.ai_services import generate_ai_response
from utils.request_tracker import tracker
from services.conversationsSaver import save_chat, get_chat_history

router = APIRouter()

tracker.api_hit()

@router.post("/chat")
async def chat(data: dict):

    print("Request received")

    user_message = data.get("message")
    user_id = "user1"

    print("Message:", user_message)

    history = get_chat_history(user_id)

    print("History loaded")

    ai_text = generate_ai_response(user_id, user_message, history)

    print("AI generated")

    save_chat(user_id, user_message, ai_text)

    print("Saved to DB")

    return {"response": ai_text}