import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
# from langchain.agents import create_agent


load_dotenv()


class LLMConfig:
    def __init__(self, openai_api_base: str | None = None, openai_api_key: str | None = None, model: str | None = None, temperature: float | None = None):
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self.temperature = temperature if temperature is not None else float(os.getenv("OPENAI_TEMPERATURE", "0"))
        self.openai_api_base = openai_api_base or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY") or "sk-xxx"

    def create_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            openai_api_base=self.openai_api_base,
            openai_api_key=self.openai_api_key,
        )