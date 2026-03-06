from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.chat_routes import router as chat_router
from app.mongo_client import MongoDBClient
from app.utils.request_tracker import tracker
from dotenv import load_dotenv

# ==========================
# Load Environment Variables
# ==========================
load_dotenv()

# ==========================
# FastAPI App
# ==========================
app = FastAPI(title="AI Chatbot with MongoDB")

# ==========================
# MongoDB Instance
# ==========================
mongo = MongoDBClient()

# ==========================
# Startup Event
# ==========================
@app.on_event("startup")
def startup_db():
    mongo.connect_with_retry()
    app.state.mongo = mongo

# ==========================
# Shutdown Event
# ==========================
@app.on_event("shutdown")
def shutdown_db():
    mongo.close()

# ==========================
# CORS Middleware
# Allow all origins
# ==========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# Routes
# ==========================
app.include_router(chat_router)

# ==========================
# Health Check / Root Route
# ==========================
@app.get("/")
def home():
    return {"message": "AI Chatbot Running 🚀"}