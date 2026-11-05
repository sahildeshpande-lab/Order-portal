"""
Unit tests for Role-Based Access Control (RBAC)
Covers all 4 roles: Admin, Viewer, User, Retainer
"""

import pytest
from db import User, Products, Order, UserRole
from main import hash_password, create_access_token


@pytest.fixture
def test_users(db_session):
    """Creates users with all four roles"""
    roles = {
        "admin": User(email="admin@test.com", password=hash_password("admin123"), role=UserRole.ADMIN.value),
        "viewer": User(email="viewer@test.com", password=hash_password("viewer123"), role=UserRole.VIEWER.value),
        "user": User(email="customer@test.com", password=hash_password("user123"), role=UserRole.USER.value),
        "retainer": User(email="retainer@test.com", password=hash_password("retainer123"), role=UserRole.RETAINER.value),
    }
    for u in roles.values():
        db_session.add(u)
    db_session.commit()
    for u in roles.values():
        db_session.refresh(u)
    return roles


def auth_client_for(client, user):
    token = create_access_token(user.id)
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", "test_csrf_token")
    return client


class TestRoleBasedAccessControl:
    """RBAC validation across roles and endpoints"""

    def test_admin_cannot_place_order(self, client, test_users, test_product, db_session):
        """Admin CANNOT place order"""
        c = auth_client_for(client, test_users["admin"])
        response = c.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1,
            "csrf_token": "test_csrf_token"
        }, follow_redirects=False)
        assert response.status_code == 303
        order = db_session.query(Order).filter(Order.c_id == test_users["admin"].id).first()
        assert order is None

    def test_retainer_cannot_place_order(self, client, test_users, test_product, db_session):
        """Retainer CANNOT place order"""
        c = auth_client_for(client, test_users["retainer"])
        response = c.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1,
            "csrf_token": "test_csrf_token"
        }, follow_redirects=False)
        assert response.status_code == 303
        order = db_session.query(Order).filter(Order.c_id == test_users["retainer"].id).first()
        assert order is None

    def test_viewer_cannot_place_order(self, client, test_users, test_product):
        """Viewer CANNOT place order"""
        c = auth_client_for(client, test_users["viewer"])
        response = c.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1,
            "csrf_token": "test_csrf_token"
        }, follow_redirects=False)
        assert response.status_code == 303

    def test_user_can_place_order(self, client, test_users, test_product, db_session):
        """Standard user CAN place order"""
        c = auth_client_for(client, test_users["user"])
        response = c.post("/order", data={
            "product_id": test_product.p_id,
            "quantity": 1,
            "csrf_token": "test_csrf_token"
        }, follow_redirects=False)
        assert response.status_code == 303
        order = db_session.query(Order).filter(Order.c_id == test_users["user"].id).first()
        assert order is not None

    def test_admin_and_viewer_can_access_profiles(self, client, test_users):
        """Admin and Viewer can access profiles page"""
        admin_c = auth_client_for(client, test_users["admin"])
        res_admin = admin_c.get("/admin/profiles")
        assert res_admin.status_code == 200
        assert "User & Retainer Profiles" in res_admin.text

        viewer_c = auth_client_for(client, test_users["viewer"])
        res_viewer = viewer_c.get("/admin/profiles")
        assert res_viewer.status_code == 200
        assert "User & Retainer Profiles" in res_viewer.text

    def test_regular_user_and_retainer_denied_profiles(self, client, test_users):
        """User and Retainer cannot access profiles page"""
        user_c = auth_client_for(client, test_users["user"])
        res_user = user_c.get("/admin/profiles", follow_redirects=False)
        assert res_user.status_code == 303

        ret_c = auth_client_for(client, test_users["retainer"])
        res_ret = ret_c.get("/admin/profiles", follow_redirects=False)
        assert res_ret.status_code == 303

    def test_viewer_and_admin_can_access_all_orders(self, client, test_users):
        """Viewer and Admin can audit all orders"""
        viewer_c = auth_client_for(client, test_users["viewer"])
        res_viewer = viewer_c.get("/viewer/orders")
        assert res_viewer.status_code == 200
        assert "Global Orders Audit" in res_viewer.text

        admin_c = auth_client_for(client, test_users["admin"])
        res_admin = admin_c.get("/viewer/orders")
        assert res_admin.status_code == 200

    def test_user_cannot_access_global_orders(self, client, test_users):
        """Customer cannot audit all orders"""
        user_c = auth_client_for(client, test_users["user"])
        res_user = user_c.get("/viewer/orders", follow_redirects=False)
        assert res_user.status_code == 303

    def test_admin_can_update_discount(self, client, test_users, test_product):
        """Admin can access and update discount"""
        admin_c = auth_client_for(client, test_users["admin"])
        res = admin_c.get("/updatediscount")
        assert res.status_code == 200

    def test_retainer_and_viewer_cannot_update_discount(self, client, test_users, test_product):
        """Retainer, Viewer, and User cannot update discounts"""
        for role in ["retainer", "viewer", "user"]:
            c = auth_client_for(client, test_users[role])
            res = c.get("/updatediscount", follow_redirects=False)
            assert res.status_code == 303
