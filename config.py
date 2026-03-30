"""設定管理モジュール"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Discord
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

    # LLM
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # TimeTree
    TIMETREE_EMAIL = os.getenv("TIMETREE_EMAIL")
    TIMETREE_PASSWORD = os.getenv("TIMETREE_PASSWORD")
    TIMETREE_CALENDAR_NAME = os.getenv("TIMETREE_CALENDAR_NAME", "My Calendar")

    # Selenium
    HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

    @classmethod
    def validate(cls):
        """必須設定の検証"""
        errors = []

        if not cls.DISCORD_BOT_TOKEN:
            errors.append("DISCORD_BOT_TOKEN is required")
        if cls.DISCORD_CHANNEL_ID == 0:
            errors.append("DISCORD_CHANNEL_ID is required")

        if cls.LLM_PROVIDER == "openai" and not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        if cls.LLM_PROVIDER == "anthropic" and not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")

        if not cls.TIMETREE_EMAIL or not cls.TIMETREE_PASSWORD:
            errors.append("TIMETREE_EMAIL and TIMETREE_PASSWORD are required")

        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"- {e}" for e in errors))

config = Config()
