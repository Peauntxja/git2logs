#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告文本归一化：抹掉时间戳等非确定性字段，便于 golden 对比。"""

import re


def normalize_report_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n")
    text = re.sub(
        r"\*\*生成时间\*\*:.*\n",
        "**生成时间**: <NORMALIZED>\n",
        text,
    )
    text = re.sub(
        r"\*\*日期\*\*:.*\n",
        "**日期**: <NORMALIZED>\n",
        text,
        count=1,
    )
    return text.strip() + "\n"
