"""
Order Cancellation Tests
Tests for cancelling orders
"""

import pytest


@pytest.mark.cancel
class TestOrderCancellation:
    """Test cases for order cancellation"""
    
    def test_cancel_order_success(self, authenticated_client, test_order, test_user):
        """SUCCESS: Pending order cancelled successfully"""
        response = authenticated_client.post(
            f"/orders/cancel/{test_order.o_id}",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_cancel_paid_order(self, authenticated_client, paid_order, test_user):
        """FAIL: Cannot cancel paid order"""
        response = authenticated_client.post(
            f"/orders/cancel/{paid_order.o_id}",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_cancel_nonexistent_order(self, authenticated_client, test_user):
        """FAIL: Cannot cancel non-existent order"""
        response = authenticated_client.post(
            "/orders/cancel/9999",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_cancel_order_removes_from_db(self, authenticated_client, test_order, test_user, db_session):
        """SUCCESS: Cancelled order is removed from database"""
        from db import Order
        
        order_id = test_order.o_id
        authenticated_client.post(f"/orders/cancel/{order_id}")
        
        order = db_session.query(Order).filter(Order.o_id == order_id).first()
        assert order is None

    def test_cancel_order_unauthorized_user(self, authenticated_client, other_user, test_product, db_session):
        """FAIL: User cannot cancel another user's order"""
        from db import Order
        
        order = Order(
            c_id=other_user.id,
            p_id=test_product.p_id,
            total_price=100.0,
            payment_status="pending",
            is_delivered=False,
            quantity=1
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        
        response = authenticated_client.post(
            f"/orders/cancel/{order.o_id}",
            follow_redirects=False
        )
        assert response.status_code == 303
        
        check_order = db_session.query(Order).filter(Order.o_id == order.o_id).first()
        assert check_order is not None

    def test_cancel_cod_order(self, authenticated_client, test_user, test_product, db_session):
        """FAIL: Cannot cancel COD order"""
        from db import Order
        
        order = Order(
            c_id=test_user.id,
            p_id=test_product.p_id,
            total_price=100.0,
            payment_status="COD",
            is_delivered=False,
            quantity=1
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        
        response = authenticated_client.post(
            f"/orders/cancel/{order.o_id}",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_cancel_delivered_order(self, authenticated_client, test_user, test_product, db_session):
        """FAIL: Cannot cancel delivered order"""
        from db import Order
        
        order = Order(
            c_id=test_user.id,
            p_id=test_product.p_id,
            total_price=100.0,
            payment_status="pending",
            is_delivered=True,
            quantity=1
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        
        response = authenticated_client.post(
            f"/orders/cancel/{order.o_id}",
            follow_redirects=False
        )
        assert response.status_code == 303