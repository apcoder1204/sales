# Wateja na Madeni — Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Customers, credit at checkout (split/partial/credit), debt payments with allocation, reversals, old debts, and closing/report figures driven by real payments, with a customer ledger written alongside every money event.

**Architecture:** New `customers`, `payments`, `payment_allocations`, `opening_balances`, `customer_ledger_entries` tables (additive migration). Every shilling received is a `payments` row allocated to the receivable it settles; every change to what a customer owes is also an append-only ledger row, written in the same transaction. Closing and payment breakdowns read `payments`; P&L code is untouched.

**Tech Stack:** FastAPI, async SQLAlchemy 2 (asyncpg), Alembic, PostgreSQL 16, Pydantic v2, pytest (`.venv/bin/python -m pytest` from `backend/`); React 18 + Vite, axios, jsPDF.

**Spec:** `docs/superpowers/specs/2026-11-25-customer-debt-management-design.md` (approved 2026-11-25) — stage 1 = spec §6, §9, §10, §11.

## Global Constraints

- Money: `Numeric(14,2)` in DB, `Decimal` in Python; never `float` in new code paths (existing float-returning helpers may keep their response shape).
- New status/kind fields: `String` + `CheckConstraint`; **no new Postgres enum types, no `ALTER TYPE`**. Payment methods reuse the existing `payment_method_enum` (`cash`, `mobile_money`, `bank_transfer`) via `SAEnum(..., name="payment_method_enum", create_type=False)`.
- Audit category: reuse `"sales"` for every new audit action (no enum change).
- Errors: flat `{detail, code, params}`; every new code gets a `makosa.msimbo` entry in `frontend/src/constants/translations/sw.js` and `en.js`.
- Branch authorization only through `app/core/authorization.py` helpers; branch-scoped users get their branch forced; another branch's sale/payment/receivable → `NotFoundException` (404), matching `get_sale_for_viewing`.
- Business dates only via `app/core/business_time.py` (`business_date_today`, `business_date_for`, `utcnow`). Naive UTC datetimes in DB (`.replace(tzinfo=None)`).
- Migration is **additive**; existing rows only gain backfilled `payments`/`payment_allocations` (spec §10). `sales.payment_method`/`payment_reference` become nullable, are not dropped, not written for new sales, and not read by code after Task 9.
- Ledger sign: `debit` increases what the customer owes, `credit` decreases; exactly one of the two > 0 per row.
- Ledger rows are never updated/deleted by application code; a DB trigger enforces it, bypassable only with `SET LOCAL dukani.ledger_maintenance = 'on'` (used by test cleanup and demo reset).
- All UI strings via `SW.*` (sw.js + en.js); spec §30 terms: Mteja/Customer, Wateja/Customers, Deni/Debt, Madeni/Debts, Salio la Deni/Outstanding Balance, Malipo/Payment, Malipo ya Sehemu/Partial Payment, Kikomo cha Mkopo/Credit Limit, Yaliyochelewa/Overdue.
- Error codes and HTTP statuses (one table, used by every task):

| code | status | params |
|---|---|---|
| CUSTOMER_PHONE_DUPLICATE | 409 | — |
| CUSTOMER_INACTIVE | 400 | — |
| CREDIT_REQUIRES_CUSTOMER | 400 | — |
| CREDIT_NOT_ALLOWED | 400 | — (limit is 0) |
| CREDIT_LIMIT_EXCEEDED | 422 | `{limit, current, requested, available}` (strings of whole TZS) |
| PAYMENT_EXCEEDS_TOTAL | 400 | — |
| PAYMENT_EXCEEDS_DEBT | 400 | `{owed}` |
| ALLOCATION_INVALID | 400 | — |
| ALLOCATION_MISMATCH | 400 | — |
| SALE_HAS_DEBT_PAYMENTS | 400 | — |
| PAYMENT_ALREADY_REVERSED | 400 | — |
| SALE_PAYMENT_USE_VOID | 400 | — |
| OPENING_BALANCE_DUPLICATE | 409 | — |
| OPENING_BALANCE_SELF_DECISION | 403 | — |
| OPENING_BALANCE_NOT_PENDING | 400 | — |

## Review Focus

1. **Legacy checkout payload** — browsers holding the pre-deploy JS bundle still POST `{payment_method, payment_reference}`; it must keep working as one full payment (Task 4, `test_legacy_payload_still_sells`).
2. **Nightly demo reset** — `seed_demo._wipe_generated_data` runs `DELETE` on sales at 03:00; new FK tables and the ledger trigger would break it (Task 9, `test_demo_wipe_handles_debt_tables`).
3. **Voided sale with customer then statement balance** — void must net the customer balance to exactly what it was before the sale (Task 5, `test_void_credit_sale_restores_balance`).
4. **Debt payment on a day whose register is closed** at that branch — refused, not silently counted in a closed closing (Task 6, `test_debt_payment_refused_when_day_closed`).
5. **Customer with debt at two branches; cashier at branch B** — sees B's receivables only, can't allocate to A's sale even by posting A's sale id (Task 6, `test_cashier_cannot_allocate_other_branch_sale`).

---

## File map

Backend (`backend/`):
- `app/models/customer.py` — `Customer`
- `app/models/payment.py` — `Payment`, `PaymentAllocation`
- `app/models/opening_balance.py` — `OpeningBalance`
- `app/models/customer_ledger.py` — `CustomerLedgerEntry`
- `app/models/sale.py`, `app/models/daily_closing.py` — new columns
- `app/db/base.py` — register models
- `alembic/versions/c0d1e2f3a4b5_customer_debt_stage1.py` — down_revision `f1a2b3c4d5e6`
- `app/core/exceptions.py` — `DebtException`, `debt_error(code, params=None)`
- `app/schemas/customer.py`, `app/schemas/payment.py` (new); `app/schemas/sale.py`, `app/schemas/daily_closing.py`, `app/schemas/report.py` — extended
- `app/services/ledger_service.py` — balances, receivables, posting, customer lock
- `app/services/customer_service.py`
- `app/services/payment_service.py` — debt payments, reversals, receipts, numbering
- `app/services/opening_balance_service.py`
- `app/services/sale_service.py`, `daily_closing_service.py`, `report_service.py`, `app/repositories/sale_repo.py`, `app/api/v1/reports.py` — modified
- `app/api/v1/customers.py`, `payments.py`, `opening_balances.py`; `router.py`
- `app/db/seed_demo.py` — wipe + payments + demo customers
- Tests: `tests/test_debt_schema.py`, `test_customers.py`, `test_ledger_service.py`, `test_credit_sales.py`, `test_credit_sales_true_concurrency.py`, `test_sale_void_credit.py`, `test_debt_payments.py`, `test_debt_payments_true_concurrency.py`, `test_payment_reversal.py`, `test_opening_balances.py`, `test_closing_payments.py`, `test_debt_acceptance.py`; `conftest.py` gains `make_customer`.

Frontend (`frontend/src/`):
- `services/customerService.js`, `services/paymentService.js`
- `features/pos/CheckoutModal.jsx`, `features/pos/CustomerPicker.jsx` (new), `features/pos/ReceiptModal.jsx`
- `features/customers/CustomersPage.jsx`, `CustomerDetail.jsx`, `CustomerFormModal.jsx`, `RecordPaymentModal.jsx`, `PaymentReceiptModal.jsx`, `OpeningBalancesPage.jsx`
- `features/sales/SalesPage.jsx`, `features/closing/ClosingPage.jsx`
- `routes/AppRouter.jsx`, `components/layout/Sidebar.jsx`, `utils/permissions.js`
- `constants/translations/sw.js`, `en.js`

---

### Task 1: Schema, migration, ledger guard

**Files:** models above, `app/db/base.py`, migration, `tests/test_debt_schema.py`, `tests/conftest.py`

**Interfaces — Produces:**
- `Customer(id, customer_no, name, phone, email, address, customer_type, tin, credit_limit, credit_days, status, notes, created_by, created_at, updated_at)` — CHECKs: `customer_type IN ('individual','business','institution','government')`, `status IN ('active','inactive')`, `credit_limit >= 0`, `credit_days BETWEEN 0 AND 365`; UNIQUE `phone`, UNIQUE `customer_no`.
- `Payment(id, payment_no, kind, customer_id, branch_id, method, reference, amount, business_date, received_by, notes, status, reversed_by, reversed_at, reversal_reason, balance_before, balance_after, created_at)` — CHECKs: `kind IN ('sale','debt')`, `status IN ('active','reversed')`, `amount > 0`, `kind <> 'debt' OR customer_id IS NOT NULL`. `balance_before/after` nullable Numeric: receipt snapshot for debt payments (branch balance), informational only. Relationship `allocations` (selectin).
- `PaymentAllocation(id, payment_id, sale_id, opening_balance_id, amount)` — CHECKs: `amount > 0`, `(sale_id IS NULL) <> (opening_balance_id IS NULL)`; UNIQUE `(payment_id, sale_id)`, `(payment_id, opening_balance_id)`.
- `OpeningBalance(id, customer_id, branch_id, amount, effective_date, due_date, reference, description, status, entered_by, decided_by, decided_at, decision_note, created_at)` — CHECKs: `amount > 0`, `status IN ('pending','approved','rejected')`, `decided_by IS NULL OR decided_by <> entered_by`.
- `CustomerLedgerEntry(id, customer_id, branch_id, entry_type, source_type, source_id, debit, credit, business_date, due_date, description, reverses_entry_id, created_by, created_at)` — CHECKs: `entry_type IN ('sale','payment','payment_reversal','sale_void','opening_balance')`, `debit >= 0 AND credit >= 0 AND (debit > 0) <> (credit > 0)`; UNIQUE `(source_type, source_id, entry_type)`.
- `Sale.customer_id` (nullable FK, relationship `customer` selectin), `Sale.due_date` (nullable Date); `Sale.payment_method`/`payment_reference` nullable. `Sale.payments` relationship is NOT added (query via allocations).
- `DailyClosing.total_credit_given`, `total_debt_collected` Numeric(14,2) NOT NULL server_default 0.
- Sequences `seq_customer_number`, `seq_payment_number`.
- Trigger `trg_ledger_append_only` (BEFORE UPDATE OR DELETE, FOR EACH ROW) raising `'customer_ledger_entries is append-only'` unless `current_setting('dukani.ledger_maintenance', true) = 'on'`.
- Indexes: ledger `(customer_id, branch_id)`, payments `(branch_id, created_at)`, payments `(customer_id)`, allocations `(sale_id)`, `(opening_balance_id)`, sales `(customer_id)`.
- Backfill in `upgrade()`: for each existing sale one `payments` row (`kind='sale'`, `payment_no='PAY-'||to_char(created_at + interval '3 hours','YYYYMMDD')||'-'||lpad(nextval('seq_payment_number')::text,4,'0')`, method/reference/amount=total_amount/branch/created_at, `business_date=(created_at + interval '3 hours')::date`, `received_by=cashier_id`, `status = CASE WHEN sale.status='voided' THEN 'reversed' ELSE 'active' END`, reversal fields copied from void fields) plus one allocation for the full amount. Single `INSERT ... SELECT` statements.
- `downgrade()`: restore `sales.payment_method/payment_reference` from each sale's first payment where null, set them NOT NULL again, drop trigger/function, tables, columns, sequences.
- `tests/conftest.py`: `async def make_customer(db, *, credit_limit=Decimal("0"), credit_days=30, status="active", phone=None) -> Customer` (unique random 2557XXXXXXXX phone, `customer_no` from `nextval('seq_customer_number')`).

- [ ] **Step 1: Write failing tests** in `tests/test_debt_schema.py`:
  - `test_ledger_update_rejected` — insert a ledger row (via `make_customer`, `make_branch`, debit 100), `UPDATE ... SET debit=200` raises `DBAPIError` whose text contains `append-only`.
  - `test_ledger_delete_rejected` — same for `DELETE`.
  - `test_ledger_delete_allowed_in_maintenance` — `SET LOCAL dukani.ledger_maintenance = 'on'` then `DELETE` succeeds.
  - `test_ledger_requires_exactly_one_side` — debit=0, credit=0 → IntegrityError; debit=10, credit=10 → IntegrityError.
  - `test_debt_payment_requires_customer` — `Payment(kind='debt', customer_id=None, ...)` flush → IntegrityError.
  - `test_allocation_exactly_one_target` — both null → IntegrityError.
  - `test_customer_phone_unique` — two customers same phone → IntegrityError.
  - Wrap each expected DB error in `async with db_session.begin_nested()` so the outer test transaction survives.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_debt_schema.py -v` — Expected: FAIL (import errors: models don't exist).
- [ ] **Step 3: Implement models, register in `app/db/base.py`, write migration.** Run `.venv/bin/alembic upgrade head` against the dev DB.
- [ ] **Step 4: Verify backfill** — `psql` (or a short python one-off) on dev DB: `SELECT count(*) FROM sales` = `SELECT count(*) FROM payments WHERE kind='sale'` = `SELECT count(*) FROM payment_allocations`; and `SELECT count(*) FROM sales s JOIN payment_allocations a ON a.sale_id=s.id WHERE a.amount <> s.total_amount` = 0. Then `.venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head` — Expected: both succeed, counts equal again.
- [ ] **Step 5: Run** the schema tests — Expected: PASS. Run full suite — Expected: all pass (Sale nullable columns don't break existing tests).
- [ ] **Step 6: Commit** `feat(debt): customer/payment/ledger schema with append-only guard`.

### Task 2: Customer master

**Files:** `app/schemas/customer.py`, `app/services/customer_service.py`, `app/api/v1/customers.py`, `router.py`, `app/core/exceptions.py`, `tests/test_customers.py`

**Interfaces:**
- Consumes: Task 1 models; `normalize_phone` from `app/services/whatsapp_service.py` (move it to `app/core/phone.py` and re-export from whatsapp_service so existing imports keep working).
- Produces:
  - `DebtException(AppException)`; `debt_error(code: str, params: dict | None = None) -> DebtException` using the Global Constraints table (detail = Swahili message, one per code).
  - Schemas: `CustomerCreate{name 2–150, phone, email?, address? ≤255, customer_type='individual', tin? ≤30, notes? ≤500}`; `CustomerUpdate` (same fields, all optional); `CustomerCreditUpdate{credit_limit: Decimal ≥0, credit_days: int 0–365, status: 'active'|'inactive', reason: 5–500}`; `CustomerResponse{id, customer_no, name, phone, email, address, customer_type, tin, credit_limit, credit_days, status, notes, created_at}`; `CustomerSummary{balance: Decimal, overdue: Decimal, available_credit: Decimal, last_payment_at: datetime|None}`; `CustomerDetailResponse{customer: CustomerResponse, summary: CustomerSummary}`.
  - `customer_service.create(db, data, user) -> Customer`, `update(db, customer_id, data, user) -> Customer`, `update_credit(db, customer_id, data, user) -> Customer`, `search(db, q, status, page, per_page) -> (list[Customer], total)`, `get_detail(db, customer_id, user) -> CustomerDetailResponse` (summary computed in Task 3 — until then return zeros; Task 3 wires it).
  - Routes: `GET /customers` (all roles except store_keeper), `POST /customers` (cashier, admin, super_admin), `GET /customers/{id}` (all except store_keeper), `PUT /customers/{id}` (cashier, admin, super_admin), `PUT /customers/{id}/credit` (admin, super_admin). No DELETE route.
  - Audit actions: `CUSTOMER_CREATED`, `CUSTOMER_UPDATED` (details: changed field names + old/new), `CUSTOMER_CREDIT_CHANGED` (details: old/new limit, old/new days, old/new status, current exposure (Task 3 balance; 0 until wired), reason).
  - Search `q` matches `name ILIKE %q%`, `phone` contains digits of q, `customer_no ILIKE`, or a sale `transaction_no = q` linked to the customer.

- [ ] **Step 1: Failing tests** `tests/test_customers.py`:
  - `test_cashier_creates_customer` — 201, phone `0712345678` stored as `255712345678`, `customer_no` matches `^CUS-\d{4,}$`, `credit_limit == "0.00"`, audit `CUSTOMER_CREATED` exists.
  - `test_duplicate_phone_rejected` — second create with `+255 712 345 678` → 409 `CUSTOMER_PHONE_DUPLICATE`.
  - `test_invalid_phone_rejected` — `"12ab"` → 422.
  - `test_search_by_name_phone_number` — finds by partial name, by `0712`, by `customer_no`.
  - `test_cashier_cannot_change_credit` — `PUT /customers/{id}/credit` as cashier → 403.
  - `test_admin_changes_credit_audited` — 200; audit `CUSTOMER_CREDIT_CHANGED` details has `old_limit "0.00"`, `new_limit "2000000.00"`, `reason`.
  - `test_cashier_update_cannot_touch_credit_fields` — `PUT /customers/{id}` with `credit_limit` in body → field ignored (schema has no such field; value unchanged).
  - `test_store_keeper_cannot_list_customers` — 403.
  - `test_no_delete_route` — `DELETE /customers/{id}` → 405.
  - `test_deactivate_customer` — admin sets `status=inactive`; GET shows inactive.
- [ ] **Step 2: Run** — Expected: FAIL (404 routes).
- [ ] **Step 3: Implement** schemas, service, routes, `debt_error`, phone helper move.
- [ ] **Step 4: Run** `tests/test_customers.py` and `tests/test_whatsapp_settings.py` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(debt): customer master records`.

### Task 3: Ledger service (balances, receivables, posting)

**Files:** `app/services/ledger_service.py`, `tests/test_ledger_service.py`; wire summary into `customer_service.get_detail` and exposure into `update_credit`.

**Interfaces — Produces** (`app/services/ledger_service.py`):
- `@dataclass Receivable: kind: Literal['sale','opening_balance']; id: UUID; reference: str; branch_id: UUID; branch_name: str; date: date; due_date: date | None; amount: Decimal; paid: Decimal; outstanding: Decimal; status: str`
  - `reference` = sale `transaction_no`, or `"DENI-ZAMANI " + opening_balance.reference`.
- `def receivable_status(amount: Decimal, outstanding: Decimal, due_date: date | None, today: date) -> str` → `'PAID'` if outstanding == 0; `'OVERDUE'` if outstanding > 0 and due_date and due_date < today; `'UNPAID'` if outstanding == amount; else `'PARTIALLY_PAID'`.
- `async def customer_balance(db, customer_id: UUID, branch_id: UUID | None = None) -> Decimal` — Σdebit − Σcredit from ledger.
- `async def receivables(db, customer_id: UUID, branch_id: UUID | None = None, open_only: bool = True) -> list[Receivable]` — completed sales with this customer + approved opening balances; `paid` = Σ allocations whose payment `status='active'`; ordered FIFO: `due_date ASC NULLS LAST, date ASC, reference ASC`.
- `async def lock_customer(db, customer_id: UUID) -> Customer` — `SELECT ... FOR UPDATE`; `NotFoundException("Mteja","customer")` if missing.
- `async def post(db, *, customer_id, branch_id, entry_type, source_type, source_id, business_date, description, created_by, debit=Decimal("0"), credit=Decimal("0"), due_date=None, reverses_entry_id=None) -> CustomerLedgerEntry` (flush, no commit).
- `async def summary(db, customer: Customer, branch_id: UUID | None) -> CustomerSummary` — `balance`/`overdue` scoped to `branch_id`; `available_credit = max(0, credit_limit − customer_balance(all branches))`; `last_payment_at` of active debt payments in scope.
- `customer_service.get_detail` passes `resolve_read_branch_id(db, user, None)` as scope (cashier → own branch; global → all).

- [ ] **Step 1: Failing tests** `tests/test_ledger_service.py`:
  - `test_receivable_status_table` — parametrized: (100,0,None)→PAID; (100,100,future)→UNPAID; (100,40,future)→PARTIALLY_PAID; (100,40,yesterday)→OVERDUE; (100,100,None)→UNPAID.
  - `test_balance_is_debits_minus_credits` — post debit 500, credit 200 → 300; scoped to other branch → 0.
  - `test_receivables_ignore_reversed_payment_allocations` — build a sale (direct model inserts) total 400, a `kind='debt'` payment 100 allocated, marked `reversed` → receivable outstanding 400.
  - `test_cashier_sees_branch_scoped_summary_but_global_available_credit` — customer limit 1,000,000; ledger debit 300,000 at branch A and 200,000 at branch B; cashier of B GETs `/customers/{id}` → `summary.balance == "200000.00"`, `available_credit == "500000.00"`.
- [ ] **Step 2: Run** — Expected: FAIL (module missing).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** ledger + customer tests — Expected: PASS.
- [ ] **Step 5: Commit** `feat(debt): ledger balances and receivables`.

### Task 4: Checkout with split / partial / credit

**Files:** `app/schemas/sale.py`, `app/services/sale_service.py`, `app/services/payment_service.py` (numbering only here), `app/api/v1/sales.py`, `app/repositories/sale_repo.py` (list filter), `tests/test_credit_sales.py`, `tests/test_credit_sales_true_concurrency.py`

**Interfaces:**
- Consumes: `ledger_service.lock_customer`, `customer_balance`, `post`; `debt_error`.
- Produces:
  - `PaymentLineInput{method: Literal['cash','mobile_money','bank_transfer'], amount: Decimal > 0, reference: str|None ≤100}` with the existing "reference required for mobile_money/bank_transfer" rule.
  - `SaleCreate` gains `payments: list[PaymentLineInput] | None` (max 3) and `customer_id: UUID | None`; `payment_method` becomes optional. Validator: if `payments is None` and `payment_method` given → legacy mode (the service turns it into one payment of the full total); both given → 422; neither → `payments = []`.
  - `payment_service.next_payment_no(db) -> str` → `PAY-YYYYMMDD-NNNN` (business date, `seq_payment_number`).
  - `SalePaymentOut{id, payment_no, kind, method, amount, reference, status, created_at}`; `CustomerRef{id, customer_no, name, phone}`.
  - `SaleResponse` gains `customer: CustomerRef|None`, `payments: list[SalePaymentOut]`, `paid: Decimal`, `outstanding: Decimal`, `payment_status: str` (Task 3 `receivable_status`; walk-in fully paid → `PAID`), `due_date: date|None`; `payment_method` becomes `str|None` = the single payment's method, `"mixed"` if >1 active payments, `"credit"` if none; `payment_reference` = first payment's reference.
  - `ReceiptData` gains `customer_name: str|None`, `payments: list[{method: str, amount: str, reference: str|None}]`, `paid: str`, `balance: str|None` (formatted outstanding if > 0), `due_date: str|None` (`dd/mm/YYYY`).
  - `create_sale` order inside the existing `begin_nested`: (1) compute total; (2) resolve payment lines; `paid > total` → `PAYMENT_EXCEEDS_TOTAL`; (3) `outstanding > 0`: no customer → `CREDIT_REQUIRES_CUSTOMER`; `lock_customer`; inactive → `CUSTOMER_INACTIVE`; `credit_limit == 0` → `CREDIT_NOT_ALLOWED`; `current = customer_balance(all)`; `current + outstanding > limit` → `CREDIT_LIMIT_EXCEEDED` with params; `due_date = business_date_today() + credit_days`; (4) customer given and `outstanding == 0` → existence checked with `db.get` only (404 if missing); an inactive customer may be attached to a fully-paid sale (purchase history); (5) existing sale/items/stock; (6) one `Payment(kind='sale', status='active', business_date=today, received_by=cashier)` + allocation per line; (7) if customer: ledger `sale` debit total (`source_type='sale'`, due_date), then one ledger `payment` credit per payment line (`source_type='payment'`, `source_id=payment.id`).
  - Sale must not write `sales.payment_method`/`payment_reference` for new sales.
  - Audit `SALE_CREATED` details gain `customer_id`, `payments` (list of `{method, amount}` strings), `credit_amount`.
  - `GET /sales?payment_method=` filters via `EXISTS (payments p JOIN payment_allocations a ... WHERE a.sale_id = sales.id AND p.method = :m)`.

- [ ] **Step 1: Failing tests** `tests/test_credit_sales.py` (product selling_price 80,000, cost 50,000 via direct `Product` insert or `make_product` + update; inventory 100):
  - `test_full_cash_sale_walk_in` — `payments=[{cash, 400000}]`, 5 items → 201; `payment_status == "PAID"`, `outstanding == "0.00"`, one payment, no ledger rows.
  - `test_split_payment_sale` — cash 200,000 + mobile_money 200,000 ref "MP1" → two payments; `payment_method == "mixed"`.
  - `test_partial_payment_creates_debt` — customer limit 2,000,000 credit_days 30; cash 150,000 → `outstanding == "250000.00"`, `payment_status == "PARTIALLY_PAID"`; `due_date == business_date_today() + 30 days`; ledger: one debit 400,000 + one credit 150,000; `customer_balance == 250000`.
  - `test_full_credit_sale` — `payments=[]`, customer → `outstanding == total`, `payment_status == "UNPAID"`.
  - `test_credit_without_customer_rejected` — partial, no customer → 400 `CREDIT_REQUIRES_CUSTOMER`; stock unchanged.
  - `test_credit_limit_zero_rejected` — `CREDIT_NOT_ALLOWED`.
  - `test_inactive_customer_credit_rejected` — `CUSTOMER_INACTIVE`.
  - `test_credit_limit_exceeded` — limit 2,000,000, existing ledger debit 1,700,000 (direct `ledger_service.post`), new full-credit sale of a product priced 500,000 qty 1 → 422 `CREDIT_LIMIT_EXCEEDED`, `params == {"limit":"2000000","current":"1700000","requested":"500000","available":"300000"}`; no sale row created.
  - `test_overpayment_rejected` — paid 500,000 on 400,000 → `PAYMENT_EXCEEDS_TOTAL`.
  - `test_legacy_payload_still_sells` — `{payment_method:"cash", items}` → 201, one cash payment = total.
  - `test_both_payload_styles_rejected` — 422.
  - `test_receipt_shows_balance_and_due_date` — partial sale; `GET /sales/{id}/receipt` → `balance` non-null, `due_date` set, `payments` length 1.
  - `test_cashier_cannot_sell_on_credit_at_other_branch` — existing `BRANCH_WRITE_RESTRICTED` still applies with credit payload.
  - `test_sales_list_filter_by_method_uses_payments` — split sale appears under both `cash` and `mobile_money` filters.
- [ ] **Step 2: Failing test** `tests/test_credit_sales_true_concurrency.py::test_concurrent_credit_sales_cannot_exceed_limit` — committed fixtures (pattern of `test_sale_void_true_concurrency.py`): customer limit 500,000, two cashiers at two branches each run `sale_service.create_sale` full-credit 400,000 concurrently via `asyncio.gather` on separate sessions → exactly one succeeds, the other raises `DebtException` with code `CREDIT_LIMIT_EXCEEDED`; `customer_balance == 400000`. Cleanup sets `SET LOCAL dukani.ledger_maintenance = 'on'` before deleting ledger rows, then deletes allocations, payments, sale items, inventory txns, sales, customer, users, product, branches.
- [ ] **Step 3: Run** both files — Expected: FAIL.
- [ ] **Step 4: Implement.** Existing tests posting `payment_method` keep passing through legacy mode — run `tests/test_sale_*.py tests/test_opening_register*.py tests/test_branch_context.py tests/test_user_management.py tests/test_profit_loss.py` to confirm.
- [ ] **Step 5: Run** full suite — Expected: PASS.
- [ ] **Step 6: Commit** `feat(debt): split, partial and credit checkout`.

### Task 5: Void with payments and customer ledger

**Files:** `app/services/sale_service.py`, `tests/test_sale_void_credit.py`

**Interfaces — Produces:** `void_sale` additions, inside its existing locked block, after the closed-day check:
- `SALE_HAS_DEBT_PAYMENTS` if any allocation to this sale belongs to an `active` `kind='debt'` payment.
- Mark each `active` `kind='sale'` payment allocated to the sale `reversed` (`reversed_by`, `reversed_at`, `reversal_reason = "Muamala umebatilishwa: " + reason`).
- If `sale.customer_id`: ledger `sale_void` credit = total (`source_type='sale'`, `reverses_entry_id` = the sale's `sale` entry) and per reversed sale payment a `payment_reversal` debit = its amount (`source_type='payment'`, `reverses_entry_id` = that payment's `payment` entry).

- [ ] **Step 1: Failing tests:**
  - `test_void_credit_sale_restores_balance` — balance 0; partial sale 400,000 paid 150,000 → 250,000; void → `customer_balance == 0`; the sale's payment `status == "reversed"`; ledger has 4 rows for the sale.
  - `test_void_walk_in_sale_reverses_payments` — payment reversed, closing preview cash excludes it (via `GET /closings/preview`).
  - `test_void_blocked_by_debt_payment` — credit sale + a `kind='debt'` active payment allocated (direct insert) → 400 `SALE_HAS_DEBT_PAYMENTS`; sale still completed.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** `tests/test_sale_void*.py` — PASS.
- [ ] **Step 5: Commit** `feat(debt): void reverses payments and customer ledger`.

### Task 6: Debt payments, allocation, receipts

**Files:** `app/schemas/payment.py`, `app/services/payment_service.py`, `app/api/v1/customers.py` (payments + receivables routes), `app/api/v1/payments.py`, `router.py`, `tests/test_debt_payments.py`, `tests/test_debt_payments_true_concurrency.py`

**Interfaces:**
- Consumes: ledger service, `require_write_branch_access`, `resolve_read_branch_id`, `daily_closing_repo.get_by_branch_date`, idempotency helpers.
- Produces:
  - `AllocationInput{sale_id: UUID|None, opening_balance_id: UUID|None, amount: Decimal>0}` (exactly one id).
  - `DebtPaymentCreate{branch_id: UUID|None, method, amount: Decimal>0, reference ≤100 (required for mobile_money/bank_transfer), notes ≤500, allocations: list[AllocationInput]|None (≤50)}`.
  - `ReceivableOut` (fields of `Receivable` + `kind`), `AllocationOut{receivable_kind, receivable_id, reference, amount}`, `PaymentOut{id, payment_no, kind, customer: CustomerRef|None, branch_id, branch_name, method, reference, amount, business_date, received_by_name, notes, status, reversed_by_name, reversed_at, reversal_reason, allocations: list[AllocationOut], created_at}`.
  - `PaymentReceipt{business_name, payment_no, customer_name, customer_no, date, amount, method, reference, allocations: list[AllocationOut], balance_before, balance_after, branch_name, received_by, reversed: bool}` — money as formatted strings like `ReceiptData`; `business_name = settings.APP_NAME` (existing setting).
  - `payment_service.record_debt_payment(db, customer_id, data, user) -> Payment`:
    1. Branch: cashier → `user.branch_id` (ignore body); others → `data.branch_id` required (`ValidationException` code `BRANCH_REQUIRED`), checked with `require_write_branch_access` + must be active `pos_point`.
    2. Closed day: `daily_closing_repo.get_by_branch_date(db, branch, business_date_today())` closed → `DAY_ALREADY_CLOSED` (same message as sales).
    3. `lock_customer`; `open = receivables(db, customer_id, branch, open_only=True)`; `owed = Σ outstanding`; `amount > owed` → `PAYMENT_EXCEEDS_DEBT {owed}`.
    4. Allocations given: each id must be in `open` (else `ALLOCATION_INVALID` — this also covers another branch's/customer's sale), each `amount ≤ outstanding`, no duplicate ids, `Σ == amount` (else `ALLOCATION_MISMATCH`). Not given: FIFO over `open`.
    5. `balance_before = customer_balance(customer, branch)`; insert payment (`kind='debt'`) + allocations; ledger `payment` credit = amount at that branch; `balance_after = balance_before − amount`; commit; audit `CUSTOMER_PAYMENT_RECORDED` (payment_no, amount, method, allocations).
  - `payment_service.get_payment_for_viewing(db, payment_id, user) -> Payment` — branch-scoped users only their branch's payments, else 404.
  - `payment_service.build_receipt(payment) -> PaymentReceipt`.
  - Routes: `GET /customers/{id}/receivables?open_only=true` (scoped by `branch_context`), `POST /customers/{id}/payments` (cashier, admin, super_admin; Idempotency-Key endpoint name `"POST /customers/payments"`), `GET /customers/{id}/payments` (scoped), `GET /payments/{id}`, `GET /payments/{id}/receipt` (no writes).
  - Receivables/payments reads: a cashier asking for a customer gets only their branch's rows; general_manager/admin/super_admin may pass `branch_id` or none (all).

- [ ] **Step 1: Failing tests** `tests/test_debt_payments.py` (helper builds credit sales via the API from Task 4):
  - `test_cash_debt_payment_fifo` — sales A (due earlier) 300,000 owed, B 200,000 owed; pay 400,000 cash, no allocations → A fully allocated, B 100,000; balance 100,000; receipt `balance_before == _fmt(Decimal("500000"))`, `balance_after == _fmt(Decimal("100000"))` (`_fmt` from `sale_service`).
  - `test_manual_allocation` — pay 150,000 allocated entirely to B → B outstanding 50,000, A untouched.
  - `test_allocation_mismatch_rejected` — Σ allocations ≠ amount → `ALLOCATION_MISMATCH`.
  - `test_allocation_over_outstanding_rejected` → `ALLOCATION_INVALID`.
  - `test_payment_exceeds_debt_rejected` → `PAYMENT_EXCEEDS_DEBT`, `params.owed`.
  - `test_mobile_money_requires_reference` → 422.
  - `test_bank_payment_recorded_with_reference`.
  - `test_cashier_cannot_allocate_other_branch_sale` — debt at A and B; cashier at B posts allocation to A's sale → `ALLOCATION_INVALID`; nothing written.
  - `test_cashier_payment_forced_to_own_branch` — body `branch_id` = A, cashier of B → payment branch B (allocated to B's debt).
  - `test_debt_payment_refused_when_day_closed` — close B's day via `/closings/close`, then pay → `DAY_ALREADY_CLOSED`.
  - `test_idempotent_retry_returns_same_payment` — same Idempotency-Key twice → one payment row, same `payment_no`.
  - `test_receipt_reprint_has_no_side_effects` — GET receipt twice → payments count unchanged, identical body.
  - `test_cashier_cannot_view_other_branch_payment` — 404.
  - `test_general_manager_cannot_record_payment` — 403.
  - `test_full_settlement_marks_paid` — receivables(open_only=False) shows `PAID`.
- [ ] **Step 2: Failing test** `test_debt_payments_true_concurrency.py::test_concurrent_payments_cannot_overpay` — debt 300,000; two sessions each pay 200,000 concurrently → one succeeds, other `PAYMENT_EXCEEDS_DEBT`; Σ active allocations to the sale == 200,000. Same cleanup pattern as Task 4.
- [ ] **Step 3: Run** — FAIL. **Step 4: Implement.** **Step 5: Run** both files + full suite — PASS.
- [ ] **Step 6: Commit** `feat(debt): debt payments with FIFO/manual allocation and receipts`.

### Task 7: Payment reversal

**Files:** `app/services/payment_service.py`, `app/api/v1/payments.py`, `tests/test_payment_reversal.py`

**Interfaces — Produces:**
- `PaymentReverseRequest{reason: str 5–500}`.
- `payment_service.reverse_payment(db, payment_id, reason, user) -> Payment`: lock payment row `FOR UPDATE`; missing → 404; `status == 'reversed'` → `PAYMENT_ALREADY_REVERSED`; `kind == 'sale'` → `SALE_PAYMENT_USE_VOID`; payment's branch day `business_date_for(payment.created_at)` closed → `DAY_ALREADY_CLOSED`; set reversed fields; ledger `payment_reversal` debit = amount, `reverses_entry_id` = the payment's `payment` entry; commit; audit `CUSTOMER_PAYMENT_REVERSED` (payment_no, amount, reason).
- Route `POST /payments/{id}/reverse` — admin, super_admin; Idempotency-Key endpoint `"POST /payments/reverse"`.
- Receipt of a reversed payment returns `reversed: true` (frontend prints "IMEBATILISHWA").

- [ ] **Step 1: Failing tests:**
  - `test_reverse_restores_receivable` — debt 400,000, pay 100,000 → 300,000; reverse → 400,000 outstanding; original payment still listed with `status "reversed"`; ledger has both `payment` and `payment_reversal` rows.
  - `test_double_reverse_rejected` → `PAYMENT_ALREADY_REVERSED`.
  - `test_sale_payment_cannot_be_reversed_directly` → `SALE_PAYMENT_USE_VOID`.
  - `test_cashier_cannot_reverse` → 403; `test_general_manager_cannot_reverse` → 403.
  - `test_reverse_blocked_on_closed_day`.
  - `test_concurrent_reversals` (in `test_debt_payments_true_concurrency.py`) — two sessions reverse one payment → one success, one `PAYMENT_ALREADY_REVERSED`; exactly one `payment_reversal` ledger row.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(debt): authorized payment reversal`.

### Task 8: Opening balances (old debts)

**Files:** `app/services/opening_balance_service.py`, `app/schemas/payment.py` (or `customer.py`), `app/api/v1/opening_balances.py`, `app/api/v1/customers.py`, `router.py`, `tests/test_opening_balances.py`

**Interfaces — Produces:**
- `OpeningBalanceCreate{branch_id: UUID, amount: Decimal>0, effective_date: date (≤ business_date_today()), due_date: date|None, reference: str 1–100, description ≤500}`; `OpeningBalanceDecision{note: str ≤500 (required, min 3, for reject)}`; `OpeningBalanceOut{id, customer: CustomerRef, branch_id, branch_name, amount, effective_date, due_date, reference, description, status, entered_by_name, decided_by_name, decided_at, decision_note, created_at}`.
- `create(db, customer_id, data, user)`: branch must be active `pos_point`; duplicate (same customer, branch, amount, reference with status pending/approved) → `OPENING_BALANCE_DUPLICATE`; `due_date` default `effective_date + credit_days`; audit `OPENING_BALANCE_ENTERED`.
- `approve(db, id, user, note)`: lock row; not pending → `OPENING_BALANCE_NOT_PENDING`; `user.id == entered_by` → `OPENING_BALANCE_SELF_DECISION`; status approved + ledger `opening_balance` debit (`source_type='opening_balance'`, business_date = effective_date, due_date); audit `OPENING_BALANCE_APPROVED`.
- `reject(db, id, user, note)`: same guards, no ledger; audit `OPENING_BALANCE_REJECTED`.
- Routes: `POST /customers/{id}/opening-balances`, `GET /opening-balances?status=&branch_id=`, `POST /opening-balances/{id}/approve`, `POST /opening-balances/{id}/reject` — all admin, super_admin.
- Approved opening balances already appear in `ledger_service.receivables` (Task 3) and are payable via Task 6.

- [ ] **Step 1: Failing tests:**
  - `test_pending_old_debt_is_not_owed` — create → balance 0, not in receivables.
  - `test_second_admin_approves` — approve by other admin → balance = amount; receivable reference starts `DENI-ZAMANI`; status `OVERDUE` when due_date past.
  - `test_self_approval_rejected` → 403 `OPENING_BALANCE_SELF_DECISION`.
  - `test_duplicate_old_debt_rejected` → 409.
  - `test_reject_writes_no_ledger`.
  - `test_pay_old_debt` — debt payment allocated to the opening balance → outstanding 0.
  - `test_cashier_cannot_enter_old_debt` → 403.
  - `test_future_effective_date_rejected` → 422.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(debt): opening balances with two-person approval`.

### Task 9: Closing, dashboard and sales report from payments; demo data

**Files:** `app/repositories/sale_repo.py`, `app/services/daily_closing_service.py`, `app/schemas/daily_closing.py`, `app/services/report_service.py`, `app/api/v1/reports.py`, `app/schemas/report.py`, `app/db/seed_demo.py`, `tests/test_closing_payments.py`

**Interfaces — Produces:**
- `sale_repo.get_totals_by_payment_method(db, branch_id, from_dt, to_dt) -> dict` keeps its name and keys and adds `credit_given`, `debt_collected`: method totals = Σ `payments.amount` where `status='active'`, `branch_id`, `created_at` in window (both kinds); `count`/`revenue` unchanged (completed sales in window); `credit_given` = Σ over completed sales in window of `total_amount − Σ active kind='sale' allocations`; `debt_collected` = Σ active `kind='debt'` payments in window.
- `DailyClosing` preview/response and close payload include `total_credit_given`, `total_debt_collected`; `close_day` stores them; audit details include them.
- Dashboard `_payment_breakdown_query` → active `kind='sale'` payments (+ branch filter on `payments.branch_id`) since the period start; `_breakdown_dict` gains key `credit` (credit given in the same period).
- Sales report `payment_breakdown` → from active `kind='sale'` payments in range, `method` label as today (`"Cash"`, `"Mobile Money"`, `"Bank Transfer"`), plus `PaymentBreakdown(method="Credit", count=<sales with credit>, total=<credit given>)` when > 0.
- P&L: no code change.
- `seed_demo`: `_wipe_generated_data` first runs `SET LOCAL dukani.ledger_maintenance = 'on'` in the same transaction, then deletes `CustomerLedgerEntry, PaymentAllocation, Payment, OpeningBalance` before the existing list, and `Customer` after `Sale`; `_generate_sale` writes a `Payment(kind='sale')` + allocation instead of `sale.payment_method`; `_generate_history` accumulates `day_totals` by payment method; demo creates 6 customers (credit limits 500,000–3,000,000) and turns ~10% of generated sales into partial/credit sales for them with matching ledger rows and due dates, plus 3 debt payments and 1 pending opening balance — all through the same model rules as the services (debit total, credit per payment).

- [ ] **Step 1: Failing tests** `tests/test_closing_payments.py`:
  - `test_closing_counts_collections_not_credit` — in one window: cash walk-in 100,000; partial sale 400,000 with cash 150,000; full-credit sale 200,000; debt payment cash 50,000 on an earlier debt → preview `total_cash == 300000`, `total_revenue == 700000`, `total_credit_given == 450000`, `total_debt_collected == 50000`.
  - `test_close_stores_credit_and_collections` — close → stored columns equal the preview.
  - `test_reversed_debt_payment_excluded_from_closing`.
  - `test_pl_unchanged_by_debt_payment` — P&L report for the day before and after recording a debt payment: identical `revenue`, `cost_of_goods_sold`, `gross_profit`.
  - `test_dashboard_breakdown_has_credit` — `today_payment_breakdown["credit"] == 450000` for the scenario.
  - `test_sales_report_breakdown_includes_credit_row`.
  - `test_demo_wipe_handles_debt_tables` — create a customer, credit sale (via service), debt payment, then call `seed_demo._wipe_generated_data(db_session)` adapted to take the session (refactor signature if needed: it already takes `db`) → no exception; ledger/payments/customers empty. (Runs inside the rolled-back test transaction; `_wipe_generated_data` must use `db.flush()` instead of `commit()` when a `commit=False` flag is passed — add `commit: bool = True` parameter.)
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** `tests/test_closing_payments.py tests/test_daily_closing*.py tests/test_opening_register*.py tests/test_profit_loss.py tests/test_report_authorization.py` — PASS.
- [ ] **Step 5: Run** `.venv/bin/python -m app.db.seed_demo` against the **local dev DB only** (it must print its usual completion line) and spot-check: `SELECT count(*) FROM customers` = 6, payments > 0, no sale without an allocation.
- [ ] **Step 6: Commit** `feat(debt): closing and payment breakdowns from real payments; demo data`.

### Task 10: Frontend — checkout, receipts, translations

**Files:** `services/customerService.js`, `services/paymentService.js`, `features/pos/CheckoutModal.jsx`, `features/pos/CustomerPicker.jsx`, `features/pos/ReceiptModal.jsx`, `features/customers/PaymentReceiptModal.jsx`, `constants/translations/sw.js`, `en.js`

**Interfaces:**
- Consumes: Tasks 2–8 endpoints and response shapes.
- Produces:
  - `customerService`: `search(q, params)`, `get(id, params)`, `create(payload)`, `update(id, payload)`, `updateCredit(id, payload)`, `receivables(id, params)`, `payments(id, params)`, `recordPayment(id, payload, idempotencyKey)`, `openingBalances.list(params)`, `openingBalances.create(customerId, payload)`, `openingBalances.approve(id, note)`, `openingBalances.reject(id, note)`.
  - `paymentService`: `get(id)`, `receipt(id)`, `reverse(id, reason, idempotencyKey)`.
  - `CustomerPicker({ value, onChange, allowCreate })` — debounced search (300 ms, min 2 chars) showing name, phone, customer_no; "Mteja mpya" inline form (name, phone, type) calling `customerService.create`; selected customer shows `available_credit` from `customerService.get`.
  - `CheckoutModal`: payment lines (method, amount, reference; add up to 3; "Lipa yote" fills remainder into the line), computed `paid`, `deni = total − paid` (shown in red when > 0); customer picker always visible, required (submit disabled + hint) when `deni > 0`; sends `{branch_id, customer_id, payments, items}`; maps `CREDIT_LIMIT_EXCEEDED` params into the toast via the existing `apiError` util. Money arithmetic in whole shillings (integers) on the client.
  - `ReceiptModal`: reads `data.receipt` (fixing the known shape mismatch: `PosPage` passes `{sale, receipt}`) — transaction_no, branch, date, items (`item.product`), totals, each payment line, customer name, balance + due date when present.
  - `PaymentReceiptModal({ paymentId, open, onClose })` — loads `paymentService.receipt`, prints with the same `window.open` + `print()` approach as `ReceiptModal`; shows "IMEBATILISHWA" banner when `reversed`.
  - Translations: new sections `wateja`, `malipo`, `madeniYaZamani`, nav entries, checkout strings, and `makosa.msimbo` for every Global Constraints code (sw + en, same keys).

- [ ] **Step 1: Implement** services, picker, checkout, receipts, translations.
- [ ] **Step 2: Verify build** `cd frontend && node node_modules/.bin/vite build` — Expected: build succeeds, no missing-import errors.
- [ ] **Step 3: Browser check** against local dev (backend + Vite already running): cashier login → cart 5 items → partial payment without customer → button disabled with hint; pick customer with limit → sell → receipt shows payments, Deni and due date; over-limit customer → toast shows the limit numbers; legacy-free split cash+M-Pesa sale → receipt lists both lines. Switch language to English → no Swahili-only strings in the new UI.
- [ ] **Step 4: Commit** `feat(debt): checkout with customers, split and credit; receipts`.

### Task 11: Frontend — Wateja pages, sales and closing views, nav and permissions

**Files:** `features/customers/CustomersPage.jsx`, `CustomerDetail.jsx`, `CustomerFormModal.jsx`, `RecordPaymentModal.jsx`, `OpeningBalancesPage.jsx`, `features/sales/SalesPage.jsx`, `features/closing/ClosingPage.jsx`, `routes/AppRouter.jsx`, `components/layout/Sidebar.jsx`, `utils/permissions.js`, translations

**Interfaces — Produces:**
- Permissions (`PERMISSION_MAP`): `customers.read` (super_admin, admin, general_manager, cashier), `customers.write` (super_admin, admin, cashier), `customers.credit` (super_admin, admin), `payments.collect` (super_admin, admin, cashier), `payments.reverse` (super_admin, admin), `opening_balances.manage` (super_admin, admin).
- Routes: `/wateja` (list, `customers.read`), `/wateja/:id` (detail, `customers.read`), `/wateja/madeni-ya-zamani` (`opening_balances.manage`). Sidebar entry "Wateja" (icon `Contact` from lucide-react) with child "Madeni ya Zamani".
- `CustomersPage`: search box, status filter, table (Mteja, Simu, Salio la Deni, Kikomo cha Mkopo, Yaliyochelewa, Malipo ya Mwisho, Hali); "Ongeza Mteja" (`customers.write`). Balance column comes from a list endpoint field — **add** `balance`, `overdue`, `last_payment_at` to each `GET /customers` item (scoped like `summary`) in this task's backend step with test `test_customer_list_includes_scoped_balance` in `tests/test_customers.py`.
- `CustomerDetail`: header (name, phone, no., type, status, limit, available credit, balance, overdue); tabs **Madeni** (receivables with status badges; toggle "onyesha yaliyolipwa"), **Malipo** (payments; receipt reprint; "Batilisha" for `payments.reverse` with reason modal). Actions: "Pokea Malipo" (`payments.collect`), "Hariri" (`customers.write`), "Mkopo" (credit modal, `customers.credit`, reason required).
- `RecordPaymentModal`: branch (forced for cashier; global user picks a POS branch where the customer owes), method, amount, reference, toggle "chagua mauzo" for manual allocation (per-receivable amount inputs, must sum to amount) else shows FIFO preview computed client-side from receivables; on success opens `PaymentReceiptModal`; Idempotency-Key per modal open.
- `OpeningBalancesPage`: list by status; "Ingiza Deni la Zamani" form (customer picker, branch, amount, effective date, reference, description); approve/reject buttons hidden on rows the current user entered.
- `SalesPage`: columns/filters show customer, `payment_status` badge, outstanding; payment method column renders `mixed` / `credit` labels.
- `ClosingPage`: KPI cards add "Mkopo Uliotolewa" and "Madeni Yaliyolipwa"; closing table/export rows include them (`toClosingExportData` in `utils/reportExport.js`).

- [ ] **Step 1: Backend list fields** — failing test `test_customer_list_includes_scoped_balance`, implement, PASS.
- [ ] **Step 2: Implement** pages, routes, nav, permissions, translations.
- [ ] **Step 3: Verify build** — `vite build` succeeds.
- [ ] **Step 4: Browser check** (local dev): admin creates customer, sets limit; cashier sells on credit; cashier records FIFO payment → receipt prints; admin reverses it → status IMEBATILISHWA and balance back; admin A enters old debt, admin A sees no approve button, admin B approves; cashier of another branch opening `/wateja/<id>` sees zero balance for that branch and no other-branch rows; closing preview shows credit given / debt collected; English toggle clean.
- [ ] **Step 5: Commit** `feat(debt): Wateja pages, sales and closing views`.

### Task 12: Acceptance scenario, regression, docs

**Files:** `tests/test_debt_acceptance.py`, `RUNBOOK.md`, `DEPLOYMENT.md`

- [ ] **Step 1: Write** `test_debt_acceptance.py::test_abc_technologies_scenario` (API-level, one test, spec §12 stage-1 subset): customer "ABC Technologies" (business) limit 2,000,000; product cost 50,000 / price 80,000; sale qty 5 with cash 150,000 →
  1. exactly one sale row; 2. `sale.customer.id` = ABC; 3–5. P&L for today: revenue 400,000, COGS 250,000, gross profit 150,000; 6–7. one sale payment 150,000 allocated to the sale; 8. balance 250,000; 11. P&L unchanged after step below; 12. closing preview cash includes 150,000 and `total_credit_given == 250000`;
  then debt payment 100,000 → balance 150,000; reverse it → balance 250,000; payments list shows both the reversed payment and the original 150,000; ledger rows: sale debit, payment credit, payment credit, payment_reversal debit;
  finally a cashier at another branch: `GET /customers/{id}/receivables` returns `[]`, `GET /sales/{sale_id}` → 404, `POST /customers/{id}/payments` allocating to the sale → `ALLOCATION_INVALID`.
- [ ] **Step 2: Run** it — Expected: PASS (all behaviour exists from Tasks 1–9; a failure here is a bug to debug, not a test to loosen).
- [ ] **Step 3: Run full suite** `.venv/bin/python -m pytest -q` — Expected: all pass; record the count.
- [ ] **Step 4: Docs** — `RUNBOOK.md`: "Wateja na Madeni" section (who can give credit, raising a limit, reversing a payment, entering old debts, the ledger trigger and `dukani.ledger_maintenance`, what to do if a debt payment was recorded at the wrong branch: reverse + re-record). `DEPLOYMENT.md`: stage-1 migration note (backup first, additive, downgrade command, legacy sales columns kept).
- [ ] **Step 5: Commit** `test(debt): stage 1 acceptance scenario; docs`.
- [ ] **Step 6: STOP for owner approval before push** — pushing to main deploys prod and demo. Before asking: take note that prod needs a DB backup (`BACKUP_RESTORE.md`) before the deploy runs the migration.
