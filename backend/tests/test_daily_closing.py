from tests.conftest import auth_headers, make_branch, make_user


async def test_cashier_cannot_preview_another_branch(client, db_session):
    own_branch = await make_branch(db_session)
    other_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)

    resp = await client.get(
        "/api/v1/closings/preview",
        params={"branch_id": str(other_branch.id)},
        headers=auth_headers(cashier),
    )
    assert resp.status_code == 403


async def test_cashier_cannot_close_another_branch(client, db_session):
    own_branch = await make_branch(db_session)
    other_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)

    resp = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(cashier),
        json={"branch_id": str(other_branch.id), "counted_cash": 0, "expenses": []},
    )
    assert resp.status_code == 403


async def test_unauthorized_reopen_rejected(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    cashier = await make_user(db_session, "cashier", branch=branch)
    manager = await make_user(db_session, "general_manager")

    close_resp = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={"branch_id": str(branch.id), "counted_cash": 0, "expenses": []},
    )
    assert close_resp.status_code == 201
    closing_id = close_resp.json()["id"]

    for actor in (cashier, manager):
        resp = await client.put(
            f"/api/v1/closings/{closing_id}/reopen",
            headers=auth_headers(actor),
            json={"reason": "trying to reopen without permission"},
        )
        assert resp.status_code == 403


async def test_reopen_then_reclose_replaces_reconciliation(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    close_resp = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={
            "branch_id": str(branch.id), "counted_cash": 100,
            "expenses": [{"description": "matumizi 1", "amount": 10}],
        },
    )
    assert close_resp.status_code == 201
    closing_id = close_resp.json()["id"]
    assert close_resp.json()["status"] == "closed"

    reopen_resp = await client.put(
        f"/api/v1/closings/{closing_id}/reopen",
        headers=auth_headers(admin),
        json={"reason": "correcting an error"},
    )
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["status"] == "open"

    reclose_resp = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={"branch_id": str(branch.id), "counted_cash": 200, "expenses": []},
    )
    assert reclose_resp.status_code == 201
    body = reclose_resp.json()
    assert body["id"] == closing_id
    assert body["status"] == "closed"
    assert float(body["counted_cash"]) == 200
    assert body["expenses"] == []


async def test_close_already_closed_day_rejected(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    first = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={"branch_id": str(branch.id), "counted_cash": 0, "expenses": []},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={"branch_id": str(branch.id), "counted_cash": 0, "expenses": []},
    )
    assert second.status_code == 400
