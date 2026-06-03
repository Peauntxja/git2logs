#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 提供商延迟加载注册测试。"""
from __future__ import annotations

import unittest

from tests import _common  # noqa: F401 — 确保项目根在 sys.path

from ai_analysis import AI_SERVICES, get_ai_service, _SERVICE_LOADERS


class AIProviderRegistryTests(unittest.TestCase):
    def setUp(self):
        AI_SERVICES.clear()

    def test_supported_providers_lazy_load(self):
        for name in _SERVICE_LOADERS:
            with self.subTest(provider=name):
                cls = get_ai_service(name)
                self.assertTrue(callable(cls))
                self.assertIn(name, AI_SERVICES)

    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError) as ctx:
            get_ai_service("unknown-vendor")
        self.assertIn("不支持的AI服务", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
