from tests.conftest import auth_headers, make_branch, make_inventory, make_product, make_user


async def _open(client, admin, branch, cash=50000):
    return await client.post(
        "/api/v1/closings/open",
        headers=auth_headers(admin),
        json={"branch_id": str(branch.id), "opening_cash": cash},
    )


async def _close(client, admin, branch, counted_cash=0):
    return await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={"branch_id": str(branch.id), "counted_cash": counted_cash, "expenses": []},
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


async def test_branch_can_open_register(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    resp = await _open(client, admin, branch, cash=25000)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "open"
    assert body["register_number"] == 1
    assert float(body["opening_cash"]) == 25000
    assert body["opened_by"] == admin.full_name


async def test_two_branches_open_registers_independently(client, db_session):
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    resp_a = await _open(client, admin, branch_a, cash=10000)
    resp_b = await _open(client, admin, branch_b, cash=20000)
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201
    assert resp_a.json()["branch_id"] == str(branch_a.id)
    assert resp_b.json()["branch_id"] == str(branch_b.id)


async def test_branch_a_closing_does_not_affect_branch_b(client, db_session):
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    await _open(client, admin, branch_a)
    await _open(client, admin, branch_b)

    close_a = await _close(client, admin, branch_a)
    assert close_a.status_code == 201
    assert close_a.json()["status"] == "closed"

    preview_b = await client.get(
        "/api/v1/closings/preview",
        params={"branch_id": str(branch_b.id)},
        headers=auth_headers(admin),
    )
    assert preview_b.status_code == 200
    assert preview_b.json()["already_closed"] is False
    assert preview_b.json()["register_open"] is True


async def test_double_open_register_rejected(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    first = await _open(client, admin, branch)
    assert first.status_code == 201

    second = await _open(client, admin, branch)
    assert second.status_code == 400


async def test_open_new_register_after_closing(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    first_open = await _open(client, admin, branch, cash=10000)
    assert first_open.json()["register_number"] == 1

    close_resp = await _close(client, admin, branch)
    assert close_resp.status_code == 201

    second_open = await _open(client, admin, branch, cash=15000)
    assert second_open.status_code == 201
    assert second_open.json()["register_number"] == 2
    assert second_open.json()["status"] == "open"


async def test_cannot_open_register_while_another_is_open(client, db_session):
    """Same guard as double-open, but exercised through the close->reopen
    interaction rather than two raw opens."""
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    await _open(client, admin, branch)
    resp = await _open(client, admin, branch)
    assert resp.status_code == 400


async def test_sales_blocked_after_closing_until_new_register_opens(client, db_session):
    """The period-scoped *totals* correctness (register #2's close must
    reflect only its own sales, never register #1's) is covered by
    test_opening_register_true_timing.py instead of here: this fixture's
    whole test runs inside one DB transaction, and Postgres's now() (which
    stamps Sale.created_at) returns the transaction's start time for every
    call within it — frozen, not real wall-clock time — so a savepoint-based
    test can never observe real time progression between register #1's
    sales and register #2's. This test instead covers what the savepoint
    harness *can* validate correctly: the block/unblock transition itself
    and register numbering."""
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    cashier = await make_user(db_session, "cashier", branch=branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=100)

    await _open(client, admin, branch)
    await _sell(client, cashier, branch, product, qty=2)
    close1 = await _close(client, admin, branch)
    assert close1.status_code == 201

    # Sales should now be blocked until a new register opens.
    blocked = await _sell(client, cashier, branch, product, qty=1)
    assert blocked.status_code == 400

    # Opening a new register (rather than reopening #1) unblocks selling
    # again, and is tracked as its own, separately-numbered period.
    open2 = await _open(client, admin, branch)
    assert open2.json()["register_number"] == 2
    resumed = await _sell(client, cashier, branch, product, qty=1)
    assert resumed.status_code == 201
    close2 = await _close(client, admin, branch)
    assert close2.status_code == 201
    assert close2.json()["register_number"] == 2


async def test_historical_closing_unchanged_after_new_register_closes(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    cashier = await make_user(db_session, "cashier", branch=branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=100)

    await _open(client, admin, branch)
    await _sell(client, cashier, branch, product, qty=5)
    close1 = await _close(client, admin, branch, counted_cash=1000)
    close1_id = close1.json()["id"]
    close1_revenue = close1.json()["total_revenue"]

    await _open(client, admin, branch)
    await _sell(client, cashier, branch, product, qty=1)
    await _close(client, admin, branch, counted_cash=2000)

    # Re-fetch register #1's own closing record — must be exactly as it was.
    listing = await client.get(
        "/api/v1/closings", params={"branch_id": str(branch.id)}, headers=auth_headers(admin)
    )
    assert listing.status_code == 200
    register_1 = next(r for r in listing.json()["items"] if r["id"] == close1_id)
    assert register_1["total_revenue"] == close1_revenue
    assert register_1["register_number"] == 1


async def test_cashier_cannot_open_register_for_another_branch(client, db_session):
    own_branch = await make_branch(db_session)
    other_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)

    resp = await _open(client, cashier, other_branch)
    assert resp.status_code == 403


async def test_cashier_can_open_register_for_own_branch(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)

    resp = await _open(client, cashier, branch)
    assert resp.status_code == 201


async def test_cannot_open_register_for_nonexistent_branch(client, db_session):
    import uuid

    admin = await make_user(db_session, "admin")
    resp = await client.post(
        "/api/v1/closings/open",
        headers=auth_headers(admin),
        json={"branch_id": str(uuid.uuid4()), "opening_cash": 1000},
    )
    assert resp.status_code == 404


async def test_sale_still_blocked_after_closing_even_with_fresh_login(client, db_session):
    """The closed-day block is pure DB state (daily_closings.status), never
    session/token state — so logging out and back in (a fresh JWT, nothing
    reused from the old session) must NOT be a way around it. Proves this by
    minting a brand-new token via a real /auth/login call, not by reusing
    the token captured before the day was closed."""
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    cashier = await make_user(db_session, "cashier", branch=branch, password="Test1234")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=100)

    await _open(client, admin, branch)
    first_sale = await _sell(client, cashier, branch, product, qty=1)
    assert first_sale.status_code == 201

    close_resp = await _close(client, admin, branch)
    assert close_resp.status_code == 201

    # Simulate logout + fresh login: a brand-new access token minted by a
    # real login call, not the token captured earlier in this test.
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": cashier.username, "password": "Test1234"},
    )
    assert login_resp.status_code == 200
    fresh_token = login_resp.json()["access_token"]
    fresh_headers = {"Authorization": f"Bearer {fresh_token}"}

    blocked_sale = await client.post(
        "/api/v1/sales",
        headers=fresh_headers,
        json={
            "branch_id": str(branch.id),
            "payment_method": "cash",
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )
    assert blocked_sale.status_code == 400

    # Confirm inventory wasn't touched by the blocked attempt.
    from sqlalchemy import select

    from app.models.inventory import Inventory

    inv = (
        await db_session.execute(
            select(Inventory).where(Inventory.branch_id == branch.id, Inventory.product_id == product.id)
        )
    ).scalar_one()
    assert inv.quantity == 99  # 100 - 1 from the pre-closing sale, untouched since


async def test_reopen_rejected_when_another_register_already_open(client, db_session):
    """Reopening an old closed register while a newer one is already open
    would create two simultaneously-open registers — must be rejected."""
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    await _open(client, admin, branch)
    close1 = await _close(client, admin, branch)
    close1_id = close1.json()["id"]

    await _open(client, admin, branch)  # register #2, now open

    reopen_resp = await client.put(
        f"/api/v1/closings/{close1_id}/reopen",
        headers=auth_headers(admin),
        json={"reason": "trying to reopen an old register while a new one is open"},
    )
    assert reopen_resp.status_code == 400
