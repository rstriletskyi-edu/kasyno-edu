import logging

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient

from src.configs.settings import Settings
from src.utils.exceptions import FirebaseNotInitializedError

logger = logging.getLogger(__name__)


def init_firebase(settings: Settings) -> bool:
    if is_firebase_initialized():
        return True

    credentials_file = settings.firebase_credentials_file
    if not credentials_file.is_file():
        logger.warning("Firebase credentials not found at %s; Firebase is disabled", credentials_file)
        return False

    options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else None
    firebase_admin.initialize_app(credentials.Certificate(credentials_file), options)
    logger.info("Firebase initialized for project %s", settings.firebase_project_id)
    return True


def is_firebase_initialized() -> bool:
    try:
        firebase_admin.get_app()
    except ValueError:
        return False
    return True


def get_firestore() -> FirestoreClient:
    if not is_firebase_initialized():
        raise FirebaseNotInitializedError()
    return firestore.client()
