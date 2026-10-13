"""
MongoDB Atlas setup and validation script.
Connects to Atlas, verifies credentials, and provisions required collections and initial documents.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from bot.config import settings

# Ensure UTF-8 output on all shells
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def setup_mongodb():
    print("==================================================")
    print("      MONGODB ATLAS CONNECTION & SETUP           ")
    print("==================================================")

    uri = settings.mongo_uri
    if not uri:
        print("❌ Error: MONGO_URI is not set in .env")
        return False

    if "<db_password>" in uri:
        print("⚠️ Warning: Your MONGO_URI still contains the placeholder '<db_password>'.")
        print("Please replace '<db_password>' with your actual database user password.")
        return False

    print("Connecting to MongoDB Atlas...")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=7000)

    try:
        # 1. Ping admin
        await client.admin.command("ping")
        print("✅ Ping successful! Authentication and Network Access verified.")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return False

    db = client[settings.mongo_db_name]
    print(f"📁 Target Database: '{settings.mongo_db_name}'")

    # 2. Setup indexes
    print("Creating indexes on 'users' and 'jobs'...")
    await db.users.create_index("user_id", unique=True)
    await db.jobs.create_index("job_id", unique=True)
    await db.jobs.create_index("status")

    # 3. Provision Owner record in 'users'
    owner_id = settings.primary_owner_id
    if owner_id:
        print(f"Provisioning Primary Owner ({owner_id}) in 'users' collection...")
        await db.users.update_one(
            {"user_id": owner_id},
            {
                "$set": {
                    "user_id": owner_id,
                    "role": "owner",
                    "mode": "convert",
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        print(f"✅ Owner {owner_id} record saved.")

    # 4. Provision Host Handoff Lock
    print("Provisioning 'master_host_lock' in 'handoff_lock' collection...")
    await db.handoff_lock.update_one(
        {"_id": "master_host_lock"},
        {
            "$set": {
                "active_host": "render",
                "heartbeat": datetime.now(timezone.utc),
                "colab_waiting": False,
            }
        },
        upsert=True,
    )
    print("✅ Master host lock initialized with active_host='render'.")

    # 5. List collections
    collections = await db.list_collection_names()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🎉 MongoDB Setup Complete! Active Collections in '{settings.mongo_db_name}':")
    for col in collections:
        count = await db[col].count_documents({})
        print(f"  • {col} ({count} documents)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return True


if __name__ == "__main__":
    asyncio.run(setup_mongodb())
