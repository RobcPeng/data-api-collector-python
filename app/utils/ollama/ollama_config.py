from openai import OpenAI
from app.core.config import settings

client = OpenAI(
    base_url=settings.OLLAMA_BASE_URL,
    api_key="---"
)

model: str = "gpt-oss:20b"