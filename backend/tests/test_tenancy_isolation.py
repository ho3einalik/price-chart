import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role
from apps.catalog.models import Product, ProductVariant

@pytest.mark.django_db
def test_tenant_isolation_products():
    """Verify that User from Store A cannot see or access Store B's products"""
    user_a = User.objects.create_user(email="user_a@example.com", password="password123", full_name="User A")
    biz_a = Business.objects.create(name="Business A", owner=user_a)
    store_a = Store.objects.create(business=biz_a, name="Store A")
    StoreMembership.objects.create(store=store_a, user=user_a, role=Role.OWNER)

    user_b = User.objects.create_user(email="user_b@example.com", password="password123", full_name="User B")
    biz_b = Business.objects.create(name="Business B", owner=user_b)
    store_b = Store.objects.create(business=biz_b, name="Store B")
    StoreMembership.objects.create(store=store_b, user=user_b, role=Role.OWNER)

    # Product in Store B
    product_b = Product.objects.create(store=store_b, name="Secret Product B")
    variant_b = ProductVariant.objects.create(
        store=store_b,
        product=product_b,
        name="Variant B",
        sku="SKU-B",
        cost_price=Decimal('1000'),
        retail_price=Decimal('2000')
    )

    client = APIClient()
    client.force_authenticate(user=user_a)

    # User A requests products with their active store Store A
    client.credentials(HTTP_X_STORE_ID=str(store_a.id))
    response = client.get('/api/v1/catalog/products/')
    assert response.status_code == 200
    assert response.data['count'] == 0

    # User A attempts to tamper with X-Store-Id header targeting Store B
    client.credentials(HTTP_X_STORE_ID=str(store_b.id))
    response_tampered = client.get('/api/v1/catalog/products/')
    # Because User A has NO membership in Store B, middleware strips request.store and permission rejects
    assert response_tampered.status_code in [403, 200]
    if response_tampered.status_code == 200:
        # Must return empty results
        assert response_tampered.data['count'] == 0
