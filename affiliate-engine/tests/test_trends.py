"""Tests for the trends module."""

from pipeline.trends.seasonal import get_seasonal_keywords


class TestSeasonalKeywords:
    def test_returns_keywords_for_valid_month(self):
        keywords = get_seasonal_keywords(month=1)
        assert len(keywords) > 0
        assert all(kw.source == "seasonal_calendar" for kw in keywords)

    def test_returns_keywords_for_all_months(self):
        for month in range(1, 13):
            keywords = get_seasonal_keywords(month=month)
            assert len(keywords) > 0, f"No keywords for month {month}"

    def test_keyword_fields(self):
        keywords = get_seasonal_keywords(month=12)
        kw = keywords[0]
        assert kw.keyword
        assert kw.category
        assert kw.trend_score == 50.0

    def test_defaults_to_current_month(self):
        keywords = get_seasonal_keywords()
        assert len(keywords) > 0
