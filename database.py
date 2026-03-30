"""
database.py
-----------
Async MongoDB connection and collection accessors using Motor.

Collections:
    - questions:     GRE question bank with IRT difficulty metadata.
    - user_sessions: Adaptive testing sessions with per-user theta tracking.

Indexes created on startup:
    - questions.difficulty (ascending) — supports O(log n) range queries.
    - user_sessions.session_id (unique)
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017"
    db_name: str = "gre_prep"
    gemini_api_key: str = ""
    openai_api_key: str = ""


settings = Settings()

# ---------------------------------------------------------------------------
# Motor client — single instance reused across requests (connection pooling)
# ---------------------------------------------------------------------------
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        logger.info("MongoDB client created: %s", settings.mongodb_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[settings.db_name]
    return _db


async def create_indexes() -> None:
    """
    Ensure required MongoDB indexes exist.

    Called once on application startup via the FastAPI lifespan event.
    Safe to call multiple times (Motor/PyMongo is idempotent for existing indexes).
    """
    db = get_db()

    # questions collection — indexed for difficulty-range queries
    await db.questions.create_indexes(
        [
            IndexModel([("difficulty", ASCENDING)], name="difficulty_asc"),
            IndexModel([("topic", ASCENDING)], name="topic_asc"),
        ]
    )

    # user_sessions collection
    await db.user_sessions.create_indexes(
        [
            IndexModel(
                [("session_id", ASCENDING)],
                name="session_id_unique",
                unique=True,
            ),
        ]
    )

    logger.info("MongoDB indexes created/verified.")


async def close_connection() -> None:
    """Cleanly close the Motor connection pool on app shutdown."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed.")
