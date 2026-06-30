import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

    DATABASE_URL = os.getenv("DATABASE_URL")
