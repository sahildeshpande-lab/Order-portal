"""
Password Reset Tests
Tests for password reset/forget password functionality
"""

import pytest


@pytest.mark.password
class TestPasswordReset:
    """Test cases for password reset functionality"""
    
    def test_forget_password_page_loads(self, client):
        """SUCCESS: Forget password page loads"""
        response = client.get("/forget-password")
        assert response.status_code == 200

    def test_password_update_success(self, client, test_user):
        """SUCCESS: Password should update successfully"""
        response = client.post("/password", data={
            "email": "test@example.com",
            "password": "newpassword123"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_password_update_nonexistent_email(self, client):
        """FAIL: Non-existent email should show error"""
        response = client.post("/password", data={
            "email": "nonexistent@example.com",
            "password": "newpassword123"
        })
        assert response.status_code == 200
        assert b"not found" in response.content.lower()

    def test_password_update_same_password(self, client, test_user):
        """FAIL: Same password should be rejected"""
        response = client.post("/password", data={
            "email": "test@example.com",
            "password": "password123"
        })
        assert response.status_code == 200
        assert b"same" in response.content.lower() or b"different" in response.content.lower()

    def test_password_update_short_password(self, client, test_user):
        """EDGE: Short password should be rejected"""
        response = client.post("/password", data={
            "email": "test@example.com",
            "password": "123"
        })
        assert response.status_code == 200
        assert b"length" in response.content.lower() or b"greater" in response.content.lower()

    def test_password_update_redirects_to_login(self, client, test_user):
        """SUCCESS: After password update, should redirect to login"""
        response = client.post("/password", data={
            "email": "test@example.com",
            "password": "newpassword456"
        }, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_login_after_password_update(self, client, test_user):
        """SUCCESS: Can login with new password after update"""
        client.post("/password", data={
            "email": "test@example.com",
            "password": "updatedpassword"
        })
        
        response = client.post("/login", data={
            "email": "test@example.com",
            "password": "updatedpassword"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_old_password_fails_after_update(self, client, test_user):
        """FAIL: Old password should not work after update"""
        client.post("/password", data={
            "email": "test@example.com",
            "password": "brandnewpassword"
        })
        
        response = client.post("/login", data={
            "email": "test@example.com",
            "password": "password123"
        })
        assert response.status_code == 200
        assert b"not match" in response.content.lower()

    def test_password_update_empty_fields(self, client):
        """EDGE: Empty fields should be handled"""
        response = client.post("/password", data={
            "email": "",
            "password": ""
        })
        assert response.status_code in [200, 422]