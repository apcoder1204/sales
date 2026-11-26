# Wateja na Madeni — Stage 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Customer statements, debt ageing, a debt dashboard on Madeni Yote, factual risk indicators, collection follow-up notes, and seven debt reports with PDF/Excel/WhatsApp export.

**Architecture:** Everything is read from what stage 1 already records: the append-only ledger (statements), receivables (`ledger_service.collect_receivables`: ageing, dashboard, risk, reports) and `payments` (collections). The only new table is `customer_follow_ups`, which has no financial effect. Every endpoint is branch-scoped through `branch_context`. The frontend adds tabs and blocks to existing pages, and debt reports go into the existing Reports page through the existing `reportExport.js` normaliser.

**Tech Stack:** FastAPI, async SQLAlchemy 2 (asyncpg), Alembic, PostgreSQL 16, Pydantic v2, pytest (`.venv/bin/python -m pytest` from `backend/`); React 18 + Vite, jsPDF/xlsx via `reportExport.js`.

**Spec:** `docs/superpowers/specs/2026-11-25-customer-debt-management-design.md`. Stage 2 is §7, and the 2026-11-26 addendum (one admin per business, Madeni menu) applies. The brief's sections are 13–18 and 29.

## Global Constraints

- All stage 1 constraints still hold: Decimal money, `String`+CHECK instead of enums, audit category `"sales"`, flat error format with sw/en `makosa.msimbo` entries, branch checks only through `app/core/authorization.py`, dates only through `app/core/business_time.py`, all UI text through `SW.*` with identical keys in `sw.js` and `en.js`.
- **No financial writes in stage 2** except follow-up notes. Statements, ageing, the dashboard, risk indicators and reports are read-only, and follow-ups never touch the ledger, payments or balances (brief §16).
- **Branch scope:** a cashier sees only their branch. The admin and general manager see all branches, or the one they pick. The store keeper sees none (403). Credit-limit utilization uses all-branch totals, so it is admin and GM only.
- **Ageing:** days overdue = today (business date) − due date. Buckets: `not_due` (≤ 0), `1_30`, `31_60`, `61_90`, `90_plus`. A receivable with no due date uses its date + the customer's `credit_days` (the documented default term, brief §14). Only open receivables (outstanding > 0) are aged.
- **Ageing is always as of today.** Ruling: the spec outline's `as_of` parameter is dropped, because what is still owed is only known as of now; a past date would mix today's payments with an old cut-off. If wrong, it costs one query parameter later.
- **Risk flags** are factual codes, never a "bad debtor" label (brief §15): `NEAR_LIMIT` (all-branch balance ≥ 80% of a limit > 0, not over it), `OVER_LIMIT` (all-branch balance > limit, limit > 0), `OVERDUE` (any overdue receivable in scope), `LONG_OUTSTANDING` (any receivable > 90 days overdue in scope), `INACTIVE_WITH_DEBT` (status inactive and balance in scope > 0).
- **Statement:** opening balance = Σ(debit − credit) of ledger rows with `business_date < from`. Lines are rows with `from ≤ business_date ≤ to`, ordered by (business_date, created_at, id), each with a running balance. Closing = opening + Σ lines, and must equal the ledger balance up to `to`.
- **Report periods** reuse `report_service._resolve_period_dates(period, from_date, to_date)` and the query params `period`, `from_date` and `to_date`.
- Performance: the customer list must not add queries per row beyond what stage 1 does. Flags there are computed from the receivables already loaded.

## Review Focus

1. **Nightly demo reset with the new table:** `customer_follow_ups` references customers, so the 03:00 wipe must delete it first (Task 4, `test_demo_wipe_clears_follow_ups`).
2. **Statement range cutting through a reversal:** a payment on day 1, reversed on day 3, with range day 2 to day 3. The opening balance includes the payment credit, the lines show the reversal debit, and the closing equals the ledger balance (Task 1, `test_statement_range_cuts_through_reversal`).
3. **Cashier asking for another branch:** a statement, ageing or report with `branch_id` of another branch returns only their own branch's data, never the other's (Task 1 `test_cashier_statement_only_own_branch`, Task 5 `test_cashier_reports_forced_to_own_branch`).
4. **Receivable without a due date:** ageing falls back to date + `credit_days` and doesn't crash or silently show "not due" (Task 2, `test_ageing_missing_due_date_uses_credit_days`).
5. **Report totals agree:** the outstanding report total = the Madeni Yote summary total = the ledger balance in scope (Task 5, `test_report_totals_reconcile_with_ledger`).

---

## File map

Backend (`backend/`):
- Create `app/schemas/debt.py`: every new response/request schema in this plan
- Create `app/services/statement_service.py`: `statement()`
- Create `app/services/debt_insights_service.py`: `ageing_bucket()`, `ageing()`, `dashboard()`, `risk_flags()`, `risk_details()`
- Create `app/services/follow_up_service.py`, `app/models/follow_up.py`, migration `alembic/versions/e2f3a4b5c6d7_customer_follow_ups.py`
- Create `app/services/debt_report_service.py`, `app/api/v1/debt_reports.py` (prefix `/reports/debts`)
- Modify `app/api/v1/customers.py` (statement, follow-ups, risk on detail), `app/api/v1/receivables.py` (ageing, dashboard), `app/api/v1/router.py`, `app/db/base.py`, `app/schemas/customer.py`, `app/services/ledger_service.py` (flags in `summary`), `app/services/whatsapp_service.py` (`REPORT_TYPE_ROLES`), `app/db/seed_demo.py`

Frontend (`frontend/src/`):
- Create `features/customers/StatementTab.jsx`, `FollowUpsTab.jsx`, `RiskFlags.jsx`, `AgeingTable.jsx`, `features/reports/DebtReportView.jsx`
- Modify `features/customers/CustomerDetail.jsx`, `CustomersPage.jsx`, `DebtsPage.jsx`, `features/reports/ReportsPage.jsx`, `services/customerService.js`, `services/reportService.js`, `utils/reportExport.js`, `utils/permissions.js`, `constants/translations/sw.js`, `en.js`

---

### Task 1: Customer statement (backend)

**Files:** Create `app/schemas/debt.py`, `app/services/statement_service.py`. Modify `app/api/v1/customers.py`. Test: `tests/test_statement.py`.

**Interfaces:**
- Consumes: `CustomerLedgerEntry` (stage 1), `branch_context`, `require_customer_reader` (customers.py).
- Produces:
  - `StatementLine(date: date, reference: str, description: str, entry_type: str, branch_name: str, debit: Decimal, credit: Decimal, balance: Decimal)`
  - `StatementOut(customer: CustomerRef, branch_id: UUID | None, date_from: date, date_to: date, opening_balance: Decimal, lines: list[StatementLine], total_debit: Decimal, total_credit: Decimal, closing_balance: Decimal)`
  - `statement_service.statement(db, customer_id: UUID, branch_id: UUID | None, date_from: date, date_to: date) -> StatementOut`
  - `GET /customers/{id}/statement?date_from=&date_to=&branch_id=`. Defaults: from = the 1st of the current business month, to = today. `from > to` → 422 `DATE_RANGE_INVALID`.
- Reference per source: sale → `transaction_no`; payment → `payment_no`; opening_balance → `"DENI-ZAMANI " + reference`. Use outer joins on `source_type`/`source_id`, not a query per row.

- [ ] **Step 1: Write the failing tests** in `tests/test_statement.py` (use `tests.test_debt_payments.World`):
  - `test_statement_lines_and_running_balance`: credit sale 200,000, then a debt payment of 50,000. Lines are `[("sale", 200000, 0, 200000), ("payment", 0, 50000, 150000)]`, with opening 0, closing 150,000 and closing == `ledger_service.customer_balance`.
  - `test_statement_opening_balance_before_range`: back-date the sale's ledger row via `business_date` with `SET LOCAL dukani.ledger_maintenance='on'`. Range from today: opening 200,000, and the line holds only the payment.
  - `test_statement_range_cuts_through_reversal` (Review Focus 2).
  - `test_statement_includes_void_and_old_debt`: the void line is a credit equal to the sale; the old-debt line's reference starts with `DENI-ZAMANI`.
  - `test_cashier_statement_only_own_branch` (Review Focus 3): debt at A and B; cashier B with `branch_id=A` gets only B's lines and B's balance.
  - `test_statement_bad_range_422`, and a store keeper gets 403.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_statement.py -q`. Expected: FAIL (404 route).
- [ ] **Step 3: Implement** the schemas, `statement()` and the route. Add `DATE_RANGE_INVALID` (422) to `_DEBT_ERRORS` and to sw/en.
- [ ] **Step 4: Run** the same command. Expected: all pass.
- [ ] **Step 5: Commit** `feat(debt): customer statement from the ledger`.

### Task 2: Ageing and debt dashboard (backend)

**Files:** Create `app/services/debt_insights_service.py`. Modify `app/schemas/debt.py`, `app/api/v1/receivables.py`. Test: `tests/test_ageing_dashboard.py`.

**Interfaces:**
- Consumes: `ledger_service.collect_receivables(db, *, customer_id=None, branch_id=None, search=None, open_only=True)`, `Receivable` (has `customer_id`, `date`, `due_date`, `outstanding`).
- Produces:
  - `BUCKETS = ("not_due", "1_30", "31_60", "61_90", "90_plus")`; `ageing_bucket(days_overdue: int) -> str`; `effective_due(r: Receivable, credit_days: int) -> date`
  - `AgeingRow(customer: CustomerRef, buckets: dict[str, Decimal], total: Decimal)`; `AgeingOut(rows: list[AgeingRow], totals: dict[str, Decimal], total: Decimal, by_branch: list[{branch_id, branch_name, buckets, total}])`
  - `debt_insights_service.ageing(db, branch_id: UUID | None) -> AgeingOut`. Rows are sorted by total, largest first.
  - `DashboardOut(total_outstanding, customers_owing: int, overdue_total, collected_in_period, customers_over_limit: int, oldest_debt: {customer: CustomerRef, reference, date, days_overdue: int, outstanding} | None, ageing: dict[str, Decimal], top_debtors: list[{customer: CustomerRef, outstanding, overdue}])`. Top debtors are the top 5 by outstanding.
  - `debt_insights_service.dashboard(db, branch_id, date_from: date, date_to: date) -> DashboardOut`. `collected_in_period` = Σ active `kind="debt"` payments in scope with `business_date` in range. `customers_over_limit` counts customers owing in scope whose all-branch balance > a limit > 0.
  - Routes `GET /receivables/ageing` and `GET /receivables/dashboard?period=&from_date=&to_date=` (default period `month`), both `require_customer_reader` + `branch_context`.

- [ ] **Step 1: Write the failing tests**:
  - `test_ageing_bucket_edges`: the parametrized pairs are 0→not_due, −5→not_due, 1→1_30, 30→1_30, 31→31_60, 60→31_60, 61→61_90, 90→61_90, 91→90_plus.
  - `test_ageing_groups_per_customer_and_branch`: debts due in +10, −20 and −100 days give buckets not_due, 1_30 and 90_plus, and each row's total = Σ buckets.
  - `test_ageing_missing_due_date_uses_credit_days` (Review Focus 4): set the sale's `due_date=None` with the sale 45 days old and `credit_days` 30, so it lands in 1_30.
  - `test_dashboard_figures`: total, customers owing, overdue, a 50,000 debt payment collected this month, an over-limit count after lowering the limit below the balance, the oldest debt's reference, and top debtors ordered.
  - `test_dashboard_cashier_scope`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_ageing_dashboard.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the service, schemas and routes. Customers' `credit_days` come from one `select(Customer)` over the ids involved.
- [ ] **Step 4: Run** the same command. Expected: all pass.
- [ ] **Step 5: Commit** `feat(debt): ageing and debt dashboard`.

### Task 3: Risk indicators (backend)

**Files:** Modify `app/services/debt_insights_service.py`, `app/services/ledger_service.py` (`summary`), `app/schemas/customer.py`, `app/api/v1/customers.py`. Test: `tests/test_risk.py`.

**Interfaces:**
- Produces:
  - `risk_flags(customer: Customer, scope_rows: list[Receivable], scope_balance: Decimal, total_balance: Decimal) -> list[str]`, using the rules in Global Constraints and the codes in this order: OVER_LIMIT/NEAR_LIMIT, OVERDUE, LONG_OUTSTANDING, INACTIVE_WITH_DEBT.
  - `CustomerSummary.flags: list[str] = []`, filled by `ledger_service.summary` from rows it already loads.
  - `RiskOut(limit_used_pct: Decimal | None, overdue_count: int, oldest_open_date: date | None, total_purchases: Decimal, total_payments: Decimal)`; `risk_details(db, customer, branch_id) -> RiskOut`. Purchases = Σ completed sales with this customer in scope. Payments = Σ active payments of both kinds in scope. `limit_used_pct` uses all-branch figures and is None when the limit is 0.
  - `CustomerDetailResponse.risk: RiskOut` (the detail endpoint only). `CustomerListItem.flags: list[str]`.

- [ ] **Step 1: Write the failing tests**:
  - `test_flags_near_and_over_limit`: limit 1,000,000 with balance 800,000 gives NEAR_LIMIT; with 1,100,000 (after lowering the limit) it gives OVER_LIMIT and not NEAR_LIMIT.
  - `test_flags_overdue_and_long_outstanding`
  - `test_flags_inactive_with_debt`
  - `test_no_flags_for_clean_customer`
  - `test_detail_risk_details`: purchases 300,000, payments 150,000, overdue count 1, oldest open date, limit used %.
  - `test_list_carries_flags_without_extra_queries`: count statements on the list call with an SQLAlchemy `before_cursor_execute` listener; flags must add 0 queries versus the stage 1 baseline (the queries for 3 customers ≤ the stage 1 count, recorded in the test).
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_risk.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** `tests/test_risk.py` plus `tests/test_customers.py`. Expected: pass.
- [ ] **Step 5: Commit** `feat(debt): factual risk indicators`.

### Task 4: Collection follow-ups (backend)

**Files:** Create `app/models/follow_up.py`, migration `e2f3a4b5c6d7_customer_follow_ups.py` (down_revision `d1e2f3a4b5c6`), `app/services/follow_up_service.py`. Modify `app/db/base.py`, `app/api/v1/customers.py`, `app/db/seed_demo.py`. Test: `tests/test_follow_ups.py`.

**Interfaces:**
- Table `customer_follow_ups`:
  - `id`, `customer_id` (FK), `branch_id` (FK), `contact_date` (date, not null, ≤ today)
  - `method` String(10), CHECK in (`phone`, `visit`, `sms`, `whatsapp`)
  - `note` Text (3–1000 chars), `expected_payment_date` (date, null)
  - `responsible_user_id` (FK users, not null), `created_by` (FK users), `created_at` timestamptz
  - Index (`customer_id`, `contact_date`)
- `FollowUpCreate(branch_id: UUID | None, contact_date: date, method, note, expected_payment_date: date | None)`. The responsible user is always the creator; admin assignment is not needed (YAGNI). `FollowUpOut(id, branch_id, branch_name, contact_date, method, note, expected_payment_date, responsible_user_name, created_at)`.
- `POST /customers/{id}/follow-ups` (super_admin, admin, cashier). A cashier's branch is pinned like old debts (another branch → 403). The admin must pass a POS `branch_id`, otherwise `BRANCH_REQUIRED`. Writes audit `FOLLOW_UP_ADDED`.
- `GET /customers/{id}/follow-ups` (`require_customer_reader` + `branch_context`), newest first.

- [ ] **Step 1: Write the failing tests**:
  - `test_cashier_adds_follow_up_own_branch`
  - `test_follow_up_changes_no_balance`: the ledger count, balance and payment count are identical before and after.
  - `test_cashier_lists_only_own_branch_follow_ups`
  - `test_manager_cannot_add`
  - `test_future_contact_date_422`
  - `test_demo_wipe_clears_follow_ups` (Review Focus 1, modeled on `test_demo_wipe_handles_debt_tables`)
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_follow_ups.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**. Add `CustomerFollowUp` to the `_wipe_generated_data` list before `Customer`. `seed_demo` adds 3 follow-ups on demo debtors (one with an expected payment date).
- [ ] **Step 4: Run** the same command, plus `alembic downgrade -1 && alembic upgrade head`. Expected: pass, and the round trip runs clean.
- [ ] **Step 5: Commit** `feat(debt): collection follow-up notes`.

### Task 5: Debt reports API (backend)

**Files:** Create `app/services/debt_report_service.py`, `app/api/v1/debt_reports.py`. Modify `app/api/v1/router.py`, `app/services/whatsapp_service.py`. Test: `tests/test_debt_reports.py`.

**Interfaces** (all under `/reports/debts`, `branch_context`, Decimal amounts, each response `{rows: [...], summary: {...}}`):

| path | roles | rows | summary |
|---|---|---|---|
| `/outstanding` | reader* | customer, balance, overdue, credit_limit, last_payment_at, flags | total_balance, total_overdue, customers |
| `/overdue` | reader | customer, branch_name, reference, due_date, days_overdue, outstanding | total, count |
| `/ageing` | reader | = `AgeingOut` (Task 2) | — |
| `/collections?period` | reader | payment_no, business_date, customer, branch_name, method, amount, received_by | total, count, by_method {cash, mobile_money, bank_transfer} |
| `/branches?period` | reader | branch_name, outstanding, overdue, customers_owing, collected_in_period | totals of each |
| `/credit-utilization` | admin, super_admin, general_manager | customer, credit_limit, balance (all branches), used_pct, available, flags | customers_over_limit, customers_near_limit |
| `/opening-balances?status` | admin, super_admin, cashier | customer, branch_name, amount, effective_date, status, entered_by_name, decided_by_name | count and amount per status |

\*reader = super_admin, admin, general_manager, cashier. Collections = active `kind="debt"` payments only. Reversed payments are excluded, and the period filters `business_date`.
- `REPORT_TYPE_ROLES` gains `debt_outstanding`, `debt_overdue`, `debt_ageing`, `debt_collections`, `debt_branches` and `customer_statement` = `_FINANCIAL + ("cashier",)`; `debt_credit_utilization` = `_FINANCIAL`; `debt_opening_balances` = admin roles + cashier.

- [ ] **Step 1: Write the failing tests**:
  - `test_outstanding_report`
  - `test_overdue_report_days`
  - `test_collections_excludes_reversed_and_sale_payments`
  - `test_branches_report_two_branches`
  - `test_credit_utilization_admin_only`: a cashier gets 403.
  - `test_opening_balance_report_by_status`
  - `test_cashier_reports_forced_to_own_branch` (Review Focus 3)
  - `test_report_totals_reconcile_with_ledger` (Review Focus 5)
  - `test_whatsapp_accepts_debt_report_types`: role table lookup only.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_debt_reports.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**. Reuse `collect_receivables`, `debt_insights_service.ageing` and `ledger_service.summary`; don't add new query logic for receivables.
- [ ] **Step 4: Run** the same command plus the full suite (`-q`). Expected: all pass.
- [ ] **Step 5: Commit** `feat(debt): debt reports API`.

### Task 6: Customer page: statement, follow-ups, risk (frontend)

**Files:** Create `features/customers/StatementTab.jsx`, `FollowUpsTab.jsx`, `RiskFlags.jsx`. Modify `CustomerDetail.jsx`, `CustomersPage.jsx`, `services/customerService.js`, `utils/reportExport.js`, `utils/permissions.js`, sw/en.

**Interfaces:**
- `customerService.statement(id, {date_from, date_to, branch_id})`, `customerService.followUps.list(id, params)`, `.create(id, payload)`.
- `RiskFlags({ flags })` shows a coloured `Badge` per code; the labels are in `SW.hatari[code]`.
- CustomerDetail tabs: Madeni, Malipo, **Taarifa** (statement), **Ufuatiliaji** (follow-ups). The header shows risk figures from `risk` plus `RiskFlags`, and the customer list shows `RiskFlags` under the status.
- `StatementTab`: date range (default this month), the table (date, reference, description, branch, debit, credit, balance) with opening and closing rows, and PDF/Excel/`SendWhatsAppButton` using report type `customer_statement` with a new `normalise` case.
- Permission `customers.follow_up` (super_admin, admin, cashier). Managers see the list without the add form.
- [ ] **Step 1:** Implement, then `node node_modules/.bin/vite build`. Expected: build OK, and the sw/en key comparison script reports no differences.
- [ ] **Step 2: Browser check** (Playwright, local dev):
  - Admin: the statement for a customer with a sale, payment and reversal shows the running balance and its closing equals the header balance; PDF download works.
  - Cashier: adds a follow-up and sees only their branch's statement lines.
  - Manager: can read but has no add button.
- [ ] **Step 3: Commit** `feat(debt): statement, follow-ups and risk on the customer page`.

### Task 7: Madeni Yote dashboard and ageing (frontend)

**Files:** Create `features/customers/AgeingTable.jsx`. Modify `DebtsPage.jsx`, `customerService.js`, sw/en.

- DebtsPage top: the KPIs from `/receivables/dashboard` (total, overdue, customers owing, collected this month, over limit, oldest debt), an ageing distribution bar (HTML rows with % width, one per bucket) and the top 5 debtors. Below that, two tabs: **Orodha** (the existing list) and **Umri wa Madeni** (`AgeingTable` from `/receivables/ageing`: customer rows × buckets, totals row).
- [ ] **Step 1:** Implement and build. Expected: build OK and keys match.
- [ ] **Step 2: Browser check:** the dashboard totals equal the list summary totals, the ageing totals equal the dashboard total, and the cashier view shows one branch only.
- [ ] **Step 3: Commit** `feat(debt): debt dashboard and ageing on Madeni Yote`.

### Task 8: Debt reports in Reports page (frontend)

**Files:** Create `features/reports/DebtReportView.jsx`. Modify `ReportsPage.jsx`, `services/reportService.js`, `utils/reportExport.js`, `utils/permissions.js`, sw/en.

**Interfaces:**
- Export `normaliseReport(type, data, period)` from `reportExport.js` (the current `normalise`). New cases: `debt_outstanding`, `debt_overdue`, `debt_ageing`, `debt_collections`, `debt_branches`, `debt_credit_utilization`, `debt_opening_balances`. Each is a summary sheet plus a rows sheet.
- `DebtReportView({ type, data, period })` renders the `sheets` from `normaliseReport` as tables, so screen and export show the same figures.
- `reportService.debts.{outstanding, overdue, ageing, collections, branches, creditUtilization, openingBalances}(params)`.
- `REPORT_TYPES` gains these with permissions `reports.debts` (super_admin, admin, general_manager, cashier) or `reports.debts_credit` (super_admin, admin, general_manager). The period selector shows only for collections and branches.
- [ ] **Step 1:** Implement and build. Expected: build OK and keys match.
- [ ] **Step 2: Browser check:** each report loads for the admin, PDF and Excel download, a cashier doesn't see credit utilization, and the closing PDF still shows Mkopo Uliotolewa and Madeni Yaliyolipwa (stage 1 check).
- [ ] **Step 3: Commit** `feat(debt): debt reports with export and WhatsApp`.

### Task 9: Acceptance, docs, release prep

**Files:** Modify `tests/test_debt_acceptance.py`, `RUNBOOK.md`, `DEPLOYMENT.md` (migration note for `e2f3a4b5c6d7`), and the spec (stage 2 marked done, with rulings).
- [ ] **Step 1:** Extend the ABC Technologies scenario. Its statement has lines sale 400,000, payment 150,000, payment 100,000 and reversal 100,000, with closing 250,000 = balance. Ageing puts 250,000 in `not_due`. The outstanding report shows 250,000.
- [ ] **Step 2:** Run the full suite. Expected: all pass. Report the count.
- [ ] **Step 3:** RUNBOOK gets "Statements, ageing and reports" (where to find each, who sees what) and "Follow-up notes don't change balances".
- [ ] **Step 4: Commit** `test(debt): stage 2 acceptance; docs`.
