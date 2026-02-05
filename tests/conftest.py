"""
Pytest configuration and shared fixtures
Ensures complete isolation from production database and files
"""

import pytest
import os
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from io import BytesIO

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_suite.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def pytest_configure(config):
    """Called before test run starts - Set up test environment"""
    print("\n" + "="*70)
    print("Starting Test Suite - Order Portal API")
    print("="*70)
    print("⚠️  Using isolated test database: test_suite.db")
    print("⚠️  Using isolated uploads directory: test_uploads/")
    print("⚠️  Your main test.db and uploads/ will NOT be affected")
    print("="*70 + "\n")


def pytest_unconfigure(config):
    """Called after all tests finish - Clean up test artifacts"""
    print("\n" + "="*70)
    print("Test Suite Completed - Cleaning Up")
    print("="*70)

    if os.path.exists("test_suite.db"):
        try:
            os.remove("test_suite.db")
            print("✓ Removed test database: test_suite.db")
        except Exception as e:
            print(f"⚠️  Could not remove test_suite.db: {e}")
    

    if os.path.exists("test_uploads"):
        try:
            shutil.rmtree("test_uploads")
            print("✓ Removed test uploads: test_uploads/")
        except Exception as e:
            print(f"⚠️  Could not remove test_uploads: {e}")
    
    if os.path.exists("__pycache__"):
        try:
            shutil.rmtree("__pycache__")
            print("✓ Removed cache files")
        except:
            pass
    
    print("="*70 + "\n")


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def test_engine():
    """Provide test database engine"""
    return engine


@pytest.fixture(scope="session")
def test_db_session():
    """Provide test database session"""
    return TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_and_teardown(test_engine):
    """Set up and tear down database for each test"""
    from db import Base
    
    Base.metadata.create_all(bind=test_engine)
    os.makedirs("test_uploads", exist_ok=True)
    
    yield
    
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("test_uploads"):
        try:
            shutil.rmtree("test_uploads")
        except:
            pass


@pytest.fixture
def client():
    """Provide FastAPI test client with database override"""
    from main import app, get_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(test_db_session):
    """Provide a fresh database session for tests"""
    session = test_db_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    from main import hash_password
    from db import User
    
    user = User(email="test@example.com", password=hash_password("password123"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_product(db_session):
    """Create a test product"""
    from db import Products
    
    product = Products(
        title="Test Product",
        description="Test Description",
        price=100.0,
        discount=20.0,
        image="uploads/test.jpg",
        category="Electronics"
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def authenticated_client(client, test_user):
    """Provide authenticated client session"""
    client.post("/login", data={
        "email": "test@example.com",
        "password": "password123"
    })
    return client


@pytest.fixture
def test_image():
    """Provide a test image file"""
    return BytesIO(b"fake image content")


@pytest.fixture
def other_user(db_session):
    """Create another test user for authorization tests"""
    from main import hash_password
    from db import User
    
    user = User(email="other@example.com", password=hash_password("password123"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_order(db_session, test_user, test_product):
    """Create a test order"""
    from db import Order
    
    order = Order(
        c_id=test_user.id,
        p_id=test_product.p_id,
        total_price=80.0,
        payment_status="pending",
        is_delivered=False,
        quantity=1
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def paid_order(db_session, test_user, test_product):
    """Create a paid test order"""
    from db import Order
    
    order = Order(
        c_id=test_user.id,
        p_id=test_product.p_id,
        total_price=80.0,
        payment_status="PAID",
        is_delivered=False,
        quantity=1
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Make test results available to fixtures"""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)