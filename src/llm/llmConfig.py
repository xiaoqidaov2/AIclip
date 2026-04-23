import os


from dotenv import load_dotenv


from langchain_openai import ChatOpenAI
from pydantic import SecretStr

# from langchain.agents import create_agent


load_dotenv()


class LLMConfig:

    def __init__(
        self,
        openai_api_base: str | None = None,
        openai_api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ):

        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

        self.temperature = (
            temperature
            if temperature is not None
            else float(os.getenv("OPENAI_TEMPERATURE", "0"))
        )

        self.openai_api_base = (
            openai_api_base
            or os.getenv("OPENAI_API_BASE")
            or "https://api.openai.com/v1"
        )

        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        self.request_timeout = float(os.getenv("OPENAI_REQUEST_TIMEOUT", "120"))

        if not self.openai_api_key:

            raise ValueError("OPENAI_API_KEY not configured")

    def create_llm(self) -> ChatOpenAI:

        api_key = self.openai_api_key

        if api_key is None:

            raise ValueError("OPENAI_API_KEY not configured")

        return ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            base_url=self.openai_api_base,
            api_key=SecretStr(api_key),
            max_retries=5,
            request_timeout=self.request_timeout,
        )
