# Wateja na Madeni: Customer Accounts, Debt Management & Reconciliation (Design)

**Status:** draft for owner approval
**Date:** 2026-11-25
**Source brief:** the owner's "DUKANI POS — Customer Accounts, Debt Management & Financial Reconciliation" brief, parts 1 and 2 (sections 1–34), pasted in conversation. This document turns that brief into decisions; where the brief offered options, the chosen one is recorded here.

---

## 1. Intent

The shops sell on credit today, informally: who owes what lives in people's heads or a paper book. Management needs to know who owes, how much, since when, at which branch, and whether the numbers add up. Every answer must come from real records (sales, payments, approved old debts), never from a number someone typed in.

What success looks like:
- A cashier can sell partly or fully on credit to a registered customer, within the limit an admin set.
- A customer can pay a debt later, at the branch that owns the debt, and gets a receipt.
- Every customer balance can be explained line by line in a statement.
- Daily closing counts only money actually received. Credit given never shows up as cash.
- P&L does not change when a debt is paid.
- A reconciliation run can show that sales, payments and the ledger all agree, and list every place they don't.

## 2. Decisions the owner made (binding)

| # | Decision |
|---|---|
| D1 | A customer is registered **once** and shared by all branches. Each debt belongs to the **branch where the goods were taken**. |
| D2 | A debt is paid **only at the branch that owns it**. There is no cross-branch collection. |
| D3 | **Credit authorization, option A.** A cashier may give credit directly, but only to a registered, active customer and only within that customer's credit limit. Over the limit, the sale is blocked at the till; only admin or super_admin can raise the limit, and every change is audited. |
| D4 | The credit limit is **one total across all branches**. The exposure check uses the customer's outstanding balance at all branches. A branch-scoped user sees only the resulting "available credit", not other branches' details. |
| D5 | Old debts (from before the system) are **few**. Each is entered through a simple form and approved by a second person. There is no Excel import. |
| D6 | **Approach A:** a single payments record for all money received, plus an append-only customer ledger written in the same transaction. Reconciliation compares the two. |
| D7 | Build in **three stages**, each tested and deployed before the next (§13). |

## 3. Goals, non-goals, anti-goals

**Goals:** brief sections 2, 4–33, delivered over the three stages.

**Non-goals:**
- A general ledger or chart of accounts. This is a receivables subledger only.
- Refunds of money to customers, and credit notes. Today the system only voids whole sales; this design keeps that. A partial return or refund is a later feature.
- Unapplied or overpayment customer credit. A payment can never exceed what the customer owes at that branch (§6.3).
- Automatic "bad debtor" labels. Indicators are factual only (brief §15).
- Verifying mobile money or bank references against a provider.

**Anti-goals** (the feature has failed if any of these happens, even if everything "works"):
- Any customer balance that can be edited directly.
- A debt payment that shows up as revenue in P&L.
- Credit given that shows up as cash expected in the drawer at closing.
- A reconciliation run that changes financial data.
- A branch-scoped user seeing another branch's debts, statements or payments.
- Existing production data (users, products, inventory, closings) altered beyond the additive changes listed in §10.

## 4. Current state (Phase Zero assessment)

| # | Question (brief §3) | Finding |
|---|---|---|
| 1 | Split payments? | **No.** `sales.payment_method` is a single enum `payment_method_enum` (`cash`, `mobile_money`, `bank_transfer`). |
| 2 | Partial payments? | **No.** |
| 3 | Outstanding balance on a sale? | **No.** Every sale is assumed fully paid by its one method. |
| 4 | Payment status on sale? | **No.** `sales.status` is `completed` or `voided` only. |
| 5 | Payment methods recorded? | **Yes.** A reference is required for mobile money and bank (`SaleCreate` validator). |
| 6 | Refunds? | **No.** Only a whole-sale void, by admin or super_admin, while the sale's business day is not closed; it restores stock. |
| 7 | Customers linked to sales? | **No.** There is no customer table. |
| 8 | Edit or void? | No edit. Void as in 6. |
| 9 | How totals are computed | **Closing:** `sale_repo.get_totals_by_payment_method` sums `sales.total_amount` of completed sales by `payment_method` over the register window. The sales report payment breakdown (`report_service`) and the dashboard breakdown (`api/v1/reports.py`) use the same idea. **P&L:** sums `sale_items.line_total` and `quantity × cost_price` (cost snapshotted at sale) for completed sales, minus closing expenses. |
| 10 | P&L basis | **Accrual:** revenue is recognized on the sale's date. |

**Roles that exist:**
- `super_admin` and `admin`: global.
- `general_manager`: global for reads and transfers. Cannot create sales.
- `store_keeper`: main store only.
- `cashier`: own branch.

There is **no branch "Manager" role**. Only super_admin, admin and cashier can create sales (`POST /sales`).

**Existing infrastructure to reuse:**
- Branch authorization: `app/core/authorization.py` (`branch_context`, `resolve_read_branch_id`, `require_write_branch_access`).
- Idempotency keys: `app/core/idempotency.py`.
- Audit: `audit_service.log`.
- Tanzania business dates: `app/core/business_time.py`.
- Sequences for document numbers: `seq_sale_number` → `TXN-YYYYMMDD-NNNN`.
- Error format: flat `{detail, code, params}` with frontend `makosa.msimbo` translations.
- Exports: `frontend/src/utils/reportExport.js` (jsPDF and xlsx).
- Receipt printing: browser print in `ReceiptModal.jsx`.
- Translations: `constants/translations/sw.js` and `en.js`.
- Phone normalization: `whatsapp_service.normalize_phone`.

**What the change touches:**
- Checkout (`SaleCreate`, `sale_service.create_sale`, `CheckoutModal.jsx`).
- Void (`sale_service.void_sale`).
- Every reader of `sales.payment_method`: closing preview and close, sales report breakdown, dashboard breakdown, sales list filter, receipt, `SalesPage.jsx`, `seed_demo.py`.

**Data on the servers:** prod has users, branches, products and inventory but **no sales yet** (owner, 2026-11-25). Demo has seeded sales and closings.

## 5. Approaches considered

1. **Payments record plus append-only ledger (chosen, D6).** Every shilling received is a `payments` row allocated to the sale(s) it pays. Every event that changes what a customer owes is also an immutable `customer_ledger_entries` row, written in the same transaction. Statements read the ledger. Closing reads payments. Reconciliation compares documents against the ledger.
   - Cost: two records to keep in step; reconciliation exists to catch drift.
2. **Derive everything from sales and payments, no ledger.** Nothing can drift, but there's nothing independent to reconcile against (brief §9, §19C), and statements become heavy union queries.
   - Rejected by the owner.
3. **Mutable balance column on the customer.** Forbidden by the brief (§2, §9).

## 6. Domain design (stage 1, exact)

### 6.1 Money conventions

- All money is `Numeric(14,2)` in the database and `Decimal` in Python. Never float in new code. Responses serialize Decimal as the existing schemas do.
- **Ledger sign:** `debit` = increases what the customer owes; `credit` = decreases it. Each entry has exactly one of the two > 0 and the other = 0 (CHECK).
- **Customer balance** = Σdebit − Σcredit over the customer's ledger entries. **Branch balance** = the same, filtered by `branch_id`.
- **Outstanding on a receivable** (a sale or an approved old debt) = its amount − Σ allocations from **active** payments. There is **no cached balance column** anywhere. Balances are always computed (indexed queries). Reconciliation therefore compares the ledger against the documents, not against a cache.

### 6.2 New and changed tables

New columns and status fields use `String` plus a CHECK constraint rather than new Postgres enum types, following the project rule against enum-alter migrations. The existing `payment_method_enum` type is **reused** for payment methods (brief §10: no duplicate definitions).

**`customers`**

| column | notes |
|---|---|
| id | UUID PK |
| customer_no | `CUS-NNNN`, from new sequence `seq_customer_number`, unique |
| name | 2–150 chars, required |
| phone | required. Normalized to `255XXXXXXXXX` with `normalize_phone`. **Unique** (duplicate detection). |
| email, address | optional |
| customer_type | `individual` \| `business` \| `institution` \| `government` |
| tin | optional, ≤ 30 |
| credit_limit | Numeric ≥ 0, default 0. **0 means no credit.** |
| credit_days | int 0–365, default 30. The due period. |
| status | `active` \| `inactive` |
| notes | optional |
| created_by, created_at, updated_at | standard |

There is no delete endpoint at all. Deactivation is the only way to retire a customer (invariant 1). An inactive customer cannot receive new credit but can still pay debts.

**`sales` (changed, additive)**
- Add `customer_id` (nullable FK).
- Add `due_date` (Date, nullable). Set only when the sale leaves a balance: business date of the sale + customer's `credit_days`.
- The existing `payment_method` and `payment_reference` become **nullable legacy columns**. They are backfilled into `payments` (§10), no longer written for new sales, and no longer read by any code. Dropping them is deferred to a later release, after reconciliation has passed on prod.

**`payments`**: all money received.

| column | notes |
|---|---|
| id | UUID PK |
| payment_no | `PAY-YYYYMMDD-NNNN`, from new sequence `seq_payment_number`, unique |
| kind | `sale` (taken at checkout) \| `debt` (collected later) |
| customer_id | nullable. NULL only for `kind='sale'` walk-in payments. CHECK: `kind='debt'` ⇒ NOT NULL. |
| branch_id | **receiving** branch |
| method | `payment_method_enum` |
| reference | ≤ 100. Required for `mobile_money` and `bank_transfer`, same rule as today. |
| amount | > 0 |
| business_date | Tanzania business date when received |
| received_by | user FK |
| notes | optional |
| status | `active` \| `reversed` |
| reversed_by, reversed_at, reversal_reason | set once |
| created_at | standard |

**`payment_allocations`**: which receivable a payment settles.

| column | notes |
|---|---|
| id | UUID PK |
| payment_id | FK |
| sale_id | nullable FK |
| opening_balance_id | nullable FK |
| amount | > 0 |

- CHECK: exactly one of `sale_id` or `opening_balance_id` is set.
- UNIQUE (payment_id, sale_id) and UNIQUE (payment_id, opening_balance_id).

Allocations are never deleted. An allocation is "active" iff its payment is active (invariant 6, derived). The service enforces:
- Σ allocations of a payment = payment amount. There is no unapplied remainder (non-goal).
- An allocation never exceeds the receivable's outstanding amount.
- The receivable's branch = the payment's branch (D2).
- A `kind='sale'` payment allocates only to its own sale.

**`opening_balances`**: old debts (D5).

| column | notes |
|---|---|
| id | UUID PK |
| customer_id | FK |
| branch_id | FK |
| amount | > 0 |
| effective_date | business date the debt dates from, must be ≤ today |
| due_date | defaults to effective_date + customer.credit_days |
| reference | required, e.g. book page |
| description | optional |
| status | `pending` \| `approved` \| `rejected` |
| entered_by | user FK |
| decided_by, decided_at, decision_note | set once |
| created_at | standard |

CHECK: `decided_by <> entered_by`; a second person must decide. Only an approved row is a receivable and creates a ledger entry. Duplicate detection: entering the same (customer, branch, amount, reference) while a pending or approved row exists returns `OPENING_BALANCE_DUPLICATE`.

**`customer_ledger_entries`**: append-only.

| column | notes |
|---|---|
| id | UUID PK |
| customer_id | FK |
| branch_id | FK. The debt's branch: sale branch, opening-balance branch, or payment branch (all equal under D2). |
| entry_type | `sale` \| `payment` \| `payment_reversal` \| `sale_void` \| `opening_balance` |
| source_type, source_id | `sale` / `payment` / `opening_balance` plus its id |
| debit, credit | §6.1 |
| business_date | standard |
| due_date | for `sale` and `opening_balance` entries |
| description | system-generated |
| reverses_entry_id | nullable FK to the entry it reverses |
| created_by, created_at | standard |

- A DB trigger rejects `UPDATE` and `DELETE` on this table (invariant 8, enforced at DB level).
- UNIQUE (source_type, source_id, entry_type) makes duplicate posting impossible (invariant 5).

**`daily_closings` (changed, additive):** add `total_credit_given` and `total_debt_collected`, both Numeric default 0. Existing rows keep 0.

### 6.3 Flows

**Checkout** (`POST /sales`, extended; cashier, admin, super_admin as today)

The request replaces `payment_method`/`payment_reference` with:
- `payments: [{method, amount, reference?}]`, 0–3 entries.
- `customer_id?`

Server-side steps:
1. Compute the total from product prices, as today.
2. Let `paid` = Σ payments. Each amount > 0 and `paid ≤ total`. Cash change is the cashier's business: only the amount kept is entered, so the server never stores money tendered.
3. If `outstanding = total − paid > 0`:
   - `customer_id` is required, and the customer must be active with `credit_limit > 0`.
   - Lock the customer row `FOR UPDATE`. This serializes every credit decision for that customer across all branches, so concurrent sales can't jointly exceed the limit.
   - Compute exposure = customer ledger balance (all branches) + outstanding.
   - If exposure > credit_limit → 422 `CREDIT_LIMIT_EXCEEDED` with `params {limit, current, requested, available}`.
   - Set `due_date`.
4. A customer may also be attached to a fully paid sale (purchase history).
5. In the same transaction:
   - Create the sale, items and stock movements as today.
   - Create one `payments` row (`kind='sale'`) per payment, each with one allocation to this sale.
   - If a customer is attached, write the ledger: one `sale` debit for the **full total**, plus one `payment` credit per payment. The statement then shows what was bought and what was paid at the till; the net is the debt.
6. Audit `SALE_CREATED` gains `customer_id`, `payments`, `credit_amount`. Idempotency-Key works as today.

A sale with no payments and no customer is rejected (`CREDIT_REQUIRES_CUSTOMER`).

**Sale void** (admin, super_admin, as today, same closed-day rule)
- Refused with `SALE_HAS_DEBT_PAYMENTS` if any **active `kind='debt'`** payment is allocated to the sale. Those must be reversed first.
- Otherwise:
  - Stock is restored as today.
  - The sale's `kind='sale'` payments are marked reversed (reason "sale voided"). The money is assumed handed back, consistent with today's behaviour where a voided sale drops out of closing.
  - If a customer is attached: `sale_void` credit for the total, plus a `payment_reversal` debit per sale-time payment. Net change to the balance = −(outstanding).

**Debt payment** (`POST /customers/{id}/payments`; cashier for own branch, admin and super_admin for any branch)
- Body: `{branch_id, method, amount, reference?, notes?, allocations?: [{sale_id | opening_balance_id, amount}]}`.
- Cashier: `branch_id` is forced to their own branch, using `require_write_branch_access`.
- Refused if the branch's current business day is closed (`DAY_ALREADY_CLOSED`, same rule as sales).
- Locking: lock the customer row `FOR UPDATE`, then compute the branch's open receivables.
- `amount` ≤ outstanding at that branch, else `PAYMENT_EXCEEDS_DEBT`.
- Allocation:
  - If `allocations` is given, each must reference an open receivable of that customer at that branch, must not exceed its outstanding, and the allocations must sum to `amount`.
  - Otherwise **FIFO**: oldest due date first, then oldest date. The response and receipt list the allocations, so the rule is visible (brief §11).
- Writes `payments` (`kind='debt'`), the allocations, and one ledger `payment` credit. Audit `CUSTOMER_PAYMENT_RECORDED`.
- Idempotency-Key is required from the frontend.
- The receipt is returned only after commit.

**Payment reversal** (`POST /payments/{id}/reverse`; admin and super_admin only; reason 5–500 chars)
- Lock the payment.
- Must be `active` and `kind='debt'`, else `PAYMENT_ALREADY_REVERSED` or `SALE_PAYMENT_USE_VOID`. Sale-time payments are undone only by voiding the sale.
- Refused if the payment's business day is closed at that branch.
- Mark it reversed, write a ledger `payment_reversal` debit with `reverses_entry_id`, and audit `CUSTOMER_PAYMENT_REVERSED`.
- Its allocations become inactive by derivation, so the receivables reopen. Original rows stay visible.
- The corrected payment is then recorded normally (brief §23).

**Credit limit / terms change** (`PUT /customers/{id}/credit`; admin and super_admin; reason required)
- Audit `CUSTOMER_CREDIT_CHANGED` with: old and new limit, old and new days, current exposure, reason, user, timestamp.
- This is the D3 "override". It is not a per-sale bypass.

**Opening balance:**
- `POST /customers/{id}/opening-balances` (admin, super_admin) creates `pending`.
- `POST /opening-balances/{id}/approve` and `.../reject` (admin, super_admin, **not** the person who entered it).
- On approve: write a ledger `opening_balance` debit, and the row becomes an allocatable receivable.
- Approval does not check the credit limit. The debt already exists; the indicators will show any limit breach.

### 6.4 Daily closing and reports

- **Closing collections** = Σ **active** `payments` with `branch_id` = branch and `created_at` in the register window, grouped by method. This includes both kinds. It replaces `get_totals_by_payment_method`'s sale-total sums. Cash expected = cash payments.
- `total_revenue` and `total_sales_count` stay as today (completed sales in the window).
- New closing lines:
  - `total_credit_given` = Σ (sale total − its sale-time payments) for completed sales in the window.
  - `total_debt_collected` = Σ active `kind='debt'` payments in the window.
- Check: revenue = sale-time collections + credit given.
- **Sales report and dashboard "by payment method"**: the same payments source, sale-kind only, with an added "Mkopo / Credit" row. Debt collections are reported separately (stage 2).
- **P&L: unchanged code and unchanged figures.** It never reads payments, so a debt payment can't add revenue. This is pinned by a test (§12).

### 6.5 Who can do what (stage 1)

| Action | cashier | store_keeper | general_manager | admin / super_admin |
|---|---|---|---|---|
| Search/view customers (profile) | ✔ | ✘ | ✔ | ✔ |
| Create customer; edit name, phone, email, address, type, TIN | ✔ | ✘ | ✘ | ✔ |
| Set credit limit / days, (de)activate | ✘ | ✘ | ✘ | ✔ |
| See a customer's debts, payments, statement | own branch only, plus the total "available credit" | ✘ | all branches | all branches |
| Credit sale within limit | ✔ own branch | ✘ | ✘ (cannot sell today) | ✔ |
| Record debt payment | ✔ own branch | ✘ | ✘ | ✔ any branch |
| Reverse payment | ✘ | ✘ | ✘ | ✔ |
| Enter old debt | ✔ own branch | ✘ | ✘ | ✔ |
| Approve / reject / cancel old debt | ✘ | ✘ | ✘ | ✔ (may decide own entry, as a separate step) |
| See all debts (Madeni Yote) | own branch only | ✘ | all branches, read-only | all branches |
| Run reconciliation (stage 3) | ✘ | ✘ | ✔ read-only | ✔ |
| Resolve reconciliation exception (stage 3) | ✘ | ✘ | ✘ | ✔ |

All of this is enforced in the backend services, not only by hiding buttons. Profile edits are audited (`CUSTOMER_UPDATED` with changed fields).

### 6.6 API (stage 1)

All routes are under `/api/v1`, following existing naming and the flat error format. New error codes are added to `makosa.msimbo` in sw and en.

- `GET /customers?q=&status=&page=`: search by name, phone, customer_no, or a sale's transaction_no.
- `POST /customers`
- `GET /customers/{id}`: profile plus summary. Summary contains: balance (scoped), available credit (global figure), overdue amount, last payment.
- `PUT /customers/{id}`
- `PUT /customers/{id}/credit`
- `GET /customers/{id}/receivables?branch_id=`: open and recent sales and old debts, each with outstanding and a derived status `UNPAID|PARTIALLY_PAID|PAID|OVERDUE`. OVERDUE = outstanding > 0 and due_date < today (Tanzania business date).
- `POST /customers/{id}/payments`
- `GET /customers/{id}/payments`
- `GET /payments/{id}`
- `GET /payments/{id}/receipt`: reprint, no side effects.
- `POST /payments/{id}/reverse`
- `POST /customers/{id}/opening-balances`
- `GET /opening-balances?status=`
- `POST /opening-balances/{id}/approve|reject`
- `POST /sales`: changed body (§6.3).
- `GET /sales`: response gains `customer`, `payments[]`, `outstanding`, `payment_status`. The `payment_method` filter now matches via payments.

### 6.7 Frontend (stage 1)

- **Checkout** (`CheckoutModal.jsx`):
  - Customer picker (search, or "Mteja mpya" quick-add: name, phone, type).
  - Payment lines (method, amount, reference), with "Lipa yote" filling the remainder.
  - A live "Deni / Balance" line, and available credit when a customer is selected.
  - The server's `CREDIT_LIMIT_EXCEEDED` is shown with the numbers.
- **Receipt:** the sale receipt shows the payments and any balance plus due date. A new debt-payment receipt (§12 of the brief: business name, receipt no, customer, date, amount, method, reference, sales paid, previous balance, remaining, branch, received by) uses the same browser-print mechanism. Reprint calls the receipt endpoint.
- **New page `/wateja`** (nav "Wateja", for every role but store_keeper):
  - Customer list (name, phone, balance, limit, overdue, last payment, status).
  - Customer detail with tabs: Madeni (receivables), Malipo (payments, with reverse for admins), Taarifa (statement, stage 2).
  - "Pokea Malipo" (record payment) with a FIFO preview and optional manual allocation.
- **Admin pages:** "Madeni ya Zamani" (old debts: enter, approve and reject).
- **Sales page:** shows the customer, payments and balance per sale.
- **Closing page and report:** show credit given and debt collected.
- **Translations:** all strings in `sw.js` and `en.js` using the brief §30 terms. No hard-coded text.

## 7. Stage 2: Statements, ageing, dashboard, follow-ups, reports (outline)

- **Statement** (`GET /customers/{id}/statement?from=&to=&branch_id=`):
  - Opening balance at `from`, the ledger lines in order with running balance, and the closing balance.
  - Branch-scoped users see only their branch's lines.
  - PDF and Excel via `reportExport.js`.
- **Ageing** (`GET /receivables/ageing?branch_id=&as_of=`):
  - Per open receivable, days overdue = as_of − due_date.
  - Buckets: not due, 1–30, 31–60, 61–90, 90+.
  - Grouped per customer, with branch totals.
- **Debt dashboard:**
  - Total outstanding, customers owing, overdue total, collected in period, customers over limit, oldest debt, ageing distribution, top debtors.
  - Scoped by `branch_context`.
- **Risk indicators** (factual): available credit, % of limit used, overdue count and amount, oldest open item, last payment, total purchases and payments.
  - Flags: "≥ 80% of limit", "over limit", "overdue", "> 90 days", "inactive with debt".
- **Follow-ups:**
  - `customer_follow_ups` table: customer, branch, contact date, method (phone, visit, SMS, WhatsApp), note, expected payment date, responsible user.
  - No financial effect.
- **Reports and exports** (brief §29 items 1–7, 9) in `ReportsPage`, reusing `reportExport.js`. WhatsApp share reuses the existing button with new report types.

## 8. Stage 3: Reconciliation engine and exceptions (outline)

**Tables:**
- `reconciliation_runs`: id, scope (`all` / branch / customer / sale / payment), period, started and finished, run_by, records_examined, discrepancy_count, status `PASSED|WARNING|FAILED`.
- `reconciliation_exceptions`: run_id, check, customer, sale, payment, branch, expected, actual, difference, status `OPEN|UNDER_REVIEW|RESOLVED|DISMISSED`, resolution reason, user, timestamp, supporting reference.

**Checks**, mapped to brief §19. Every check is read-only.
- **A. Sale vs payments vs receivable:** for each completed sale, total = Σ active allocations + outstanding. A walk-in sale must have outstanding 0. The derived status must match.
- **B. Payment allocation:** for each payment, Σ allocations = amount. Allocations must point at existing receivables at the same branch. Flag duplicate allocations, allocations on voided sales from active debt payments, and orphaned allocations.
- **C. Ledger vs documents:** for each customer and branch, ledger balance = Σ outstanding of their receivables. Every sale with a customer, every payment with a customer, and every approved old debt has its ledger entries (missing or duplicate posting check).
- **D. Branch:** branch receivables = Σ outstanding of the branch's receivables. Payment branch = receivable branch.
- **E. Sales:** per period and branch, completed sale totals = sale-kind collections + credit given. Voided sales have no active payments.
- **F. P&L:** P&L revenue for the period = Σ completed sale item totals, independent of payments. Payments never appear in P&L inputs.
- **G. Closing:** for each closed register, stored totals by method, credit given and debt collected = recomputed from payments in its window. Flag duplicate mobile money and bank references.

**Status rules:**
- `FAILED` if any money mismatch.
- `WARNING` for reference duplicates and legacy-column mismatches only.
- `PASSED` otherwise.

**Resolution:** admin and super_admin only, with a reason and supporting reference. The fix itself is a normal correcting action (reversal, void, approved old debt). A run never writes financial rows.

## 9. Concurrency and idempotency

- **Credit decisions and debt payments** lock the customer row `FOR UPDATE`. This prevents concurrent over-limit, over-allocation and double settlement.
- **Reversals and voids** lock their payment or sale row. This prevents double reversal.
- **Document numbers** come from Postgres sequences, so they are unique by construction.
- **Idempotency-Key**: `POST /sales` already uses it. `POST /customers/{id}/payments`, `/payments/{id}/reverse` and opening-balance approve use the same mechanism.
- **True-concurrency tests** use separate committed sessions (existing `tests/` pattern) for:
  - two credit sales racing the same limit;
  - two payments racing the same debt;
  - two reversals of one payment;
  - a duplicate retry with the same key.

## 10. Migration and data safety

Stage 1 migrations are **additive**, because prod now holds real data. Migrations must not alter existing data beyond:
1. **Create** the new tables, sequences and the ledger trigger.
2. **Add** the nullable columns on `sales` and the defaulted columns on `daily_closings`.
3. Make `sales.payment_method` and `sales.payment_reference` nullable.
4. **Backfill**: insert one `payments` row (`kind='sale'`, same method, reference, amount = total, branch, created_at, business_date, received_by = cashier, status `reversed` if the sale is voided) plus its allocation for each existing sale. Prod has 0 sales, so this is a no-op there; demo gets its history converted. No ledger entries are created, because no existing sale has a customer.
5. Existing closings are untouched; their new columns are 0.

**Rollout steps:**
- Take a DB backup before deploying each stage (`BACKUP_RESTORE.md`).
- Each migration has a working `downgrade`. Stage 1's downgrade restores `payment_method` and `payment_reference` from the single payment of each sale.
- Rollback = downgrade, then redeploy the previous commit.

## 11. Security

Everything in §6.5 is enforced server-side. In addition:
- Branch-scoped users get their branch forced on every read and write.
- Customer search for a cashier returns profiles but scopes all money figures to their branch, plus the one global "available credit" number.
- IDs of other branches' sales or payments return 404, not 403, matching `get_sale_for_viewing`.
- Inputs are validated with Pydantic and lengths are bounded.
- Phone numbers are normalized.
- Every write is audited.

## 12. Testing and acceptance

Every test list in brief §31 becomes concrete tests in the stage that owns the code, all under `backend/tests/` with existing fixtures. Pinned invariants:
- P&L figures identical before and after a debt payment.
- Closing cash excludes credit given and includes debt cash collected.
- Ledger UPDATE and DELETE are rejected by the DB.
- Over-limit is blocked even with two concurrent sales.
- Tanzania midnight boundaries for business_date, due_date and ageing.

The brief §33 scenario (ABC Technologies, 5 × 80,000, pays 150,000 → 250,000; pays 100,000 → 150,000; reverse → 250,000; cross-branch access blocked) is one end-to-end test:
- Stage 1 covers steps 1–8 and 11–12, plus the second payment, the reversal and the access check.
- Steps 9–10 are added in stage 2.
- Step 13 is added in stage 3.

The brief §34 report is produced at the end of stage 3. It reports only test runs actually executed.

## 13. Stages

| Stage | Contents | Deploys |
|---|---|---|
| 1 | §6, §9, §10, §11: customers, checkout with split / partial / credit, payments, allocations, reversals, old debts, closing and report changes, `/wateja` pages, receipts, translations | yes |
| 2 | §7: statements, ageing, dashboard, indicators, follow-ups, reports and exports | yes |
| 3 | §8: reconciliation engine, exceptions, final acceptance report | yes |

Each stage gets its own implementation plan and is deployed only with the owner's approval. Pushing to main deploys prod and demo.

## 14. Left to the builder

- Exact Swahili and English copy (using the brief §30 terms and existing dictionary style).
- Page layout details.
- Query optimization and indexes (index at least: ledger `(customer_id, branch_id)`, payments `(branch_id, created_at)`, allocations `(sale_id)` and `(opening_balance_id)`, sales `(customer_id)`).
- How the FIFO preview is presented.
- Demo seed data for customers and credit sales (stage 1). The demo must show the feature.

## 15. Calls made by Claude (owner, please check)

1. Phone is **required and unique** per customer. This is the duplicate rule; name-alike customers only get a warning in search.
2. Default credit period is **30 days**, adjustable per customer by admins.
3. **No overpayment or unapplied credit**: a payment ≤ what is owed at that branch.
4. Mobile money and bank references are treated as received, as for sales today.
5. Only admin and super_admin reverse payments, change limits and approve old debts. The general manager reads everything but doesn't change money.
6. The cashier can create customers and edit contact details (audited), but not limits.
7. A credit sale with debt payments can't be voided until those payments are reversed.
8. The customer ledger records the full purchase and the till payment as separate lines, so the statement shows purchase history, not just debt.
9. Old payment columns on sales are kept, unused, until a later release, because prod now holds real data.
10. Debt payments and reversals are blocked on a closed day, the same as sales and voids.
11. Old-debt approval doesn't check the credit limit; the debt already exists.


## Addendum (2026-11-26): one admin per business, Madeni menu

Decided by the owner after stage 1 went live:

- **Each business has exactly one admin.** The superadmin is the system owner's hidden account and never acts for the business. The two-person rule for old debts (D5) is replaced: the admin checks an old debt against the notebook and approves or rejects it as a separate step, and may decide their own entries (migration `d1e2f3a4b5c6` drops `chk_opening_balances_two_person`).
- **Cashiers enter old debts** for their own branch (the server pins the branch); only the admin decides. Cashiers see their branch's entries and statuses.
- **Cancel ("Batilisha") an approved old debt**, admin only, reason required, only while no active payment is allocated to it. Status `cancelled`, posts an `opening_void` ledger credit. Lock order customer → old debt, the same as debt payments.
- **Madeni menu:** "Madeni Yote" (`GET /receivables`): every open debt with totals (owed, overdue, customers owing), status filter, search, and a per-row "Pokea Malipo". Branch-scoped like the customer pages. "Madeni ya Zamani" moves under it. Stage 2's ageing and debt dashboard extend this page rather than adding a new one.

## Stage 2 status (2026-11-27)

Built as planned in `docs/superpowers/plans/2026-11-27-customer-debt-stage2.md`: statements, ageing, the debt dashboard on Madeni Yote, factual risk flags, follow-up notes (`customer_follow_ups`, migration `e2f3a4b5c6d7`) and seven debt reports with PDF, Excel and WhatsApp. Rulings made while building:
- Ageing is always as of today (no `as_of` parameter).
- Ledger rows get their own `created_at`, so a sale always comes before its till payment in a statement.
- The "reconciliation exceptions" report (brief §29 item 8) belongs to stage 3.

## Stage 3 status (2026-11-27)

Built as planned in `docs/superpowers/plans/2026-11-27-customer-debt-stage3.md`: on-demand reconciliation runs (`reconciliation_runs`, `reconciliation_exceptions`, migration `f3a4b5c6d7e8`), checks A–G, exception review (open, under review, resolved, dismissed), the reconciliation exceptions report and the "Upatanisho wa Hesabu" page. The final report is `docs/customer-debt-implementation-report.md`. Rulings made while building:
- An active payment on a voided sale is `ORPHAN_ALLOCATION` (group B), not a separate group E code, so it is reported once and in every scope. Group E produces the period figures only.
- The sale items are compared with `sales.subtotal`, not the total: sales from before VAT was removed (migration 0007) have total = subtotal + VAT, which is history, not a discrepancy. The P&L check uses Σ subtotal for the same reason.
- Group D has no code of its own: branch totals are in each run's summary, and a branch gap is the sum of that branch's ledger-balance findings.
- Duplicate payment references are checked across all time, not just the period.
- Who may: run and read — super_admin, admin, general_manager; change an exception's status — super_admin, admin. Cashiers and store keepers get 403.
- Sale and payment scopes are started from an exception's "Kagua Tena"; the run form offers all, branch and customer.
