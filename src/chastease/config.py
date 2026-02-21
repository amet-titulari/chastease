import os


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/chastease.db")
