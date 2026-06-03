#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Gemini 提供商"""

from ai_analysis import BaseAIService


class GeminiService(BaseAIService):
    """Google Gemini AI服务"""

    def _get_default_model(self) -> str:
        return "gemini-3-flash-preview"

    def _make_api_call(self, prompt: str, system_message: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        full_prompt = f"{system_message}\n\n{prompt}"
        model_instance = genai.GenerativeModel(self.model)
        response = model_instance.generate_content(full_prompt)

        if not response.text:
            raise ValueError("Gemini API 返回空响应")

        return response.text

    def _handle_error(self, error: Exception) -> Exception:
        import google.api_core.exceptions as google_exceptions

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

        if (
            isinstance(actual_error, google_exceptions.Unauthenticated)
            or isinstance(error, google_exceptions.Unauthenticated)
            or "401" in error_msg
            or "unauthorized" in error_msg.lower()
            or "invalid" in error_msg.lower()
            or "API key" in error_msg
            or "authentication" in error_msg.lower()
        ):
            return ValueError(
                f"API密钥无效或已过期。请检查您的Google Gemini API Key是否正确。"
                f"错误详情: {combined_msg}"
            )

        is_retry_error = (
            isinstance(error, google_exceptions.RetryError)
            or "RetryError" in error_type_name
        )
        is_network_error = (
            isinstance(
                actual_error,
                (google_exceptions.ServiceUnavailable, google_exceptions.DeadlineExceeded),
            )
            or isinstance(
                error,
                (google_exceptions.ServiceUnavailable, google_exceptions.DeadlineExceeded),
            )
            or is_retry_error
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
                "网络连接失败。无法连接到Google Gemini服务，可能是网络问题、"
                f"防火墙限制或服务暂时不可用。错误详情: {combined_msg}"
            )

        if (
            isinstance(actual_error, google_exceptions.ResourceExhausted)
            or isinstance(error, google_exceptions.ResourceExhausted)
            or "quota" in error_msg.lower()
            or "rate limit" in error_msg.lower()
            or "配额" in error_msg
            or "quota exceeded" in error_msg.lower()
        ):
            suggestion = ""
            if "gemini-2.5-pro" in self.model or "gemini-3-pro" in self.model:
                suggestion = (
                    "\n提示: 该模型可能需要付费配额。建议尝试使用 gemini-3-flash-preview"
                    "（有免费层级）或 gemini-2.5-flash。"
                )
            return ValueError(
                f"API调用频率超限或配额已用完。请稍后重试或检查您的API配额。{suggestion}"
                f"错误详情: {combined_msg}"
            )

        return ValueError(f"Google Gemini API调用失败: {combined_msg}")
