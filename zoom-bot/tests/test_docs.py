from app.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_docs_available():
    """
    Check that the Swagger UI (/docs) is reachable.
    """
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
