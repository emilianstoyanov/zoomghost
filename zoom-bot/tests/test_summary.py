from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_summarize_valid_text():
    """
    Check that /summarize returns a summary for valid text.
    """
    response = client.post("/api/summarize", json={"text": "Sample text for summarization."})
    assert response.status_code == 200
    assert "summary" in response.json()
    assert isinstance(response.json()["summary"], str)


def test_summarize_missing_text():
    """
    Check the behavior when the JSON payload has no 'text' key.
    Expect status 400 and a suitable message.
    """
    response = client.post("/api/summarize", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "No text provided"


def test_summarize_empty_text():
    """
    Check that empty text also returns status 400.
    """
    response = client.post("/api/summarize", json={"text": ""})
    assert response.status_code == 400
    assert response.json()["detail"] == "No text provided"
