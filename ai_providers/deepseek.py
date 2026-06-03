#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DeepSeek（OpenAI 兼容）提供商"""

from typing import Optional

from ai_analysis import OpenAICompatibleService


class DeepSeekService(OpenAICompatibleService):
    """DeepSeek AI服务（兼容OpenAI API）"""

    def _get_default_model(self) -> str:
        return "deepseek-chat"

    def _get_base_url(self) -> Optional[str]:
        return "https://api.deepseek.com/v1"
