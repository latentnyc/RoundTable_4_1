import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    PROJECT_NAME = "RoundTable 4.1"
    VERSION = "0.1.0"
    API_PREFIX = ""

    # CORS
    DEFAULT_ORIGINS = [
        "https://roundtable41-1dc2c.web.app",
        "https://roundtable41-1dc2c.firebaseapp.com",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]

    @property
    def ALLOWED_ORIGINS(self):
        origins_env = os.getenv("ALLOWED_ORIGINS", "")
        allow_origins = []
        if origins_env:
            if ";" in origins_env:
                allow_origins = [o.strip() for o in origins_env.split(";") if o.strip()]
            else:
                allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()]

        return list(set(allow_origins + self.DEFAULT_ORIGINS))

settings = Settings()
