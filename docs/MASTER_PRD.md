# ShopPilot — Master Product Requirements Document (PRD)

## 1. Executive Summary & Vision
**ShopPilot** is an enterprise-grade, modular, multi-tenant SaaS operations and intelligence platform designed for modern e-commerce and social commerce businesses (particularly Instagram-first sellers, multi-channel merchants, and growing direct-to-consumer brands).

The system serves as the operational central nervous system and decision-support cockpit for store owners, answering five fundamental operational questions:
1. **What is happening in my business?** (Real-time multi-channel overview: orders, inventory, payments, fulfillment)
2. **What needs immediate attention?** (Daily Action Center: stockouts, delayed shipments, failed payments, unverified transfers, customer disputes)
3. **Which products, customers, and channels generate real profit?** (True net margin and unit economics engine incorporating COGS, packaging, shipping, gateway fees, and returns)
4. **What is likely to happen next?** (Predictive intelligence: demand forecasting, lead-time stockout projection, seasonal trends, churn risk)
5. **What action should I take, and what evidence supports that recommendation?** (Actionable, explainable AI recommendations backed by verifiable tenant data)

---

## 2. Target Audience & Market Conventions
- **Primary Market:** Iran & MENA initially, architected for global expansion with locale/currency adapters.
- **Locales & UI Direction:** Full Persian (`fa-IR`) right-to-left (RTL) first, designed for internationalization (i18n) with English (`en-US`).
- **Currency & Minor Units:** Explicit currency configuration:
  - Iranian Toman (IRT) and Iranian Rial (IRR).
  - Explicit rule: **Never mix Rials and Tomans silently**. All monetary values are stored in exact minor units or exact decimal representations with an explicit currency code field (`currency='IRT'` / `currency='IRR'`).
- **Operational Scope vs. Storefront Exclusion:**
  - ShopPilot explicitly **excludes** building generic drag-and-drop website builders or consumer storefront themes.
  - ShopPilot integrates with existing storefronts (WooCommerce, custom APIs, Instagram, Telegram, WhatsApp, Marketplaces).
  - Included operational external customer-facing pages: Hosted Order Tracking, Payment Link checkout, Pro-Forma Invoices / Packing Slips, and Customer Return submission portal.

---

## 3. Core System Capabilities & Scope

| Module | Code | Core Capabilities |
| :--- | :--- | :--- |
| **Tenancy & IAM** | `tenancy`, `accounts` | Multi-business, multi-store, role-based access control (RBAC), fine-grained permissions, audit logging, session isolation. |
| **Catalog** | `catalog` | Products, variants (SKU/barcode), categories, brand, multi-tier pricing (retail/wholesale/cost), bundles, images, custom attributes. |
| **Inventory & Warehouses** | `inventory` | Multiple warehouses/bins, available-to-sell vs reserved vs on-hand vs quarantined, double-entry immutable stock ledger, transactional reservation locking. |
| **Orders & Fulfillment** | `orders`, `fulfillment` | Multi-channel normalized orders, lifecycle state machine, atomic reservations, shipments, multi-package partial fulfillment, packing slips/invoices. |
| **Payments & Reconciliation**| `payments` | Gateway transactions (Zarinpal, etc. adapter-based), manual card-to-card review workflow, partial payments, refunds, idempotent webhooks. |
| **Returns & Exchanges** | `returns` | Return RMA requests, item inspection flow, restocking decisions (quarantine vs sellable), refund allocation. |
| **Suppliers & Purchasing** | `suppliers` | Supplier directory, price agreements, Purchase Orders (PO lifecycle: Draft -> Approved -> Sent -> Partially Received -> Completed), goods receipts. |
| **CRM & Customers** | `crm` | Unified customer profiles, RFM segmentation, LTV calculation, multi-address, purchase history, internal notes. |
| **Social Commerce & Inbox** | `social_inbox`, `messaging`| Instagram DM/Comment workflow, Telegram/WhatsApp adapters, unified agent inbox, AI response suggestions, human takeover safeguards. |
| **Analytics & Profit Engine**| `analytics` | True gross and net profit, contribution margin, COGS snapshots on order items, marketing attribution, channel ROI. |
| **Action Center & Automations**| `daily_actions`, `automation` | Prioritized operational alerts, trigger-condition-action workflow engine, audit trail. |
| **AI Management Assistant** | `ai_assistant` | Grounded, read-only analytical queries over tenant data, explainable reorder and margin recommendations, rate-limited and audit-logged. |

---

## 4. Non-Negotiable Architectural Principles
1. **Strict Multi-Tenant Isolation:** Every operational query and command enforces tenant (`store_id`/`business_id`) ownership in the backend service layer and database filters.
2. **Transactional Integrity & Concurrency:** Pessimistic locking (`select_for_update`) during order inventory reservations to mathematically eliminate overselling.
3. **Double-Entry Stock Ledger:** Inventory is never updated via arbitrary mutable counter increments without a corresponding `InventoryMovement` entry.
4. **Historical Margin Preservation:** Every `OrderItem` captures historical snapshots of unit cost price (`cost_price_snapshot`) at time of purchase.
5. **Adapter Pattern for External Systems:** Payments, shipping carriers, SMS gateways, and messaging platforms are abstracted behind clean interfaces with fallback/mock sandboxes for local testing.
6. **Async Resilience:** High-volume ingestion (webhooks, CSV imports, sync jobs) leverages background tasks with idempotency keys and exponential backoff retries.
