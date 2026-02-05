"""
Payment Processing Tests
Tests for checkout and payment functionality
"""

import pytest


@pytest.mark.payment
class TestPayment:
    """Test cases for payment functionality"""
    
    def test_payment_page_without_checkout(self, authenticated_client):
        """FAIL: Payment page without checkout should redirect"""
        response = authenticated_client.get("/payment", follow_redirects=False)
        assert response.status_code == 303

    def test_start_checkout_success(self, authenticated_client, test_product):
        """SUCCESS: Checkout process starts successfully"""
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        response = authenticated_client.post("/checkout/start", follow_redirects=False)
        assert response.status_code == 303

    def test_start_checkout_without_orders(self, authenticated_client):
        """FAIL: Checkout without orders should redirect"""
        response = authenticated_client.post("/checkout/start", follow_redirects=False)
        assert response.status_code == 303

    def test_payment_page_after_checkout(self, authenticated_client, test_product):
        """SUCCESS: Payment page accessible after checkout"""
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/checkout/start")
        response = authenticated_client.get("/payment")
        assert response.status_code == 200

    def test_payment_cod_success(self, authenticated_client, test_product):
        """SUCCESS: COD payment completes successfully"""
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/checkout/start")
        response = authenticated_client.post("/payment", data={
            "method": "COD"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_payment_online_success(self, authenticated_client, test_product):
        """SUCCESS: Online payment completes successfully"""
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/checkout/start")
        response = authenticated_client.post("/payment", data={
            "method": "Credit Card"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_payment_without_orders(self, authenticated_client):
        """FAIL: Payment without orders should redirect"""
        response = authenticated_client.post("/payment", data={
            "method": "COD"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_payment_updates_order_status_cod(self, authenticated_client, test_product, db_session):
        """SUCCESS: COD payment updates order status to COD"""
        from db import Order
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/checkout/start")
        authenticated_client.post("/payment", data={"method": "COD"})
        
        order = db_session.query(Order).filter(
            Order.p_id == test_product.p_id
        ).first()
        assert order.payment_status == "COD"

    def test_payment_updates_order_status_paid(self, authenticated_client, test_product, db_session):
        """SUCCESS: Online payment updates order status to PAID"""
        from db import Order
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/checkout/start")
        authenticated_client.post("/payment", data={"method": "Credit Card"})
        
        order = db_session.query(Order).filter(
            Order.p_id == test_product.p_id
        ).first()
        assert order.payment_status == "PAID"

    def test_payment_creates_transaction_for_online(self, authenticated_client, test_product, db_session):
        """SUCCESS: Online payment creates transaction record"""
        from db import Transactions
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/checkout/start")
        authenticated_client.post("/payment", data={"method": "Debit Card"})
        
        transaction = db_session.query(Transactions).first()
        assert transaction is not None
        assert transaction.status == "success"

    def test_payment_no_transaction_for_cod(self, authenticated_client, test_product, db_session):
        """SUCCESS: COD payment does not create transaction"""
        from db import Transactions
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/checkout/start")
        authenticated_client.post("/payment", data={"method": "COD"})
        
        transaction = db_session.query(Transactions).first()
        assert transaction is None

    def test_payment_multiple_orders(self, authenticated_client, test_product, db_session):
        """SUCCESS: Payment processes multiple pending orders"""
        from db import Products, Order
        
        product2 = Products(
            title="Second Product",
            description="Description",
            price=50.0,
            discount=10.0,
            image="test2.jpg",
            category="Books"
        )
        db_session.add(product2)
        db_session.commit()
        db_session.refresh(product2)
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/order", data={
            "product_id": product2.p_id,
            "quantity": 2
        })
        
        authenticated_client.post("/checkout/start")
        authenticated_client.post("/payment", data={"method": "COD"})
        
        orders = db_session.query(Order).all()
        assert len(orders) == 2
        assert all(o.payment_status == "COD" for o in orders)