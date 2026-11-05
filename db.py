from sqlalchemy import Column, Integer, Text ,String, create_engine , ForeignKey , Boolean ,DateTime ,Index
from sqlalchemy.orm import sessionmaker, declarative_base , relationship
from pydantic import BaseModel , EmailStr 
from typing import Optional
from sqlalchemy.sql import func
import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    VIEWER = "viewer"
    USER = "user"
    RETAINER = "retainer"
    DELIVERY = "delivery"

class ApprovalStatus(str, Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"

DATABASE_URL = "sqlite:///./data/test.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()



class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password=Column(String, nullable=False)
    role = Column(String, default=UserRole.USER.value, nullable=False)
    requested_role = Column(String, nullable=True)
    approval_status = Column(String, default=ApprovalStatus.APPROVED.value, nullable=False)
    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Personal Identifiable Information (PII)
    full_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    street_address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, default="India")

    # Retailer / Vendor Verification
    business_name = Column(String, nullable=True)
    gstin_id = Column(String, nullable=True)              # Fake GSTIN/Govt Vendor ID
    pan_id = Column(String, nullable=True)                # Fake PAN/National ID
    is_verified = Column(Boolean, default=False)          # Verification Status

    # Simulated Card Information (Safe masked PCI-DSS simulation)
    card_brand = Column(String, default="Visa")          # Visa, Mastercard, RuPay
    card_holder_name = Column(String, nullable=True)
    card_last4 = Column(String(4), default="4242")
    card_exp = Column(String(5), default="12/28")

    user = relationship("User", back_populates="profile")


class Products(Base):
    __tablename__ = "products"
    p_id=Column(Integer,primary_key=True,index=True)
    title=Column(String,nullable=False,unique=True)
    description=Column(String)
    price=Column(Integer,nullable=False)
    discount=Column(Integer,nullable=False)
    image=Column(String,nullable=False)
    category=Column(String,nullable=False)
    stock_quantity=Column(Integer,nullable=False,default=100)
    created_by_id=Column(Integer, ForeignKey("users.id"), nullable=True)
    creator = relationship("User", foreign_keys=[created_by_id])

class Order(Base):
    __tablename__ = "orders"
    o_id=Column(Integer,primary_key=True,index=True)
    c_id = Column(Integer,ForeignKey("users.id"))
    p_id=Column(Integer,ForeignKey("products.p_id"))
    total_price=Column(Integer,nullable=False)
    is_delivered=Column(Boolean,default=False)
    payment_status=Column(String, nullable=False, default="pending")
    quantity=Column(Integer,nullable=False)
    customer = relationship("User", foreign_keys=[c_id])
    product = relationship("Products", foreign_keys=[p_id])
    payment = relationship("Payment", back_populates="order", uselist=False)

class Transactions(Base):
    __tablename__="transactions"
    t_id=Column(Integer,primary_key=True,index=True)
    stripe_intent_id = Column(String, unique=True, nullable=False)
    created_at=Column(DateTime,server_default=func.now(),nullable=False)
    amount=Column(Integer,nullable=False)
    status=Column(String,nullable=False)

class Payment(Base):
    __tablename__="payment"
    pay_id=Column(Integer,primary_key=True,index=True )
    o_id=Column(Integer,ForeignKey("orders.o_id"),nullable=False ,unique=True)
    t_id=Column(Integer,ForeignKey("transactions.t_id"),nullable=True)
    amount=Column(Integer,nullable=False)
    method=Column(String,nullable=False)
    status=Column(String,nullable=False)
    order = relationship("Order", back_populates="payment")

class Review(Base):
    __tablename__="reviews"

    r_id = Column(Integer,primary_key=True,index=True)
    user_id = Column(Integer,ForeignKey("users.id"),nullable=False)
    product_id = Column(Integer,ForeignKey("products.p_id"),nullable=False)
    rating=Column(Integer,nullable=False)
    comment=Column(Text,nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user=relationship("User")
    product = relationship("Products")


class ProductView(Base):
    __tablename__ = "product_views"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.p_id"), nullable=False)
    viewed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User")
    product = relationship("Products")




class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.p_id"), nullable=True)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User")


class EmailCheck(BaseModel):
    email:EmailStr 



class ProductResponse(BaseModel):
    p_id:int
    title : str 
    description:Optional[str]
    price:int
    discount : int
    image : str
    category:str
    stock_quantity:int

    class Config:
        from_attributes=True

class CreateOrder(BaseModel):
    c_id:int
    p_id:int
    total_price:float 
    is_delivered:bool 
    quantity:int

class OrderResponse(BaseModel):
    o_id:int
    p_id:int
    title:str  
    description:str
    total_price:float
    quantity:int
    is_delivered:bool
    payment_status:str|None 

    class Config:
        from_attributes=True

class ProductManger(BaseModel):
    p_id:int
    title:str
    discount:int
    price:int
    total_price:float
    quantity:int

    class Config:
        from_attributes=True

class ProductCategory(BaseModel):
    title:str
    category:str
    discount:int
    total_price:float

    class Config :
        from_attributes=True

class UpdateDelivery(BaseModel):
    is_delivered:bool

    class Config :
        from_attributes=True

class ReviewResponse(BaseModel):
    user_email:str
    rating:int
    comment:Optional[str]
    created_at : datetime.datetime

    class Config :
        orm_mode = True 


class EmailLogRequest(BaseModel):
    user_id: int
    product_id: int


Base.metadata.create_all(bind=engine)

Index("idx_user_product_view", ProductView.user_id, ProductView.product_id)
Index("idx_email_user_time", EmailLog.user_id, EmailLog.sent_at)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

