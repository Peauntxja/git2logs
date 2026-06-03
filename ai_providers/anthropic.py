#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anthropic 提供商"""

from config import AIConfig
from ai_analysis import BaseAIService


class AnthropicService(BaseAIService):
    """Anthropic Claude AI服务"""

    def _get_default_model(self) -> str:
        return "claude-3-5-sonnet-20241022"

    def _make_api_call(self, prompt: str, system_message: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)

        message = client.messages.create(
            model=self.model,
            max_tokens=AIConfig.MAX_TOKENS,
            messages=[
                {"role": "user", "content": f"{system_message}\n\n{prompt}"}
            ],
        )

        if not message.content or len(message.content) == 0:
            raise ValueError("Anthropic API 返回空响应")

        return message.content[0].text

    def _handle_error(self, error: Exception) -> Exception:
        from anthropic import APIConnectionError, APIError, AuthenticationError, RateLimitError

        if isinstance(error, AuthenticationError):
            return ValueError(
                f"API密钥无效或已过期。请检查您的Anthropic API Key是否正确。错误详情: {str(error)}"
            )
        if isinstance(error, APIConnectionError):
            return ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {str(error)}")
        if isinstance(error, RateLimitError):
            return ValueError(f"API调用频率超限。请稍后重试。错误详情: {str(error)}")
        if isinstance(error, APIError):
            return ValueError(f"Anthropic API错误: {str(error)}")
        return super()._handle_error(error)
