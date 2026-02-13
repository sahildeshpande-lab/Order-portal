from sqlalchemy import Column, Integer, Text ,String, create_engine , ForeignKey , Boolean ,DateTime
from sqlalchemy.orm import sessionmaker, declarative_base , relationship
from pydantic import BaseModel , EmailStr 
from typing import Optional
from sqlalchemy.sql import func
import datetime

DATABASE_URL = "sqlite:///./data/test.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password=Column(String, nullable=False)


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

class Order(Base):
    __tablename__ = "orders"
    o_id=Column(Integer,primary_key=True,index=True)
    c_id = Column(Integer,ForeignKey("users.id"))
    p_id=Column(Integer,ForeignKey("products.p_id"))
    total_price=Column(Integer,nullable=False)
    is_delivered=Column(Boolean,default=False)
    payment_status=Column(String, nullable=False, default="pending")
    quantity=Column(Integer,nullable=False)
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
    created_at=Column(DateTime,default=datetime.datetime.now())

    user=relationship("User")
    product = relationship("Products")

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

Base.metadata.create_all(bind=engine)



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

