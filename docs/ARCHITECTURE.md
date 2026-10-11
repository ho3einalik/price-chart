# ShopPilot — Architecture Specification

## 1. High-Level Architecture (Modular Monolith)

ShopPilot is architected as a clean **Modular Monolith** with well-isolated business domain boundaries. This avoids premature microservice overhead while enforcing strict module separation, explicit domain contracts, and independent schema evolution.

```
                    +------------------------------------------+
                    |           Next.js 14 Frontend            |
                    |   (TypeScript, TailwindCSS, RTL/fa-IR)   |
                    +--------------------+---------------------+
                                         | REST API (/api/v1/)
                                         v
+-----------------------------------------------------------------------------------+
|                            Django & DRF Backend                                  |
|                                                                                   |
|  [ Tenancy & IAM ]      [ Catalog Module ]       [ Inventory & Warehouses ]       |
|  - Business/Store       - Products & Variants    - Multi-warehouse ledger         |
|  - RBAC & Memberships   - Pricing & Categories   - Safe reservation locking       |
|                                                                                   |
|  [ Orders & Fulfillment] [ Payments & Billing ]   [ Shipping & Carriers ]         |
|  - State Machine         - Gateways / Webhooks    - Tracking & Invoices           |
|  - Items & Snapshots     - Card-to-Card Review    - Label generation              |
|                                                                                   |
|  [ CRM & Customers ]    [ Analytics Engine ]     [ Daily Action Center ]          |
|  - Profiles & RFM       - True COGS & Profit     - Operational alerts             |
|  - Segments & LTV       - Metrics & Snapshots    - Prioritized recommendations    |
|                                                                                   |
|  [ Integrations Engine ][ Workflow Automations ] [ AI Assistant Tools ]           |
|  - Adapters (Woo/IG/SMS)- Event-driven triggers  - Read-only grounded queries     |
+--------------------------+-----------------------+--------------------------------+
                           |                       |
                           v                       v
               +-----------------------+ +---------------------+
               | PostgreSQL Database   | | Redis & Celery      |
               | (Multi-tenant schemas | | (Async background   |
               |  with store scoping)  | |  tasks & caching)   |
               +-----------------------+ +---------------------+
```

---

## 2. Directory Structure

```
onlineshop/
├── backend/
│   ├── manage.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── apps/
│   │   ├── accounts/          # Custom User model, auth, sessions
│   │   ├── tenancy/           # Business, Store, StoreMembership, RBAC
│   │   ├── catalog/           # Products, Variants, Categories, Pricing
│   │   ├── inventory/         # Warehouses, InventoryBalance, Ledger, Reservations
│   │   ├── orders/            # Orders, OrderItems, State Transitions, CSV imports
│   │   ├── payments/          # Payment transactions, Gateway adapters, Verification
│   │   ├── fulfillment/       # Shipments, Packages, Tracking events, Invoices
│   │   ├── returns/           # ReturnRequests, Inspections, Restocking, Refunds
│   │   ├── crm/               # Customers, Segments, Addresses, Activity
│   │   ├── suppliers/         # Suppliers, PurchaseOrders, Goods Receipts
│   │   ├── analytics/         # Sales, Profit Engine, Cohorts, Trends
│   │   ├── daily_actions/     # Action Center, Operational Alerts, Evidence
│   │   ├── integrations/      # Channel adapters (WooCommerce, Instagram, Telegram)
│   │   ├── automation/        # Workflow rules (Trigger -> Condition -> Action)
│   │   ├── ai_assistant/      # Grounded LLM tools, context retrieval, audit
│   │   └── audit/             # System-wide audit log for compliance
│   └── tests/                 # Comprehensive pytest test suite
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.mjs
│   ├── src/
│   │   ├── app/               # Next.js App Router (Persian RTL layouts)
│   │   ├── components/        # UI components (Buttons, Modals, Tables, Forms)
│   │   ├── contexts/          # AuthContext, StoreContext, LocaleContext
│   │   ├── lib/               # API client, Currency formatters (Toman/Rial), date helpers
│   │   └── types/             # TypeScript domain interfaces
├── docs/                      # Master PRD, Architecture, Implementation Plan
├── docker-compose.yml         # Containerized development orchestration
├── .env.example               # Environment variables template
└── README.md
```

---

## 3. Data Integrity & Security Invariants

### 3.1 Strict Multi-Tenancy Enforcement
- All tenant-owned models inherit from a common base model (`TenantScopedModel`) which enforces `store_id` foreign key.
- DRF ViewSets use a mandatory `TenantFilterBackend` and `IsStoreMemberPermission` ensuring requests without an active authorized `X-Store-Id` header (or store query parameter) are rejected with `403 Forbidden`.
- Every mutation (Create, Update, Delete) validates that the object being manipulated belongs strictly to the authenticated user's active store membership.

### 3.2 Inventory Concurrency & Overselling Prevention
- Available-to-sell formula:
  $$\text{Available} = \text{On-Hand} - \text{Reserved} - \text{Quarantined}$$
- Order reservation uses atomic transactions with row-level locking:
  ```python
  balance = InventoryBalance.objects.select_for_update().get(
      warehouse=warehouse, variant=variant, store=store
  )
  if balance.available < requested_qty:
      raise InsufficientInventoryError(...)
  balance.reserved_quantity += requested_qty
  balance.save()
  InventoryMovement.objects.create(...)
  ```
- No stock is deducted or reserved without an immutable ledger entry in `InventoryMovement`.

### 3.3 Historical Cost & Profit Accuracy
- When an order is placed, the current `cost_price` of each variant is captured into `OrderItem.cost_price_snapshot`.
- Gross Margin formula:
  $$\text{Gross Margin} = \sum (\text{Selling Price} - \text{Unit Discount} - \text{Cost Price Snapshot}) \times \text{Quantity}$$
- Calculated net profit explicitly accounts for item costs, shipping paid vs actual cost, packaging expenses, gateway processing fees, and returned items.
