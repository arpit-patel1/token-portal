from fastapi.testclient import TestClient
from app.main import app # Import your FastAPI application instance

client = TestClient(app)

def test_request_otp_success():
    """
    Test POST /api/v1/auth/request-otp with a valid email.
    Expects a 200 OK response and a success message.
    """
    test_email = "test.user@example.com"
    response = client.post("/api/v1/auth/request-otp", json={"email": test_email})
    assert response.status_code == 200
    assert "message" in response.json()
    assert "OTP has been sent to your email address if it is registered." in response.json()["message"]

def test_request_otp_invalid_email_format():
    """
    Test POST /api/v1/auth/request-otp with an invalid email format.
    Expects a 422 Unprocessable Entity response.
    """
    response = client.post("/api/v1/auth/request-otp", json={"email": "invalid-email"})
    assert response.status_code == 422
    assert "detail" in response.json()
    assert isinstance(response.json()["detail"], list)
    assert len(response.json()["detail"]) > 0
    error_detail = response.json()["detail"][0]
    assert "type" in error_detail
    assert error_detail["type"] == "value_error"
    assert "msg" in error_detail
    assert "not a valid email address" in error_detail["msg"]

def test_request_otp_missing_email():
    """
    Test POST /api/v1/auth/request-otp with no email provided.
    Expects a 422 Unprocessable Entity response.
    """
    response = client.post("/api/v1/auth/request-otp", json={})
    assert response.status_code == 422
    assert "detail" in response.json()
    assert isinstance(response.json()["detail"], list)
    assert len(response.json()["detail"]) > 0
    error_detail = response.json()["detail"][0]
    assert "type" in error_detail
    assert error_detail["type"] == "missing"
    assert "loc" in error_detail
    assert "email" in error_detail["loc"]

# --- Tests for /verify-otp --- 

def test_verify_otp_missing_email():
    """
    Test POST /api/v1/auth/verify-otp with no email provided.
    Expects a 422 Unprocessable Entity response.
    """
    response = client.post("/api/v1/auth/verify-otp", json={"otp": "12345"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(err["type"] == "missing" and "email" in err["loc"] for err in detail)

def test_verify_otp_missing_otp_code():
    """
    Test POST /api/v1/auth/verify-otp with no otp_code provided.
    Expects a 422 Unprocessable Entity response.
    """
    response = client.post("/api/v1/auth/verify-otp", json={"email": "test@example.com"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(err["type"] == "missing" and "otp" in err["loc"] for err in detail)

def test_verify_otp_invalid_email_format():
    """
    Test POST /api/v1/auth/verify-otp with an invalid email format.
    Expects a 422 Unprocessable Entity response.
    """
    response = client.post("/api/v1/auth/verify-otp", json={"email": "invalid-email", "otp": "12345"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("not a valid email address" in err["msg"] for err in detail)

def test_verify_otp_code_too_short():
    """
    Test POST /api/v1/auth/verify-otp with an OTP code that is too short.
    Now expects a 400 Bad Request as service layer handles this.
    """
    response = client.post("/api/v1/auth/verify-otp", json={"email": "test@example.com", "otp": "123"})
    assert response.status_code == 400 # Changed from 422
    assert "detail" in response.json()
    assert response.json()["detail"] == "Invalid OTP, email, or OTP has expired. Please try again."

def test_verify_otp_code_too_long():
    """
    Test POST /api/v1/auth/verify-otp with an OTP code that is too long.
    Now expects a 400 Bad Request as service layer handles this.
    """
    response = client.post("/api/v1/auth/verify-otp", json={"email": "test@example.com", "otp": "123456"})
    assert response.status_code == 400 # Changed from 422
    assert "detail" in response.json()
    assert response.json()["detail"] == "Invalid OTP, email, or OTP has expired. Please try again."

def test_verify_otp_code_not_numeric():
    """
    Test POST /api/v1/auth/verify-otp with an OTP code that is not numeric.
    Now expects a 400 Bad Request as service layer handles this.
    """
    response = client.post("/api/v1/auth/verify-otp", json={"email": "test@example.com", "otp": "abcde"})
    assert response.status_code == 400 # Changed from 422
    assert "detail" in response.json()
    assert response.json()["detail"] == "Invalid OTP, email, or OTP has expired. Please try again."

def test_verify_otp_invalid_or_expired():
    """
    Test POST /api/v1/auth/verify-otp with a correctly formatted but invalid/expired OTP.
    Requests an OTP first to ensure user context.
    Expects a 400 Bad Request response.
    """
    test_email = "verify.otp.fail.ascii.only@example.com" # Simplified to ASCII only
    
    # Use a separate TestClient instance for the setup call to ensure isolation
    setup_client = TestClient(app)
    request_otp_response = setup_client.post("/api/v1/auth/request-otp", json={"email": test_email})
    assert request_otp_response.status_code == 200 # Ensure OTP request itself was successful
    
    # Use the main test client for the actual verification test
    response = client.post("/api/v1/auth/verify-otp", json={"email": test_email, "otp": "00000"})
    assert response.status_code == 400
    assert "detail" in response.json()
    assert response.json()["detail"] == "Invalid OTP, email, or OTP has expired. Please try again." 