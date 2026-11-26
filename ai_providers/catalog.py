#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""各 AI 厂商默认模型与可选模型列表（与官方 API 文档对齐，供 GUI 与提供商共用）。"""

from __future__ import annotations

from typing import Dict, List

# service 键与 ai_analysis._SERVICE_LOADERS 一致
PROVIDER_MODELS: Dict[str, List[str]] = {
    "openai": [
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-5.6-sol",
        "gpt-5.6",
        "gpt-5.4-mini",
        "gpt-5.4",
        "gpt-5.4-nano",
        "gpt-5.2",
        "gpt-5-mini",
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-4o-mini",
        "gpt-4o",
    ],
    "anthropic": [
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
        "claude-opus-5-5",
        "claude-fable-5-2",
        "claude-sonnet-5",
        "claude-opus-5",
    ],
    "gemini": [
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-pro-preview",
    ],
    "doubao": [
        "doubao-seed-2-1-lite-260915",
        "doubao-seed-2-1-pro-260915",
        "doubao-seed-evolving",
        "doubao-seed-2-1-turbo-260628",
        "doubao-seed-2-0-lite-260428",
        "doubao-seed-2-0-mini-260428",
    ],
    "deepseek": [
        "deepseek-flash",
        "deepseek-v4-pro",
    ],
}

PROVIDER_DEFAULT_MODEL: Dict[str, str] = {
    "openai": "gpt-5.6-luna",
    "anthropic": "claude-sonnet-5-5",
    "gemini": "gemini-3.8-flash",
    "doubao": "doubao-seed-2-1-lite-260915",
    "deepseek": "deepseek-flash",
}


def get_provider_models(service: str) -> List[str]:
    key = (service or "openai").lower()
    return list(PROVIDER_MODELS.get(key, PROVIDER_MODELS["openai"]))


def get_provider_default_model(service: str) -> str:
    key = (service or "openai").lower()
    return PROVIDER_DEFAULT_MODEL.get(key, PROVIDER_DEFAULT_MODEL["openai"])
