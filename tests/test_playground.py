from fastapi.testclient import TestClient

from orionxcore.main import app


def test_playground_page_renders() -> None:
    client = TestClient(app)
    response = client.get("/playground")

    assert response.status_code == 200
    assert "OrionXCore Playground" in response.text
    assert "/v1/agent/respond" in response.text
    assert "/v1/chat/completions" in response.text
