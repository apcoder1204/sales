import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app as fastapi_app
from app.models.branch import Branch
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.role import Role
from app.models.user import User

# All fixtures run the whole test inside one DB transaction with a SAVEPOINT
# per session.commit() (join_transaction_mode="create_savepoint"), then roll
# the outer transaction back. Nothing a test does is ever persisted to the
# shared dev DB, even though app code under test calls db.commit() freely.

DEFAULT_TEST_PASSWORD = "Test1234"

# Every timestamp column in this schema is TIMESTAMPTZ; the app's naive
# `_utcnow()` convention assumes the DB session interprets naive values as
# UTC. The server's actual configured zone is Africa/Dar_es_Salaam (+3),
# so any engine used in tests needs this same override as app/db/session.py
# — otherwise naive-datetime comparisons/writes silently shift by 3 hours.
UTC_CONNECT_ARGS = {"server_settings": {"timezone": "UTC"}}


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL, connect_args=UTC_CONNECT_ARGS)
    conn = await engine.connect()
    outer_tx = await conn.begin()
    session = AsyncSession(
        bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        await session.close()
        await outer_tx.rollback()
        await conn.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def _get_db_override():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def get_or_create_role(db: AsyncSession, name: str) -> Role:
    row = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
    if row:
        return row
    row = Role(name=name)
    db.add(row)
    await db.flush()
    return row


async def make_branch(
    db: AsyncSession, branch_type: str = "pos_point", is_active: bool = True
) -> Branch:
    name = _uid("branch")
    b = Branch(name=name, code=name[:20].upper(), branch_type=branch_type, is_active=is_active)
    db.add(b)
    await db.flush()
    return b


async def get_main_store(db: AsyncSession) -> Branch:
    """Reuse the single seeded active main-store branch rather than creating a
    second one, since the app assumes exactly one active main store exists."""
    row = (
        await db.execute(
            select(Branch).where(Branch.branch_type == "main_store", Branch.is_active == True)
        )
    ).scalars().first()
    if row:
        return row
    return await make_branch(db, branch_type="main_store")


async def make_user(
    db: AsyncSession,
    role_name: str,
    branch: Branch | None = None,
    password: str = DEFAULT_TEST_PASSWORD,
    is_active: bool = True,
) -> User:
    role = await get_or_create_role(db, role_name)
    username = _uid("user")
    u = User(
        username=username,
        full_name=username,
        email=f"{username}@test.local",
        password_hash=hash_password(password),
        role_id=role.id,
        branch_id=branch.id if branch else None,
        is_active=is_active,
    )
    db.add(u)
    await db.flush()
    result = await db.execute(select(User).where(User.id == u.id))
    return result.scalar_one()


async def make_product(db: AsyncSession, minimum_stock: int = 5) -> Product:
    cat = (await db.execute(select(Category))).scalars().first()
    if not cat:
        cat = Category(name=_uid("cat"))
        db.add(cat)
        await db.flush()
    p = Product(
        product_code=_uid("code"),
        name=_uid("product"),
        category_id=cat.id,
        unit="Kipande",
        cost_price=1000,
        selling_price=1500,
        minimum_stock=minimum_stock,
    )
    db.add(p)
    await db.flush()
    return p


async def make_inventory(
    db: AsyncSession, product: Product, branch: Branch, quantity: int = 0, reserved_qty: int = 0
) -> Inventory:
    inv = Inventory(
        product_id=product.id, branch_id=branch.id, quantity=quantity, reserved_qty=reserved_qty
    )
    db.add(inv)
    await db.flush()
    return inv


def auth_headers(user: User) -> dict:
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}
