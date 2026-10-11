from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from apps.tenancy.permissions import IsStoreMemberPermission, TenantFilterBackend
from .models import Category, Product, ProductVariant
from .serializers import (
    CategorySerializer, ProductDetailSerializer, ProductCreateUpdateSerializer, ProductVariantSerializer
)

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, filters.SearchFilter]
    search_fields = ['name']
    queryset = Category.objects.all()

class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category']
    search_fields = ['name', 'brand', 'variants__sku', 'variants__barcode']
    ordering_fields = ['created_at', 'name']
    queryset = Product.objects.all().prefetch_related('variants', 'images')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

class ProductVariantViewSet(viewsets.ModelViewSet):
    serializer_class = ProductVariantSerializer
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'sku', 'barcode', 'product__name']
    queryset = ProductVariant.objects.all().select_related('product')
