from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass
class AzureOpenAISettings:
    endpoint: Optional[str]
    api_key: Optional[str]
    deployment: Optional[str]
    api_version: Optional[str]

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.deployment and self.api_version)

    @property
    def missing_env_vars(self) -> List[str]:
        missing = []
        if not self.endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if not self.deployment:
            missing.append("AZURE_OPENAI_DEPLOYMENT")
        if not self.api_version:
            missing.append("AZURE_OPENAI_API_VERSION")
        return missing


@dataclass
class AppSettings:
    azure_openai: AzureOpenAISettings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    azure = AzureOpenAISettings(
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )
    return AppSettings(azure_openai=azure)
