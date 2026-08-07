#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI 提供商"""

from typing import List

from config import AIConfig
from ai_analysis import OpenAICompatibleService
from ai_providers.catalog import get_provider_default_model


class OpenAIService(OpenAICompatibleService):
    """OpenAI AI服务"""

    def _get_default_model(self) -> str:
        return get_provider_default_model("openai")

    def _build_token_params(self) -> dict:
        # GPT-5 / o 系列不兼容 max_tokens，需用 max_completion_tokens
        model = (self.model or "").lower()
        if model.startswith(("gpt-5", "o1", "o3", "o4")):
            return {"max_completion_tokens": AIConfig.MAX_TOKENS}
        return {"max_tokens": AIConfig.MAX_TOKENS}

    def _get_json_mode_models(self) -> List[str]:
        return [
            'gpt-4o', 'gpt-4.1', 'gpt-5', 'gpt-5.6', 'gpt-5.4', 'gpt-5.2',
            'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo',
        ]
