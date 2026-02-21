import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
