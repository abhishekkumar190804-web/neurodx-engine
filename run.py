"""
NeuroDx Testing System — Startup Script
Run: python run.py

This script:
  1. Seeds the database (if empty)
  2. Starts the FastAPI server on port 8000
"""
import asyncio
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))


async def seed_if_needed():
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv()

    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "gre_adaptive")

    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
        db = client[db_name]
        count = await db.gre_questions.count_documents({})
        client.close()

        if count < 20:
            print(f"📦 Only {count} questions found — seeding database...")
            from backend.seed_db import seed
            await seed()
        else:
            print(f"✅ Database ready: {count} questions found")
    except Exception as e:
        print(f"⚠️  MongoDB connection error: {e}")
        print("   Make sure MongoDB is running on localhost:27017")
        sys.exit(1)


def main():
    print("=" * 55)
    print("  ⚡ NeuroDx Testing System")
    print("=" * 55)

    asyncio.run(seed_if_needed())

    print("\n🚀 Starting API server on http://localhost:8000")
    print("📖 API docs: http://localhost:8000/docs")
    print("🌐 Frontend: open frontend/index.html in your browser")
    print("   (or visit http://localhost:8000 if served via API)")
    print("\nPress Ctrl+C to stop the server.")
    print("-" * 55)

    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ])


if __name__ == "__main__":
    main()
