#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包（OpenAI 兼容）提供商"""

from typing import Optional

from ai_analysis import OpenAICompatibleService


class DoubaoService(OpenAICompatibleService):
    """豆包AI服务（兼容OpenAI API）"""

    def _get_default_model(self) -> str:
        return "doubao-pro-128k"

    def _get_base_url(self) -> Optional[str]:
        return "https://ark.cn-beijing.volces.com/api/v3"
