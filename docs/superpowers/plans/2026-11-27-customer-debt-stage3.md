# Wateja na Madeni — Stage 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reconciliation engine, run on demand, that proves sales, payments, allocations, the customer ledger, P&L and daily closings agree and lists every place they don't. Add exception management (open, under review, resolved, dismissed), a reconciliation exceptions report, the §33 step 13 check and the brief's §34 final report.

**Architecture:**
- **Checks** (`reconciliation_checks.py`): pure readers. Each one bulk-loads its scope in a few queries and returns `Finding`s.
- **The run** (`reconciliation_service.run`): runs the checks that apply to the scope, then writes one `reconciliation_runs` row and upserts `reconciliation_exceptions` by fingerprint. It writes nothing else.
- **Fixes:** a person fixes a discrepancy with the normal correcting actions (reversal, void, old debt). Marking an exception resolved re-runs the check, and the server refuses if the discrepancy is still there.
- **Frontend:** a new "Upatanisho wa Hesabu" page under the Madeni menu, plus one new type on the Reports page.

**Tech Stack:** FastAPI, async SQLAlchemy 2 (asyncpg), Alembic, PostgreSQL 16 (JSONB, advisory locks), Pydantic v2, pytest (`.venv/bin/python -m pytest` from `backend/`). React 18 + Vite, with jsPDF and xlsx through `reportExport.js`.

**Spec:** `docs/superpowers/specs/2026-11-25-customer-debt-management-design.md` §8 (stage 3 outline), plus the 2026-11-26 addendum and "Stage 2 status". These parts of the brief apply: §19, §20, §21, §29 item 8, §31 (reconciliation and security tests), §33 step 13 and §34.

## Global Constraints

- **The stage 1 and 2 constraints still hold:**
  - Money is Decimal.
  - Status columns use `String` + CHECK, not enums.
  - Errors use the flat format, with sw/en `makosa.msimbo` entries.
  - Branch checks go only through `app/core/authorization.py`, and dates only through `app/core/business_time.py`.
  - All UI text goes through `SW.*`, with identical keys in `sw.js` and `en.js`.
  - The audit category is `"sales"`.
- **A run never writes financial rows** (spec anti-goal; brief §20 "read-only by default"). It may write only `reconciliation_runs` and `reconciliation_exceptions`. Changing an exception's status writes only that exception and an audit row. Nothing in stage 3 fixes data automatically.
- **Who may do what:**

  | Action | super_admin | admin | general_manager | cashier, store_keeper |
  |---|---|---|---|---|
  | Start a run | yes | yes | yes | 403 |
  | See runs and exceptions | yes, all branches | yes, all branches | yes, all branches | 403 |
  | Change an exception's status | yes | yes | no | 403 |

  Ruling: the spec says only admins resolve, and is silent on who runs. A run changes no money, so the GM, who reads everything, may run it. Cashiers get nothing, because a run crosses branches. If this is wrong, one role list changes.
- **Statuses** (spec §8):
  - A run is `FAILED` if any money finding counts, `WARNING` if the only findings are warnings, and `PASSED` otherwise.
  - The two warning codes are `DUPLICATE_PAYMENT_REFERENCE` and `LEGACY_PAYMENT_MISMATCH`. Every other code is money.
- **Exception transitions:**
  - `OPEN → UNDER_REVIEW | RESOLVED | DISMISSED`
  - `UNDER_REVIEW → OPEN | RESOLVED | DISMISSED`
  - `RESOLVED` and `DISMISSED` are final.
  - Every change needs a reason (5–500 characters).
  - `RESOLVED` and `DISMISSED` also need a supporting reference (1–100 characters, brief §21).
  - `RESOLVED` is refused with `EXCEPTION_STILL_PRESENT` (409) while a fresh check, over the exception's last run scope, still finds the same fingerprint.
- **Fingerprints and repeat runs:**
  - Fingerprint = `code:` + the ids that identify the discrepancy, plus the field name for closing totals.
  - A repeat run that finds an `OPEN` or `UNDER_REVIEW` exception with the same fingerprint updates its `last_run_id`, `last_seen_at`, expected, actual and difference. It never creates a second row.
  - A partial unique index enforces this: at most one live exception per fingerprint.
  - A finding is **suppressed** when its fingerprint matches a `DISMISSED` exception with the same difference. A suppressed finding counts in `suppressed_count`, not in the status. With a changed difference, it becomes a new `OPEN` exception.
  - After `RESOLVED`, the same fingerprint found again becomes a new `OPEN` exception.
- **Concurrency:** runs are serialized with `SELECT pg_advisory_xact_lock(hashtext('dukani_reconciliation'))`. A status change locks its exception row `FOR UPDATE`.
- **Period:** `period`, `from_date` and `to_date` resolve through `report_service._resolve_period_dates`, defaulting to `month`. The period limits only checks E, F and G. Checks A–D always examine every record in scope as of now. `from > to` returns 422 `DATE_RANGE_INVALID`.
- **Prod safety:** the migration only adds two new tables and a sequence. Running a reconciliation on prod creates rows, so after deploy the agent verifies on demo only and never starts a run on prod. The owner runs the first one.

### Checks (exact rules; `paid` = Σ allocations whose payment is `active`)

| Group | Code | Finding when | expected / actual |
|---|---|---|---|
| A | `RECEIVABLE_OVERPAID` | A completed sale or approved old debt has paid > amount | amount / paid |
| A | `WALKIN_SALE_UNPAID` | A completed sale with `customer_id IS NULL` has paid ≠ total | total / paid |
| A | `SALE_ITEMS_MISMATCH` | A completed sale's total ≠ Σ `sale_items.line_total` | Σ items / total |
| A | `LEGACY_PAYMENT_MISMATCH` (warning) | A sale's `payment_method` is not null, and its `kind='sale'` payments are not exactly one row with that method and amount = total | total / Σ till payments |
| B | `ALLOCATION_TOTAL_MISMATCH` | A payment's Σ allocations ≠ its amount (no unapplied money exists, spec call 3) | amount / Σ allocations |
| B | `ALLOCATION_BRANCH_MISMATCH` | An allocation's target branch ≠ the payment's branch | — (detail names both branches) |
| B | `ALLOCATION_CUSTOMER_MISMATCH` | A `kind='debt'` payment's customer ≠ the target's customer | — |
| B | `ORPHAN_ALLOCATION` | An active payment is allocated to a voided sale or to an old debt that is not `approved` | 0 / allocation amount |
| B | `TILL_PAYMENT_MISMATCH` | A `kind='sale'` payment allocates to an old debt, to more than one sale, or to a sale on another business date | — |
| C | `LEDGER_BALANCE_MISMATCH` | For a (customer, branch), the ledger's Σ(debit − credit) ≠ Σ outstanding of their receivables (`collect_receivables(open_only=False)`) | receivables / ledger |
| C | `MISSING_LEDGER_ENTRY` | One of the expected rows (below) is absent | document amount / 0 |
| C | `LEDGER_ENTRY_MISMATCH` | An expected row exists, but its amount, customer or branch differs from the document | document / entry (detail names the field) |
| C | `ORPHAN_LEDGER_ENTRY` | A ledger row whose source is missing, or whose document's state doesn't call for it (a `sale_void` on a completed sale, an `opening_balance` on a pending or rejected old debt, a `payment_reversal` on an active payment) | 0 / entry amount |
| E | `VOIDED_SALE_ACTIVE_PAYMENT` | A voided sale still has an allocation from an active payment of either kind | 0 / paid |
| F | `PNL_REVENUE_MISMATCH` | Per branch for the period, the P&L revenue (`report_service.get_profit_loss_report(db, "custom", from, to, branch_id).summary.revenue`) ≠ Σ total of completed sales in the same window | Σ sales / P&L |
| G | `CLOSING_TOTAL_MISMATCH` | For a **closed** register whose `business_date` falls in the period, a stored field ≠ the recomputed figure. One finding per field. Window: `[opened_at, closed_at]`, or `utc_range_for_business_date(business_date)` when `opened_at` is null | recomputed / stored |
| G | `DUPLICATE_PAYMENT_REFERENCE` (warning) | Two or more active `mobile_money` or `bank_transfer` payments share a reference (trimmed, upper-cased). One finding per reference | — (detail lists the payment numbers) |

**Fields compared by `CLOSING_TOTAL_MISMATCH`:**
- They come from `sale_repo.get_totals_by_payment_method`: `total_cash`, `total_mobile_money`, `total_bank_transfer`, `total_revenue`, `total_sales_count`, `total_credit_given` and `total_debt_collected`.
- Compare at 2 decimal places.

**Expected ledger rows** (`source_type`, `entry_type`, side, amount), by document:

| Document | Expected rows |
|---|---|
| Sale with a customer | (`sale`, `sale`, debit, total); if voided, also (`sale`, `sale_void`, credit, total) |
| Payment with a customer | (`payment`, `payment`, credit, amount); if reversed, also (`payment`, `payment_reversal`, debit, amount) |
| Approved or cancelled old debt | (`opening_balance`, `opening_balance`, debit, amount); if cancelled, also (`opening_balance`, `opening_void`, credit, amount) |

Each row's customer and branch must equal the document's.

**Group D and the checks the brief names that don't apply here:**
- **D is not a separate code.** Ruling: the per-branch ledger total and receivables total go into `summary.branches`, and any gap there is exactly the sum of that branch's `LEDGER_BALANCE_MISMATCH` findings. A separate code would report every problem twice. Payment branch versus debt branch is `ALLOCATION_BRANCH_MISMATCH`. If this is wrong, it costs one aggregate comparison.
- **"Duplicate posting" and "cached balance" checks are not built.** Ruling: `uq_ledger_source_entry` makes duplicate postings impossible, and no balance is stored anywhere; the receipt snapshots are informational. C's "ledger vs receivables" check is the cached-balance check of brief §31. If this is wrong, it costs one check.
- **The derived-status comparison in spec §8 A is replaced.** Ruling: sale status is never stored, so A checks the inputs it is derived from.

### Scope → checks

| Scope | Needs | Checks run |
|---|---|---|
| `all` | — | A, B, C, E, F, G for every branch, plus `summary.branches` |
| `branch` | `branch_id` | A–G, limited to that branch's documents and closings; duplicate references among its payments |
| `customer` | `customer_id` | A, B, C over that customer's sales, payments, old debts and ledger rows |
| `sale` | `sale_id` | A for the sale; B for every payment allocated to it; C for its ledger rows and its customer's balance at its branch; E for the sale |
| `payment` | `payment_id` | B for the payment; C for its ledger rows; G duplicate references for its reference |

A missing id, or an id that doesn't exist, returns 422 `RECON_SCOPE_INVALID`.

## Review Focus

1. **False alarms on normal history.** All of these together must produce zero findings:
   - split till payments;
   - a partial debt payment, then a reversal;
   - a voided credit sale whose debt payment was reversed first;
   - a cancelled old debt;
   - a walk-in sale;
   - a register closed, reopened and closed again.

   (Task 4, `test_clean_mixed_history_passes`.)
2. **The nightly demo reset with the new tables.** Exceptions reference sales, payments, closings and customers, so the 03:00 wipe must delete exceptions and then runs before anything else (Task 1, `test_demo_wipe_clears_reconciliation`).
3. **Repeat runs:**
   - no duplicate live exceptions;
   - a dismissed finding with the same difference stays quiet;
   - a changed difference opens a new exception.

   (Task 4, `test_rerun_updates_not_duplicates`, `test_dismissed_suppressed_unless_difference_changes`.)
4. **Legacy demo sales.** A backfilled pre-debt sale (`payment_method` set, one matching `kind='sale'` payment) gives no finding; a mismatching one is only a warning (Task 2, `test_legacy_sale_clean_and_mismatch_is_warning`).
5. **Old registers and the Tanzania day:**
   - A register with `opened_at NULL` is recomputed over its whole business day.
   - A sale at 00:30 Tanzania time (21:30 UTC the day before) belongs to the local day in E, F and G.

   (Task 3, `test_closing_without_opened_at_uses_business_day`, `test_period_uses_tanzania_dates`.)

---

## File map

**Backend (`backend/`):**
- **Create:**
  - `app/models/reconciliation.py`: `ReconciliationRun`, `ReconciliationException`
  - migration `alembic/versions/f3a4b5c6d7e8_reconciliation.py` (down_revision `e2f3a4b5c6d7`)
  - `app/schemas/reconciliation.py`
  - `app/services/reconciliation_checks.py`
  - `app/services/reconciliation_service.py`
  - `app/api/v1/reconciliation.py` (prefix `/reconciliation`)
- **Modify:**
  - `app/db/base.py`
  - `app/api/v1/router.py`
  - `app/core/exceptions.py` (`_DEBT_ERRORS`)
  - `app/api/v1/debt_reports.py`
  - `app/services/debt_report_service.py`
  - `app/schemas/debt.py`
  - `app/services/whatsapp_service.py`
  - `app/db/seed_demo.py`
  - `tests/test_debt_acceptance.py`
- **Tests:** `tests/test_recon_schema.py`, `test_recon_documents.py`, `test_recon_period.py`, `test_recon_runs.py`, `test_recon_exceptions.py`, `test_recon_true_concurrency.py`

**Frontend (`frontend/src/`):**
- **Create:**
  - `features/reconciliation/ReconciliationPage.jsx`
  - `features/reconciliation/ExceptionsTable.jsx`
  - `features/reconciliation/ExceptionStatusModal.jsx`
  - `services/reconciliationService.js`
- **Modify:**
  - `routes/AppRouter.jsx`
  - `components/layout/Sidebar.jsx`
  - `utils/permissions.js`
  - `features/reports/ReportsPage.jsx`
  - `features/reports/DebtReportView.jsx` (if needed)
  - `services/reportService.js`
  - `utils/reportExport.js`
  - `constants/translations/sw.js`, `en.js`

**Docs:**
- `docs/RUNBOOK.md`
- `docs/DEPLOYMENT.md`
- the spec ("Stage 3 status")
- new `docs/customer-debt-implementation-report.md` (§34)

---

### Task 1: Tables, models, demo wipe

**Files:** Create `app/models/reconciliation.py` and migration `f3a4b5c6d7e8_reconciliation.py`. Modify `app/db/base.py` and `app/db/seed_demo.py`. Test: `tests/test_recon_schema.py`.

**Interfaces:**
- **Produces `reconciliation_runs`:**
  - Identity and scope: `id` uuid; `run_no` varchar(30) unique (`"UPT-YYYYMMDD-NNNN"` from sequence `seq_reconciliation_number`); `scope` varchar(10), CHECK in (`all`, `branch`, `customer`, `sale`, `payment`); nullable FKs `branch_id`, `customer_id`, `sale_id`, `payment_id`.
  - Period and timing: `date_from` date, `date_to` date; `started_at` and `finished_at` timestamptz.
  - Results: `run_by` FK users; `records_examined`, `discrepancy_count`, `warning_count` and `suppressed_count` int; `status` varchar(10), CHECK in (`PASSED`, `WARNING`, `FAILED`); `summary` JSONB not null default `{}`; `created_at`.
- **Produces `reconciliation_exceptions`:**
  - Identity and classification: `id`; `check_group` varchar(1), CHECK in A–G; `code` varchar(40); `severity` varchar(10), CHECK in (`money`, `warning`); `fingerprint` varchar(200); `status` varchar(15), CHECK in (`OPEN`, `UNDER_REVIEW`, `RESOLVED`, `DISMISSED`), default `OPEN`.
  - Runs: `first_run_id` and `last_run_id`, FKs to runs.
  - Affected records: nullable FKs `customer_id`, `sale_id`, `payment_id`, `opening_balance_id`, `closing_id` (to `daily_closings`) and `branch_id`.
  - Figures: `expected`, `actual` and `difference` numeric(14,2), nullable; `detail` text not null default `''`.
  - Timestamps: `detected_at`, `last_seen_at` timestamptz.
  - Latest status change: `status_reason` text, `status_reference` varchar(100), `status_by` FK users, `status_at` timestamptz.
  - Indexes: `uq_recon_exception_live` unique on `fingerprint` WHERE status IN ('OPEN','UNDER_REVIEW'); `ix_recon_exceptions_status` on (`status`, `detected_at`).
- The downgrade drops both tables and the sequence.

- [ ] **Step 1: Write the failing tests:**
  - `test_live_fingerprint_unique`: two OPEN rows with one fingerprint fail with an IntegrityError. OPEN + DISMISSED with the same fingerprint is allowed.
  - `test_run_status_check`: status `"OK"` is rejected.
  - `test_demo_wipe_clears_reconciliation` (Review Focus 2): seed demo, insert a run and an exception pointing at a demo sale and a demo closing, then `_wipe_generated_data(db, commit=False)` succeeds and leaves both tables empty.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_recon_schema.py -q`. Expected: FAIL (import error).
- [ ] **Step 3: Implement** the models, the migration (`alembic upgrade head` locally) and the registration in `base.py`. Prepend `ReconciliationException, ReconciliationRun` to the wipe tuple in `seed_demo._wipe_generated_data`.
- [ ] **Step 4: Run** the same tests, then `alembic downgrade -1 && alembic upgrade head`. Expected: pass, and the round trip is clean.
- [ ] **Step 5: Commit** `feat(recon): reconciliation runs and exceptions tables`.

### Task 2: Document checks A, B, C

**Files:** Create `app/services/reconciliation_checks.py`. Test: `tests/test_recon_documents.py`. Corrupt data is made by writing directly through `db_session` (ledger rows under `SET LOCAL dukani.ledger_maintenance='on'`), never through the API.

**Interfaces:**
- Produces:
  - `Finding` (frozen dataclass), with fields:
    - required: `group: str`, `code: str`, `severity: Literal["money","warning"]`, `fingerprint: str`
    - optional, default None: `branch_id`, `customer_id`, `sale_id`, `payment_id`, `opening_balance_id`, `closing_id`, `expected: Decimal | None`, `actual: Decimal | None`
    - optional: `detail: str = ""`
    - property `difference = actual − expected` (None if either is None)
  - `Scope` (frozen dataclass): `kind`, `branch_id`, `customer_id`, `sale_id` and `payment_id` (each `UUID | None`), `date_from: date`, `date_to: date`.
  - `CheckResult(findings: list[Finding], examined: int, summary: dict)`
  - `async def check_receivables(db, scope) -> CheckResult` (A)
  - `async def check_allocations(db, scope) -> CheckResult` (B)
  - `async def check_ledger(db, scope) -> CheckResult` (C; its `summary` = `{"branches": {branch_id: {"ledger": Decimal, "receivables": Decimal}}}`)
- Each check loads its scope in at most a handful of bulk queries (no query per document). Fingerprints take the form `f"{code}:{id}"`, or `f"{code}:{customer_id}:{branch_id}"` for balances.

- [ ] **Step 1: Write the failing tests**. Use `tests.test_debt_payments.World`. Each test asserts the exact `(code, expected, actual)` set for the corrupted record, and that the same scope without the corruption returns `[]`.
  - `test_correct_sale_payment_receivable_is_clean`: credit sale 400,000 with 150,000 at the till, then a debt payment of 100,000. A, B and C return no findings.
  - `test_receivable_overpaid`: the "duplicate allocation" of brief §31. A second active payment's allocation pushes the sale's paid amount to 450,000 against 400,000, giving `RECEIVABLE_OVERPAID` (400000, 450000).
  - `test_walkin_sale_unpaid`: lower the walk-in sale's till allocation, giving `WALKIN_SALE_UNPAID`.
  - `test_sale_items_mismatch`
  - `test_legacy_sale_clean_and_mismatch_is_warning` (Review Focus 4)
  - `test_missing_allocation`: a debt payment whose allocation row was deleted gives `ALLOCATION_TOTAL_MISMATCH` (amount, 0), and also `LEDGER_BALANCE_MISMATCH` for that customer.
  - `test_allocation_branch_and_customer_mismatch`
  - `test_orphaned_allocation`: an active payment allocated to a voided sale gives `ORPHAN_ALLOCATION`.
  - `test_reversed_payment_is_clean`: a debt payment reversed through the API gives no findings.
  - `test_missing_and_mismatched_ledger_entry`: delete the sale's `sale` row, giving `MISSING_LEDGER_ENTRY`. Change a payment row's credit, giving `LEDGER_ENTRY_MISMATCH` with detail `"amount"`.
  - `test_orphan_ledger_entry`: a `sale_void` row on a completed sale.
  - `test_cached_balance_mismatch`: an extra ledger debit of 5,000 gives `LEDGER_BALANCE_MISMATCH` (expected receivables, actual ledger, difference 5000).
  - `test_customer_scope_only_that_customer`
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_recon_documents.py -q`. Expected: FAIL (import error).
- [ ] **Step 3: Implement** checks A, B and C exactly as in the Checks table.
- [ ] **Step 4: Run** the same command. Expected: all pass.
- [ ] **Step 5: Commit** `feat(recon): sale, allocation and ledger checks`.

### Task 3: Period checks E, F, G

**Files:** Modify `app/services/reconciliation_checks.py`. Test: `tests/test_recon_period.py`.

**Interfaces:**
- Consumes: `sale_repo.get_totals_by_payment_method(db, branch_id, from_dt, to_dt)`, `report_service.get_profit_loss_report`, `utc_range_for_business_date`.
- Produces:
  - `async def check_sales_period(db, scope) -> CheckResult` (E). Its `summary.branches[id]` holds `sales_total`, `till_collected`, `credit_given`, `debt_collected`, `voided_count` and `voided_total` for the period.
  - `async def check_pnl(db, scope) -> CheckResult` (F; adds `pnl_revenue` to `summary.branches[id]`)
  - `async def check_closings(db, scope) -> CheckResult` (G, including duplicate references)
  - `closing_window(c: DailyClosing) -> tuple[datetime, datetime]`
  - `async def find_all(db, scope) -> CheckResult`: runs the checks that apply to the scope (see the Scope table) and merges findings, `examined` and `summary.branches`.

- [ ] **Step 1: Write the failing tests:**
  - `test_voided_sale_active_payment`: re-activate a till payment on a voided sale (direct update), giving `VOIDED_SALE_ACTIVE_PAYMENT`.
  - `test_period_summary_figures`: one walk-in sale of 100,000; one credit sale of 400,000 with 150,000 at the till; one debt payment of 50,000; one void. The summary has the exact figures.
  - `test_pnl_consistency`: after a debt payment, `check_pnl` returns no findings and `pnl_revenue` = Σ completed totals. Then lower one sale item's `line_total` directly, so items ≠ total. This gives `PNL_REVENUE_MISMATCH`, and Task 2's check also reports `SALE_ITEMS_MISMATCH`.
  - `test_closing_consistency`: close a day through the API, giving no findings. Then change the stored `total_cash` by +1,000, giving one `CLOSING_TOTAL_MISMATCH` with detail `"total_cash"` and difference 1000.
  - `test_closing_reopened_and_reclosed_is_clean`
  - `test_closing_without_opened_at_uses_business_day` (Review Focus 5)
  - `test_period_uses_tanzania_dates` (Review Focus 5): back-date a sale to 21:30 UTC on the previous calendar day. It falls inside the period of the local day and outside the period of the day before.
  - `test_duplicate_payment_reference_is_warning`: two mobile-money debt payments with reference `" mp123 "` and `"MP123"` give one finding of severity `warning`.
  - `test_scope_table`: `find_all` for `customer` scope runs no G check; `payment` scope runs B, C and the reference check.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_recon_period.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** checks E, F and G, `closing_window` and `find_all`.
- [ ] **Step 4: Run** the same command, then `tests/test_recon_documents.py`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(recon): period, P&L and closing checks`.

### Task 4: Runs (service and API)

**Files:** Create `app/schemas/reconciliation.py`, `app/services/reconciliation_service.py` and `app/api/v1/reconciliation.py`. Modify `app/api/v1/router.py`, `app/core/exceptions.py` and `app/db/seed_demo.py`. Test: `tests/test_recon_runs.py`.

**Interfaces:**
- **Produces, schemas:**
  - `RunCreate`: `scope`; `branch_id`, `customer_id`, `sale_id`, `payment_id` (optional); `period = "month"`, `from_date`, `to_date`.
  - `RunOut`: `id`, `run_no`, `scope`, `branch_name`, `customer: CustomerRef | None`, `sale_no`, `payment_no`, `date_from`, `date_to`, `started_at`, `finished_at`, `duration_ms`, `run_by_name`, `records_examined`, `discrepancy_count`, `warning_count`, `suppressed_count`, `status`, `by_code: dict[str, int]`, `summary: dict`.
  - `RunDetailOut(RunOut)`, which adds `exceptions: list[ExceptionOut]` (those whose `last_run_id` is this run).
- **Produces, service:**
  - `reconciliation_service.run(db, data: RunCreate, user) -> ReconciliationRun`:
    - takes the advisory lock, then runs `find_all`;
    - upserts by fingerprint, applying the Global Constraints rules;
    - sets the counts and status;
    - writes audit `RECON_RUN` (details: run_no, scope, status, counts);
    - commits.
  - `list_runs(db, limit=50)`, newest first; `get_run(db, run_id)`.
- **Routes:**
  - `POST /reconciliation/runs` → 201 `RunOut`
  - `GET /reconciliation/runs` → `list[RunOut]`
  - `GET /reconciliation/runs/{id}` → `RunDetailOut`
  - Access: `require_role("super_admin","admin","general_manager")`.
- **Errors:** `RECON_SCOPE_INVALID` (422) and `EXCEPTION_STILL_PRESENT` (409), plus `EXCEPTION_CLOSED` and `EXCEPTION_TRANSITION_INVALID` (both 422) for Task 5. All go in `_DEBT_ERRORS`, with sw/en text.

- [ ] **Step 1: Write the failing tests:**
  - `test_clean_mixed_history_passes` (Review Focus 1): a `PASSED` run with `discrepancy_count == 0`, `records_examined > 0`, and `run_no` starting `UPT-`.
  - `test_failed_run_lists_exceptions`: one corrupted ledger row gives a `FAILED` run, whose detail has the exception with its customer, branch, expected, actual and difference.
  - `test_warning_only_run`
  - `test_rerun_updates_not_duplicates` (Review Focus 3)
  - `test_dismissed_suppressed_unless_difference_changes` (Review Focus 3)
  - `test_run_writes_no_financial_rows`: snapshot `(count, Σ amount)` for sales, sale_items, payments, payment_allocations, customer_ledger_entries, opening_balances, daily_closings and customers, before and after a `FAILED` run. They must be identical.
  - `test_scope_validation`: `scope=sale` without `sale_id` → 422 `RECON_SCOPE_INVALID`; an unknown `branch_id` → 422; `from > to` → 422 `DATE_RANGE_INVALID`.
  - `test_unauthorized_reconciliation`: cashier and store keeper get 403 on all three routes; the GM can start a run and read runs.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_recon_runs.py -q`. Expected: FAIL (404).
- [ ] **Step 3: Implement** the schemas, service and routes. At the end of `seed_demo` seeding, start one `scope=all` run as the demo admin, so the demo page isn't empty and the seed proves its own data reconciles. Ruling: if the demo data doesn't reconcile, the seed is wrong; fix the seed, never the check.
- [ ] **Step 4: Run** the same command, plus `tests/test_recon_schema.py` and `tests/test_follow_ups.py::test_demo_wipe_clears_follow_ups`. Then check the seed on a throwaway database, never the dev DB:
  - `createdb dukani_seedcheck`;
  - with `DATABASE_URL` pointing at it, run `alembic upgrade head`, then `python -m app.db.seed_demo`;
  - read the seeded run's status;
  - `dropdb dukani_seedcheck`.

  Expected: all tests pass, and the seeded run is `PASSED` or `WARNING`, never `FAILED`.
- [ ] **Step 5: Commit** `feat(recon): on-demand reconciliation runs`.

### Task 5: Exception management

**Files:** Modify `app/services/reconciliation_service.py`, `app/schemas/reconciliation.py` and `app/api/v1/reconciliation.py`. Tests: `tests/test_recon_exceptions.py`, `tests/test_recon_true_concurrency.py`.

**Interfaces:**
- **Produces, schemas:**
  - `ExceptionOut`: `id`, `group`, `code`, `severity`, `status`, `customer: CustomerRef | None`, `sale_no`, `payment_no`, `opening_balance_ref`, `closing: {business_date, register_number} | None`, `branch_name`, `expected`, `actual`, `difference`, `detail`, `detected_at`, `last_seen_at`, `first_run_no`, `last_run_no`, `status_reason`, `status_reference`, `status_by_name`, `status_at`.
  - `StatusChange`: `status: Literal["OPEN","UNDER_REVIEW","RESOLVED","DISMISSED"]`, `reason: str` (5–500 characters, stripped), `reference: str | None` (≤100 characters).
- **Produces, service:**
  - `list_exceptions(db, status: list[str] | None, code, branch_id, run_id) -> list[ExceptionOut]`. Defaults to `OPEN` + `UNDER_REVIEW`; newest first.
  - `change_status(db, exception_id, data, user)`:
    - locks the row and validates the transition;
    - for `RESOLVED`, re-runs `find_all` with the scope and period of the exception's `last_run`, without persisting anything, and refuses if the fingerprint is still found;
    - writes the `status_*` fields and the audit `RECON_EXCEPTION_STATUS` (from, to, reason, reference).
- **Routes:**
  - `GET /reconciliation/exceptions?status=&code=&branch_id=&run_id=`: the three reader roles.
  - `POST /reconciliation/exceptions/{id}/status`: `require_role("super_admin","admin")`.

- [ ] **Step 1: Write the failing tests:**
  - `test_status_flow`: OPEN → UNDER_REVIEW (reason only) → DISMISSED (reason and reference). The audit row has from and to.
  - `test_resolve_requires_reference_and_reason`: 422 without them.
  - `test_resolve_refused_while_present`:
    1. Close a day through the API, then raise the stored `total_cash` by 1,000 directly, which gives `CLOSING_TOTAL_MISMATCH`.
    2. Resolving it now gives 409 `EXCEPTION_STILL_PRESENT`, and its status stays `OPEN`.
    3. Fix it with the normal correcting action: reopen the day and close it again through the API, which recomputes the totals.
    4. Resolving it again, with reference = the closing date, succeeds.
  - `test_final_states_locked`: changing a DISMISSED exception gives 422 `EXCEPTION_CLOSED`, and OPEN → OPEN gives `EXCEPTION_TRANSITION_INVALID`.
  - `test_unauthorized_exception_resolution`: GM, cashier and store keeper get 403 on the status route. The GM can list exceptions.
  - `test_true_concurrent_runs_one_live_exception` (`test_recon_true_concurrency.py`, separate committed sessions, the existing pattern): two runs started together over the same corruption leave exactly one live exception, and both runs succeed.
  - `test_true_concurrent_status_changes`: two DISMISSED requests at once on one OPEN exception. Exactly one returns 200, the other gets 422 `EXCEPTION_CLOSED`, and there is exactly one `RECON_EXCEPTION_STATUS` audit row.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_recon_exceptions.py tests/test_recon_true_concurrency.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the schemas, service and routes.
- [ ] **Step 4: Run** the same command. Expected: all pass.
- [ ] **Step 5: Commit** `feat(recon): exception review, resolution and dismissal`.

### Task 6: Exceptions report, WhatsApp, acceptance step 13

**Files:** Modify `app/api/v1/debt_reports.py`, `app/services/debt_report_service.py`, `app/schemas/debt.py`, `app/services/whatsapp_service.py` and `tests/test_debt_acceptance.py`. Test: `tests/test_debt_reports.py`.

**Interfaces:**
- **Produces:**
  - `ReconciliationReport(rows: list[ExceptionOut], summary: {by_status: dict[str, int], by_code: dict[str, int], money_open: int, last_run: RunOut | None})`
  - `GET /reports/debts/reconciliation?status=` (default: OPEN + UNDER_REVIEW; `status=all` for every status): the three reader roles. It has no period, because it describes the current exceptions.
  - `REPORT_TYPE_ROLES["debt_reconciliation"] = ("super_admin", "admin", "general_manager")`

- [ ] **Step 1: Write the failing tests:**
  - `test_reconciliation_report`: two exceptions (one dismissed). The default report shows one row; `status=all` shows two; and `summary.last_run.run_no` matches.
  - Cashier → 403.
  - Extend `test_whatsapp_accepts_debt_report_types` with `debt_reconciliation`.
  - In `test_abc_technologies_scenario`, add step 13. After the first payment, after the second payment and after the reversal, a `scope=all` run is `PASSED` with 0 discrepancies. A `scope=customer` run for ABC is `PASSED`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_debt_reports.py tests/test_debt_acceptance.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** the same command. Expected: all pass.
- [ ] **Step 5: Commit** `feat(recon): reconciliation exceptions report and acceptance step 13`.

### Task 7: Frontend — Upatanisho page and report

**Files:** see the File map (frontend). Verify with a local browser script in the session scratchpad (`s3_recon.mjs`, same `lib.mjs` session helper as stage 2), against the local dev DB only.

**Interfaces:**
- Consumes: the Task 4–6 routes.
- **Produces, permissions:**
  - `reconciliation.read` (super_admin, admin, general_manager)
  - `reconciliation.resolve` (super_admin, admin)
- **Produces, route and menu:**
  - Route `/madeni/upatanisho` behind `reconciliation.read`.
  - Sidebar child "Upatanisho wa Hesabu" under Madeni, with the same permission.
- **Produces, service:** `reconciliationService.runs.list/get/create` and `reconciliationService.exceptions.list/changeStatus`.
- **Produces, Reports page:**
  - Report type `debt_reconciliation` (label `SW.ripotiMadeni.upatanisho`, permission `reconciliation.read`), added to `NO_PERIOD_DEBT_REPORTS`.
  - A `normaliseReport` case, so it exports to PDF, Excel and WhatsApp.
- **Produces, translations:** sw/en section `upatanisho`, with:
  - page text;
  - the scope names;
  - the statuses (Imepita / Onyo / Imeshindwa; Wazi / Inakaguliwa / Imetatuliwa / Imepuuzwa);
  - one plain-language line per check code (`upatanisho.kodi.<CODE>`) saying what is wrong and the usual correcting action;
  - the error texts.
- **Page layout:**
  1. A run form: scope; branch, customer search, or sale/payment number as the scope needs; period, for the `all` and `branch` scopes.
  2. A list of the last runs: number, time, scope, run by, records examined, discrepancies, and a status badge.
  3. The selected run's (default: the latest) branch summary and its exceptions table.
  4. An "Tofauti Zote" tab: every live exception, filtered by status and code.
  5. Admins see a status button per row, which opens `ExceptionStatusModal`. Its reason is required, and the reference is required for Imetatuliwa and Imepuuzwa. The 409 `EXCEPTION_STILL_PRESENT` message is shown in the modal.

- [ ] **Step 1: Write the browser script** `s3_recon.mjs`:
  - as admin:
    - a clean `scope=all` run shows "Imepita";
    - after a corruption made through a local-only SQL helper on the dev DB, a run shows "Imeshindwa" with the exception's Swahili explanation;
    - resolving it unfixed shows the still-present message;
    - dismissing it with a reason and reference removes it from the live list;
  - as GM: can run, and sees no status button;
  - as cashier: the menu item is absent, and `/madeni/upatanisho` redirects;
  - on the Reports page: `debt_reconciliation` loads and downloads PDF and Excel.
- [ ] **Step 2: Run it.** Expected: FAIL (route missing).
- [ ] **Step 3: Implement** the page, components, service, permissions, route, sidebar, translations, report type and export case.
- [ ] **Step 4: Run** `node node_modules/.bin/vite build`, the sw/en key checker (`scratchpad/keys.mjs`) and the browser script. Expected: the build succeeds, the keys are identical, and every check reports PASS.
- [ ] **Step 5: Commit** `feat(recon): Upatanisho wa Hesabu page and exceptions report`.

### Task 8: Docs and the final acceptance report (§34)

**Files:** Modify `docs/RUNBOOK.md`, `docs/DEPLOYMENT.md` and the spec. Create `docs/customer-debt-implementation-report.md`.

- [ ] **Step 1: Run** the full suite `.venv/bin/python -m pytest -q > <workspace>/final_suite.txt` and the true-concurrency tests by name. Record the real counts. Brief §31: never report a test that didn't run.
- [ ] **Step 2: Write the docs:**
  - **RUNBOOK:** how to run a reconciliation, what each status means, how to handle an exception (the correcting action per code, then resolve with a reference), and why a run never fixes anything.
  - **DEPLOYMENT:** migration `f3a4b5c6d7e8` only creates tables. Do not start runs as part of deploy checks on prod.
  - **Spec:** a "Stage 3 status" section with this plan's rulings.
- [ ] **Step 3: Write** `docs/customer-debt-implementation-report.md`, with the §34 headings in order. Each item is marked **Completed**, **Partially completed** or **Not implemented**, with evidence (test names, endpoints, pages). It has these sections:
  - Database migrations (`c0d1e2f3a4b5`, `d1e2f3a4b5c6`, `e2f3a4b5c6d7`, `f3a4b5c6d7e8`, all additive).
  - Tests passed and failed (from Step 1's real output).
  - Known accounting limitations: no refunds or credit notes, no unapplied credit, references not verified with a provider, ageing as of today only, legacy sale payment columns kept, and the deferred stage 2 minors.
  - Production migration required: **YES**.
  - Rollback: downgrade per stage, then redeploy the previous commit; backup from deploy.sh.
  - Outstanding risks.
- [ ] **Step 4: Commit** `docs(debt): stage 3 runbook and final implementation report`.
