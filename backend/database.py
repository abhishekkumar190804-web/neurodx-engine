"""
MongoDB async connection using Motor.
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "gre_adaptive")

client: AsyncIOMotorClient = None
db = None


async def connect_db():
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    # Create indexes
    await db.gre_questions.create_index("difficulty")
    await db.gre_questions.create_index("topic")
    await db.user_sessions.create_index("session_id")
    print(f"✅ Connected to MongoDB: {MONGO_URI}/{DB_NAME}")


async def close_db():
    global client
    if client:
        client.close()


def get_db():
    return db
