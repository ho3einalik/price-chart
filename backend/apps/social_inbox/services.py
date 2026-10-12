from django.utils import timezone
from .models import ConversationThread, ChatMessage, SenderType, ThreadStatus
from apps.catalog.models import ProductVariant
from apps.features.adapters import get_integration_adapter

def generate_ai_suggested_reply(thread, context_hint=''):
    """
    Generate an AI draft response grounded in the store's verified product catalog and store inventory.
    """
    store = thread.store
    # Grab latest customer messages
    recent_messages = thread.messages.order_by('-created_at')[:4]
    customer_query = ""
    for msg in reversed(list(recent_messages)):
        customer_query += f"{msg.sender_type}: {msg.text}\n"

    # Fetch top active products for catalog grounding
    products = ProductVariant.objects.filter(store=store, is_active=True).select_related('product')[:5]
    catalog_context = "\n".join([
        f"- {p.product.name} ({p.sku}): قیمت {p.retail_price:,} {store.currency}"
        for p in products
    ])

    prompt = f"""
شما پشتیبان فروشگاه {store.name} در دایرکت هستید.
مخاطب: {thread.contact_name} ({thread.contact_handle})
تاریخچه گفتگو:
{customer_query}

محصولات برگزیده در دسترس فروشگاه:
{catalog_context}

لطفاً یک پاسخ بسیار محترمانه، صمیمی، دقیق و مختصر بنویسید. در صورتی که قیمت پرسیده شده، قیمت دقیق موجود در کاتالوگ را بگویید و اعلام کنید ارسال از طریق پست پیشتاز و تیپاکس به سراسر کشور انجام می‌شود.
"""

    adapter = get_integration_adapter('ai_provider')
    res = adapter.generate_caption_or_text(prompt=prompt, tone='friendly')
    suggested_text = res.get('text', '')

    if not suggested_text:
        # Heuristic reliable fallback
        suggested_text = (
            f"سلام {thread.contact_name} عزیز، وقت بخیر! 🌸\n"
            f"ممنون از پیامتون به {store.name}.\n"
            f"سفارش شما با نهایت دقت ثبت و با پست پیشتاز/تیپاکس ارسال خواهد شد. در صورت نیاز به راهنمایی در مورد هر کدام از محصولات در خدمتتون هستیم!"
        )

    return {
        'suggested_text': suggested_text.strip(),
        'source': res.get('source', 'heuristic_fallback')
    }

def send_agent_message(thread, text, user=None, is_ai=False, was_edited=False):
    msg = ChatMessage.objects.create(
        thread=thread,
        sender_type=SenderType.AGENT,
        sender_user=user,
        text=text,
        is_ai_generated=is_ai,
        was_edited_by_human=was_edited
    )

    thread.last_message_preview = text[:200]
    thread.status = ThreadStatus.PENDING_CUSTOMER
    thread.unread_count = 0
    thread.last_message_at = timezone.now()
    thread.save()
    return msg
