"""Seasonal keyword calendar for Japan.

Provides curated product keywords tied to Japanese seasons, events,
and shopping periods. These supplement Google Trends for consistent
coverage even when trending data is sparse.
"""

from __future__ import annotations

from datetime import datetime

from pipeline.models import TrendKeyword

# month -> list of (keyword, category)
_SEASONAL_MAP: dict[int, list[tuple[str, str]]] = {
    1: [
        ("福袋", "セール"),
        ("暖房器具 おすすめ", "家電"),
        ("加湿器 比較", "家電"),
        ("新年 ガジェット", "ガジェット"),
    ],
    2: [
        ("バレンタイン ギフト", "ギフト"),
        ("花粉対策 グッズ", "健康グッズ"),
        ("空気清浄機 比較", "家電"),
    ],
    3: [
        ("新生活 家電", "家電"),
        ("引越し 必需品", "生活用品"),
        ("入学祝い プレゼント", "ギフト"),
        ("花粉症 対策", "健康グッズ"),
    ],
    4: [
        ("新生活 おすすめ", "生活用品"),
        ("GW 旅行グッズ", "アウトドア"),
        ("UV対策 グッズ", "美容"),
    ],
    5: [
        ("母の日 プレゼント", "ギフト"),
        ("梅雨対策 グッズ", "生活用品"),
        ("除湿機 おすすめ", "家電"),
    ],
    6: [
        ("父の日 ギフト", "ギフト"),
        ("除湿機 比較", "家電"),
        ("扇風機 おすすめ", "家電"),
        ("Amazon プライムデー", "セール"),
    ],
    7: [
        ("夏 ガジェット", "ガジェット"),
        ("ポータブル扇風機 比較", "家電"),
        ("冷感グッズ おすすめ", "生活用品"),
        ("夏休み 自由研究", "文房具"),
    ],
    8: [
        ("夏 家電 セール", "家電"),
        ("防災グッズ おすすめ", "生活用品"),
        ("アウトドア用品 比較", "アウトドア"),
    ],
    9: [
        ("敬老の日 プレゼント", "ギフト"),
        ("秋 新製品 ガジェット", "ガジェット"),
        ("運動会 カメラ おすすめ", "ガジェット"),
    ],
    10: [
        ("ハロウィン グッズ", "イベント"),
        ("暖房器具 早割", "家電"),
        ("加湿器 おすすめ", "家電"),
    ],
    11: [
        ("ブラックフライデー おすすめ", "セール"),
        ("クリスマス プレゼント", "ギフト"),
        ("年末 大掃除 家電", "家電"),
    ],
    12: [
        ("クリスマス ギフト", "ギフト"),
        ("年末セール 家電", "セール"),
        ("お歳暮 おすすめ", "ギフト"),
        ("ふるさと納税 おすすめ", "生活用品"),
    ],
}


def get_seasonal_keywords(
    month: int | None = None,
) -> list[TrendKeyword]:
    """Return seasonal keywords for the given month (defaults to current)."""
    target_month = month or datetime.now().month
    entries = _SEASONAL_MAP.get(target_month, [])

    return [
        TrendKeyword(
            keyword=kw,
            category=cat,
            trend_score=50.0,
            source="seasonal_calendar",
            discovered_at=datetime.now(),
        )
        for kw, cat in entries
    ]
