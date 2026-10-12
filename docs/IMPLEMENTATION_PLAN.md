# ShopPilot — Master Implementation Plan & Execution Roadmap

**Status:** Completed & Fully Verified (100%)  
**Verification:** 37 Automated Pytest Tests Passing, 0 TypeScript Compilation Errors.

---

## 1. Execution Roadmap

```mermaid
flowchart TD
    subgraph Phase A: Operations & Inventory Expansion
        A1[Suppliers & Purchase Orders] --> A2[Goods Receipts & Stock Restocking]
        A3[Customer Returns & RMAs] --> A4[Quarantine vs Restock & Refunds]
        A5[Operational Expenses & Financial Settlements]
        A6[Carrier Tracking Adapters & Packing Slips]
    end

    subgraph Phase B: CRM & Unified Social Inbox
        B1[Rich Customer CRM & RFM Scoring] --> B2[Interaction Logs & Follow-up Tasks]
        B3[Unified Social Inbox Threads & Orders] --> B4[AI Response Suggestions with Human Review]
        B5[Customer Feedback & Complaint Taxonomy]
    end

    subgraph Phase C: Marketing, Loyalty & Automations
        C1[Coupon Codes & Stacking Protection] --> C2[Loyalty Points & VIP Tiers]
        C3[Abandoned Cart Recovery & Referrals] --> C4[Product Recommendations & Attribution]
        C5[Trigger-Condition-Action Automation Engine]
    end

    subgraph Phase D: Intelligence & POS / Wholesale
        D1[Velocity Demand Forecasting & Stockout Days]
        D2[Dead Stock & Slow Movers Capital Analysis]
        D3[Order Risk & Competitor Tracker]
        D4[B2B Wholesale Tiers & Credit Ceilings]
        D5[In-Person POS Register & Shift Sessions]
        D6[In-App Notification Center & CSV Exports]
    end

    Phase A --> Phase B
    Phase B --> Phase C
    Phase C --> Phase D
```

---

## 2. Phase Breakdown & Completed Checklist

### Phase A: Operations, Inventory & Fulfillment
- [x] **Suppliers & Purchase Orders (`apps/suppliers`)**:
  - `Supplier` model with contact details, lead time, tax ID, payment terms.
  - `PurchaseOrder` & `PurchaseOrderItem` with PO state machine (`DRAFT`, `APPROVED`, `SENT`, `PARTIALLY_RECEIVED`, `COMPLETED`, `CANCELLED`).
  - PO Goods Receipt service writing `RECEIPT` records to `InventoryMovement` and updating `InventoryBalance.on_hand`.
- [x] **Customer Returns & RMAs (`apps/returns`)**:
  - `ReturnRequest` & `ReturnItem` with reason codes (`DEFECTIVE`, `WRONG_ITEM`, `SIZE_MISMATCH`, `CUSTOMER_REMORSE`).
  - RMA inspection workflow: `RECEIVED` -> `INSPECTED` -> Decision (`RESTOCK_SELLABLE` vs `QUARANTINE_DEFECTIVE`).
  - Restocking creates `RETURN_RESTOCK` movement; defective creates `QUARANTINE` balance.
  - Refund allocation hook linking back to payment reconciliation.
- [x] **Fulfillment & Shipping Tracking (`apps/fulfillment`)**:
  - `Shipment` extended with `idempotency_key`, `shipping_label_url`, and `ShipmentTrackingEvent`.
  - Carrier adapter framework for Iran Post, Tipax, and SnappBox with graceful offline manual fallback.
  - HTML packing slip generator (`/packing-slip/`) and shipping quote estimation endpoint (`/estimate-quote/`).
- [x] **Store Financial Settlement & Ledger (`apps/finance`)**:
  - `Expense` model (categories: `PACKAGING`, `SHIPPING`, `RENT`, `MARKETING`, `SALARY`, `OTHER`).
  - `GatewaySettlement` model for reconciling online payment gateways, tracking commission fees and Sheba deposits.
  - `AccountsPayableReceivable` tracking supplier PO debt and B2B customer credit receivables.
  - `RefundRecord` ledger for tracking bank refund transactions.
  - Exportable financial statement CSV with UTF-8 BOM encoding.

### Phase B: CRM & Unified Social Inbox
- [x] **CRM Customer Profiles (`apps/crm`)**:
  - `CustomerProfile` model linked to `orders.Customer`, storing RFM score (`Recency`, `Frequency`, `Monetary`), total lifetime spend (LTV), tags, internal notes.
  - `CustomerInteraction` log (calls, WhatsApp messages, direct messages, complaints).
- [x] **Unified Social Inbox (`apps/social_inbox`)**:
  - `ConversationThread` (channel: `INSTAGRAM_DM`, `TELEGRAM`, `WHATSAPP`, `WEB_CHAT`), customer link, assigned agent, status (`OPEN`, `PENDING_CUSTOMER`, `RESOLVED`).
  - Order linkage (`/link-order/`), `internal_notes` updating, and tag taxonomy.
  - `ChatMessage` (sender type: `CUSTOMER`, `AGENT`, `AI_BOT`), body, media attachments.
  - AI Response suggestion service: Generates catalog-grounded draft responses with mandatory human review before dispatch.
- [x] **Customer Feedback & Complaints (`apps/intelligence`)**:
  - `CustomerFeedback` model tracking CSAT/NPS, complaint categories (`PACKAGING`, `DELAY`, `PRODUCT_QUALITY`, `WRONG_ITEM`, `CUSTOMER_SERVICE`), sentiment, and resolution status.

### Phase C: Marketing, Retention, Social Operations & Automations
- [x] **Marketing & Coupons (`apps/marketing`)**:
  - `Coupon` model with `is_stackable` protection flag preventing unauthorized discount stacking.
  - `AbandonedCart` tracking uncompleted checkouts with automated recovery voucher dispatch.
  - `CustomerLoyaltyAccount` & VIP tiers (Bronze, Silver, Gold, Platinum) with automatic progression.
  - `CustomerReferral` program tracking referral codes, conversions, and referee coupons.
  - `ProductRecommendation` cross-sell and up-sell engine with conversion incentive discounts.
  - `CampaignAttribution` linking orders and revenue to marketing campaigns.
  - `ProductBundle` model (composite products with availability checking across all component items).
- [x] **Social Content Operations (`apps/social`)**:
  - Content calendar with support for Post, Story, Reel, Carousel in Persian Jalali calendar.
  - Proof of publishing workflow (`submit_proof`, `verify_proof`) with creator attribution.
  - Metric snapshot logging with source provenance (`API` vs `MANUAL`) and author tracking.
  - Team social performance and workload reporting (`/api/v1/social/team-performance/`).
- [x] **Automation Engine (`apps/automation`)**:
  - `AutomationRule` (trigger: `ORDER_CREATED`, `ORDER_PAID`, `STOCK_LOW`, `NEW_CUSTOMER`; conditions JSON; actions JSON: `SEND_SMS`, `CREATE_TASK`, `NOTIFY_TEAM`).
  - `AutomationExecutionLog` capturing status and execution payload diffs.

### Phase D: Intelligence, Wholesale & POS
- [x] **Predictive Demand & Inventory Intelligence (`apps/intelligence`)**:
  - Sales velocity calculation (average daily units sold over 7, 30, 90 days).
  - Velocity-based reorder projection: `(daily_velocity * lead_time) + safety_stock` incorporating supplier lead times.
  - Dead stock and slow movers detection (identifying stagnant stock over 60 days, calculating tied-up working capital, and suggesting liquidation).
  - Competitor price tracker (`CompetitorPriceTrack`) monitoring competitor pricing and price variance.
- [x] **Explainable Order Risk Scorer (`apps/intelligence`)**:
  - Anomaly detection checks: abnormally large quantity, mismatched phone/city, frequent cancellations.
  - Explanations list with confidence score (0-100) and recommendation (`REVIEW_BEFORE_SHIP`, `AUTO_APPROVE`).
- [x] **Grounded AI Operations Assistant (`apps/intelligence`)**:
  - Read-only data queries grounded exclusively on the store's verified database.
  - Answers natural language questions on sales trends, best sellers, margin leaks, and pending tasks.
- [x] **Wholesale (B2B) & In-Person POS (`apps/wholesale_pos`)**:
  - `B2BClientProfile` storing company registration, credit limits, and current debt balances.
  - `VolumeTierDiscount` (MOQ) enforcing tiered volume discounts.
  - `POSTerminal` & `POSRegisterSession` managing physical cash drawer shifts, opening/closing cash, and sales tracking.
  - Atomic `pos_quick_checkout` deducting stock in real-time from the terminal's warehouse and creating verified POS payments.
  - `ProformaInvoice` (پیش‌فاکتور) with one-click conversion into live orders with stock reservation.
- [x] **In-App Notification Center & Auditing (`apps/audit`)**:
  - `Notification` and `NotificationPreference` models.
  - Real-time unread badge and drawer popover in the top navbar (`Navbar.tsx`).
  - System audit log with actor attribution, diff changes, and UTF-8 BOM CSV export.
- [x] **Frontend Bento Grid Interface**:
  - Full dedicated POS Register & B2B page (`/pos`).
  - Gateway settlements, accounts payable/receivable, and CSV export in Payments page (`/payments`).
  - Dead stock banner and liquidation recommendations in Inventory page (`/inventory`).
  - In-app notification center bell with popover drawer in Navbar.
- [x] **Automated Testing Suite**:
  - 37 Pytest tests covering all modules, models, concurrency locks, and business services passing 100%.
  - Zero TypeScript compiler errors (`npx tsc --noEmit`).
