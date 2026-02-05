"""
Product Management Tests
Tests for product listing, creation, and management
"""

import pytest
from io import BytesIO


@pytest.mark.products
class TestProducts:
    """Test cases for product management"""
    
    def test_products_home_page(self, client):
        """SUCCESS: Home page with products loads"""
        response = client.get("/")
        assert response.status_code == 200

    def test_products_page_loads(self, client):
        """SUCCESS: Products page loads"""
        response = client.get("/products")
        assert response.status_code in [200, 303]

    def test_add_product_page_authenticated(self, authenticated_client):
        """SUCCESS: Authenticated user can access add product page"""
        response = authenticated_client.get("/addproduct")
        assert response.status_code == 200

    def test_add_product_page_unauthenticated(self, client):
        """FAIL: Unauthenticated user redirected"""
        response = client.get("/addproduct", follow_redirects=False)
        assert response.status_code == 303

    def test_add_product_success(self, authenticated_client, test_image):
        """SUCCESS: Product added successfully"""
        response = authenticated_client.post("/add-product", data={
            "title": "New Product",
            "description": "Product Description",
            "price": "150.0",
            "discount": "25.0",
            "category": "Electronics"
        }, files={
            "image": ("test.jpg", test_image, "image/jpeg")
        })
        assert response.status_code == 200

    def test_add_product_missing_fields(self, authenticated_client):
        """FAIL: Missing fields should show error"""
        response = authenticated_client.post("/add-product", data={
            "title": "Incomplete Product",
            "price": "100.0"
        })
        assert response.status_code == 200
        assert b"required" in response.content.lower() or b"fields" in response.content.lower()

    def test_add_product_invalid_discount_high(self, authenticated_client, test_image):
        """FAIL: Discount >= 90 should be rejected"""
        response = authenticated_client.post("/add-product", data={
            "title": "Invalid Discount Product",
            "description": "Description",
            "price": "100.0",
            "discount": "95.0",
            "category": "Electronics"
        }, files={
            "image": ("test.jpg", test_image, "image/jpeg")
        })
        assert response.status_code == 200
        assert b"valid" in response.content.lower() or b"range" in response.content.lower()

    def test_add_product_invalid_discount_low(self, authenticated_client, test_image):
        """FAIL: Discount < 10 should be rejected"""
        response = authenticated_client.post("/add-product", data={
            "title": "Low Discount Product",
            "description": "Description",
            "price": "100.0",
            "discount": "5.0",
            "category": "Electronics"
        }, files={
            "image": ("test.jpg", test_image, "image/jpeg")
        })
        assert response.status_code == 200
        assert b"valid" in response.content.lower() or b"range" in response.content.lower()

    def test_add_duplicate_product(self, authenticated_client, test_product, test_image):
        """FAIL: Duplicate product name should be rejected"""
        response = authenticated_client.post("/add-product", data={
            "title": "Test Product",
            "description": "Description",
            "price": "100.0",
            "discount": "20.0",
            "category": "Electronics"
        }, files={
            "image": ("test.jpg", test_image, "image/jpeg")
        })
        assert response.status_code == 200
        assert b"exist" in response.content.lower()

    def test_add_product_case_insensitive_duplicate(self, authenticated_client, test_product, test_image):
        """FAIL: Case-insensitive duplicate should be rejected"""
        response = authenticated_client.post("/add-product", data={
            "title": "TEST PRODUCT",
            "description": "Description",
            "price": "100.0",
            "discount": "20.0",
            "category": "Electronics"
        }, files={
            "image": ("test.jpg", test_image, "image/jpeg")
        })
        assert response.status_code == 200
        assert b"exist" in response.content.lower()

    def test_add_product_negative_price(self, authenticated_client, test_image):
        """EDGE: Negative price should be handled"""
        response = authenticated_client.post("/add-product", data={
            "title": "Negative Price Product",
            "description": "Description",
            "price": "-100.0",
            "discount": "20.0",
            "category": "Electronics"
        }, files={
            "image": ("test.jpg", test_image, "image/jpeg")
        })
        assert response.status_code in [200, 422]

    def test_add_product_zero_price(self, authenticated_client, test_image):
        """EDGE: Zero price should be handled"""
        response = authenticated_client.post("/add-product", data={
            "title": "Zero Price Product",
            "description": "Description",
            "price": "0.0",
            "discount": "20.0",
            "category": "Electronics"
        }, files={
            "image": ("test.jpg", test_image, "image/jpeg")
        })
        assert response.status_code in [200, 422]