"""
Delivery Update Tests
Tests for updating delivery status of orders
"""

import pytest


@pytest.mark.delivery
class TestDeliveryUpdate:
    """Test cases for delivery status updates"""
    
    def test_update_delivery_success_cod(self, authenticated_client, test_user, test_product, db_session):
        """SUCCESS: Delivery status updated successfully for COD order"""
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
        
        response = authenticated_client.put(
            f"/updatedeliver/{test_product.p_id}",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_update_delivery_success_paid(self, authenticated_client, test_user, test_product, db_session):
        """SUCCESS: Delivery status updated successfully for PAID order"""
        from db import Order
        
        order = Order(
            c_id=test_user.id,
            p_id=test_product.p_id,
            total_price=100.0,
            payment_status="PAID",
            is_delivered=False,
            quantity=1
        )
        db_session.add(order)
        db_session.commit()
        
        response = authenticated_client.put(
            f"/updatedeliver/{test_product.p_id}",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_update_delivery_already_delivered(self, authenticated_client, test_user, test_product, db_session):
        """FAIL: Cannot update already delivered order"""
        from db import Order
        from fastapi import HTTPException
        
        order = Order(
            c_id=test_user.id,
            p_id=test_product.p_id,
            total_price=100.0,
            payment_status="COD",
            is_delivered=True,
            quantity=1
        )
        db_session.add(order)
        db_session.commit()
        
        response = authenticated_client.put(f"/updatedeliver/{test_product.p_id}")
        assert response.status_code == 400
        assert b"already delivered" in response.content.lower()

    def test_update_delivery_unpaid_order(self, authenticated_client, test_order, test_product):
        """FAIL: Cannot update delivery for unpaid order"""
        response = authenticated_client.put(f"/updatedeliver/{test_product.p_id}")
        assert response.status_code == 404
        assert b"not found" in response.content.lower() or b"unpaid" in response.content.lower()

    def test_update_delivery_nonexistent_product(self, authenticated_client):
        """FAIL: Cannot update delivery for non-existent product"""
        response = authenticated_client.put("/updatedeliver/9999")
        assert response.status_code == 404
        assert b"not found" in response.content.lower() or b"unpaid" in response.content.lower()

    def test_update_delivery_sets_flag(self, authenticated_client, test_user, test_product, db_session):
        """SUCCESS: Delivery update sets is_delivered flag"""
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
        
        authenticated_client.put(f"/updatedeliver/{test_product.p_id}")

        db_session.expire(order)
        updated_order = db_session.query(Order).filter(Order.o_id == order.o_id).first()
        assert updated_order.is_delivered is True

    def test_update_delivery_case_insensitive_status(self, authenticated_client, test_user, test_product, db_session):
        """SUCCESS: Payment status check is case-insensitive"""
        from db import Order
        
        order = Order(
            c_id=test_user.id,
            p_id=test_product.p_id,
            total_price=100.0,
            payment_status="cod",
            is_delivered=False,
            quantity=1
        )
        db_session.add(order)
        db_session.commit()
        
        response = authenticated_client.put(
            f"/updatedeliver/{test_product.p_id}",
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_update_delivery_unauthorized_user(self, authenticated_client, other_user, test_product, db_session):
        """FAIL: User cannot update delivery for another user's order"""
        from db import Order
        
        order = Order(
            c_id=other_user.id,
            p_id=test_product.p_id,
            total_price=100.0,
            payment_status="COD",
            is_delivered=False,
            quantity=1
        )
        db_session.add(order)
        db_session.commit()
        
        response = authenticated_client.put(f"/updatedeliver/{test_product.p_id}")
        assert response.status_code == 404
        assert b"not found" in response.content.lower() or b"unpaid" in response.content.lower()