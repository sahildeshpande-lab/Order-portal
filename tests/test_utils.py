"""
Utility Functions Tests
Tests for helper functions like password hashing and verification
"""

import pytest
from main import hash_password, verify_password


@pytest.mark.utility
class TestUtilityFunctions:
    """Test cases for utility functions"""
    
    def test_hash_password(self):
        """SUCCESS: Password hashing works"""
        password = "testpassword"
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """SUCCESS: Correct password verification"""
        password = "testpassword"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """FAIL: Incorrect password verification"""
        password = "testpassword"
        hashed = hash_password(password)
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_password_too_long(self):
        """EDGE: Very long password should raise exception"""
        long_password = "a" * 100
        with pytest.raises(Exception):
            hash_password(long_password)

    def test_hash_password_consistency(self):
        """SUCCESS: Same password produces different hashes (salt)"""
        password = "testpassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_verify_password_with_different_hashes(self):
        """SUCCESS: Verify works with different hashes of same password"""
        password = "testpassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_hash_password_special_characters(self):
        """SUCCESS: Password with special characters can be hashed"""
        password = "p@ssw0rd!#$%"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_unicode(self):
        """SUCCESS: Password with unicode characters can be hashed"""
        password = "пароль密码"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_empty(self):
        """EDGE: Empty password should be handled"""
        password = ""
        hashed = hash_password(password)
        assert len(hashed) > 0
        assert verify_password(password, hashed) is True

    def test_verify_password_empty_plain(self):
        """EDGE: Empty plain password verification"""
        password = "testpassword"
        hashed = hash_password(password)
        assert verify_password("", hashed) is False

    def test_hash_password_min_length(self):
        """SUCCESS: Minimum length password works"""
        password = "12345"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_max_safe_length(self):
        """SUCCESS: Maximum safe length (72 bytes) works"""
        password = "a" * 72
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_case_sensitive(self):
        """SUCCESS: Password verification is case-sensitive"""
        password = "TestPassword"
        hashed = hash_password(password)
        assert verify_password("testpassword", hashed) is False
        assert verify_password("TESTPASSWORD", hashed) is False
        assert verify_password("TestPassword", hashed) is True