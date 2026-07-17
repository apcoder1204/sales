"""
Seed script — run once after migrations:
  python -m app.db.seed
"""
import asyncio
from app.db.session import AsyncSessionLocal
from app.core.security import hash_password


async def seed():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text, insert, select
        from app.models.branch import Branch
        from app.models.role import Role
        from app.models.category import Category
        from app.models.user import User

        existing = await db.execute(select(Role).limit(1))
        if existing.scalar_one_or_none():
            print("Seed data already exists. Skipping.")
            return

        # Branches
        branches_data = [
            {"name": "Duka Kuu", "code": "MAIN", "branch_type": "main_store"},
            {"name": "CCTV POINT ILOMBA", "code": "POS1", "branch_type": "pos_point"},
            {"name": "CCTV POINT KABWE", "code": "POS2", "branch_type": "pos_point"},
            {"name": "CCTV POINT AH", "code": "POS3", "branch_type": "pos_point"},
        ]
        branches = {}
        for b in branches_data:
            branch = Branch(**b)
            db.add(branch)
            await db.flush()
            branches[b["code"]] = branch
            print(f"  Branch: {b['name']}")

        # Roles
        roles_data = [
            {"name": "super_admin", "description": "Msimamizi Mkuu - Ufikiaji kamili"},
            {"name": "admin", "description": "Msimamizi - Ufikiaji wa kiutawala"},
            {"name": "store_keeper", "description": "Mhusika wa Hifadhi - Usimamizi wa hisa"},
            {"name": "general_manager", "description": "Meneja Mkuu - Usimamizi wa matawi yote"},
            {"name": "cashier", "description": "Mhusika wa Fedha - Ufikiaji wa sehemu ya mauzo"},
        ]
        roles = {}
        for r in roles_data:
            role = Role(**r)
            db.add(role)
            await db.flush()
            roles[r["name"]] = role
            print(f"  Role: {r['name']}")

        # Categories
        cats_data = [
            {"name": "CCTV Camera", "name_sw": "Kamera ya CCTV", "description": "Kamera za usalama"},
            {"name": "Access Control", "name_sw": "Udhibiti wa Ufikiaji", "description": "Mifumo ya udhibiti"},
            {"name": "Networking", "name_sw": "Vifaa vya Mitandao", "description": "Router, switch, cables"},
            {"name": "Alarm System", "name_sw": "Mfumo wa Kengele", "description": "Alarm panels, sensors"},
        ]
        for c in cats_data:
            db.add(Category(**c))
            print(f"  Category: {c['name']}")
        await db.flush()

        # Users
        pwd = hash_password("1234")
        users_data = [
            {"username": "superadmin", "full_name": "Msimamizi Mkuu",
             "email": "superadmin@dukani.co.tz", "role": "super_admin", "branch": None},
            {"username": "admin", "full_name": "Msimamizi",
             "email": "admin@dukani.co.tz", "role": "admin", "branch": None},
            {"username": "storekeeper", "full_name": "Mhusika wa Hifadhi",
             "email": "hifadhi@dukani.co.tz", "role": "store_keeper", "branch": "MAIN"},
            {"username": "manager", "full_name": "Meneja Mkuu",
             "email": "meneja@dukani.co.tz", "role": "general_manager", "branch": None},
            {"username": "cctvpoint", "full_name": "Mhusika wa Fedha - Ilomba",
             "email": "ilomba@dukani.co.tz", "role": "cashier", "branch": "POS1"},
            {"username": "kabwepoint", "full_name": "Mhusika wa Fedha - Kabwe",
             "email": "kabwe@dukani.co.tz", "role": "cashier", "branch": "POS2"},
            {"username": "ahpoint", "full_name": "Mhusika wa Fedha - AH",
             "email": "ah@dukani.co.tz", "role": "cashier", "branch": "POS3"},
        ]
        for u in users_data:
            user = User(
                username=u["username"],
                full_name=u["full_name"],
                email=u["email"],
                password_hash=pwd,
                role_id=roles[u["role"]].id,
                branch_id=branches[u["branch"]].id if u["branch"] else None,
            )
            db.add(user)
            print(f"  User: {u['username']} / 1234  [{u['role']}]")

        await db.commit()
        print("\n✓ Seed data created successfully!")
        print("\nDemo credentials:")
        print("  superadmin / 1234")
        print("  admin / 1234")
        print("  storekeeper / 1234")
        print("  manager / 1234")
        print("  cctvpoint / 1234")
        print("  kabwepoint / 1234")
        print("  ahpoint / 1234")


if __name__ == "__main__":
    asyncio.run(seed())
