from fastapi.testclient import TestClient
from app.main import app # Import your FastAPI application instance

client = TestClient(app)

def test_read_root():
    """
    Test if the root endpoint ('/') returns the expected welcome message.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Token Portal MVP! Visit /docs for API documentation."}

def test_read_docs():
    """
    Test if the /docs endpoint is accessible.
    """
    response = client.get("/docs")
    assert response.status_code == 200
    # We don't need to assert the full HTML content, just that it's accessible.

def test_read_openapi_json():
    """
    Test if the OpenAPI schema at /api/v1/openapi.json is accessible.
    """
    # The openapi_url is defined in app.main as f"{settings.API_V1_STR}/openapi.json"
    # settings.API_V1_STR is "/api/v1"
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert "openapi" in response.json() # Check for a key common in OpenAPI schemas 