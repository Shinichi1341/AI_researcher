"""Tests for product scoring."""

from pipeline.models import Product
from pipeline.products.scorer import score_and_rank, score_product


class TestScorer:
    def test_score_product_returns_valid_score(self, sample_products: list[Product]):
        score = score_product(sample_products[0], sample_products)
        assert 0.0 <= score.total_score <= 1.0
        assert score.product_id == "amazon_B001"
        assert len(score.breakdown) == 5

    def test_all_dimensions_present(self, sample_products: list[Product]):
        score = score_product(sample_products[0], sample_products)
        dims = {b.dimension for b in score.breakdown}
        assert dims == {
            "price_competitiveness",
            "review_rating",
            "review_volume",
            "spec_richness",
            "cross_platform",
        }

    def test_normalized_values_in_range(self, sample_products: list[Product]):
        score = score_product(sample_products[0], sample_products)
        for b in score.breakdown:
            assert 0.0 <= b.normalized <= 1.0, f"{b.dimension}: {b.normalized}"

    def test_score_and_rank_assigns_ranks(self, sample_products: list[Product]):
        scores = score_and_rank(sample_products)
        assert len(scores) == 3
        ranks = [s.rank for s in scores]
        assert ranks == [1, 2, 3]
        # First rank should have highest score
        assert scores[0].total_score >= scores[1].total_score
        assert scores[1].total_score >= scores[2].total_score

    def test_cheapest_product_has_best_price_score(self, sample_products: list[Product]):
        scores = score_and_rank(sample_products)
        # rakuten_R002 is cheapest at 6480
        cheapest_score = next(s for s in scores if s.product_id == "rakuten_R002")
        price_dim = next(b for b in cheapest_score.breakdown if b.dimension == "price_competitiveness")
        assert price_dim.normalized == 1.0

    def test_empty_products(self):
        scores = score_and_rank([])
        assert scores == []
