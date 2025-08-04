"""MongoDB connection utilities."""

from pymongo import MongoClient
from .config import settings


def get_client() -> MongoClient:
    """Create a MongoDB client using configured settings."""
    return MongoClient(settings.MONGO_URI)


def get_collection(name: str):
    """Get a collection from the configured database."""
    client = get_client()
    db = client[settings.DB_NAME]
    return db[name]
