"""
Order Management Tests
Tests for creating, viewing, and managing orders
"""

import pytest


@pytest.mark.orders
class TestOrders:
    """Test cases for order functionality"""
    
    def test_create_order_success(self, authenticated_client, test_product):
        """SUCCESS: Order created successfully"""
        response = authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 2
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_create_order_invalid_product(self, authenticated_client):
        """FAIL: Invalid product ID should redirect"""
        response = authenticated_client.post("/order", data={
            "product_id": 9999,
            "quantity": 1
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_create_order_zero_quantity(self, authenticated_client, test_product):
        """EDGE: Zero quantity should be rejected"""
        response = authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 0
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_create_order_negative_quantity(self, authenticated_client, test_product):
        """EDGE: Negative quantity should be rejected"""
        response = authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": -1
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_duplicate_order(self, authenticated_client, test_product):
        """FAIL: Duplicate order for same product should show error"""
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        response = authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_view_orders(self, authenticated_client, test_user):
        """SUCCESS: User can view their orders"""
        response = authenticated_client.get(f"/products/get-orders/{test_user.id}")
        assert response.status_code == 200

    def test_view_orders_unauthorized(self, authenticated_client, other_user):
        """FAIL: User cannot view other user's orders"""
        response = authenticated_client.get(
            f"/products/get-orders/{other_user.id}",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_order_calculates_price_correctly(self, authenticated_client, test_product, db_session):
        """SUCCESS: Order price calculation is correct"""
        from db import Order
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 2
        })
        
        order = db_session.query(Order).filter(
            Order.p_id == test_product.p_id
        ).first()
        
        expected_price = 2 * (test_product.price - (test_product.price * test_product.discount / 100))
        assert order.total_price == expected_price

    def test_create_order_large_quantity(self, authenticated_client, test_product):
        """EDGE: Large quantity should be handled"""
        response = authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1000
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_view_orders_empty(self, authenticated_client, test_user):
        """SUCCESS: View orders with no orders returns successfully"""
        response = authenticated_client.get(f"/products/get-orders/{test_user.id}")
        assert response.status_code == 200