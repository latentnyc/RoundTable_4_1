import os
import firebase_admin
import logging
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

def init_firebase():
    """
    Initializes the Firebase Admin SDK.
    - Connects to Emulators if FIREBASE_AUTH_EMULATOR_HOST is set.
    - Uses Default Application Credentials otherwise (for Prod).
    """
    try:
        # Check if already initialized to avoid "consult log" errors
        if not firebase_admin._apps:

            # If running locally with emulators, no creds needed/or use mock
            # The Admin SDK automatically detects emulators via env vars:
            # FIRESTORE_EMULATOR_HOST=localhost:8080
            # FIREBASE_AUTH_EMULATOR_HOST=localhost:9099

            if os.getenv("FIRESTORE_EMULATOR_HOST"):
                logger.info(f"Connecting to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')}")

                # Dummy key for emulator (valid PEM format required by Admin SDK)
                # This key is only used for local emulation and has no real access.
                fallback_key = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDEdDR2gnvUG2Ya
oT8mjttthGolX1qLULU6RuTLgvUaRCzqQcKKu+8e8breBFLfuJue+ABcNKaJNbWd
OTT3FYKKKUhDwUg3bRUabPYZtvc94XfcmhfixkJTNsL4tMnNfZVBVHDdGBueTATC
Ngt3IxXZRlMQ2apxNnfb9C6wEycMln9n+lr9Rpd+rTFqp5l8EUDLMDPkDbypZFgO
D43Fj5AsChdRrgfnWkym6C8IjzKeM9+nO4Twjwfh3z9dZ/ZwjX+ZkLuBujqFVb/x
ZLrS5slF9cnvzF6HQq/5FavRuNaMxH7asOVEZpVVM0XTllss4LMV2+V/+ArxknOQ
Ed+KImbFAgMBAAECggEABLiiNiLmpO9Pod40LVILlfMztdg3zddPs6nWf8mS6GGx
DqQr77eahIzcp89EypmeK9Db+VtOkUeYKMIiMrnynC1nzjEL8kEN28e4ll+eS39q
qQOPBWUsXOGZB+8YVnbpKlvEJpwYtdIv3xb7aY6PTNxyzJnejb/4W3Hf2V1sd9Hv
T5knoy0YjtDH2npB5tHHcvAvA1Bquo7A9dNONYHCmC3ZkbMPndB5GT14i4lU3duN
0zOvygfQK5M3vFsklhHfuH7csldpt/5B8O8SiGUVBmHpigw2sj7SJHk6XNPWzeLK
h5vxmJL5L5eYz5b0x9ZZtTAHQjvq6X5MxfTE9ewxYQKBgQDl+UpCdxkKgCwMI+iQ
o5/6cs1CVK3+rit8HFMNfI0xbUI0JvjbOFJrN9HwpukAUF9139nJQr1Jnmtk8pnQ
z4dEI90AmTn9+ukbHHlJ4iYGGSKRnciXzQB+eCN4bQ3z5v15j4odyYNC+O/PdjYu
yZcZ2DV+JgHWJvDfTPWjGeWbOQKBgQDar8pjkEx5/cyeKfVseEVYbuBuonvawUeQ
61qliYrjD/p6ZuhSvP6hRwJy4WzqwX1X8GvP4T8ZjDUP9ki2F5qApEGYlEmdBfVZ
tQ9JXgrP8LITGvQ2ziq5gGX0pNaBfliWs5ZpH3K4gYU5tQW9u1zaK1NvmSk4TPQb
IOOF9NhL7QKBgAVTpuKvO4dAvMRzOHnRMG1up054A6e4hQ1U4p+XWPXiH/xxQqZh
QZd2LYizdQYq1ms2iibdQuEnqDkoXWO2yt1LL11KL0uwuiGEoVKSyGqvvls9Gl5Z
wz8qrTem3wHdQdXE+2ABQOcWOQfHJy4iQTu6BFMtsjExqbaiY7YpbWYRAoGATVun
/WZbF0BHdJ+lGJTG+wxlyd0icPS0KziGHU61WbMaSNhEUJhYfpaO8DJ8A+MkQspi
aOvmFVR6pMXbXMamueDg72dtTuV/sBcTbEGfE4WyiH2dbBGsHWilKFBzLOWT0uN+
Tnt4anoutYYqnL49j1OKNUz5vtfB9iLBOW6uYNUCgYEAy3fdxBp7hQI6TOO+STnE
1rvUAZ1YUM8mnuu52SWNvwJv+tVC/ClhC2JVzClPnsDpZLhcblCOAy0bmZIyvJN4
WWxQ6RfITJQIg5LNTQ6axUg9c5LabzPVnc3bcsxAaW5ObtbNo8MWSwnZfWj3TWyo
9woYPuD6Xx+kG/PuXFegM4o=
-----END PRIVATE KEY-----"""

                env_key = os.getenv("FIREBASE_EMULATOR_PRIVATE_KEY", "")
                final_key = env_key if env_key else fallback_key

                cred = credentials.Certificate({
                    "type": "service_account",
                    "project_id": "roundtable41-1dc2c",
                    "private_key_id": "dummy_key_id",
                    "private_key": final_key.replace("\\n", "\n"),
                    "client_email": "firebase-adminsdk-dummy@roundtable41-1dc2c.iam.gserviceaccount.com",
                    "client_id": "dummy_client_id",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-dummy%40roundtable41-1dc2c.iam.gserviceaccount.com"
                })
            else:
                # Production: Use Service Account content from env or file
                # Best practice: Use Google Application Default Credentials (ADC)
                cred = credentials.ApplicationDefault()
                logger.info("Connecting to Production Firestore")

            firebase_admin.initialize_app(cred, {
                'projectId': 'roundtable41-1dc2c' # From .firebaserc
            })

            logger.info("Firebase Admin Initialized")

    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        raise e

def get_firestore():
    return firestore.client()
