from .models import ProductRecommendation, LoyaltyTier

def calculate_loyalty_tier(lifetime_points: int) -> str:
    """Calculates customer loyalty tier based on cumulative lifetime points earned."""
    if lifetime_points >= 5000:
        return LoyaltyTier.PLATINUM
    elif lifetime_points >= 2000:
        return LoyaltyTier.GOLD
    elif lifetime_points >= 500:
        return LoyaltyTier.SILVER
    return LoyaltyTier.BRONZE

def evaluate_product_recommendations(store, source_variant_id):
    qs = ProductRecommendation.objects.filter(
        store=store,
        source_variant_id=source_variant_id
    ).select_related('recommended_variant__product')

    results = []
    for rec in qs:
        results.append({
            'recommendation_id': str(rec.id),
            'recommended_variant_id': str(rec.recommended_variant.id),
            'recommended_product_name': rec.recommended_variant.product.name,
            'recommended_sku': rec.recommended_variant.sku,
            'retail_price': str(rec.recommended_variant.retail_price),
            'recommendation_type': rec.recommendation_type,
            'discount_incentive_percent': rec.discount_incentive_percent
        })
    return results

