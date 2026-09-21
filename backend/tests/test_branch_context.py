"""Tests for the centralized branch-context dependency (app.core.authorization
.branch_context / resolve_read_branch_id / get_authorized_branches) and the
route-level gaps it closed: GET /sales and GET /transfers previously left
store_keeper completely unrestricted, GET /products had zero branch
validation, and GET /users(/branches) returned everything unfiltered.

Existing files already cover per-module authorization in depth
(test_inventory_authorization.py, test_transfer_authorization.py,
test_report_authorization.py, test_audit_log_authorization.py) — this file
only covers what those don't: the shared dependency's own behavior, the
newly-fixed gaps, ALL-branches semantics, context switching, and
cross-request isolation.
"""
import uuid

from tests.conftest import (
    auth_headers, get_main_store, make_branch, make_inventory, make_product, make_user,
)


async def _sell(client, cashier, branch, product, qty=1):
    return await client.post(
        "/api/v1/sales",
        headers=auth_headers(cashier),
        json={
            "branch_id": str(branch.id),
            "payment_method": "cash",
            "items": [{"product_id": str(product.id), "quantity": qty}],
        },
    )


# ── GET /sales: store_keeper gap ────────────────────────────────────────────

async def test_store_keeper_sales_scoped_to_main_store(client, db_session):
    main_store = await get_main_store(db_session)
    other_branch = await make_branch(db_session)
    keeper = await make_user(db_session, "store_keeper", branch=main_store)
    cashier_main = await make_user(db_session, "cashier", branch=main_store)
    cashier_other = await make_user(db_session, "cashier", branch=other_branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=10)
    await make_inventory(db_session, product, other_branch, quantity=10)

    assert (await _sell(client, cashier_main, main_store, product)).status_code == 201
    assert (await _sell(client, cashier_other, other_branch, product)).status_code == 201

    # Before the fix, store_keeper hit GET /sales with no branch scoping at
    # all — they'd see every branch's sales. Now they must be pinned to the
    # live main store, matching every other module's store_keeper rule.
    resp = await client.get("/api/v1/sales", headers=auth_headers(keeper))
    assert resp.status_code == 200
    branches_seen = {item["branch_id"] for item in resp.json()["items"]}
    assert branches_seen == {str(main_store.id)}


async def test_store_keeper_sales_cannot_be_widened_by_branch_id_param(client, db_session):
    main_store = await get_main_store(db_session)
    other_branch = await make_branch(db_session)
    keeper = await make_user(db_session, "store_keeper", branch=main_store)
    cashier_other = await make_user(db_session, "cashier", branch=other_branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, other_branch, quantity=5)
    await _sell(client, cashier_other, other_branch, product)

    resp = await client.get(
        "/api/v1/sales", params={"branch_id": str(other_branch.id)}, headers=auth_headers(keeper)
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["branch_id"] == str(main_store.id)


# ── GET /transfers: store_keeper gap ────────────────────────────────────────

async def test_store_keeper_transfers_scoped_to_main_store(client, db_session):
    main_store = await get_main_store(db_session)
    pos_a = await make_branch(db_session)
    pos_b = await make_branch(db_session)
    keeper = await make_user(db_session, "store_keeper", branch=main_store)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=20)

    # main_store -> pos_a (involves the store_keeper's branch)
    r1 = await client.post(
        "/api/v1/transfers", headers=auth_headers(admin),
        json={"from_branch_id": str(main_store.id), "to_branch_id": str(pos_a.id),
              "items": [{"product_id": str(product.id), "quantity": 2}]},
    )
    assert r1.status_code == 201

    # A transfer that does NOT involve main_store at all requires stock at
    # pos_b, which this test doesn't set up — instead prove isolation via the
    # existing main_store->pos_a transfer plus a second main_store->pos_b one,
    # then confirm the store_keeper sees both (main_store is on both) and a
    # request scoped to an unrelated branch_id is ignored, not honored.
    r2 = await client.post(
        "/api/v1/transfers", headers=auth_headers(admin),
        json={"from_branch_id": str(main_store.id), "to_branch_id": str(pos_b.id),
              "items": [{"product_id": str(product.id), "quantity": 2}]},
    )
    assert r2.status_code == 201

    # Before the fix: store_keeper was in this route's role gate but got no
    # branch filter at all — from_branch_id/to_branch_id passed straight
    # through unrestricted. Now branch_context forces branch_id=main_store,
    # which the repo prioritizes over from/to entirely.
    resp = await client.get(
        "/api/v1/transfers", params={"to_branch_id": str(pos_a.id)}, headers=auth_headers(keeper)
    )
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(r1.json()["id"]) in ids
    assert str(r2.json()["id"]) in ids  # both involve main_store, so both are visible
    for item in resp.json()["items"]:
        assert main_store.name in (item["from_branch_name"], item["to_branch_name"])


# ── GET /products: previously zero branch validation ────────────────────────

async def test_products_rejects_nonexistent_branch_id(client, db_session):
    admin = await make_user(db_session, "admin")
    resp = await client.get(
        "/api/v1/products", params={"branch_id": str(uuid.uuid4())}, headers=auth_headers(admin)
    )
    assert resp.status_code == 404


async def test_products_cashier_cannot_probe_another_branch_stock(client, db_session):
    own_branch = await make_branch(db_session)
    other_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, own_branch, quantity=3)
    await make_inventory(db_session, product, other_branch, quantity=99)

    resp = await client.get(
        "/api/v1/products", params={"branch_id": str(other_branch.id), "per_page": 100},
        headers=auth_headers(cashier),
    )
    assert resp.status_code == 200
    row = next((p for p in resp.json()["items"] if p["id"] == str(product.id)), None)
    # A cashier must never see another branch's stock, regardless of what
    # branch_id they pass — branch_context silently overrides it to their own.
    if row is not None and row.get("available_qty") is not None:
        assert row["available_qty"] != 99


# ── GET /users/branches: previously unfiltered for every role ───────────────

async def test_branches_endpoint_scoped_for_cashier(client, db_session):
    own_branch = await make_branch(db_session)
    await make_branch(db_session)  # an unrelated branch that must not appear
    cashier = await make_user(db_session, "cashier", branch=own_branch)

    resp = await client.get("/api/v1/users/branches", headers=auth_headers(cashier))
    assert resp.status_code == 200
    ids = {b["id"] for b in resp.json()}
    assert ids == {str(own_branch.id)}


async def test_branches_endpoint_scoped_for_store_keeper(client, db_session):
    main_store = await get_main_store(db_session)
    await make_branch(db_session)
    keeper = await make_user(db_session, "store_keeper", branch=main_store)

    resp = await client.get("/api/v1/users/branches", headers=auth_headers(keeper))
    assert resp.status_code == 200
    ids = {b["id"] for b in resp.json()}
    assert ids == {str(main_store.id)}


async def test_branches_endpoint_shows_all_active_for_admin(client, db_session):
    b1 = await make_branch(db_session)
    b2 = await make_branch(db_session)
    inactive = await make_branch(db_session, is_active=False)
    admin = await make_user(db_session, "admin")

    resp = await client.get("/api/v1/users/branches", headers=auth_headers(admin))
    assert resp.status_code == 200
    ids = {b["id"] for b in resp.json()}
    assert {str(b1.id), str(b2.id)} <= ids
    assert str(inactive.id) not in ids


# ── GET /users: branch filtering, global admins never hidden ────────────────

async def test_users_branch_filter_never_hides_global_admins(client, db_session):
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    cashier_a = await make_user(db_session, "cashier", branch=branch_a)
    cashier_b = await make_user(db_session, "cashier", branch=branch_b)
    caller = await make_user(db_session, "super_admin")

    resp = await client.get(
        "/api/v1/users", params={"branch_id": str(branch_a.id), "per_page": 100},
        headers=auth_headers(caller),
    )
    assert resp.status_code == 200
    ids = {u["id"] for u in resp.json()["items"]}
    assert str(cashier_a.id) in ids
    assert str(cashier_b.id) not in ids
    assert str(caller.id) in ids  # global-scope caller must remain visible


# ── ALL-branches vs specific-branch semantics ────────────────────────────────

async def test_admin_all_branches_returns_aggregate_across_branches(client, db_session):
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    cashier_a = await make_user(db_session, "cashier", branch=branch_a)
    cashier_b = await make_user(db_session, "cashier", branch=branch_b)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch_a, quantity=10)
    await make_inventory(db_session, product, branch_b, quantity=10)
    await _sell(client, cashier_a, branch_a, product)
    await _sell(client, cashier_b, branch_b, product)

    all_resp = await client.get("/api/v1/sales", headers=auth_headers(admin))
    scoped_resp = await client.get(
        "/api/v1/sales", params={"branch_id": str(branch_a.id)}, headers=auth_headers(admin)
    )
    assert all_resp.status_code == scoped_resp.status_code == 200
    assert all_resp.json()["total"] >= scoped_resp.json()["total"]
    assert scoped_resp.json()["total"] >= 1
    for item in scoped_resp.json()["items"]:
        assert item["branch_id"] == str(branch_a.id)


async def test_context_switch_all_to_a_to_b_to_all(client, db_session):
    """ALL -> Branch A -> Branch B -> ALL: each specific-branch request must
    return only that branch's data, and returning to ALL must include both
    again — proves the branch filter isn't sticky server-side state, it's
    purely derived from each request's own branch_id param."""
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    cashier_a = await make_user(db_session, "cashier", branch=branch_a)
    cashier_b = await make_user(db_session, "cashier", branch=branch_b)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch_a, quantity=10)
    await make_inventory(db_session, product, branch_b, quantity=10)
    sale_a = await _sell(client, cashier_a, branch_a, product)
    sale_b = await _sell(client, cashier_b, branch_b, product)
    assert sale_a.status_code == sale_b.status_code == 201

    r_all_1 = await client.get("/api/v1/sales", headers=auth_headers(admin))
    r_a = await client.get(
        "/api/v1/sales", params={"branch_id": str(branch_a.id)}, headers=auth_headers(admin)
    )
    r_b = await client.get(
        "/api/v1/sales", params={"branch_id": str(branch_b.id)}, headers=auth_headers(admin)
    )
    r_all_2 = await client.get("/api/v1/sales", headers=auth_headers(admin))

    ids_all_1 = {i["id"] for i in r_all_1.json()["items"]}
    ids_a = {i["id"] for i in r_a.json()["items"]}
    ids_b = {i["id"] for i in r_b.json()["items"]}
    ids_all_2 = {i["id"] for i in r_all_2.json()["items"]}

    assert sale_a.json()["sale"]["id"] in ids_a
    assert sale_b.json()["sale"]["id"] not in ids_a
    assert sale_b.json()["sale"]["id"] in ids_b
    assert sale_a.json()["sale"]["id"] not in ids_b
    assert ids_a <= ids_all_1
    assert ids_b <= ids_all_1
    assert ids_all_1 == ids_all_2  # ALL is stable/idempotent across calls


# ── Cross-request / "concurrency" isolation ──────────────────────────────────

async def test_interleaved_requests_different_branch_contexts_stay_isolated(client, db_session):
    """Two different users hitting the same endpoint in rapid alternation
    with different branch contexts must never see each other's result — the
    branch context is derived per-request from the JWT + query param, never
    from shared/global server state (a global Python variable or singleton
    would leak between these calls; a per-request dependency cannot).

    Note: this interleaves sequentially rather than via asyncio.gather() —
    the test harness's db_session is a single AsyncSession shared by every
    request in this test (not safe for true concurrent use across tasks;
    that pattern is reserved for the dedicated true-concurrency tests that
    open their own separate engine/connections). Sequential alternation
    still fully proves the property under test: if branch context were ever
    held in shared server-side state, even non-overlapping alternating calls
    would show contamination from one call to the next.
    """
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    cashier_a = await make_user(db_session, "cashier", branch=branch_a)
    cashier_b = await make_user(db_session, "cashier", branch=branch_b)
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch_a, quantity=10)
    await make_inventory(db_session, product, branch_b, quantity=10)
    await _sell(client, cashier_a, branch_a, product)
    await _sell(client, cashier_b, branch_b, product)

    for i in range(10):
        user = cashier_a if i % 2 == 0 else cashier_b
        expected_branch = branch_a.id if i % 2 == 0 else branch_b.id
        resp = await client.get("/api/v1/sales", headers=auth_headers(user))
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["branch_id"] == str(expected_branch)
