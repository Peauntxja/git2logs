#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DeepSeek（OpenAI 兼容）提供商"""

from typing import List, Optional

from ai_analysis import OpenAICompatibleService
from ai_providers.catalog import get_provider_default_model


class DeepSeekService(OpenAICompatibleService):
    """DeepSeek AI服务（兼容 OpenAI API）"""

    def _get_default_model(self) -> str:
        return get_provider_default_model("deepseek")

    def _get_provider_base_url(self) -> Optional[str]:
        return "https://api.deepseek.com"

    def _get_json_mode_models(self) -> List[str]:
        return ['deepseek-v4']

    def _extra_request_params(self) -> dict:
        # V4 默认开启 thinking；日报分析关闭以降低时延与费用
        return {"extra_body": {"thinking": {"type": "disabled"}}}
