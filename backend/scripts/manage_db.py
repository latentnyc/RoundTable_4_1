
import asyncio
import os
import sys
import argparse

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import engine
from db.schema import metadata

async def reset_db():
    print(f"Resetting database: {engine.url}")
    
    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(metadata.drop_all)
        print("Creating all tables...")
        await conn.run_sync(metadata.create_all)
    
    print("Database reset complete.")

async def create_db():
    print(f"Creating tables in: {engine.url}")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    print("Tables created.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage the database.")
    parser.add_argument("action", choices=["reset", "create"], help="Action to perform")
    
    args = parser.parse_args()
    
    if args.action == "reset":
        confirm = input("This will DESTROY ALL DATA in the database. Are you sure? (y/N): ")
        if confirm.lower() == "y":
            asyncio.run(reset_db())
        else:
            print("Operation cancelled.")
    elif args.action == "create":
        asyncio.run(create_db())
