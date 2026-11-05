import pytest
from fastapi.testclient import TestClient
from main import app, create_access_token
from db import SessionLocal, User, UserRole, ApprovalStatus

def make_client():
    return TestClient(app)

def set_csrf(client):
    token = "test-csrf-token-1234567890"
    client.cookies.set("csrf_token", token)
    return token

def get_admin_token():
    db = SessionLocal()
    admin = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
    db.close()
    return create_access_token(admin.id)

def test_user_self_registration():
    client = make_client()
    email = "new_customer_test@example.com"
    csrf = set_csrf(client)
    db = SessionLocal()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        db.delete(existing)
        db.commit()
    db.close()

    res = client.post("/register", data={
        "email": email,
        "password": "Password123!",
        "role": "user",
        "csrf_token": csrf
    }, follow_redirects=False)

    assert res.status_code == 303
    assert res.headers["location"] == "/"

    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.role == UserRole.USER.value
    assert user.approval_status == ApprovalStatus.APPROVED.value
    assert user.requested_role is None
    db.delete(user)
    db.commit()
    db.close()

def test_retainer_self_registration():
    client = make_client()
    email = "new_retainer_test@example.com"
    csrf = set_csrf(client)
    db = SessionLocal()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        db.delete(existing)
        db.commit()
    db.close()

    res = client.post("/register", data={
        "email": email,
        "password": "Password123!",
        "role": "retainer",
        "csrf_token": csrf
    }, follow_redirects=False)

    assert res.status_code == 303
    assert res.headers["location"] == "/"

    db = SessionLocal()
    ret = db.query(User).filter(User.email == email).first()
    assert ret is not None
    assert ret.role == UserRole.RETAINER.value
    assert ret.approval_status == ApprovalStatus.APPROVED.value
    db.delete(ret)
    db.commit()
    db.close()

def test_admin_applicant_registration_and_restricted_status():
    client = make_client()
    email = "applicant_admin@example.com"
    csrf = set_csrf(client)
    db = SessionLocal()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        db.delete(existing)
        db.commit()
    db.close()

    res = client.post("/register", data={
        "email": email,
        "password": "Password123!",
        "role": "admin",
        "csrf_token": csrf
    }, follow_redirects=False)

    assert res.status_code == 303
    assert res.headers["location"] == "/account/status"

    db = SessionLocal()
    applicant = db.query(User).filter(User.email == email).first()
    assert applicant is not None
    assert applicant.role == UserRole.USER.value
    assert applicant.requested_role == "admin"
    assert applicant.approval_status == ApprovalStatus.PENDING.value

    # Attempting to access privileged route as applicant
    priv_client = make_client()
    token = create_access_token(applicant.id)
    priv_client.cookies.set("access_token", token)
    priv_res = priv_client.get("/updatediscount", follow_redirects=False)
    # Blocked from privileged route (403 or redirect to status)
    assert priv_res.status_code in [303, 403]
    if priv_res.status_code == 303:
        assert priv_res.headers["location"] in ["/account/status", "/"]

    # Non-admin attempting to approve via API
    hack_client = make_client()
    hack_client.cookies.set("access_token", token)
    hack_csrf = set_csrf(hack_client)
    hack_res = hack_client.post(f"/admin/role-requests/{applicant.id}/approve", data={"csrf_token": hack_csrf}, follow_redirects=False)
    assert hack_res.status_code in [303, 403]

    # Admin approves
    admin_client = make_client()
    admin_token = get_admin_token()
    admin_client.cookies.set("access_token", admin_token)
    admin_csrf = set_csrf(admin_client)
    approve_res = admin_client.post(f"/admin/role-requests/{applicant.id}/approve", data={"csrf_token": admin_csrf}, follow_redirects=False)
    assert approve_res.status_code == 303
    assert approve_res.headers["location"] == "/admin/role-requests"

    # Verify role was granted
    db.refresh(applicant)
    assert applicant.role == UserRole.ADMIN.value
    assert applicant.approval_status == ApprovalStatus.APPROVED.value

    # Now approved admin can access /updatediscount
    approved_client = make_client()
    approved_client.cookies.set("access_token", token)
    approved_access = approved_client.get("/updatediscount")
    assert approved_access.status_code == 200

    db.delete(applicant)
    db.commit()
    db.close()

def test_admin_rejects_role_request():
    client = make_client()
    email = "applicant_delivery@example.com"
    csrf = set_csrf(client)
    db = SessionLocal()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        db.delete(existing)
        db.commit()
    db.close()

    res = client.post("/register", data={
        "email": email,
        "password": "Password123!",
        "role": "delivery",
        "csrf_token": csrf
    }, follow_redirects=False)

    db = SessionLocal()
    applicant = db.query(User).filter(User.email == email).first()
    assert applicant is not None
    assert applicant.approval_status == ApprovalStatus.PENDING.value
    assert applicant.role == UserRole.USER.value

    # Admin rejects
    admin_client = make_client()
    admin_token = get_admin_token()
    admin_client.cookies.set("access_token", admin_token)
    admin_csrf = set_csrf(admin_client)
    reject_res = admin_client.post(f"/admin/role-requests/{applicant.id}/reject", data={"csrf_token": admin_csrf}, follow_redirects=False)
    assert reject_res.status_code == 303

    db.refresh(applicant)
    assert applicant.role == UserRole.USER.value
    assert applicant.approval_status == ApprovalStatus.REJECTED.value

    # Rejected applicant cannot access delivery dashboard
    deliv_client = make_client()
    token = create_access_token(applicant.id)
    deliv_client.cookies.set("access_token", token)
    deliv_res = deliv_client.get("/delivery/orders", follow_redirects=False)
    assert deliv_res.status_code in [303, 403]
    if deliv_res.status_code == 303:
        assert deliv_res.headers["location"] in ["/account/status", "/"]

    db.delete(applicant)
    db.commit()
    db.close()
