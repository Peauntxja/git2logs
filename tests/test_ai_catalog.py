#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 厂商模型目录与默认模型一致性测试。"""
from __future__ import annotations

import unittest

from tests import _common  # noqa: F401

from ai_analysis import _SERVICE_LOADERS
from ai_providers.catalog import (
    PROVIDER_DEFAULT_MODEL,
    PROVIDER_MODELS,
    get_provider_default_model,
    get_provider_models,
)


class AICatalogTests(unittest.TestCase):
    def test_catalog_covers_all_registered_providers(self):
        self.assertEqual(set(PROVIDER_MODELS.keys()), set(_SERVICE_LOADERS.keys()))
        self.assertEqual(set(PROVIDER_DEFAULT_MODEL.keys()), set(_SERVICE_LOADERS.keys()))

    def test_default_model_in_options(self):
        for service in _SERVICE_LOADERS:
            with self.subTest(provider=service):
                default = get_provider_default_model(service)
                options = get_provider_models(service)
                self.assertIn(default, options)

    def test_unknown_service_falls_back_to_openai(self):
        self.assertEqual(get_provider_default_model("unknown"), "gpt-5.6-luna")
        self.assertTrue(len(get_provider_models("unknown")) > 0)


if __name__ == "__main__":
    unittest.main()
