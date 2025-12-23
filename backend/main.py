from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routers import chat

# Khởi tạo FastAPI app
app = FastAPI(title="ERP Chatbot API", version="1.0.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, tags=["Chat"])

# Health check endpoint
@app.get("/")
def home():
    return {"message": "Server Chatbot đang chạy ngon lành!", "version": "1.0.0"}

