# ShopPilot — Final Product Gap Report & Production Readiness Audit

**Document Version:** 1.1.0 (Production Verified & Hardened)  
**Date:** October 13, 2026  
**Auditor:** Senior Software Architect & Security Engineering Pair  
**Repository Working Copy:** `c:\Users\ASUS\OneDrive\Desktop\onlineshop`  
**Backend Framework:** Django 5.1.15 / Django REST Framework 3.15  
**Frontend Framework:** Next.js 14.2.15 (App Router, TypeScript, Tailwind CSS)  
**Test Suite Status:** **62 passed / 62 tests (100% PASS)** in 73.77 seconds  
**Frontend Build Status:** **21/21 static pages compiled cleanly with 0 TypeScript/ESLint errors**

---

## 1. Executive Summary

This report concludes a comprehensive, repository-wide code audit, bug remediation, security hardening, and production-readiness verification of the **ShopPilot** multi-tenant commerce SaaS platform.

Previously, the platform had several critical security vulnerabilities (fail-open membership queries, privilege escalation to store owner, cross-business store allocation, raw token invitation replay), commerce data-integrity hazards (silent clamping to zero on overselling, duplicate non-idempotent shipments, order cancellation after shipment dispatch, non-atomic return quantities, and supplier receiving disconnect from accounts payable), incomplete integration adapters masquerading as connected via simulated mocks, and missing frontend-backend contract bindings.

Over the course of this mission, **all identified security vulnerabilities, production configurations, and architectural gaps were remediated with production-grade implementations**, verifiable database constraints, fail-closed permissions, and automated regression tests.

Key Production Hardening Enhancements:
1. **Production Configuration Hardening (`config/settings.py`):** Fail-closed startup if `DJANGO_SECRET_KEY` is default/weak (< 32 chars), if `DJANGO_ALLOWED_HOSTS` contains wildcard `*` or is empty, or if SQLite is used without explicit override. Added native 12-factor `DATABASE_URL` parsing. Enforced explicit `CORS_ALLOWED_ORIGINS` with `CORS_ALLOW_ALL_ORIGINS = False` in production. Configured secure HTTPS session/CSRF cookies and headers (`X_FRAME_OPTIONS = 'DENY'`, `SECURE_PROXY_SSL_HEADER`).
2. **Subscription Tier Default & Upgrade Protection (`apps/features/`):** New store feature settings strictly default to `SubscriptionTier.FREE`. Arbitrary tenant self-upgrade to `PRO` or `ENTERPRISE` without payment authorization or staff approval is blocked with 403 Forbidden.
3. **Payment Integrity & Concurrency (`apps/payments/`):** Strict positive amount validation (rejecting zero/negative), server-authoritative remaining payable checks, database row-locking (`select_for_update`), and idempotent payment verification/rejection.
4. **Integration Honesty & Sensitive Logging:** Added honest states (`CONFIGURED`, `CONNECTION_TESTED`, `ERROR`, `MOCKED`, `MANUAL_ONLY`). Redacted PII (phone number masking) in integration logs.
5. **Demo Authentication Isolation:** Gated frontend demo login button by environment flags, removed default superuser privileges from demo seeding, and blocked demo seeding execution in production.

---

## 2. Evidence-Based Test Suite Execution

All test suites were executed on the working copy against Python 3.13.2 and Django 5.1.15.

```text
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-9.1.1, pluggy-1.6.0
django: version: 5.1.15, settings: config.settings (from ini)
rootdir: C:\Users\ASUS\OneDrive\Desktop\onlineshop\backend
configfile: pytest.ini
plugins: django-4.14.0
collected 62 items

tests\test_audit_and_security_hardening.py .....                         [  8%]
tests\test_commerce_integrity_regression.py ........                     [ 20%]
tests\test_feature_modularity.py ..........                              [ 37%]
tests\test_field_and_features_regression.py .....                        [ 45%]
tests\test_full_product_capabilities.py .......                          [ 56%]
tests\test_inventory_concurrency.py .                                    [ 58%]
tests\test_marketing_and_intelligence.py ...                             [ 62%]
tests\test_order_lifecycle.py ..                                         [ 66%]
tests\test_payments_and_profit.py .                                      [ 67%]
tests\test_production_hardening_and_integrity.py .......                 [ 79%]
tests\test_social_operations.py ...                                      [ 83%]
tests\test_suppliers_and_returns.py ..                                   [ 87%]
tests\test_tasks.py ....                                                 [ 93%]
tests\test_team_rbac.py ...                                              [ 98%]
tests\test_tenancy_isolation.py .                                        [100%]

======================== 62 passed in 73.77s (0:01:13) ========================
```

Furthermore, database schema checks confirmed zero pending unapplied migrations (`manage.py makemigrations --check` returned clean code 0), and Next.js frontend production compilation (`npm run build`) succeeded across all 21 client routes with zero type errors.

---

## 3. Systematic Breakdown of Defect Remediations

### 3.1 Security & Multi-Tenant Authorization (Section 3 Audit)

| Component | Defect Found | Resolution & Implementation | Regression Verification |
| :--- | :--- | :--- | :--- |
| **Tenancy Permissions** (`apps/tenancy/permissions.py`) | `get_request_store` checked only `is_active=True`, allowing suspended memberships (`status='SUSPENDED'`) and inactive stores to execute mutating queries. Invalid UUID header crashed with 500 unhandled exception. | Enforced UUID parsing validation (fail-closed 400/403). Centralized lookup requiring `is_active=True`, `status=MembershipStatus.ACTIVE`, and `store.is_active=True`. Added `IsStoreAdminOrOwnerPermission` and strict role lookup. | `test_suspended_member_blocked_across_endpoints`<br>`test_member_suspension_blocks_access` |
| **Privilege Escalation** (`apps/tenancy/views.py`, `serializers.py`) | Members could assign `Role.OWNER` via invitation or membership edit; last remaining owner could demote themselves, stranding tenant. | In `StoreMembershipSerializer.validate_role`, blocked assigning `Role.OWNER` and verified active owner count before demotion. In `TeamInvitationSerializer`, disallowed inviting users with `Role.OWNER`. Dedicated `transfer-ownership` action requires existing owner authentication. | `test_privilege_escalation_role_assignment` |
| **Store Provisioning** (`apps/tenancy/views.py`) | `StoreViewSet.create` accepted arbitrary `business` UUID from client payload without verifying owner authorization. | Added `validate_business` ensuring `request.user == business.owner`. Restricted update/destroy to `Role.OWNER`. Soft-archives stores with existing orders to preserve financial and audit trail. | `test_store_creation_cross_business_protection` |
| **Team Invitations** (`apps/tenancy/views.py`) | Invitation tokens were sent as plain strings; any authenticated user could accept another user's invite URL (`cross-user replay`). | Bound invitation acceptance strictly to `request.user.email == invite.email`. Implemented atomic row locking (`select_for_update`) to prevent concurrent double-acceptance race conditions. Supported both `/invitations/accept/` (by token) and `/invitations/{id}/accept/`. | `test_invitation_email_binding_and_cross_user_acceptance` |
| **Audit Log Field Alignment & CSV Injection** (`apps/audit/views.py`) | Team activity summary crashed querying non-existent `user__username`, `user__first_name`, `user__last_name` on custom `User` model. CSV exports were vulnerable to formula injection (`=`, `+`, `-`, `@`). | Replaced user queries with `user__full_name` and `user__email`. Implemented `sanitize_csv_value` prepending single quotes to formula-trigger characters and forced UTF-8 BOM encoding (`\ufeff`) for proper Persian/RTL Excel rendering. | `test_team_activity_summary_and_audit_export` |

---

### 3.2 Commerce, Inventory & Financial Integrity (Section 4 Audit)

| Component | Defect Found | Resolution & Implementation | Regression Verification |
| :--- | :--- | :--- | :--- |
| **Inventory Overselling** (`apps/inventory/services.py`, `wholesale_pos/services.py`) | `commit_stock_sale` silently clamped negative inventory to 0 using `max(0, balance.on_hand_quantity - quantity)`, corrupting ledger accuracy. | Replaced silent clamping with strict check throwing `InsufficientStockError`. POS checkout catches `InsufficientStockError` and throws localized `ValidationError`. Added `transfer_stock` supporting warehouse-to-warehouse stock transfers. | `test_overselling_rejected_on_stock_sale`<br>`test_wholesale_pos_oversell_rejected` |
| **Order Fulfillment Concurrency** (`apps/orders/services.py`) | Repeating `fulfill_order` deducted stock multiple times and created duplicate shipments. Cancelling fulfilled orders released stock reservations that were already shipped. | Added row locking `select_for_update()`. If already fulfilled, returns existing `Shipment` idempotently without duplicate deduction. `cancel_order` rejects fulfilled orders with `ValueError`, enforcing RMA return flow. | `test_duplicate_order_fulfillment_idempotent`<br>`test_cancellation_of_fulfilled_order_rejected` |
| **Cumulative Returns & Refunds** (`apps/returns/services.py`) | `create_return_request` only checked single-item quantity against order quantity, allowing multiple RMA requests to return 200%+ of items purchased. | Added aggregation query checking cumulative returned quantity across all non-rejected prior RMAs (`prior_returned = ReturnItem.objects.filter(...).aggregate(Sum('quantity'))`). Enforces `quantity <= (order_item.quantity - prior_returned)`. | `test_cumulative_return_quantity_validation` |
| **Supplier Receiving & AP Liability** (`apps/suppliers/services.py`) | Receiving goods against a PO increased inventory but did not generate Accounts Payable records, creating off-balance-sheet debt. | `receive_po_goods` now locks PO rows, increases warehouse inventory, updates item quantities, and automatically writes/updates `AccountsPayableReceivable` debt records (`SUPPLIER_DEBT`) in `apps.finance`. | `test_supplier_po_receipt_creates_accounts_payable` |
| **Finance Accounts Payable / Receivable** (`apps/finance/views.py`) | `record_payment` action accepted negative or excessive amounts without bounds checking. `FinancialStatementView` crashed querying `store.slug` and invalid date attributes. | Validated `amount > Decimal('0')` and `amount <= remaining_balance`. Fixed `FinancialStatementView` and `FinancialExportCSVView` to query `store.id`, `settlement_date__gte`, and `RefundStatus.COMPLETED`. | `test_accounts_payable_receivable_payment_validation`<br>`test_financial_export_csv_and_statement` |

---

### 3.3 Feature Modularity & Integration Adapters (Section 5 Audit)

| Component | Defect Found | Resolution & Implementation | Regression Verification |
| :--- | :--- | :--- | :--- |
| **Feature Registry & DAG** (`apps/features/registry.py`, `services.py`) | Missing keys for `suppliers.management`, `wholesale_pos.cashier`, `marketing.abandoned_carts`, `crm.customer_profiles`, `automation.rules`. Disabling features crashed dependent services. | Registered all 17 system features with clear dependencies. `check_feature_access` enforces DAG dependency satisfaction. If parent feature is inactive, dependent feature actions fail closed. | `test_feature_catalog_and_dag_validation`<br>`test_dependency_management_and_missing_prerequisites` |
| **Gemini AI Integration** (`apps/features/adapters.py`) | Adapter claimed `CONNECTED` even with blank credentials and simulated fake captions. | Checks `GEMINI_API_KEY` (from environment or store settings). If absent, returns honest `NOT_CONFIGURED` status. If present, executes real HTTP POST to Google Gemini 1.5 Flash endpoint (`generativelanguage.googleapis.com`) with 10s timeout, gracefully degrading to heuristic templates on network outage. | `test_ai_provider_degradation_and_heuristic_fallback` |
| **SMS Gateway Integration** (`apps/features/adapters.py`) | SMS adapter simulated delivery without verifying gateway credentials or phone validation. | Checks `KAVENEGAR_API_KEY` or `SMS_API_KEY`. Returns `NOT_CONFIGURED` without keys. Validates Iranian phone formats (`09XXXXXXXXX`). In `AbandonedCartViewSet.trigger_recovery`, enforces 2-hour anti-spam cooldown per cart and skips already-recovered carts. | `test_sms_adapter_resilience`<br>`test_abandoned_cart_trigger_recovery` |
| **Payments Role Verification** (`apps/payments/views.py`) | Any authenticated member could verify/reject payment transactions. | Enforced role check restricting verification to `OWNER`, `ADMIN`, `BUSINESS_MANAGER`, or `payments.verify` permission. | `test_payment_verification_role_protection` |

---

### 3.4 Frontend API Client & View Alignment (Section 6 Audit)

| Component | Defect Found | Resolution & Implementation |
| :--- | :--- | :--- |
| **JWT Token Refresh** (`frontend/src/lib/api.ts`) | On token expiry, DRF 401 response led to stuck UI without refresh attempt or request replay. | Implemented automatic token refresh via `/auth/token/refresh/` with subscriber queue, locking, and request replay. Added `api.downloadFile(endpoint, filename)` handling authenticated binary/blob downloads. |
| **Dashboard Metrics & Visuals** (`frontend/src/app/page.tsx`) | Hardcoded SVG curve points, dummy 4.2M-9.1M weekly bars, and 4 static mock tasks were displayed regardless of store data. | Replaced with real dynamic baseline metrics, real tasks query, and clean empty states when database has no activity. |
| **Orders Risk Visualization** (`frontend/src/app/orders/page.tsx`) | Contract mismatch: frontend looked for non-existent risk fields. | Aligned card with backend `OrderRiskSerializer` (`recommendation_display`, `risk_score`, `reasons`). |
| **Payments Export Action** (`frontend/src/app/payments/page.tsx`) | Direct unauthenticated `<a href>` resulted in 401 when downloading CSV reports. | Swapped anchor tags for `api.downloadFile('/finance/export-csv/', 'report.csv')` sending `Authorization: Bearer` and `x-store-id` headers. |

---

## 4. Modified and Newly Created Files Inventory

### Backend Core & Security
- `backend/apps/tenancy/permissions.py`: Fail-closed UUID validation, active status enforcement, RBAC helper methods.
- `backend/apps/tenancy/serializers.py`: Store ownership validation, role change rules, prohibition of OWNER in invitations.
- `backend/apps/tenancy/views.py`: Store soft-archive on order presence, atomic invitation acceptance with email identity checks.
- `backend/apps/accounts/models.py`: Added standard `get_full_name()` and `get_short_name()` methods on `User`.
- `backend/apps/audit/views.py`: Fixed User field lookups in `TeamActivitySummaryView`, added `sanitize_csv_value` preventing CSV injection.
- `backend/apps/audit/models.py`: Fixed `NotificationPreference.__str__` referencing custom user attributes.
- `backend/apps/audit/serializers.py`: Aligned `AuditLogSerializer.user_name` with `user.full_name`.

### Commerce & Integrations
- `backend/apps/inventory/services.py`: Strict `commit_stock_sale` raising `InsufficientStockError`, double-entry `transfer_stock`.
- `backend/apps/wholesale_pos/services.py`: Exception translation from inventory to DRF `ValidationError`.
- `backend/apps/orders/services.py`: Idempotent `fulfill_order` using row locks, safe cancellation rejection for fulfilled orders.
- `backend/apps/returns/services.py`: Enforced cumulative return quantity across prior RMAs.
- `backend/apps/suppliers/services.py`: Synchronized PO goods receipts with `AccountsPayableReceivable` debt generation.
- `backend/apps/finance/views.py`: Added bounds checking to `record_payment`, fixed `FinancialStatementView` and `FinancialExportCSVView`.
- `backend/apps/features/registry.py`: Added missing modular keys and DAG dependencies.
- `backend/apps/features/services.py`: Enforced dependency checks before feature activation.
- `backend/apps/features/adapters.py`: Real Google Gemini 1.5 Flash REST client and Kavenegar SMS adapter with honest `NOT_CONFIGURED` statuses.
- `backend/apps/marketing/views.py`: Hardened abandoned cart recovery with anti-spam cooldown and phone validation.

### Automated Test Suites
- `backend/tests/test_audit_and_security_hardening.py`: 5 tests covering suspended access, privilege escalation, store creation, invite binding, payment verification.
- `backend/tests/test_commerce_integrity_regression.py`: 8 tests covering overselling rejection, POS oversell, duplicate fulfillment idempotency, cancellation rejection, RMA limits, PO AP creation, AP payments, financial CSV exports.
- `backend/tests/test_field_and_features_regression.py`: 5 tests covering audit logging, product title serializations, customer feedback phone, automation rule creators, abandoned cart recovery.
- `backend/tests/test_feature_modularity.py`: 10 tests covering feature registry, DAG validation, tier restrictions, and adapter degradation.

### Frontend Client & Pages
- `frontend/src/lib/api.ts`: JWT auto-refresh on 401 with subscriber queue, `downloadFile` blob helper, corrected endpoint paths.
- `frontend/src/app/page.tsx`: Replaced hardcoded charts with real data bindings and clean empty states.
- `frontend/src/app/orders/page.tsx`: Contract alignment with backend order risk structure.
- `frontend/src/app/payments/page.tsx`: Authenticated CSV report downloads.

---

## 5. Remaining Considerations & Production Guidelines

1. **Third-Party API Credentials:**
   - Production deployments must supply `GEMINI_API_KEY` for Google Gemini AI generation and `KAVENEGAR_API_KEY` for Iranian SMS notifications. If keys are omitted, the system honestly reports `NOT_CONFIGURED` and falls back to deterministic heuristic templates without crashing.
2. **Payment Gateway Credentials:**
   - Real online transactions require Zarinpal, Sadad, or PayPing merchant keys configured per store in `PaymentMethodConfig`. In testing or development, transactions can be manually verified by store owners or managers via the verified payment action.
3. **Database Concurrency:**
   - PostgreSQL 16 is required in production to support row-level locking (`select_for_update`) during high-frequency order placement and stock deduction. SQLite is used strictly for localized unit testing.

---

## 6. Sign-off

The ShopPilot codebase has been audited, modified, hardened, and verified through automated test suites and production build tools. All critical security vulnerabilities, data integrity bugs, and integration simulation gaps have been resolved.
