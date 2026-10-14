# ShopPilot — External Integrations & Adapters Status

**Document Version:** 1.0.0 (Production Verified)  
**Classification:** Integration Manual & Gateway Reference  
**Applies to:** `backend/apps/features/adapters.py`, `backend/apps/payments/`, `backend/apps/fulfillment/`, `backend/apps/social/`

---

## 1. Overview & Honest Integration Principles

In accordance with ShopPilot's production engineering principles:
1. **No Fake Success:** An integration never returns `CONNECTED` or `SENT` simply because an adapter or configuration record exists.
2. **Honest Degradation:** If an integration lacks API keys, credentials, or network availability, it explicitly returns `NOT_CONFIGURED` or `FAILED` and falls back to deterministic local heuristic processing without crashing the host application.
3. **No Silent Data Mutation:** External failures are recorded in the audit log or transaction record, preventing desynchronization between external systems and the local database.

---

## 2. Integration Status Matrix

| Integration | Primary Purpose | Real Implementation Details | Verification Status | Degradation Fallback Mode |
| :--- | :--- | :--- | :--- | :--- |
| **Google Gemini 1.5 Flash** | AI caption generation, CRM review analysis, order risk scoring, marketing copy. | `urllib.request` REST client to Google Gemini endpoint (`v1beta/models/gemini-1.5-flash:generateContent`). 10s timeout. | **Implemented & Verified** (Tested with & without `GEMINI_API_KEY`). | Returns honest `NOT_CONFIGURED` if key missing. On timeout or API error, falls back to deterministic rule-based Persian templates. |
| **Kavenegar SMS Gateway** | Order confirmation, OTP verification, abandoned cart recovery, delivery dispatch. | REST adapter supporting Kavenegar and generic Iranian SMS APIs (`api.kavenegar.com/v1/...`). Validates phone format (`09XXXXXXXXX`). | **Implemented & Verified** (Tested with and without `KAVENEGAR_API_KEY`). | Returns `NOT_CONFIGURED` if key missing. Enforces 2-hour anti-spam cooldown per cart. Logs non-blocking warning. |
| **Instagram Graph API** | Social media post scheduling, reels publishing, comment synchronization. | `InstagramIntegrationAdapter` with token validation, webhook verification, and manual tracking fallback mode. | **Implemented & Verified** (Manual & Direct API modes verified). | Defaults to `ConnectionMode.MANUAL_TRACKING` when credentials absent; marks posts as scheduled/ready for operator copy-paste. |
| **Payment Gateways (Zarinpal Online Gateway)** | Online checkout payment processing and server-to-server webhook verification. | `apps.payments.services` adapter architecture with tracking codes, bank reference validation, and role-authorized manual receipt audit. (Sadad/PayPing return explicit `UNSUPPORTED` status until certified). | **Implemented & Verified** (Admin verification lifecycle tested). | Stores can operate in manual receipt / card-to-card review mode with strict RBAC audit verification. |
| **Iran Post & National Couriers** | Parcel tracking and shipping label generation (IRPOST, TIPAX, ALOPAYK, SNAPBOX). | `apps.fulfillment.services.create_shipment` with idempotency keys (`idempotency_key=ship_{order.id}`) and tracking number validation. | **Implemented & Verified** (Fulfillment idempotency verified). | Fallback to manual barcode tracking number assignment with delivery timeline projection. |

---

## 3. Deep Dive: Google Gemini AI Integration

### 3.1 Implementation Architecture
Located in `backend/apps/features/adapters.py`:
- Checks `settings.GEMINI_API_KEY` or store-level encrypted credential.
- If missing, sets status to `IntegrationStatus.NOT_CONFIGURED` and returns:
  `{"configured": False, "mode": "HEURISTIC_FALLBACK"}`.
- If present, builds a JSON payload for `gemini-1.5-flash`:
  ```json
  {
    "contents": [{
      "parts": [{"text": "Prompt text in Persian"}]
    }],
    "generationConfig": {
      "temperature": 0.7,
      "maxOutputTokens": 800
    }
  }
  ```
- Submits via standard library `urllib.request` with a **10-second timeout** to avoid worker thread exhaustion.
- Extracts `candidates[0].content.parts[0].text`.
- If the network fails, catches `urllib.error.URLError` and logs an incident without interrupting the customer request.

### 3.2 Environment Setup
```bash
# Add to backend/.env
GEMINI_API_KEY=AIzaSy...YourGeminiApiKeyHere
```

---

## 4. Deep Dive: Kavenegar SMS Gateway & Anti-Spam Protections

### 4.1 Phone Validation
Validates Iranian mobile numbers against regex `^09\d{9}$`:
- Converts leading `+98` or `0098` to `09`.
- Rejects non-mobile phone strings before invoking the external HTTP provider.

### 4.2 Abandoned Cart Recovery Anti-Spam Cooldown
Located in `backend/apps/marketing/views.py`:
```python
# 1. Cooldown protection (2 hours minimum between SMS attempts)
if cart.recovery_sms_sent_at and (timezone.now() - cart.recovery_sms_sent_at) < timedelta(hours=2):
    return Response({
        'error': 'پیامک یادآوری اخیراً برای این مشتری ارسال شده است. لطفاً حداقل ۲ ساعت پس از ارسال قبلی مجدداً تلاش کنید.'
    }, status=status.HTTP_429_TOO_MANY_REQUESTS)

# 2. Skip already recovered carts
if cart.status == AbandonedCartStatus.RECOVERED:
    return Response({
        'error': 'این سبد خرید قبلاً توسط مشتری نهایی و تبدیل به سفارش شده است.'
    }, status=status.HTTP_400_BAD_REQUEST)
```

### 4.3 Environment Setup
```bash
# Add to backend/.env
KAVENEGAR_API_KEY=1234567890abcdef...
SMS_SENDER_NUMBER=10008000
```

---

## 5. Deep Dive: Social Media & Manual Fallback

Social media integrations operate in two distinct modes:
1. **DIRECT_API:** Requires Meta Developer App review and long-lived Page Access Token. Posts are dispatched to the Meta Graph API.
2. **MANUAL_TRACKING (Default):** Operators manage social profiles directly on Instagram/Telegram, but utilize ShopPilot as an editorial calendar, caption generator, and revenue attribution engine.
   - Products are linked via `related_product`.
   - Dedicated discount codes track sales generated from specific posts.
   - Impressions and views are updated by team members and audited via `ContentMetricSnapshot`.

---

## 6. Summary of Required Production Environment Variables

| Variable | Required? | Default / Fallback | Purpose |
| :--- | :---: | :--- | :--- |
| `DJANGO_SECRET_KEY` | **Yes** | None (Throws error if missing in prod) | Cryptographic signature & session security |
| `DATABASE_URL` | **Yes** | PostgreSQL connection string | Production database connection |
| `REDIS_URL` | **Yes** | `redis://redis:6379/0` | Cache and Celery message broker |
| `GEMINI_API_KEY` | Optional | Heuristic templates used | Google Gemini 1.5 Flash AI text generation |
| `KAVENEGAR_API_KEY` | Optional | SMS logged as NOT_CONFIGURED | Transactional SMS dispatch in Iran |
| `ALLOWED_HOSTS` | **Yes** | `shoppilot.ir,api.shoppilot.ir` | HTTP Host header validation |
| `CORS_ALLOWED_ORIGINS` | **Yes** | `https://shoppilot.ir` | Cross-Origin Resource Sharing whitelist |
