#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""各 AI 厂商默认模型与可选模型列表（与官方 API 文档对齐，供 GUI 与提供商共用）。"""

from __future__ import annotations

from typing import Dict, List

# service 键与 ai_analysis._SERVICE_LOADERS 一致
PROVIDER_MODELS: Dict[str, List[str]] = {
    "openai": [
        "gpt-5.4-mini",
        "gpt-5.4",
        "gpt-5.4-nano",
        "gpt-5.2",
        "gpt-5-mini",
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo",
    ],
    "anthropic": [
        "claude-sonnet-4-6",
        "claude-sonnet-4-5",
        "claude-opus-4-6",
        "claude-opus-4-7",
        "claude-haiku-4-5",
        "claude-3-5-sonnet-20241022",
    ],
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        "gemini-2.5",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ],
    "doubao": [
        "doubao-seed-2.0-lite",
        "doubao-seed-2.0-pro",
        "doubao-seed-2.0-mini",
        "doubao-seed-2.0-code",
        "doubao-seed-1.8",
        "doubao-pro-128k",
        "doubao-lite-128k",
    ],
    "deepseek": [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "deepseek-chat",
        "deepseek-reasoner",
        "deepseek-coder",
    ],
}

PROVIDER_DEFAULT_MODEL: Dict[str, str] = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
    "doubao": "doubao-seed-2.0-lite",
    "deepseek": "deepseek-v4-flash",
}


def get_provider_models(service: str) -> List[str]:
    key = (service or "openai").lower()
    return list(PROVIDER_MODELS.get(key, PROVIDER_MODELS["openai"]))


def get_provider_default_model(service: str) -> str:
    key = (service or "openai").lower()
    return PROVIDER_DEFAULT_MODEL.get(key, PROVIDER_DEFAULT_MODEL["openai"])
