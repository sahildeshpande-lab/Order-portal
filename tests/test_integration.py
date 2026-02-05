"""
Integration Tests
End-to-end workflow tests covering multiple components
"""

import pytest


@pytest.mark.integration
class TestUserJourney:
    """Test complete user workflows"""
    
    def test_complete_purchase_flow_cod(self, client, test_product):
        """INTEGRATION: Complete purchase flow with COD payment"""
        response = client.post("/register", data={
            "email": "buyer@example.com",
            "password": "password123"
        }, follow_redirects=False)
        assert response.status_code == 303
        
        response = client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 2
        }, follow_redirects=False)
        assert response.status_code == 303
        
        response = client.post("/checkout/start", follow_redirects=False)
        assert response.status_code == 303
        
        response = client.post("/payment", data={
            "method": "COD"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_complete_purchase_flow_online(self, client, test_product):
        """INTEGRATION: Complete purchase flow with online payment"""
        client.post("/register", data={
            "email": "onlinebuyer@example.com",
            "password": "password123"
        })
        
        client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        
        client.post("/checkout/start")

        response = client.post("/payment", data={
            "method": "Credit Card"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_register_login_logout_flow(self, client):
        """INTEGRATION: User registration, login, and logout flow"""
        response = client.post("/register", data={
            "email": "flowtest@example.com",
            "password": "password123"
        }, follow_redirects=False)
        assert response.status_code == 303
        
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 303
        
        response = client.post("/login", data={
            "email": "flowtest@example.com",
            "password": "password123"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_add_product_and_purchase_flow(self, authenticated_client, test_image, db_session):
        """INTEGRATION: Add product and purchase it"""
        authenticated_client.post("/add-product", data={
            "title": "New Widget",
            "description": "A great widget",
            "price": "50.0",
            "discount": "15.0",
            "category": "Gadgets"
        }, files={
            "image": ("widget.jpg", test_image, "image/jpeg")
        })
        
        from db import Products
        product = db_session.query(Products).filter(
            Products.title == "New Widget"
        ).first()
        assert product is not None
        
        response = authenticated_client.post("/order", data={
            "product_id": product.p_id,
            "quantity": 1
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_order_cancel_flow(self, authenticated_client, test_product, db_session):
        """INTEGRATION: Create and cancel order"""
        from db import Order
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        
        order = db_session.query(Order).filter(
            Order.p_id == test_product.p_id
        ).first()
        assert order is not None
        
        response = authenticated_client.post(
            f"/orders/cancel/{order.o_id}",
            follow_redirects=False
        )
        assert response.status_code == 303
        
        cancelled = db_session.query(Order).filter(
            Order.o_id == order.o_id
        ).first()
        assert cancelled is None

    def test_password_reset_and_login_flow(self, client, test_user):
        """INTEGRATION: Reset password and login with new password"""
        client.post("/password", data={
            "email": "test@example.com",
            "password": "newpassword456"
        })
        
        response = client.post("/login", data={
            "email": "test@example.com",
            "password": "newpassword456"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_multiple_products_purchase_flow(self, authenticated_client, test_product, test_image, db_session):
        """INTEGRATION: Purchase multiple different products"""
        from db import Products
        
        authenticated_client.post("/add-product", data={
            "title": "Second Item",
            "description": "Another product",
            "price": "75.0",
            "discount": "20.0",
            "category": "Books"
        }, files={
            "image": ("item.jpg", test_image, "image/jpeg")
        })
        
        product2 = db_session.query(Products).filter(
            Products.title == "Second Item"
        ).first()
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/order", data={
            "product_id": product2.p_id,
            "quantity": 2
        })
        
        authenticated_client.post("/checkout/start")
        response = authenticated_client.post("/payment", data={
            "method": "COD"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_delivery_update_flow(self, authenticated_client, test_product, db_session):
        """INTEGRATION: Order, pay, and mark as delivered"""
        from db import Order
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        authenticated_client.post("/checkout/start")
        authenticated_client.post("/payment", data={"method": "COD"})
        
        response = authenticated_client.put(
            f"/updatedeliver/{test_product.p_id}",
            follow_redirects=False
        )
        assert response.status_code == 303
        
        order = db_session.query(Order).filter(
            Order.p_id == test_product.p_id
        ).first()
        assert order.is_delivered is True

    def test_discount_update_affects_new_orders(self, authenticated_client, test_product, db_session):
        """INTEGRATION: Updating discount affects new order prices"""
        from db import Order, Products
        
        authenticated_client.post("/updatediscount", data={
            "product_id": test_product.p_id,
            "discount": 50
        })
        
        db_session.expire(test_product)
        db_session.refresh(test_product)
        
        authenticated_client.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1
        })
        
        order = db_session.query(Order).filter(
            Order.p_id == test_product.p_id
        ).first()
        
        product = db_session.query(Products).filter(
            Products.p_id == test_product.p_id
        ).first()
        
        expected_price = product.price - (product.price * product.discount / 100)
        assert order.total_price == expected_price