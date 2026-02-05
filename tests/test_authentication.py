"""
Authentication Tests
Tests for user login, logout, and session management
"""

import pytest


@pytest.mark.auth
class TestAuthentication:
    """Test cases for user authentication functionality"""
    
    def test_login_page_loads(self, client):
        """SUCCESS: Login page should load successfully"""
        response = client.get("/login")
        assert response.status_code == 200
        assert b"login" in response.content.lower() or b"email" in response.content.lower()

    def test_login_success(self, client, test_user):
        """SUCCESS: Valid credentials should log in user"""
        response = client.post("/login", data={
            "email": "test@example.com",
            "password": "password123"
        }, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/products"

    def test_login_invalid_email_format(self, client):
        """FAIL: Invalid email format should be rejected"""
        response = client.post("/login", data={
            "email": "invalid-email",
            "password": "password123"
        })
        assert response.status_code == 200
        assert b"Invalid email" in response.content or b"error" in response.content.lower()

    def test_login_nonexistent_user(self, client):
        """FAIL: Non-existent user should redirect to register"""
        response = client.post("/login", data={
            "email": "nonexistent@example.com",
            "password": "password123"
        })
        assert response.status_code == 200
        assert b"register" in response.content.lower() or b"not found" in response.content.lower()

    def test_login_wrong_password(self, client, test_user):
        """FAIL: Wrong password should show error"""
        response = client.post("/login", data={
            "email": "test@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 200
        assert b"not match" in response.content.lower() or b"error" in response.content.lower()

    def test_login_empty_fields(self, client):
        """EDGE: Empty fields should be handled"""
        response = client.post("/login", data={
            "email": "",
            "password": ""
        })
        assert response.status_code in [200, 422]

    def test_login_sets_session(self, client, test_user):
        """SUCCESS: Login should create session"""
        response = client.post("/login", data={
            "email": "test@example.com",
            "password": "password123"
        })
        assert "session" in client.cookies or response.status_code == 303

    def test_logout_success(self, authenticated_client):
        """SUCCESS: User logged out successfully"""
        response = authenticated_client.get("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_logout_clears_session(self, authenticated_client):
        """SUCCESS: Logout should clear session"""
        authenticated_client.get("/logout")
        response = authenticated_client.get("/addproduct", follow_redirects=False)
        assert response.status_code == 303

    def test_unauthenticated_redirect(self, client):
        """FAIL: Unauthenticated user redirected from protected routes"""
        response = client.get("/addproduct", follow_redirects=False)
        assert response.status_code == 303