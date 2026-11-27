# Customer & Debt Management Implementation Report

**System:** DUKANI POS — Wateja na Madeni (customer accounts, debts and reconciliation)
**Date:** 2026-11-27
**Covers:** stages 1–3 of `docs/superpowers/specs/2026-11-25-customer-debt-management-design.md`
**Test evidence:** the full backend suite run on branch `feat/customer-debt-stage3` before release — **455 passed, 0 failed**. Every test named below ran in that suite.

Status key: **Completed** · **Partially completed** · **Not implemented**

---

## Summary by area

| Area | Status | What exists, and the evidence |
|---|---|---|
| Customer management | **Completed** | Register once, shared by all branches; phone unique (duplicate rule); search by name, phone or number; edit (audited); deactivate. There is no delete: a customer with history can only be deactivated. Tests: `test_customers.py`. |
| Credit sales | **Completed** | Fully paid, partly paid and unpaid sales; split payments; credit only to an active registered customer within the limit (option A); over-limit sales are blocked at the till. Tests: `test_credit_sales.py`, `test_credit_sales_true_concurrency.py`. |
| Payment collection | **Completed** | Cash, mobile money and bank; partial and full; receipts; idempotency key against double recording; paid only at the branch that owns the debt. Tests: `test_debt_payments.py`, `test_debt_payments_true_concurrency.py`. |
| Payment allocation | **Completed** | Oldest-first (FIFO) by default, or chosen per debt; every allocation names the sale or old debt it settles. Tests: `test_debt_payments.py`; checked again by reconciliation group B. |
| Customer statements | **Completed** | Opening balance, every line with a running balance, closing balance = ledger balance; PDF, Excel and WhatsApp. Tests: `test_statement.py`. |
| Debt ageing | **Completed** | Not due, 1–30, 31–60, 61–90 and 90+ days from the due date (Tanzania business dates), always as of today. Tests: `test_ageing_dashboard.py`. |
| Credit limits | **Completed** | One limit across all branches; only the admin changes it, with a reason; every change audited. Cashiers see only "available credit". Tests: `test_customers.py`, `test_risk.py`. |
| Payment reversals | **Completed** | Admin only, with a reason; the original stays visible as reversed and the ledger gets an offsetting entry; a till payment is undone only by voiding its sale. Tests: `test_payment_reversal.py`, `test_debt_payments_true_concurrency.py::test_concurrent_reversals`. |
| Opening balances (old debts) | **Completed** | Entered by the admin, or by a cashier for their own branch; the admin approves or rejects them in a separate step; an approved one can be cancelled while it has no payments. Tests: `test_opening_balances.py`, `test_old_debt_cancel_true_concurrency.py`. |
| Branch isolation | **Completed** | A cashier is forced to their own branch on every read and write; another branch's sale or payment returns 404. Tests: `test_branch_context.py`, `test_debt_reports.py::test_cashier_reports_forced_to_own_branch`, and the final step of `test_debt_acceptance.py`. |
| P&L integration | **Completed** | Revenue is counted on the day of the sale, from the sale items; a later debt payment never adds revenue. Tests: `test_profit_loss.py`, `test_debt_acceptance.py`; checked again by reconciliation group F. |
| Daily closing integration | **Completed** | The drawer counts money actually received; credit given and debt collected are shown separately. Tests: `test_closing_payments.py`; checked again by reconciliation group G. |
| Reconciliation engine | **Completed** | Run on demand; checks A–G; results PASSED, WARNING or FAILED; exceptions are reviewed, resolved (refused while the difference still exists) or dismissed; a run never writes financial rows. Tests: `test_recon_documents.py`, `test_recon_period.py`, `test_recon_runs.py` (including `test_run_writes_no_financial_rows`), `test_recon_exceptions.py`, `test_recon_true_concurrency.py`. |
| English localization | **Completed** | All new pages, errors and reports are in `en.js`, with the same keys as `sw.js` (key check: 0 missing either way). |
| Swahili localization | **Completed** | Swahili is the default language; the terms follow brief §30 (Upatanisho wa Hesabu, Madeni ya Wateja, and so on). |

---

## Database migrations

All four are additive: they create tables, columns, sequences and constraints, and change no existing business rows.

| Revision | Stage | What it adds |
|---|---|---|
| `c0d1e2f3a4b5` | 1 | `customers`, `payments`, `payment_allocations`, `opening_balances`, `customer_ledger_entries` (append-only trigger), sale and closing columns, and a backfill of one payment per existing sale (none on prod). |
| `d1e2f3a4b5c6` | 1 (follow-up) | Cancelling old debts and the single-admin approval rule. |
| `e2f3a4b5c6d7` | 2 | `customer_follow_ups`. |
| `f3a4b5c6d7e8` | 3 | `reconciliation_runs`, `reconciliation_exceptions`, `seq_reconciliation_number`. |

**Production migration required: YES** — only `f3a4b5c6d7e8` is still to deploy; the other three are already live.

## API endpoints

- **Customers:**
  - `GET/POST /customers`
  - `GET/PUT /customers/{id}`
  - `PUT /customers/{id}/credit`
  - `GET /customers/{id}/receivables`
  - `GET/POST /customers/{id}/payments`
  - `POST /customers/{id}/opening-balances`
  - `GET /customers/{id}/statement`
  - `GET/POST /customers/{id}/follow-ups`
- **Payments:**
  - `GET /payments/{id}`
  - `GET /payments/{id}/receipt`
  - `POST /payments/{id}/reverse`
- **Old debts:**
  - `GET /opening-balances`
  - `POST /opening-balances/{id}/approve`
  - `POST /opening-balances/{id}/reject`
  - `POST /opening-balances/{id}/cancel`
- **Receivables:** `GET /receivables`, `GET /receivables/ageing`, `GET /receivables/dashboard`
- **Debt reports** (`GET /reports/debts/…`): `outstanding`, `overdue`, `ageing`, `collections`, `branches`, `credit-utilization`, `opening-balances`, `reconciliation`
- **Reconciliation:**
  - `POST/GET /reconciliation/runs`
  - `GET /reconciliation/runs/{id}`
  - `GET /reconciliation/exceptions`
  - `POST /reconciliation/exceptions/{id}/status`
- **Changed:** `POST /sales` (split, partial and credit payments), the sale void, and the closing preview and close.

## Frontend pages

- **Wateja:** customer list, and the customer page with the tabs Madeni, Malipo, Taarifa and Ufuatiliaji, plus risk indicators.
- **Madeni → Madeni Yote:** the dashboard, ageing and the list of every open debt.
- **Madeni → Madeni ya Zamani:** old debts.
- **Madeni → Upatanisho wa Hesabu:** reconciliation.
- **Ripoti:** eight "Madeni: …" report types.
- **Changed pages:** POS checkout (split, partial and credit), receipts and daily closing.

## Security controls

- Every rule is enforced on the server.
- Roles:
  - **Cashier:** customers, credit sales, payments and old-debt entry, all for their own branch.
  - **Admin:** limits, reversals, old-debt decisions and exception resolution.
  - **General manager:** reads everything and can run a reconciliation, but changes no money.
  - **Store keeper:** no access to debts.
- Every write is audited (category "sales"), including the reconciliation actions `RECON_RUN` and `RECON_EXCEPTION_STATUS`.
- The ledger rejects UPDATE and DELETE at database level.
- Authorization tests:
  - `test_recon_runs.py::test_unauthorized_reconciliation`
  - `test_recon_exceptions.py::test_unauthorized_exception_resolution`
  - `test_payment_reversal.py`
  - `test_debt_payments.py` (branch and allocation rules)

## Tests

- **Full backend suite: 455 passed, 0 failed.** These include the brief §31 groups: customers, credit sales, payments, reconciliation, security, dates (Tanzania midnight boundaries in `test_recon_period.py::test_period_uses_tanzania_dates` and the stage 1 and 2 date tests) and concurrency.
- **Acceptance scenario (brief §33, ABC Technologies):** `test_debt_acceptance.py::test_abc_technologies_scenario`, steps 1–13. Reconciliation passes after the first payment, after the second payment and after its reversal, and access from another branch is blocked.
- **Browser checks (local, not part of the suite):**
  - stage 2: customer page 13/13, Madeni Yote 10/10, reports 14/14;
  - stage 3: Upatanisho page 16/16 (admin, general manager, cashier, and the reports export).

### Concurrency test results (separate committed database connections)

| Test | Result |
|---|---|
| `test_credit_sales_true_concurrency::test_concurrent_credit_sales_cannot_exceed_limit` | passed |
| `test_debt_payments_true_concurrency::test_concurrent_payments_cannot_overpay` | passed |
| `test_debt_payments_true_concurrency::test_concurrent_reversals` | passed |
| `test_debt_payments_true_concurrency::test_void_lock_does_not_deadlock_with_debt_payment` | passed |
| `test_old_debt_cancel_true_concurrency::test_cancel_and_payment_race_has_one_winner` | passed |
| `test_recon_true_concurrency::test_true_concurrent_runs_one_live_exception` | passed |
| `test_recon_true_concurrency::test_true_concurrent_status_changes` | passed |
| `test_sale_void_true_concurrency::test_concurrent_void_cannot_restore_inventory_twice` | passed |
| `test_daily_closing_true_concurrency::test_concurrent_close_day_does_not_500_on_race` | passed |

Duplicate retries: `test_sale_idempotency.py` (sales) and the idempotency-key tests for debt payments in `test_debt_payments.py`.

### Regression

The suites that existed before this feature (sales, voids, inventory, transfers, closings, P&L, reports, users, WhatsApp) are part of the 455 and all pass.

### Seeded data check

The demo seed (21 days of sales, debts, payments and closings) ends with a reconciliation over its whole history: **PASSED, 857 records checked, 0 discrepancies**.

---

## Known accounting limitations

1. **No refunds or credit notes.** Only whole sales can be voided; partial returns are a later feature (spec non-goal).
2. **No overpayment or unapplied credit.** A payment can never exceed what the customer owes at that branch.
3. **References are not verified with a provider.** Mobile-money and bank references are treated as received. Reconciliation warns when one reference is used twice.
4. **Ageing is always as of today.** There is no "as at a past date" ageing.
5. **Legacy payment columns** on sales are kept but unused, for history.
6. **Sales from before VAT was removed** have total = subtotal + VAT; reconciliation treats that as history.
7. **Smaller issues from stage 2, not yet fixed:**
   - Debts without a due date can count as overdue in one place and not in another.
   - A follow-up note made only of spaces is saved empty.
   - Some date-range edge cases on the statement and report screens.
   - Deleting a user who has history gives an error page instead of a clear message.
   - The credit-limit report lists customers with no limit but a debt first.

## Rollback strategy

1. `deploy.sh` takes a database dump before every deploy (in `/home/cctvpoint/backups`).
2. **Code:** redeploy the previous commit.
3. **Schema, per stage:**
   - stage 3: `alembic downgrade e2f3a4b5c6d7` drops only the reconciliation history;
   - stage 2: `alembic downgrade d1e2f3a4b5c6` drops the follow-up notes;
   - stage 1: see `DEPLOYMENT.md`. Downgrading past stage 1 loses debt records, so once the feature has been used, restore from the pre-deploy dump instead.
4. The feature's history is append-only, so a mistake is fixed with a correcting action, never a rollback.

## Outstanding risks

- **First real use on prod.** Prod has real products and prices but no customers or debts yet, so the first real credit sales are the first real data. Run a reconciliation after the first busy days.
- **Test data on prod.** It is to be cleaned back to the pre-feature baseline (`pre_deploy_20261126_045751.sql`), keeping the real products and prices. Planned after this stage, with the owner's confirmation before any delete.
- **Reference duplicates are only warnings.** Someone must actually follow them up with the provider.
- **No automatic schedule.** A reconciliation runs only when someone starts it (brief §20 "on demand"). If nobody runs it, problems are found late.
