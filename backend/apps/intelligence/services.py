from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from apps.catalog.models import ProductVariant
from apps.inventory.models import InventoryBalance
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentStatus
from apps.features.adapters import get_integration_adapter

def calculate_demand_forecasts(store, period_days=30):
    """
    Predictive velocity-based inventory demand forecasting.
    Calculates sales velocity, days until stockout, and reorder urgency.
    """
    cutoff = timezone.now() - timedelta(days=period_days)
    variants = ProductVariant.objects.filter(store=store, is_active=True).select_related('product')
    
    forecasts = []
    for var in variants:
        # Sum quantities sold in period
        sold = OrderItem.objects.filter(
            variant=var,
            order__created_at__gte=cutoff
        ).exclude(order__order_status=OrderStatus.CANCELLED).aggregate(s=Sum('quantity'))['s'] or 0

        daily_velocity = round(sold / period_days, 2)

        # Sum available balances
        balances = InventoryBalance.objects.filter(variant=var, store=store)
        total_available = sum(b.available for b in balances)
        total_on_hand = sum(b.on_hand_quantity for b in balances)

        if daily_velocity > 0:
            days_remaining = round(total_available / daily_velocity)
        else:
            days_remaining = 999 if total_available > 0 else 0

        if days_remaining <= 5 and (daily_velocity > 0 or total_available == 0):
            urgency = 'CRITICAL'
            urgency_display = 'بحرانی (اتمام موجودی کمتر از ۵ روز)'
        elif days_remaining <= 14:
            urgency = 'WARNING'
            urgency_display = 'هشدار (اتمام موجودی تا ۲ هفته)'
        else:
            urgency = 'HEALTHY'
            urgency_display = 'مطلوب و کافی'

        # Lead time & safety stock formula: Reorder Point = (Daily Velocity * Lead Time) + Safety Stock
        lead_time_days = 7
        safety_stock = max(2, round(daily_velocity * 3)) if daily_velocity > 0 else 0
        reorder_point = round((daily_velocity * lead_time_days) + safety_stock)
        needs_reorder = total_available <= reorder_point

        # Target 30 days buffer
        target_buffer = round(daily_velocity * 30)
        reorder_suggested_qty = max(0, target_buffer - total_available)

        forecasts.append({
            'variant_id': str(var.id),
            'product_name': var.product.name,
            'sku': var.sku,
            'retail_price': str(var.retail_price),
            'cost_price': str(var.cost_price),
            'units_sold_in_period': sold,
            'daily_velocity': daily_velocity,
            'total_available': total_available,
            'total_on_hand': total_on_hand,
            'lead_time_days': lead_time_days,
            'safety_stock': safety_stock,
            'reorder_point': reorder_point,
            'needs_reorder': needs_reorder,
            'days_remaining': days_remaining,
            'urgency': urgency,
            'urgency_display': urgency_display,
            'reorder_suggested_qty': reorder_suggested_qty
        })

    # Sort critical first, then warning
    urgency_order = {'CRITICAL': 0, 'WARNING': 1, 'HEALTHY': 2}
    forecasts.sort(key=lambda x: (urgency_order.get(x['urgency'], 3), x['days_remaining']))
    return forecasts


def calculate_slow_movers(store, period_days=60):
    """
    Detect dead stock / slow movers to unlock tied-up working capital.
    Identifies products with stock on hand but very low or zero sales velocity.
    """
    cutoff = timezone.now() - timedelta(days=period_days)
    variants = ProductVariant.objects.filter(store=store, is_active=True).select_related('product')

    slow_movers = []
    total_trapped_capital = Decimal('0')

    for var in variants:
        balances = InventoryBalance.objects.filter(variant=var, store=store)
        total_on_hand = sum(b.on_hand_quantity for b in balances)
        if total_on_hand <= 0:
            continue

        sold = OrderItem.objects.filter(
            variant=var,
            order__created_at__gte=cutoff
        ).exclude(order__order_status=OrderStatus.CANCELLED).aggregate(s=Sum('quantity'))['s'] or 0

        daily_velocity = round(sold / period_days, 3)

        if daily_velocity < 0.05:
            cost_val = (var.cost_price if (var.cost_price and var.cost_price > 0) else var.retail_price * Decimal('0.7')) * total_on_hand
            total_trapped_capital += cost_val

            if sold == 0:
                rec_action = 'DISCOUNT_BUNDLE'
                rec_text = 'تخفیف پکیجی یا باندل با کالاهای پرفروش جهت نقد کردن انبار'
            else:
                rec_action = 'MARKDOWN_PROMO'
                rec_text = 'اعمال تخفیف ۱۵ تا ۲۵ درصدی در کمپین فروش شگفت‌انگیز'

            slow_movers.append({
                'variant_id': str(var.id),
                'product_name': var.product.name,
                'sku': var.sku,
                'retail_price': str(var.retail_price),
                'cost_price': str(var.cost_price),
                'total_on_hand': total_on_hand,
                'units_sold_in_period': sold,
                'daily_velocity': daily_velocity,
                'tied_up_capital': str(cost_val),
                'recommended_action': rec_action,
                'recommendation_text': rec_text
            })

    slow_movers.sort(key=lambda x: Decimal(x['tied_up_capital']), reverse=True)

    return {
        'period_days': period_days,
        'slow_mover_count': len(slow_movers),
        'total_trapped_capital': str(total_trapped_capital),
        'items': slow_movers
    }


def evaluate_order_risk(order):
    """
    Explainable order anomaly and risk detection engine.
    """
    reasons = []
    risk_points = 0
    store = order.store

    # 1. Check order value anomaly against store AOV
    avg_order_val = Order.objects.filter(store=store).exclude(order_status=OrderStatus.CANCELLED).aggregate(a=Avg('grand_total'))['a'] or Decimal('500000')
    if order.grand_total > avg_order_val * Decimal('3.5'):
        risk_points += 35
        reasons.append(f"مبلغ این سفارش ({order.grand_total:,} تومان) بیش از ۳.۵ برابر میانگین سفارشات فروشگاه است.")

    # 2. Check address completeness
    address_len = len(order.customer.address_line or '')
    if address_len < 12:
        risk_points += 25
        reasons.append("نشانی ثبت‌شده بسیار کوتاه و فاقد جزئیات کافی پستی است.")

    # 3. Check customer history
    cust_orders = Order.objects.filter(customer=order.customer)
    cancelled_count = cust_orders.filter(order_status=OrderStatus.CANCELLED).count()
    if cancelled_count >= 2:
        risk_points += 30
        reasons.append(f"این خریدار سابقه {cancelled_count} سفارش لغوشده قبلی دارد.")

    # 4. Check payment status
    if order.payment_status != PaymentStatus.PAID:
        risk_points += 15
        reasons.append("پرداخت سفارش هنوز تایید یا تسویه کامل نشده است.")

    risk_score = min(100, risk_points)
    if risk_score >= 60:
        level = 'HIGH'
        level_display = 'ریسک بالا (نیازمند احراز هویت خریدار)'
        recommendation = 'MANUAL_REVIEW'
        recommendation_display = 'پیش از ارسال تماس تلفنی با خریدار گرفته شود'
    elif risk_score >= 30:
        level = 'MEDIUM'
        level_display = 'ریسک متوسط (بررسی پیش از ارسال)'
        recommendation = 'CAUTION'
        recommendation_display = 'تطابق فیش و آدرس با مشتری چک شود'
    else:
        level = 'LOW'
        level_display = 'ریسک پایین (سفارش امن)'
        recommendation = 'AUTO_APPROVE'
        recommendation_display = 'تایید خودکار برای پردازش و ارسال'

    return {
        'order_id': str(order.id),
        'order_number': order.order_number,
        'risk_score': risk_score,
        'risk_level': level,
        'risk_level_display': level_display,
        'reasons': reasons if reasons else ['کلیه مشخصات سفارش و سابقه مشتری عادی و معتبر است.'],
        'recommendation': recommendation,
        'recommendation_display': recommendation_display
    }


def ask_ai_business_copilot(store, question):
    """
    AI operational management assistant grounded exclusively in verifiable store data.
    """
    # Collect real ground truth metrics
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    
    recent_orders = Order.objects.filter(store=store, created_at__gte=thirty_days_ago).exclude(order_status=OrderStatus.CANCELLED)
    total_sales = recent_orders.aggregate(s=Sum('grand_total'))['s'] or Decimal('0')
    orders_count = recent_orders.count()

    top_items = OrderItem.objects.filter(order__in=recent_orders).values('variant_sku', 'variant_name').annotate(
        qty_sold=Sum('quantity'),
        revenue=Sum('total_price')
    ).order_by('-qty_sold')[:5]

    top_items_text = "\n".join([
        f"- {i['variant_name']} ({i['variant_sku']}): {i['qty_sold']} عدد، درآمد {i['revenue']:,} {store.currency}"
        for i in top_items
    ])

    low_stock_balances = InventoryBalance.objects.filter(store=store, on_hand_quantity__lte=5).select_related('variant__product')[:5]
    low_stock_text = "\n".join([
        f"- {b.variant.product.name} ({b.variant.sku}): موجودی فقط {b.available} عدد"
        for b in low_stock_balances
    ])

    context_prompt = f"""
شما مشاور و دستیار هوشمند عملیاتی فروشگاه {store.name} در پلتفرم ShopPilot هستید.
اطلاعات قطعی و موثق فروشگاه در ۳۰ روز اخیر:
- واحد پول: {store.currency}
- تعداد کل سفارشات: {orders_count}
- مجموع فروش خالص: {total_sales:,} {store.currency}
- پرفروش‌ترین محصولات:
{top_items_text or 'اطلاعات فروشی ثبت نشده است.'}
- کالاهای در معرض اتمام موجودی:
{low_stock_text or 'هیچ کالایی در وضعیت کمبود موجودی نیست.'}

سوال مدیر فروشگاه:
"{question}"

دستورالعمل:
پاسخ را به زبان فارسی بسیار حرفه‌ای، تحلیلی، دقیق، مستند به داده‌های بالا و همراه با ۳ اقدام پیشنهادی مشخص ارائه دهید. هرگز اطلاعات جعلی نسازید.
"""

    adapter = get_integration_adapter('ai_provider')
    res = adapter.generate_caption_or_text(prompt=context_prompt, tone='analytical')
    response_text = res.get('text', '')

    if not response_text:
        response_text = (
            f"بر اساس آمار ۳۰ روز اخیر فروشگاه {store.name}، شما {orders_count} سفارش به ارزش {total_sales:,} {store.currency} داشته‌اید.\n\n"
            f"پیشنهادات عملیاتی:\n"
            f"۱. بررسی موجودی اقلام رو به اتمام و صدور سفارش خرید (PO) برای تامین‌کننده.\n"
            f"۲. اجرای کمپین بازاریابی برای مشتریان بالقوه و وفادار با ارائه کد تخفیف هدفمند.\n"
            f"۳. پیگیری فیش‌های واریزی معلق جهت تسریع چرخه ارسال مرسولات."
        )

    return {
        'question': question,
        'answer': response_text.strip(),
        'source': res.get('source', 'grounded_tenant_analytics')
    }
