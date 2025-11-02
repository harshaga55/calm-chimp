from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass
class AzureOpenAISettings:
    endpoint: Optional[str]
    api_key: Optional[str]
    deployment: Optional[str]
    api_version: str

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.deployment)


@dataclass
class AppSettings:
    azure_openai: AzureOpenAISettings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    azure = AzureOpenAISettings(
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
    )
    return AppSettings(azure_openai=azure)
