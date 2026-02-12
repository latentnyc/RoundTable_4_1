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
                # For emulators, we can use an anonymous credential or just default
                # For emulators, we can use a dummy credential.
                # The Admin SDK requires a credential object, but emulators don't validate the signature.
                cred = credentials.Certificate({
                    "type": "service_account",
                    "project_id": "roundtable41-1dc2c",
                    "private_key_id": "dummy_key_id",
                    "private_key": os.getenv("FIREBASE_EMULATOR_PRIVATE_KEY", "").replace("\\n", "\n"),
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
                'projectId': 'roundtable41-1dc2c', # From .firebaserc
            })

            logger.info("Firebase Admin Initialized")

    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        raise e

def get_firestore():
    return firestore.client()
