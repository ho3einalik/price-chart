# ShopPilot — Master Implementation Plan

This implementation plan outlines the dependency-aware sequence for engineering the full ShopPilot SaaS platform, from repository initialization through Phase 1 MVP and subsequent phases.

---

## Phase Status Summary

| Phase | Description | Status | Target Deliverables |
| :--- | :--- | :--- | :--- |
| **Phase 0** | Inspection & Technical Architecture | **COMPLETED** | System specs, PRD, Architecture, Implementation Plan, Docker configs. |
| **Phase 1** | Working Operational MVP | **IN PROGRESS** | Multi-tenancy, Catalog, Warehouses, Inventory Ledger, Orders, Payments, Shipments, CSV import, Dashboard, Action Center, Tests. |
| **Phase 2** | Store Operations & Integrations | **PLANNED** | Returns & RMAs, Suppliers & Purchase Orders, Carrier/Payment Adapters, WooCommerce sync, Notifications. |
| **Phase 3** | Social Commerce & CRM Growth | **PLANNED** | Unified Social Inbox, Instagram DM/Comments, WhatsApp/Telegram adapters, AI sales assistant, Loyalty & Campaigns. |
| **Phase 4** | Intelligence & Profit Engine | **PLANNED** | Net margin breakdown, Inventory demand forecasting, Competitor tracking, Feedback sentiment, Order risk anomaly detection. |
| **Phase 5** | Workflows & AI Management | **PLANNED** | Workflow automation engine, AI conversational management assistant, POS/B2B wholesale, PDF reports. |

---

## Detailed Phase 1: Operational MVP Breakdown

### 1. Backend Core Setup (`backend/`)
1. **Django Project & Configuration:**
   - Django 5.x / Python 3.13 configuration in `backend/config/`.
   - Settings supporting PostgreSQL (with SQLite development fallback for standalone testing).
   - DRF with versioned router at `/api/v1/`.
   - JWT authentication (`djangorestframework-simplejwt`), CORS, and standard error handling.

2. **Accounts & Tenancy (`accounts`, `tenancy`, `audit`):**
   - Custom `User` model (email/phone identity).
   - `Business`, `Store`, `StoreMembership`, `Role` (Owner, Admin, Ops Manager, Staff, etc.).
   - Tenant middleware and DRF permission classes enforcing `store_id` isolation.
   - `AuditLog` model recording actor, action, timestamp, and metadata.

3. **Catalog Module (`catalog`):**
   - `Category`, `Product`, `ProductVariant` (SKU, barcode, weight, dimensions).
   - Multi-tier pricing (cost price, retail price, wholesale price) with explicit currency (`IRT` / `IRR`).
   - Image and attribute management.

4. **Inventory & Warehouses (`inventory`):**
   - `Warehouse`, `WarehouseLocation`.
   - `InventoryBalance` (on-hand, reserved, available, quarantined).
   - `InventoryMovement` (immutable audit ledger for receipts, adjustments, transfers, reservations).
   - Concurrency-safe atomic reservation service with pessimistic row locking.

5. **Orders & Fulfillment (`orders`, `fulfillment`):**
   - `Customer`, `CustomerAddress`.
   - `Order` state machine: Draft -> Confirmed -> Processing -> Partially Fulfilled -> Fulfilled -> Completed / Cancelled.
   - `OrderItem` with `cost_price_snapshot`.
   - `Shipment` and `ShipmentPackage` with tracking numbers and event history.
   - CSV / Excel guided import service with row validation and error reporting.

6. **Payments (`payments`):**
   - `PaymentTransaction` supporting gateway and manual card-to-card tracking.
   - Verification status: Pending -> Verified / Rejected.
   - Support for partial payments and refunds.

7. **Daily Action Center & Dashboard Analytics (`daily_actions`, `analytics`):**
   - Real-time aggregation of Gross Sales, Net Sales, Order Volume, AOV, Estimated Gross Profit.
   - Action Center alerts: Low Stock, Delayed Orders, Pending Card-to-Card Verification.

8. **Comprehensive Automated Test Suite (`tests/`):**
   - Multi-tenant boundary isolation tests (Tenant A cannot see Tenant B).
   - Concurrency overselling tests.
   - Order lifecycle and stock reservation release tests.
   - Cost snapshot and profit calculation tests.

---

### 2. Frontend Modern Web Application (`frontend/`)
1. **Next.js 14 App Router Setup:**
   - TypeScript, Tailwind CSS, Lucide icons.
   - Native RTL support for Persian (`dir="rtl"`, Vazirmatn/font setup).
2. **State & Context Management:**
   - AuthContext (JWT tokens, login/register).
   - StoreContext (active store selection, store switcher, permissions).
3. **Core Interactive Views:**
   - **Authentication:** Login, Registration, Store Creation.
   - **Dashboard & Daily Action Center:** Key KPI cards, Action Center alerts with dismissal/resolution actions, sales charts.
   - **Catalog Management:** Product listing, SKU search, variant details, stock levels.
   - **Inventory Management:** Warehouse balance overview, quick manual adjustments with reason tracking.
   - **Order Cockpit:** Normalized order table, status filters, order detail drawer, customer info, fulfillment and payment status.
   - **Payment Verification:** Review queue for manual card-to-card receipts with approve/reject workflow.
