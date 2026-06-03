#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包（OpenAI 兼容）提供商"""

from typing import List, Optional

from ai_analysis import OpenAICompatibleService
from ai_providers.catalog import get_provider_default_model


class DoubaoService(OpenAICompatibleService):
    """豆包AI服务（火山方舟 OpenAI 兼容 API）"""

    def _get_default_model(self) -> str:
        return get_provider_default_model("doubao")

    def _get_provider_base_url(self) -> Optional[str]:
        return "https://ark.cn-beijing.volces.com/api/v3"

    def _get_json_mode_models(self) -> List[str]:
        return ['doubao-seed-2.0', 'doubao-seed-1.8', 'doubao-pro']
