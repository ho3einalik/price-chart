# ShopPilot — Testing Strategy, Automated Test Suites & CI/CD Pipeline

**Document Version:** 1.0.0 (Production Verified)  
**Classification:** Quality Assurance & Continuous Integration Specification  
**Applies to:** `backend/tests/`, `backend/pytest.ini`, `frontend/`, `.github/workflows/`

---

## 1. Test Architecture Overview

ShopPilot employs a multi-tiered automated testing architecture designed to guarantee multi-tenant security isolation, financial accuracy, inventory ledger consistency, and API contract fidelity.

### Hierarchy of Test Suites
1. **Core Security & Tenancy Isolation Suites:**
   Verify fail-closed header checks, active membership status enforcement, privilege escalation defense, owner protection, and cross-business isolation.
2. **Commerce & Financial Integrity Regression Suites:**
   Verify overselling prevention, POS fast checkout stock deductions, fulfillment idempotency, cancellation guards, RMA cumulative constraints, and AP liability generation.
3. **Feature Modularity & DAG Entitlement Suites:**
   Verify that disabling features preserves data integrity, enforces DAG prerequisite dependencies, and honors subscription tier limits.
4. **Integration & Adapter Resilience Suites:**
   Verify graceful degradation and honest fallback behavior when external providers (Gemini AI, SMS gateways, Instagram API) lack API keys or encounter timeouts.
5. **Frontend Compilation & Contract Suites:**
   Verify TypeScript type safety, Next.js build integrity, and clean static pre-rendering across all 21 client pages.

---

## 2. Test Suite Inventory (55/55 Passing Tests)

| Test Module File | Test Count | Domain Coverage |
| :--- | :---: | :--- |
| `tests/test_audit_and_security_hardening.py` | 5 | Member suspension fail-closed, privilege escalation rejection, cross-business store protection, invitation email binding, payment verification RBAC. |
| `tests/test_commerce_integrity_regression.py` | 8 | Overselling rejection, wholesale POS oversell defense, duplicate order fulfillment idempotency, cancelled fulfilled order rejection, cumulative RMA return quantity validation, supplier PO AP creation, AP payment bounds checking, financial CSV export sanitization. |
| `tests/test_feature_modularity.py` | 10 | Feature registry catalog & DAG validation, tier entitlement restrictions, dependency management, feature toggle data preservation, `RequiresFeature` DRF permissions, social analytics isolation, AI provider heuristic degradation, Instagram & SMS adapter resilience, feature settings API. |
| `tests/test_field_and_features_regression.py` | 5 | Team activity summary & CSV export without field errors, task & social related product serialization, customer feedback phone formatting, automation rule creator binding & dry-run simulation, abandoned cart recovery anti-spam cooldown. |
| `tests/test_full_product_capabilities.py` | 7 | Carrier tracking label idempotency, social order attribution proof, marketing coupon discount calculations, financial gateway settlement reconciliation, demand forecasting, wholesale B2B tiered pricing, audit event notifications. |
| `tests/test_inventory_concurrency.py` | 1 | Inventory ledger double-entry movements, reservation lifecycles, and concurrency locks. |
| `tests/test_marketing_and_intelligence.py` | 3 | Coupon stackability & expiry, CRM RFM segment calculations, order risk assessment heuristics. |
| `tests/test_order_lifecycle.py` | 2 | Order reservation & cancellation lifecycles, order fulfillment sale conversion. |
| `tests/test_payments_and_profit.py` | 1 | Payment transaction verification, net profit calculation after COGS, discounts, and fees. |
| `tests/test_social_operations.py` | 3 | Content approval workflow, engagement rate calculations, social analytics summaries. |
| `tests/test_suppliers_and_returns.py` | 2 | Supplier PO receiving and inventory increment, customer RMA return inspection and restock. |
| `tests/test_tasks.py` | 4 | Task creation with checklist items, verification enforcement on task status change, checklist toggle, task CRUD API endpoints. |
| `tests/test_team_rbac.py` | 3 | Invitation lifecycle & acceptance, member suspension blocking access, granular role permissions. |
| `tests/test_tenancy_isolation.py` | 1 | Strict cross-store product tenant isolation under multi-tenant requests. |
| **Total** | **55** | **100% Pass Rate across entire repository** |

---

## 3. Running Tests Locally

### 3.1 Backend Test Execution
All backend tests must be run from the `backend/` directory where `pytest.ini` is located.

```bash
# Activate virtual environment
cd backend
source venv/bin/activate  # Or on Windows: .\venv\Scripts\Activate.ps1

# Run the complete test suite with verbose output
pytest -v

# Run a specific test module
pytest tests/test_commerce_integrity_regression.py -v

# Run with test coverage report
pytest --cov=apps --cov-report=term-missing
```

### 3.2 Testing Against Real PostgreSQL Database
To run integration tests against a live PostgreSQL 16 container rather than in-memory SQLite:
```bash
# Start test database
docker run -d --name pg-test -e POSTGRES_PASSWORD=testpass -e POSTGRES_DB=test_shoppilot -p 5433:5432 postgres:16-alpine

# Execute tests targeting PostgreSQL
DATABASE_URL=postgres://postgres:testpass@localhost:5433/test_shoppilot pytest -v
```

### 3.3 Frontend Type-Checking & Production Build Verification
```bash
cd frontend
npm run lint
npm run build
```

---

## 4. Continuous Integration (GitHub Actions)

Create `.github/workflows/ci.yml`:

```yaml
name: ShopPilot CI/CD Pipeline

on:
  push:
    branches: [ master, main, develop ]
  pull_request:
    branches: [ master, main ]

jobs:
  backend-tests:
    name: Backend Security & Regression Suite
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: shoppilot_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: testpassword
        ports:
          - 5432:5432
        options: --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: --health-cmd "redis-cli ping" --health-interval 10s --health-timeout 5s --health-retries 5

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
          cache: 'pip'

      - name: Install backend dependencies
        run: |
          cd backend
          python -m pip install --upgrade pip
          pip install -r requirements.txt pytest-cov

      - name: Check database migrations
        env:
          DATABASE_URL: postgres://postgres:testpassword@localhost:5432/shoppilot_test
          DJANGO_SECRET_KEY: ci-testing-secret-key-do-not-use-in-production
        run: |
          cd backend
          python manage.py makemigrations --check --dry-run

      - name: Run automated test suite
        env:
          DATABASE_URL: postgres://postgres:testpassword@localhost:5432/shoppilot_test
          REDIS_URL: redis://localhost:6379/0
          DJANGO_SECRET_KEY: ci-testing-secret-key-do-not-use-in-production
        run: |
          cd backend
          pytest -v --cov=apps --cov-report=xml

  frontend-build:
    name: Frontend Typecheck & Build
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Node.js 20
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run Next.js production build
        run: |
          cd frontend
          npm run build
```

---

## 5. Quality Standards & Merge Requirements

Before merging any code changes to `master`:
1. **Zero Failing Tests:** All 55 tests in `backend/tests/` must pass.
2. **Zero Pending Migrations:** `python manage.py makemigrations --check` must return code 0.
3. **No Unsanitized CSV Exports:** All export endpoints must run values through `sanitize_csv_value`.
4. **No Hardcoded Success Mocks:** All service calls must either interact with real infrastructure or invoke honest degradation modes.
5. **Clean Frontend Compilation:** `npm run build` must compile all routes with zero TypeScript or ESLint errors.
