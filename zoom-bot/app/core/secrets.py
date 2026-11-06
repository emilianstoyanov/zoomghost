import os
from app.core.secrets_aws import get_secret_from_aws


def get_secret(key: str) -> str:
    if os.getenv("CI") == "true":
        # Fallback during GitHub Actions (CI): read from .env or use a dummy value
        print(f"[CI] Using fallback for secret: {key}")
        return os.getenv(key, f"dummy-{key.lower()}")

    return get_secret_from_aws(key)
