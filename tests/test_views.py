"""
Additional Views Tests
Tests for product manager, category views, and other features
"""

import pytest


class TestProductManager:
    """Test cases for product manager functionality"""
    
    def test_product_manager_page(self, authenticated_client, test_user):
        """SUCCESS: Product manager page loads"""
        response = authenticated_client.get(
            f"/products/get-orders/{test_user.id}/productmanager"
        )
        assert response.status_code == 200

    def test_product_manager_unauthorized(self, authenticated_client, other_user):
        """FAIL: Cannot access other user's product manager"""
        response = authenticated_client.get(
            f"/products/get-orders/{other_user.id}/productmanager",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_product_manager_with_orders(self, authenticated_client, test_user, test_product, db_session):
        """SUCCESS: Product manager displays orders"""
        from db import Order
        
        order = Order(
            c_id=test_user.id,
            p_id=test_product.p_id,
            total_price=100.0,
            payment_status="pending",
            is_delivered=False,
            quantity=2
        )
        db_session.add(order)
        db_session.commit()
        
        response = authenticated_client.get(
            f"/products/get-orders/{test_user.id}/productmanager"
        )
        assert response.status_code == 200


class TestCategory:
    """Test cases for category functionality"""
    
    def test_category_page(self, authenticated_client, test_user):
        """SUCCESS: Category page loads"""
        response = authenticated_client.get(
            f"/products/get-orders/{test_user.id}/category"
        )
        assert response.status_code == 200

    def test_category_unauthorized(self, authenticated_client, other_user):
        """FAIL: Cannot access other user's categories"""
        response = authenticated_client.get(
            f"/products/get-orders/{other_user.id}/category",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_category_with_orders(self, authenticated_client, test_user, test_product, db_session):
        """SUCCESS: Category displays orders"""
        from db import Order
        
        order = Order(
            c_id=test_user.id,
            p_id=test_product.p_id,
            total_price=100.0,
            payment_status="pending",
            is_delivered=False,
            quantity=1
        )
        db_session.add(order)
        db_session.commit()
        
        response = authenticated_client.get(
            f"/products/get-orders/{test_user.id}/category"
        )
        assert response.status_code == 200


class TestProductsPage:
    """Test cases for products page behavior"""
    
    def test_products_page_redirect_when_logged_in(self, authenticated_client):
        """SUCCESS: Logged in user redirected from /products"""
        response = authenticated_client.get("/products", follow_redirects=False)
        assert response.status_code == 303

    def test_products_page_shows_products(self, client, test_product):
        """SUCCESS: Products page displays products when not logged in"""
        response = client.get("/")
        assert response.status_code == 200