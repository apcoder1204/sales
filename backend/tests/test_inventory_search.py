"""Inventory list search: the same rule as the Bidhaa list — product name
contains the text (any case), sorted by name, filtered on the server so the
results span every page, not just the page on screen."""
import uuid

import pytest

from tests.conftest import auth_headers, make_branch, make_inventory, make_product, make_user


@pytest.mark.asyncio
async def test_inventory_search_filters_across_pages(client, db_session):
    tag = uuid.uuid4().hex[:6]
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    names = [f"Zq{tag} Kamera 2", f"zq{tag} Adapta", f"Kebo Zq{tag}", f"Nyingine {tag}"]
    for name in names:
        p = await make_product(db_session)
        p.name = name
        await make_inventory(db_session, p, branch, quantity=3)
    await db_session.flush()

    async def page(n, per_page=2, search=f"zQ{tag}"):
        r = await client.get("/api/v1/inventory", params={"search": search, "page": n, "per_page": per_page},
                             headers=auth_headers(admin))
        assert r.status_code == 200, r.text
        return r.json()

    first, second = await page(1), await page(2)
    assert first["total"] == 3
    got = [x["name"] for x in first["items"] + second["items"]]
    assert got == sorted(names[:3], key=str.lower) or got == sorted(names[:3])
    assert f"Nyingine {tag}" not in got

    digits = await page(1, per_page=50, search=f"Kamera 2")
    assert f"Zq{tag} Kamera 2" in [x["name"] for x in digits["items"]]
