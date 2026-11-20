import logging

import firebase_admin
from firebase_admin import credentials, db, firestore
from firebase_admin.db import Reference
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

    options: dict[str, str] = {"databaseURL": settings.firebase_database_url}
    if settings.firebase_project_id:
        options["projectId"] = settings.firebase_project_id
    firebase_admin.initialize_app(credentials.Certificate(credentials_file), options or None)
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


def get_realtime_db() -> Reference:
    if not is_firebase_initialized():
        raise FirebaseNotInitializedError()
    try:
        return db.reference()
    except ValueError:
        raise FirebaseNotInitializedError("Realtime Database URL is not configured") from None
