import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

try:
    print("Importing app.services.game_service...")
    from app.services import game_service
    print("Success.")

    print("Importing app.routers.campaigns...")
    from app.routers import campaigns
    print("Success.")

except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
