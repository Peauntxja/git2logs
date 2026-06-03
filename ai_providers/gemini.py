#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Gemini 提供商（Google GenAI SDK）"""

from config import AIConfig
from ai_analysis import BaseAIService
from ai_providers.catalog import get_provider_default_model


class GeminiService(BaseAIService):
    """Google Gemini AI服务"""

    def _get_default_model(self) -> str:
        return get_provider_default_model("gemini")

    def _make_api_call(self, prompt: str, system_message: str) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_message,
                temperature=AIConfig.TEMPERATURE,
                max_output_tokens=AIConfig.MAX_TOKENS,
                top_p=AIConfig.TOP_P,
            ),
        )

        text = getattr(response, "text", None)
        if not text and getattr(response, "candidates", None):
            parts = response.candidates[0].content.parts
            text = "".join(getattr(p, "text", "") or "" for p in parts)

        if not text:
            raise ValueError("Gemini API 返回空响应")

        return text

    def _handle_error(self, error: Exception) -> Exception:
        error_msg = str(error)
        error_type_name = type(error).__name__

        actual_error = error
        if hasattr(error, '__cause__') and error.__cause__:
            actual_error = error.__cause__
        elif hasattr(error, 'exception') and error.exception:
            actual_error = error.exception

        actual_error_msg = str(actual_error)
        combined_msg = (
            f"{error_msg} (内部错误: {actual_error_msg})"
            if actual_error_msg != error_msg
            else error_msg
        )

        try:
            from google.genai import errors as genai_errors
        except ImportError:
            genai_errors = None

        if genai_errors and isinstance(error, genai_errors.APIError):
            status = getattr(error, "code", None) or getattr(error, "status_code", None)
            if status in (401, 403):
                return ValueError(
                    "API密钥无效或已过期。请检查您的 Google Gemini API Key 是否正确。"
                    f"错误详情: {combined_msg}"
                )
            if status == 429:
                suggestion = ""
                if "pro" in self.model.lower():
                    suggestion = (
                        "\n提示: Pro 模型可能需要付费配额，可尝试 gemini-2.5-flash。"
                    )
                return ValueError(
                    f"API调用频率超限或配额已用完。请稍后重试或检查您的API配额。{suggestion}"
                    f"错误详情: {combined_msg}"
                )
            if status in (500, 503):
                return ConnectionError(
                    "网络连接失败或服务暂时不可用。请检查网络或稍后重试。"
                    f"错误详情: {combined_msg}"
                )

        if (
            "401" in error_msg
            or "unauthorized" in error_msg.lower()
            or "invalid" in error_msg.lower()
            or "API key" in error_msg
            or "authentication" in error_msg.lower()
        ):
            return ValueError(
                "API密钥无效或已过期。请检查您的 Google Gemini API Key 是否正确。"
                f"错误详情: {combined_msg}"
            )

        is_network_error = (
            "RetryError" in error_type_name
            or "503" in error_msg
            or "service unavailable" in error_msg.lower()
            or "failed to connect" in error_msg.lower()
            or "connection" in error_msg.lower()
            or "network" in error_msg.lower()
            or "timeout" in error_msg.lower()
            or "unavailable" in error_msg.lower()
            or "unreachable" in error_msg.lower()
            or "getsockopt" in error_msg.lower()
        )

        if is_network_error:
            return ConnectionError(
                "网络连接失败。无法连接到 Google Gemini 服务。"
                f"错误详情: {combined_msg}"
            )

        if (
            "quota" in error_msg.lower()
            or "rate limit" in error_msg.lower()
            or "配额" in error_msg
            or "quota exceeded" in error_msg.lower()
            or "resource_exhausted" in error_msg.lower()
        ):
            suggestion = ""
            if "pro" in self.model.lower():
                suggestion = (
                    "\n提示: 该模型可能需要付费配额，建议尝试 gemini-2.5-flash。"
                )
            return ValueError(
                f"API调用频率超限或配额已用完。请稍后重试或检查您的API配额。{suggestion}"
                f"错误详情: {combined_msg}"
            )

        return ValueError(f"Google Gemini API调用失败: {combined_msg}")
