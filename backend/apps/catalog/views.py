import io
import csv
from decimal import Decimal
from django.db import transaction, models
from django.http import HttpResponse
from django.utils.text import slugify
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.tenancy.permissions import IsStoreMemberPermission, TenantFilterBackend
from apps.inventory.models import Warehouse
from apps.inventory.services import adjust_stock
from apps.features.services import FeatureService

from .models import Category, Product, ProductVariant, ProductPriceHistory
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
    ProductVariantSerializer,
    ProductPriceHistorySerializer,
    BulkUpdateSerializer,
)


def sanitize_csv_cell(value):
    """Prevents CSV formula injection for spreadsheet applications like Excel/LibreOffice"""
    if value is None:
        return ""
    val_str = str(value)
    if val_str and val_str[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{val_str}"
    return val_str


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

    def perform_create(self, serializer):
        store = self.request.store
        FeatureService.enforce_plan_quota(store, 'products')
        serializer.save()

    @action(detail=False, methods=['post'], url_path='bulk-update')
    @transaction.atomic
    def bulk_update(self, request):
        serializer = BulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = request.store
        items = serializer.validated_data['items']

        # Phase 1: Full validation of all rows before applying any mutations
        row_errors = []
        resolved_items = []

        for idx, item in enumerate(items):
            row_num = idx + 1
            variant_id = item.get('variant_id')
            sku = item.get('sku')
            product_id = item.get('product_id')

            variant = None
            product = None

            if variant_id:
                variant = ProductVariant.objects.filter(id=variant_id, store=store).first()
            elif sku:
                variant = ProductVariant.objects.filter(sku__iexact=sku.strip(), store=store).first()

            if product_id:
                product = Product.objects.filter(id=product_id, store=store).first()
            elif variant:
                product = variant.product

            if not variant and not product:
                row_errors.append({
                    'row': row_num,
                    'error': f"ردیف {row_num}: تنوع یا محصول با شناسه یا کد SKU ارائه شده در این فروشگاه یافت نشد."
                })
                continue

            # Validate prices if provided
            for price_field in ['retail_price', 'cost_price', 'wholesale_price']:
                val = item.get(price_field)
                if val is not None and val < 0:
                    row_errors.append({
                        'row': row_num,
                        'error': f"ردیف {row_num}: فیلد '{price_field}' نمی‌تواند منفی باشد."
                    })

            # Validate stock quantity and warehouse if provided
            target_wh = None
            if 'stock_quantity' in item and item['stock_quantity'] is not None:
                stock_qty = item['stock_quantity']
                if stock_qty < 0:
                    row_errors.append({
                        'row': row_num,
                        'error': f"ردیف {row_num}: موجودی انبار نمی‌تواند منفی باشد."
                    })

                wh_id = item.get('warehouse_id')
                if wh_id:
                    target_wh = Warehouse.objects.filter(id=wh_id, store=store).first()
                    if not target_wh:
                        row_errors.append({
                            'row': row_num,
                            'error': f"ردیف {row_num}: انبار مشخص‌شده با شناسه '{wh_id}' در این فروشگاه وجود ندارد."
                        })

            resolved_items.append({
                'item': item,
                'variant': variant,
                'product': product,
                'target_wh': target_wh
            })

        # If any row is invalid, abort immediately with 400 and full row error breakdown (strict atomicity)
        if row_errors:
            transaction.set_rollback(True)
            return Response({
                'message': 'اعتبارسنجی ردیف‌ها با خطا مواجه شد و به دلیل رعایت اتمیک بودن، هیچ تغییری در داده‌ها اعمال نگردید.',
                'errors': row_errors,
                'total_rows': len(items),
                'failed_rows_count': len(row_errors)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Phase 2: Execute all updates atomically
        updated_variants = 0
        updated_products = 0
        default_warehouse = None

        for entry in resolved_items:
            item = entry['item']
            variant = entry['variant']
            product = entry['product']
            target_wh = entry['target_wh']

            # Update product attributes
            if product and 'status' in item:
                product.status = item['status']
                product.save(update_fields=['status', 'updated_at'])
                updated_products += 1

            # Update variant attributes
            if variant:
                v_changed = False
                old_retail = variant.retail_price
                old_cost = variant.cost_price

                if 'retail_price' in item and item['retail_price'] is not None:
                    variant.retail_price = item['retail_price']
                    v_changed = True
                if 'cost_price' in item and item['cost_price'] is not None:
                    variant.cost_price = item['cost_price']
                    v_changed = True
                if 'wholesale_price' in item and item['wholesale_price'] is not None:
                    variant.wholesale_price = item['wholesale_price']
                    v_changed = True
                if 'is_active' in item and item['is_active'] is not None:
                    variant.is_active = item['is_active']
                    v_changed = True

                if v_changed:
                    variant.save()
                    updated_variants += 1

                    if variant.retail_price != old_retail or variant.cost_price != old_cost:
                        ProductPriceHistory.objects.create(
                            store=store,
                            variant=variant,
                            old_retail_price=old_retail,
                            new_retail_price=variant.retail_price,
                            old_cost_price=old_cost,
                            new_cost_price=variant.cost_price,
                            reason=item.get('reason', 'بروزرسانی گروهی قیمت'),
                            changed_by=request.user if request.user.is_authenticated else None
                        )

                if 'stock_quantity' in item and item['stock_quantity'] is not None:
                    if not target_wh:
                        if not default_warehouse:
                            default_warehouse = Warehouse.objects.filter(store=store, is_active=True).first()
                            if not default_warehouse:
                                default_warehouse = Warehouse.objects.create(store=store, name="انبار اصلی", is_default=True)
                        target_wh = default_warehouse

                    adjust_stock(
                        store=store,
                        warehouse=target_wh,
                        variant=variant,
                        new_on_hand=item['stock_quantity'],
                        reason=item.get('reason', 'تعدیل موجودی در بروزرسانی گروهی'),
                        user=request.user
                    )

        return Response({
            'message': 'عملیات بروزرسانی گروهی با موفقیت و به‌صورت اتمیک انجام شد.',
            'updated_variants': updated_variants,
            'updated_products': updated_products,
            'errors': []
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        store = request.store
        output = io.StringIO()
        # UTF-8 BOM for Microsoft Excel on Windows Persian locale
        output.write('\ufeff')
        writer = csv.writer(output)

        headers = [
            'شناسه محصول',
            'نام محصول',
            'برند',
            'دسته‌بندی',
            'وضعیت کاتالوگ',
            'شناسه تنوع',
            'کد تنوع (SKU)',
            'بارکد',
            'نام تنوع',
            'قیمت فروش (تومان)',
            'قیمت خرید (تومان)',
            'قیمت عمده (تومان)',
            'نام انبار',
            'کد انبار',
            'موجودی در این انبار',
            'موجودی فیزیکی کل',
            'تاریخ ایجاد'
        ]
        writer.writerow(headers)

        variants = ProductVariant.objects.filter(store=store).select_related('product', 'product__category')
        warehouses = list(Warehouse.objects.filter(store=store, is_active=True))
        if not warehouses:
            default_wh = Warehouse.objects.filter(store=store).first()
            if not default_wh:
                default_wh = Warehouse.objects.create(store=store, name="انبار اصلی", is_default=True)
            warehouses = [default_wh]

        for v in variants:
            p = v.product
            total_on_hand = v.balances.aggregate(s=models.Sum('on_hand_quantity'))['s'] or 0

            for wh in warehouses:
                bal = v.balances.filter(warehouse=wh).first()
                wh_qty = bal.on_hand_quantity if bal else 0
                row = [
                    sanitize_csv_cell(p.id),
                    sanitize_csv_cell(p.name),
                    sanitize_csv_cell(p.brand or ''),
                    sanitize_csv_cell(p.category.name if p.category else ''),
                    sanitize_csv_cell(p.get_status_display()),
                    sanitize_csv_cell(v.id),
                    sanitize_csv_cell(v.sku),
                    sanitize_csv_cell(v.barcode or ''),
                    sanitize_csv_cell(v.name),
                    sanitize_csv_cell(v.retail_price),
                    sanitize_csv_cell(v.cost_price),
                    sanitize_csv_cell(v.wholesale_price or 0),
                    sanitize_csv_cell(wh.name),
                    sanitize_csv_cell(wh.code or ''),
                    sanitize_csv_cell(wh_qty),
                    sanitize_csv_cell(total_on_hand),
                    sanitize_csv_cell(v.created_at.strftime('%Y-%m-%d %H:%M') if v.created_at else '')
                ]
                writer.writerow(row)

        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="products_{store.id}.csv"'
        return response

    @action(detail=False, methods=['post'], url_path='import-csv')
    @transaction.atomic
    def import_csv(self, request):
        store = request.store
        uploaded_file = request.FILES.get('file')
        csv_content = request.data.get('csv_content')

        if uploaded_file:
            try:
                decoded_file = uploaded_file.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                return Response({'error': 'فرمت انکودینگ فایل باید UTF-8 باشد.'}, status=status.HTTP_400_BAD_REQUEST)
        elif csv_content:
            decoded_file = csv_content
        else:
            return Response({'error': 'فایل CSV یا محتوای csv_content الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(io.StringIO(decoded_file))
        created_products = 0
        updated_variants = 0
        errors = []

        default_wh = Warehouse.objects.filter(store=store, is_default=True, is_active=True).first()
        if not default_wh:
            default_wh = Warehouse.objects.filter(store=store, is_active=True).first()
        if not default_wh:
            default_wh = Warehouse.objects.create(store=store, name="انبار پیش‌فرض", is_default=True)

        for row_num, row in enumerate(reader, start=2):
            normalized_row = {k.strip().lower() if k else '': v.strip() if v else '' for k, v in row.items()}
            
            # Map column names
            name = (
                normalized_row.get('نام محصول') or normalized_row.get('نام کالا') or
                normalized_row.get('product_name') or normalized_row.get('name') or ''
            )
            sku = (
                normalized_row.get('کد تنوع (sku)') or normalized_row.get('کد تنوع') or
                normalized_row.get('کد کالا') or normalized_row.get('sku') or ''
            )
            retail_price_raw = (
                normalized_row.get('قیمت فروش (تومان)') or normalized_row.get('قیمت فروش') or
                normalized_row.get('retail_price') or normalized_row.get('قیمت') or '0'
            )
            cost_price_raw = (
                normalized_row.get('قیمت خرید (تومان)') or normalized_row.get('قیمت خرید') or
                normalized_row.get('cost_price') or '0'
            )
            wholesale_price_raw = (
                normalized_row.get('قیمت عمده (تومان)') or normalized_row.get('قیمت عمده') or
                normalized_row.get('wholesale_price') or '0'
            )
            barcode = (
                normalized_row.get('بارکد') or normalized_row.get('barcode') or ''
            )
            category_name = (
                normalized_row.get('دسته‌بندی') or normalized_row.get('category') or ''
            )
            brand = (
                normalized_row.get('برند') or normalized_row.get('brand') or ''
            )
            stock_raw = (
                normalized_row.get('موجودی در این انبار') or normalized_row.get('موجودی فیزیکی کل') or
                normalized_row.get('موجودی') or normalized_row.get('stock') or normalized_row.get('quantity') or ''
            )
            wh_name = (
                normalized_row.get('نام انبار') or normalized_row.get('انبار') or normalized_row.get('warehouse') or ''
            )
            wh_code = (
                normalized_row.get('کد انبار') or normalized_row.get('warehouse_code') or ''
            )

            if not name and not sku:
                continue

            try:
                retail_price = Decimal(retail_price_raw.replace(',', '')) if retail_price_raw else Decimal('0')
                cost_price = Decimal(cost_price_raw.replace(',', '')) if cost_price_raw else Decimal('0')
                wholesale_price = Decimal(wholesale_price_raw.replace(',', '')) if wholesale_price_raw else Decimal('0')
            except Exception:
                errors.append(f"ردیف {row_num}: فرمت قیمت نامعتبر است.")
                continue

            category = None
            if category_name:
                category, _ = Category.objects.get_or_create(
                    store=store,
                    name=category_name,
                    defaults={'slug': slugify(category_name, allow_unicode=True) or category_name}
                )

            # Check if variant exists
            variant = None
            if sku:
                variant = ProductVariant.objects.filter(store=store, sku__iexact=sku).select_related('product').first()

            if variant:
                old_retail = variant.retail_price
                old_cost = variant.cost_price
                variant.retail_price = retail_price
                variant.cost_price = cost_price
                if wholesale_price:
                    variant.wholesale_price = wholesale_price
                if barcode:
                    variant.barcode = barcode
                variant.save()
                updated_variants += 1

                if old_retail != retail_price or old_cost != cost_price:
                    ProductPriceHistory.objects.create(
                        store=store,
                        variant=variant,
                        old_retail_price=old_retail,
                        new_retail_price=retail_price,
                        old_cost_price=old_cost,
                        new_cost_price=cost_price,
                        reason="بروزرسانی از طریق ایمپورت CSV",
                        changed_by=request.user if request.user.is_authenticated else None
                    )
            else:
                # Need to create product & variant -> enforce plan quota
                FeatureService.enforce_plan_quota(store, 'products')
                product_slug = slugify(name, allow_unicode=True) or name
                product = Product.objects.filter(store=store, name=name).first()
                if not product:
                    product = Product.objects.create(
                        store=store,
                        name=name,
                        slug=f"{product_slug}-{uuid_str()[:6]}",
                        category=category,
                        brand=brand,
                        status='ACTIVE'
                    )
                    created_products += 1

                actual_sku = sku or f"SKU-{str(product.id)[:8].upper()}"
                variant = ProductVariant.objects.create(
                    store=store,
                    product=product,
                    name="تنوع پیش‌فرض",
                    sku=actual_sku,
                    barcode=barcode,
                    retail_price=retail_price,
                    cost_price=cost_price,
                    wholesale_price=wholesale_price,
                    is_active=True
                )

            # Determine target warehouse for inventory adjustment
            target_wh = None
            if wh_name:
                target_wh = Warehouse.objects.filter(store=store, name__iexact=wh_name).first()
            elif wh_code:
                target_wh = Warehouse.objects.filter(store=store, code__iexact=wh_code).first()

            if not target_wh:
                target_wh = default_wh

            # Adjust stock in target warehouse if specified
            if stock_raw != '':
                try:
                    qty = int(stock_raw)
                    if qty >= 0:
                        adjust_stock(
                            store=store,
                            warehouse=target_wh,
                            variant=variant,
                            new_on_hand=qty,
                            reason=f"تنظیم موجودی از طریق ایمپورت CSV در انبار {target_wh.name}",
                            user=request.user
                        )
                except (ValueError, TypeError):
                    errors.append(f"ردیف {row_num}: تعداد موجودی '{stock_raw}' نامعتبر است.")

        return Response({
            'message': 'عملیات ایمپورت با موفقیت پردازش شد.',
            'created_products': created_products,
            'updated_variants': updated_variants,
            'errors': errors
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='barcode')
    def barcode_query(self, request):
        code = request.query_params.get('code')
        if not code:
            return Response({'error': 'پارامتر code برای استعلام بارکد الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)
        return self._lookup_barcode(request, code.strip())

    @action(detail=False, methods=['get'], url_path='barcode/(?P<barcode>[^/.]+)')
    def barcode_lookup(self, request, barcode=None):
        return self._lookup_barcode(request, barcode.strip())

    def _lookup_barcode(self, request, code):
        store = request.store
        variant = ProductVariant.objects.filter(
            store=store
        ).filter(
            models.Q(barcode=code) | models.Q(sku__iexact=code)
        ).select_related('product', 'product__category').first()

        if not variant:
            return Response({'error': f"کالایی با بارکد یا کد '{code}' در این فروشگاه یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        return Response(ProductVariantSerializer(variant, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='price-history')
    def price_history(self, request, pk=None):
        product = self.get_object()
        history = ProductPriceHistory.objects.filter(
            store=request.store,
            variant__product=product
        ).select_related('variant', 'changed_by')
        return Response(ProductPriceHistorySerializer(history, many=True).data)


class ProductVariantViewSet(viewsets.ModelViewSet):
    serializer_class = ProductVariantSerializer
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'sku', 'barcode', 'product__name']
    queryset = ProductVariant.objects.all().select_related('product')

    @action(detail=True, methods=['get'], url_path='price-history')
    def price_history(self, request, pk=None):
        variant = self.get_object()
        history = ProductPriceHistory.objects.filter(
            store=request.store,
            variant=variant
        ).select_related('variant', 'changed_by')
        return Response(ProductPriceHistorySerializer(history, many=True).data)


def uuid_str():
    import uuid
    return uuid.uuid4().hex
