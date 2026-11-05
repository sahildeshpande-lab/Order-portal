from fastapi import FastAPI, Form, Depends, Request,UploadFile ,File , HTTPException
from fastapi.responses import RedirectResponse , JSONResponse 
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import  Session
from pydantic import  ValidationError
from typing import List ,Optional
from jose import jwt , JWTError
from datetime import datetime, timedelta
from db import User , Products ,Order ,Transactions ,Payment,EmailCheck  , OrderResponse ,ProductManger , ProductCategory  , get_db ,ProductResponse , Review , ProductView ,EmailLog , EmailLogRequest, UserRole, Profile, ApprovalStatus
import shutil 
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext 
import uuid
import requests
from sqlalchemy import func , or_ , text
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import secrets
import random
import stripe 

from dotenv import load_dotenv

load_dotenv()


stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


app = FastAPI(title="Order portal")


app.add_middleware(SessionMiddleware,secret_key=os.getenv("SESSION_SECRET", "dev-secret"),same_site="lax",https_only=False,session_cookie="session",)


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

templates = Jinja2Templates(directory="Template")


pwd=CryptContext(schemes=["bcrypt"],deprecated = "auto")

SECRET_KEY = os.getenv("JWT_SECRET","dev-jwt-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 


def hash_password(password:str)->str :
    if len(password.encode("utf-8")) > 72 :
        raise HTTPException(status_code=400,detail="Password to long ")
    return pwd.hash(password)

def verify_password(plain_password:str,hashed_password:str) -> bool :
    return pwd.verify(plain_password,hashed_password)

def generate_csrf_token():
    return secrets.token_urlsafe(32)

def create_access_token(user_id:int) -> str:
    payload = {
        "sub":str(user_id),
        "exp" : datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload,SECRET_KEY,algorithm=ALGORITHM)


def csrf_protect(request: Request,csrf_token: str | None =Form(None)):
    cookie_token = request.cookies.get("csrf_token")

    if not cookie_token or not csrf_token:
        raise HTTPException(status_code=403, detail="CSRF token missing")

    if not secrets.compare_digest(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    print("COOKIE:", request.cookies.get("csrf_token"))
    print("FORM:", csrf_token)



def user_authentication(request:Request,db:Session=Depends(get_db))-> User:
    token = request.cookies.get("access_token")
    if not token :
        raise HTTPException(status_code=401)

    try :
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except JWTError :
        raise HTTPException(status_code=401)


    user = db.query(User).filter(User.id==user_id).first()
    if not user :
        raise  HTTPException(status_code=401, detail="Invalid session")
    return user


def require_roles(*allowed_roles):
    """Dependency factory that checks if authenticated user has one of allowed roles and is approved."""
    def role_checker(request: Request, current_user: User = Depends(user_authentication)) -> User:
        # Check approval status
        if getattr(current_user, "approval_status", "approved") != ApprovalStatus.APPROVED.value:
            if request.headers.get("accept", "").startswith("text/html"):
                return RedirectResponse("/account/status", status_code=303)
            raise HTTPException(status_code=403, detail="Forbidden: Account role is pending administrator approval")

        role_vals = [r.value if hasattr(r, "value") else str(r) for r in allowed_roles]
        if current_user.role not in role_vals:
            if request.headers.get("accept", "").startswith("text/html"):
                flash(request, "Access denied: insufficient permissions for your role", "error")
                return RedirectResponse("/", status_code=303)
            raise HTTPException(status_code=403, detail=f"Forbidden: requires role in {role_vals}")
        return current_user
    return role_checker

def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate ,max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def get_current_user_optional(request:Request,db:Session):
    token = request.cookies.get("access_token")
    if not token : 
        return None 
    try :
        payload = jwt.decode(token , SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        if not user_id :
            return None 
    except JWTError :
        return None 

    return db.query(User).filter(User.id == user_id).first()

def generate_otp()-> str :
    return str(random.randint(100000,999999))

def flash(request: Request, message: str, category: str = "success"):
    request.session["flash"] = {"message": message,"category": category}


@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and request.headers.get("accept", "").startswith("text/html"):
        return RedirectResponse("/login", 303)
    if exc.status_code == 403 and request.headers.get("accept", "").startswith("text/html"):
        if "pending" in str(exc.detail).lower():
            return RedirectResponse("/account/status", 303)
        flash(request, "Access denied: insufficient permissions for your role", "error")
        return RedirectResponse("/", 303)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(StarletteHTTPException)
async def not_found_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html",{"request": request,"path": request.url.path},status_code=404)
    return JSONResponse(status_code=exc.status_code,content={"detail": exc.detail},)

@app.middleware("http")
async def ensure_csrf_cookie(request: Request, call_next):
    response = await call_next(request)
    if "csrf_token" not in request.cookies:
        csrf_token = generate_csrf_token()
        response.set_cookie(key="csrf_token",value=csrf_token,httponly=False,samesite="lax",secure=True)
    return response


import math

@app.get("/")
def products_home(request: Request, page: int = 1, per_page: int = 10, category: Optional[str] = None, db: Session = Depends(get_db)):
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 10
    
    query = db.query(Products)
    if category and category.strip():
        query = query.filter(Products.category == category.strip())

    total_products = query.count()
    total_pages = max(1, math.ceil(total_products / per_page))
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page
    products = query.order_by(Products.p_id.desc()).offset(offset).limit(per_page).all()
    user = get_current_user_optional(request, db)

    # Fetch reviews only for currently displayed products
    product_ids = [p.p_id for p in products]
    reviews = []
    if product_ids:
        reviews = (
            db.query(
                Review.product_id,
                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.r_id).label("review_count")
            )
            .filter(Review.product_id.in_(product_ids))
            .group_by(Review.product_id)
            .all()
        )
    review_map = {r.product_id: {"avg": round(r.avg_rating, 1), "count": r.review_count} for r in reviews}
    flash_message = request.session.pop("flash", None)

    # All distinct categories for filter buttons
    categories = [c[0] for c in db.query(Products.category).distinct().all() if c[0]]

    return templates.TemplateResponse("products.html", {
        "request": request,
        "products": products,
        "user": user,
        "user_id": user.id if user else None,
        "flash": flash_message,
        "review_map": review_map,
        "page": page,
        "total_pages": total_pages,
        "total_products": total_products,
        "per_page": per_page,
        "current_category": category or "",
        "categories": categories
    })

@app.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if current_user:
        if current_user.approval_status != ApprovalStatus.APPROVED.value:
            return RedirectResponse("/account/status", 303)
        return RedirectResponse("/", 303)
    return templates.TemplateResponse("index.html",{"request": request, "user": None})

@app.get("/account/status")
def account_status_page(request: Request, current_user: User = Depends(user_authentication)):
    response = templates.TemplateResponse("approval_status.html", {
        "request": request,
        "user": current_user
    })
    return no_cache(response)

@app.post("/login",tags=["Login User endpoint"])
def login_form(request: Request,email: str = Form(...),password: str = Form(...),db: Session = Depends(get_db),csrf=Depends(csrf_protect)):
    try :
        EmailCheck(email=email)
    except ValidationError :
        return templates.TemplateResponse("index.html",{"request":request ,"user": None,"error":"Invalid email address"})
    
    user=db.query(User).filter(User.email == email).first()
    if not user :
        error = "Email not found please register"
        return templates.TemplateResponse("register.html",{"request":request,"error":error})
    
    if user and not verify_password(password,user.password):
        return templates.TemplateResponse("index.html",{"request":request,"user": None,"error":"Password does not match"})
    
    access_token= create_access_token(user.id)
    csrf_token = generate_csrf_token()

    # Route based on approval status
    target_url = "/"
    if getattr(user, "approval_status", "approved") != ApprovalStatus.APPROVED.value:
        target_url = "/account/status"

    response = RedirectResponse(target_url, status_code=303)
    response.set_cookie(key="access_token",value=access_token,httponly=True,samesite="lax",secure=True,path="/")
    response.set_cookie(key="csrf_token",value=csrf_token,httponly=False,samesite="lax",secure=True,path="/")
    return response

@app.get("/logout",include_in_schema=False,tags=["logout"])
def logout(request:Request):
    response = RedirectResponse("/",status_code=303)
    response.delete_cookie("access_token",path="/")
    request.session.clear()
    return no_cache(response)

@app.get("/register",tags=["Register User endpoint"])
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register",tags=["Register User endpoint"])
def register_user(request:Request, email:str=Form(...),password:str=Form(...),role:str=Form(UserRole.USER.value),db:Session=Depends(get_db),csrf=Depends(csrf_protect)):
    try :
        EmailCheck(email=email)
    except ValidationError :
        return templates.TemplateResponse("register.html",{"request":request ,"error":"Invalid email address"})
    
    if db.query(User).filter(User.email == email).first() :
        return templates.TemplateResponse("index.html",{"request":request,"message" :"User already exists"})
    
    valid_roles = [r.value for r in UserRole]
    requested_role_clean = role.strip().lower() if role and role.strip().lower() in valid_roles else UserRole.USER.value

    # Registration Policy:
    # User and Retainer: active immediately
    # Admin, Viewer, Delivery: create pending request, active role is user
    if requested_role_clean in [UserRole.USER.value, UserRole.RETAINER.value]:
        assigned_active_role = requested_role_clean
        req_role_val = None
        approval_status_val = ApprovalStatus.APPROVED.value
    else:
        assigned_active_role = UserRole.USER.value
        req_role_val = requested_role_clean
        approval_status_val = ApprovalStatus.PENDING.value

    hashed=hash_password(password)
    new_user = User(
        email=email,
        password=hashed,
        role=assigned_active_role,
        requested_role=req_role_val,
        approval_status=approval_status_val
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Initialize basic profile without fake verification data
    is_ret = (assigned_active_role == UserRole.RETAINER.value)
    initial_profile = Profile(
        user_id=new_user.id,
        full_name=email.split("@")[0].capitalize(),
        phone_number="+91 98000 00000",
        street_address="Street 101, Main Road",
        city="Mumbai",
        state="Maharashtra",
        postal_code="400001",
        country="India",
        business_name=f"{email.split('@')[0].capitalize()} Retail Ltd" if is_ret else None,
        is_verified=False
    )
    db.add(initial_profile)
    db.commit()

    token = create_access_token(new_user.id)
    csrf_token = generate_csrf_token()

    if approval_status_val == ApprovalStatus.PENDING.value:
        flash(request, f"Registration submitted! Your request for '{req_role_val}' privileges is pending Admin approval.", "info")
        target_url = "/account/status"
    else:
        flash(request, f"Welcome! Your {assigned_active_role} account has been created successfully.", "success")
        target_url = "/"

    response = RedirectResponse(target_url, 303)
    response.set_cookie("access_token",token,httponly=True,samesite="lax")
    response.set_cookie(key="csrf_token",value=csrf_token,httponly=False,samesite="lax",secure=True,path="/")
    return response


@app.get("/forget-password",tags=["Forget Password endpoint"])
def display_forget_password(request:Request):
    return templates.TemplateResponse("forget-password.html",{"request":request})

@app.post("/password",tags=["Forget Password endpoint"])
def update_password(request:Request,email:str=Form(...),otp:str=Form(...),password:str=Form(...),db:Session=Depends(get_db),csrf=Depends(csrf_protect)):

    check_email=db.query(User).filter(User.email==email).first()
     
    if not check_email :
        error="Email not found"
        return templates.TemplateResponse("forget-password.html",{"request":request,"error":error})
    
    if verify_password(password,check_email.password):
        error="New and old password is same either login or use different password"
        return templates.TemplateResponse("forget-password.html",{"request":request,"error":error})
    
    if len(password)<5 :
        error="The length of password should be greater than 5"
        return templates.TemplateResponse("register.html",{"request":request,"error":error})
    

    check_email.password=hash_password(password)
    db.commit()
    db.refresh(check_email)

    request.session["success"]="Password updated successfully please login"
    return RedirectResponse(url="/login",status_code=303)

@app.get("/addproduct",tags=["Add product endpoint"])
def addproducts_page(request:Request,current_user:User = Depends(user_authentication)):
    if current_user.role not in [UserRole.ADMIN.value, UserRole.RETAINER.value]:
        flash(request, "Only Admin or Retainer can add products", "error")
        return RedirectResponse("/", status_code=303)
    response= templates.TemplateResponse("addproduct.html",{"request":request,"user_id":current_user.id,"user":current_user})
    return no_cache(response)

@app.post("/add-product", tags=["Add product endpoint"])
def addproduct(request: Request,title: Optional[str] = Form(None),description: Optional[str] = Form(None),price: Optional[float] = Form(None),discount: Optional[float] = Form(None),image: Optional[UploadFile] = File(None),category: Optional[str] = Form(None),quantity:Optional[int] = Form(None),current_user: Optional[User] = Depends(user_authentication),db: Session = Depends(get_db),csrf=Depends(csrf_protect)):
    if not current_user:
        return RedirectResponse("/login", status_code=303)

    if current_user.role not in [UserRole.ADMIN.value, UserRole.RETAINER.value]:
        flash(request, "Access denied: Only Admin or Retainer can add products", "error")
        return RedirectResponse("/", status_code=303)

    if not all([title, description, category, image]) or price is None or discount is None:
        message = "All fields are required"
        return templates.TemplateResponse("addproduct.html",{"request": request, "message": message})

    if discount < 10 or discount > 90:
        message = "Please select a valid discount range (10–90)"
        return templates.TemplateResponse("addproduct.html",{"request": request, "message": message})

    existing = (db.query(Products).filter(func.lower(Products.title) == title.strip().lower()).first())

    if existing:
        message = "Product with this name already exists"
        return templates.TemplateResponse("addproduct.html",{"request": request, "message": message})

    UPLOAD_DIR = "uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_ext = os.path.splitext(image.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    image_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    new_product = Products(
        title=title.strip(),
        description=description.strip(),
        price=price,
        discount=discount,
        image=image_path,
        category=category.strip(),
        stock_quantity=quantity,
        created_by_id=current_user.id
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    flash(request, "Product added successfully", "success")

    return RedirectResponse("/", status_code=303)
    
@app.post("/order",tags=["Order product endpoint"])
def create_order(request:Request,product_id : int =Form(...),quantity:int = Form(...),current_user: User = Depends(user_authentication),db:Session=Depends(get_db)):
    
    if current_user.role != UserRole.USER.value:
        flash(request, f"Accounts with role '{current_user.role}' cannot place orders. Only standard users can buy products.", "error")
        return RedirectResponse(url="/",status_code=303)

    product=db.query(Products).filter(Products.p_id==product_id).first()
    if not product :
        return RedirectResponse(url="/",status_code=303)
    
    if quantity <= 0 :
        flash(request, "Select valid quantity range", "error")
        return RedirectResponse(url="/",status_code=303)

    if quantity>100 :
        flash(request, "Out of stock", "error")
        return RedirectResponse(url="/",status_code=303)
    
    if quantity > product.stock_quantity :
        flash(request, "Thanks for adding the product , but we don't have stock right now . Stay tunned we will update it !", "error")
        return RedirectResponse(url="/",status_code=303)
    
    
    product.stock_quantity = product.stock_quantity - quantity 

    if product.stock_quantity < 0 :
        flash(request, "This product is currently out of stock", "error")
        return RedirectResponse(url="/",status_code=303)
    
    existing_order = db.query(Order).filter(Order.c_id==current_user.id,Order.p_id==product.p_id,Order.is_delivered==False).first()

    if existing_order :
        return RedirectResponse(url="/",status_code=303)

    discounted_price = round(product.price - (product.price * product.discount) / 100)
    total_price = round(quantity * discounted_price)

    order=Order(c_id=current_user.id,p_id=product.p_id,total_price=int(total_price),payment_status="pending",is_delivered = False ,quantity=quantity)

    db.add(order)
    db.commit()
    flash(request, "Product added to cart successfully ", "success")

    return RedirectResponse(url="/",status_code=303)

@app.post("/checkout/start")
def start_checkout(request: Request,current_user: User = Depends(user_authentication),db: Session = Depends(get_db)):
    if current_user.role != UserRole.USER.value:
        flash(request, f"Accounts with role '{current_user.role}' cannot checkout. Only customers can buy products.", "error")
        return RedirectResponse("/", status_code=303)

    orders = db.query(Order).filter(Order.c_id == current_user.id,Order.payment_status == "pending").first()

    if not orders:
        return RedirectResponse("/", status_code=303)

    request.session["can_pay"] = True

    return RedirectResponse("/payment", status_code=303)

@app.get("/payment",tags=["Payments"])
def payment_page(request: Request,current_user: User = Depends(user_authentication),db: Session = Depends(get_db)):
    if not request.session.get("can_pay"):
        return RedirectResponse("/", status_code=303)

    orders = db.query(Order).filter(Order.c_id == current_user.id,Order.payment_status == "pending").all()

    if not orders:
        return RedirectResponse("/", status_code=303)

    total_amount = round(sum(o.total_price for o in orders))

    stripe_pk = os.getenv("STRIPE_PUBLISHABLE_KEY")
    if not stripe_pk and os.getenv("STRIPE_SECRET_KEY"):
        stripe_pk = os.getenv("STRIPE_SECRET_KEY").replace("sk_test_", "pk_test_").replace("sk_live_", "pk_live_")

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(total_amount * 100),
            currency="inr",
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            metadata={"user_id": current_user.id}
        )
        client_secret = intent.client_secret
    except Exception as e:
        client_secret = ""

    response = templates.TemplateResponse("payment.html",{
        "request": request,
        "total_amount": total_amount,
        "client_secret": client_secret,
        "stripe_pk": stripe_pk
    })

    return no_cache(response)

@app.post("/payment",tags=["Payment"])
def process_payment(request: Request,method: str = Form(...),payment_intent_id: str = Form(None),current_user: User = Depends(user_authentication),db: Session = Depends(get_db),csrf=Depends(csrf_protect)):
    orders = db.query(Order).filter(Order.c_id == current_user.id,Order.payment_status == "pending").all()

    if not orders:
        return RedirectResponse("/", status_code=303)

    if method == "COD":
        for order in orders:
            db.add(Payment( o_id=order.o_id, amount=order.total_price, method="COD", status="completed"))
            order.payment_status = "COD"

        db.commit()
        request.session.pop("can_pay", None)
        return RedirectResponse("/", status_code=303)
    
    intent = stripe.PaymentIntent.retrieve(payment_intent_id)

    if intent.metadata.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Invalid payment session")

    if intent.status != "succeeded":
        request.session.pop("can_pay",None)
        flash(request, "Payment failed!", "error")
        return RedirectResponse("/payment", status_code=303)
    
    existing = db.query(Transactions).filter(Transactions.stripe_intent_id == payment_intent_id).first()

    if existing:
        return RedirectResponse("/", status_code=303)

    transaction = Transactions(stripe_intent_id=payment_intent_id, amount=intent.amount / 100,status="success")
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    for order in orders:
        db.add(Payment(o_id=order.o_id,t_id=transaction.t_id,amount=order.total_price,method="CARD",status="completed"))
        order.payment_status = "PAID"

    db.commit()
    request.session.pop("can_pay", None)
    flash(request, "Payment successful , Order confirmed!", "success")
    return RedirectResponse("/", status_code=303)

@app.get("/products/get-orders/{user_id}",response_model=List[OrderResponse],tags=["Cart endpoint"])
def order(request:Request,user_id:int,current_user:User=Depends(user_authentication),db:Session=Depends(get_db)):
    if current_user.id != user_id : 

        return RedirectResponse(url="/",status_code=303)

    orders=db.query(Order,Products).join(Products,Order.p_id==Products.p_id).filter(Order.c_id==user_id).all()
    response = [] 

    for o,p in orders :
       response.append(OrderResponse(o_id = o.o_id,p_id=p.p_id,title=p.title,description=p.description,total_price=round(o.total_price),quantity=o.quantity,is_delivered=o.is_delivered,payment_status=None if o.payment_status == "pending" else o.payment_status))
    
    flash_message = request.session.pop("flash", None)

    response= templates.TemplateResponse("second.html",{"request":request,"response":response,"order":orders,"user_id":user_id,"user":current_user,"flash": flash_message})
    return no_cache(response)

@app.post("/orders/cancel/{o_id}", tags=["Cancel order"])
def cancel_order(request:Request,o_id: int,current_user: User = Depends(user_authentication),db: Session = Depends(get_db),csrf=Depends(csrf_protect)):
    order = (db.query(Order).filter(Order.o_id == o_id, Order.c_id == current_user.id,Order.payment_status == "pending").first())

    if not order:
        flash(request, "Order not found", "error")
        return RedirectResponse(f"/products/get-orders/{current_user.id}",status_code=303)
        

    db.delete(order)
    db.commit()
    flash(request, "Order removed successfully", "success")

    return RedirectResponse(f"/products/get-orders/{current_user.id}",status_code=303)

@app.put("/updatedeliver/{productid}")
def update_delivery(request: Request,productid: int,current_user: User = Depends(user_authentication),db: Session = Depends(get_db)):
    if current_user.role not in [UserRole.DELIVERY.value, UserRole.ADMIN.value]:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Customers cannot mark orders as delivered. Deliveries must be confirmed by a delivery agent."
        )

    order_update = db.query(Order).filter(
        Order.p_id == productid,
        Order.is_delivered == False,
        or_(Order.payment_status == "COD", Order.payment_status == "PAID")
    ).first()
     
    if not order_update :
        raise HTTPException(status_code=404,detail="Order already delivered or not found")
    order_update.is_delivered = True
    db.commit()
    db.refresh(order_update)

    return {"status":"ok", "is_delivered": True }


@app.get("/products/get-orders/{user_id}/productmanager",response_model=list[ProductManger],tags=["Product manager endpoint"])
def product_manager(request:Request,user_id:int,current_user:User = Depends(user_authentication),db:Session=Depends(get_db)):

    if current_user.id != user_id:
        return RedirectResponse("/", 303)

    pro=db.query(Order,Products).join(Products,Order.p_id==Products.p_id).filter(Order.c_id==current_user.id).all()
    response=[]
    for o,p in pro :
        response.append(ProductManger(p_id=p.p_id,title=p.title,price=p.price,quantity=o.quantity,discount=p.discount,total_price=round(o.total_price)))
    flash_message = request.session.pop("flash", None)
    response= templates.TemplateResponse("product_manager.html",{"request":request,"user_id":current_user.id,"user":current_user,"pro":response,"flash": flash_message})
    return no_cache(response)
   

@app.get("/products/get-orders/{user_id}/category",response_model=List[ProductCategory], tags=["Category endpoint"])
def get_category(request:Request,user_id:int,current_user=Depends(user_authentication),db:Session=Depends(get_db)):
    
    if current_user.id != user_id :
        return RedirectResponse("/",status_code=303)
    product_category=db.query(Order,Products).join(Products,Order.p_id==Products.p_id).filter(Order.c_id==user_id).all()
    response=[]
    for o,p in product_category:
        response.append(ProductCategory(title=p.title,category=p.category,discount=p.discount,total_price=round(o.total_price)))
    flash_message = request.session.pop("flash", None)
    response= templates.TemplateResponse("category.html",{"request":request,"user_id":current_user.id,"user":current_user,"response":response,"flash": flash_message})
    return no_cache(response)

@app.get("/updatediscount" , tags=["update discount endpoint"])
def updatediscount(request:Request,current_user=Depends(user_authentication)):
    if getattr(current_user, "approval_status", "approved") != ApprovalStatus.APPROVED.value:
        return RedirectResponse("/account/status", status_code=303)
    if current_user.role != UserRole.ADMIN.value:
        flash(request, "Access denied: Only Admin can update discounts", "error")
        return RedirectResponse("/", status_code=303)
    response = templates.TemplateResponse("Discount.html",{"request":request, "user": current_user})
    return no_cache(response)

@app.post("/updatediscount" , tags=["update discount endpoint"])
def updatediscount(request:Request,product_id:int=Form(...), discount:int=Form(...),current_user=Depends(user_authentication),db:Session=Depends(get_db),csrf=Depends(csrf_protect)):
    if getattr(current_user, "approval_status", "approved") != ApprovalStatus.APPROVED.value:
        return RedirectResponse("/account/status", status_code=303)
    if current_user.role != UserRole.ADMIN.value:
        flash(request, "Access denied: Only Admin can update discounts", "error")
        return RedirectResponse("/", status_code=303)
    exisiting = db.query(Products).filter(Products.p_id==product_id).first()
    if exisiting is None:
        message="No product found"
        return templates.TemplateResponse("Discount.html",{"request":request,"message":message })

    if discount >=80 or discount<10:
        message="Invalid Discount range [Valid range : {10-80}]"
        return templates.TemplateResponse("Discount.html",{"request":request,"message":message })
    
    exisiting.discount=discount

    db.commit()
    db.refresh(exisiting)   
    flash(request, "Discount updated successfully", "success")
    return RedirectResponse(url="/",status_code=303)

@app.get("/admin/profiles", tags=["Admin and Viewer Profiles"])
def view_profiles(request: Request, current_user: User = Depends(user_authentication), db: Session = Depends(get_db)):
    if getattr(current_user, "approval_status", "approved") != ApprovalStatus.APPROVED.value:
        return RedirectResponse("/account/status", status_code=303)
    if current_user.role not in [UserRole.ADMIN.value, UserRole.VIEWER.value]:
        flash(request, "Access denied: Only Admin and Viewer can access user & retainer profiles", "error")
        return RedirectResponse("/", status_code=303)
    
    users = db.query(User).order_by(User.id.asc()).all()
    user_profiles = [u for u in users if u.role != UserRole.RETAINER.value]
    retainer_profiles = [u for u in users if u.role == UserRole.RETAINER.value]
    
    # Map products added by each retainer
    retainer_products = {}
    for ret in retainer_profiles:
        prods = db.query(Products).filter(Products.created_by_id == ret.id).all()
        retainer_products[ret.id] = prods

    flash_message = request.session.pop("flash", None)
    return templates.TemplateResponse("profiles.html", {
        "request": request,
        "user": current_user,
        "users": user_profiles,
        "retainers": retainer_profiles,
        "retainer_products": retainer_products,
        "all_users": users,
        "flash": flash_message
    })

@app.get("/admin/role-requests", tags=["Admin Role Approvals"])
def list_role_requests(request: Request, current_user: User = Depends(require_roles(UserRole.ADMIN)), db: Session = Depends(get_db)):
    pending_requests = (
        db.query(User)
        .filter(User.approval_status == ApprovalStatus.PENDING.value)
        .order_by(User.id.desc())
        .all()
    )
    resolved_requests = (
        db.query(User)
        .filter(User.approval_status != ApprovalStatus.PENDING.value, User.requested_role != None)
        .order_by(User.id.desc())
        .limit(30)
        .all()
    )
    flash_message = request.session.pop("flash", None)
    return templates.TemplateResponse("role_requests.html", {
        "request": request,
        "current_admin": current_user,
        "pending_requests": pending_requests,
        "resolved_requests": resolved_requests,
        "flash": flash_message
    })

@app.post("/admin/role-requests/{user_id}/approve", tags=["Admin Role Approvals"])
def approve_role_request(request: Request, user_id: int, current_user: User = Depends(require_roles(UserRole.ADMIN)), db: Session = Depends(get_db), csrf=Depends(csrf_protect)):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        flash(request, "Applicant not found", "error")
        return RedirectResponse("/admin/role-requests", 303)

    if target_user.approval_status != ApprovalStatus.PENDING.value:
        flash(request, f"Request for {target_user.email} is not pending", "error")
        return RedirectResponse("/admin/role-requests", 303)

    valid_roles = [r.value for r in UserRole]
    if target_user.requested_role and target_user.requested_role in valid_roles:
        target_user.role = target_user.requested_role
    target_user.approval_status = ApprovalStatus.APPROVED.value

    db.commit()
    flash(request, f"Approved role '{target_user.role}' for {target_user.email} successfully!", "success")
    return RedirectResponse("/admin/role-requests", 303)

@app.post("/admin/role-requests/{user_id}/reject", tags=["Admin Role Approvals"])
def reject_role_request(request: Request, user_id: int, current_user: User = Depends(require_roles(UserRole.ADMIN)), db: Session = Depends(get_db), csrf=Depends(csrf_protect)):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        flash(request, "Applicant not found", "error")
        return RedirectResponse("/admin/role-requests", 303)

    if target_user.approval_status != ApprovalStatus.PENDING.value:
        flash(request, f"Request for {target_user.email} is not pending", "error")
        return RedirectResponse("/admin/role-requests", 303)

    target_user.role = UserRole.USER.value
    target_user.approval_status = ApprovalStatus.REJECTED.value

    db.commit()
    flash(request, f"Rejected role request for {target_user.email}. Account kept as standard customer.", "error")
    return RedirectResponse("/admin/role-requests", 303)

@app.get("/delivery/orders", tags=["Delivery Agent Dashboard"])
def delivery_dashboard(request: Request, current_user: User = Depends(user_authentication), db: Session = Depends(get_db)):
    if current_user.role not in [UserRole.DELIVERY.value, UserRole.ADMIN.value]:
        flash(request, "Access restricted: Only Delivery agents or Admins can access deliveries", "error")
        return RedirectResponse("/", status_code=303)

    # Orders yet to be delivered (pending delivery, but confirmed via PAID or COD)
    pending_deliveries = (
        db.query(Order)
        .filter(Order.is_delivered == False, Order.payment_status.in_(["PAID", "COD"]))
        .order_by(Order.o_id.desc())
        .all()
    )

    # Completed deliveries (already delivered)
    completed_deliveries = (
        db.query(Order)
        .filter(Order.is_delivered == True)
        .order_by(Order.o_id.desc())
        .limit(20)
        .all()
    )

    flash_message = request.session.pop("flash", None)
    return templates.TemplateResponse("delivery_dashboard.html", {
        "request": request,
        "user": current_user,
        "pending_deliveries": pending_deliveries,
        "completed_deliveries": completed_deliveries,
        "flash": flash_message
    })

@app.post("/delivery/mark-delivered/{order_id}", tags=["Delivery Agent Dashboard"])
def mark_order_delivered(request: Request, order_id: int, current_user: User = Depends(user_authentication), db: Session = Depends(get_db)):
    if current_user.role not in [UserRole.DELIVERY.value, UserRole.ADMIN.value]:
        flash(request, "Only Delivery personnel can confirm delivery", "error")
        return RedirectResponse("/", status_code=303)

    order = db.query(Order).filter(Order.o_id == order_id).first()
    if not order:
        flash(request, "Order not found", "error")
        return RedirectResponse("/delivery/orders", status_code=303)

    order.is_delivered = True
    db.commit()
    flash(request, f"Order #{order_id} marked as delivered successfully!", "success")
    return RedirectResponse("/delivery/orders", status_code=303)

@app.get("/viewer/orders", tags=["Viewer and Admin Orders Audit"])
def view_all_orders(request: Request, current_user: User = Depends(user_authentication), db: Session = Depends(get_db)):
    if current_user.role not in [UserRole.ADMIN.value, UserRole.VIEWER.value]:
        flash(request, "Access denied: Only Viewer and Admin can trace all orders", "error")
        return RedirectResponse("/", status_code=303)
    
    orders = (
        db.query(Order, Products, User)
        .join(Products, Order.p_id == Products.p_id)
        .outerjoin(User, Order.c_id == User.id)
        .order_by(Order.o_id.desc())
        .all()
    )
    
    flash_message = request.session.pop("flash", None)
    return templates.TemplateResponse("all_orders.html", {
        "request": request,
        "user": current_user,
        "orders": orders,
        "flash": flash_message
    })

@app.get("/profile", tags=["User Profile"])
def get_user_profile(request: Request, current_user: User = Depends(user_authentication), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        profile = Profile(
            user_id=current_user.id,
            full_name=current_user.email.split("@")[0].capitalize(),
            phone_number="+91 98000 00000",
            street_address="Street 101, Main Road",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            country="India",
            card_brand="Visa",
            card_holder_name=current_user.email.split("@")[0].upper(),
            card_last4=str(random.randint(1000, 9999)),
            card_exp="12/28"
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    flash_message = request.session.pop("flash", None)
    response = templates.TemplateResponse("user_profile.html", {
        "request": request,
        "user": current_user,
        "profile": profile,
        "user_id": current_user.id,
        "flash": flash_message
    })
    return no_cache(response)

@app.post("/profile/update", tags=["User Profile"])
def update_user_profile(
    request: Request,
    full_name: str = Form(...),
    phone_number: str = Form(...),
    street_address: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    postal_code: str = Form(...),
    card_brand: str = Form("Visa"),
    card_holder_name: str = Form(...),
    card_last4: str = Form("4242"),
    card_exp: str = Form("12/28"),
    business_name: Optional[str] = Form(None),
    gstin_id: Optional[str] = Form(None),
    pan_id: Optional[str] = Form(None),
    current_user: User = Depends(user_authentication),
    db: Session = Depends(get_db),
    csrf: None = Depends(csrf_protect)
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    profile.full_name = full_name.strip()
    profile.phone_number = phone_number.strip()
    profile.street_address = street_address.strip()
    profile.city = city.strip()
    profile.state = state.strip()
    profile.postal_code = postal_code.strip()

    # Masked simulated card details
    profile.card_brand = card_brand.strip()
    profile.card_holder_name = card_holder_name.strip()
    profile.card_last4 = card_last4.strip()[-4:] if len(card_last4.strip()) >= 4 else "4242"
    profile.card_exp = card_exp.strip()

    # Retailer fields
    if current_user.role == UserRole.RETAINER.value:
        profile.business_name = business_name.strip() if business_name else None
        profile.gstin_id = gstin_id.strip() if gstin_id else None
        profile.pan_id = pan_id.strip() if pan_id else None
        profile.is_verified = bool(profile.gstin_id and profile.pan_id)

    db.commit()
    flash(request, "Profile updated successfully!", "success")
    return RedirectResponse(f"/profile", status_code=303)

@app.post("/add-review",tags=["Review"])
def add_review(request:Request,product_id:int=Form(...),rating:int=Form(...),comment:str=Form(...),current_user:User=Depends(user_authentication),db:Session=Depends(get_db),csrf=Depends(csrf_protect)):

    if comment is None:
        return RedirectResponse("/",status_code=303)


    if rating < 1 or rating > 5 :
        flash(request,"Rating must be between 1 and 5","error")
        return RedirectResponse("/",status_code=303)
    
    purchased= db.query(Order).filter(Order.c_id==current_user.id,Order.p_id==product_id,Order.payment_status.in_(["PAID","COD"])).first()
    if not purchased :
        flash(request,"You can review only purchased products","error")
        return RedirectResponse("/",status_code=303)

    existing = db.query(Review).filter(Review.user_id == current_user.id , Review.product_id == product_id).first()

    if existing : 
        flash(request,"You already reviewed this product","error")
        return RedirectResponse("/",303)

    review = Review(user_id=current_user.id,product_id=product_id,rating=rating,comment=comment.strip())
    db.add(review)
    db.commit()

    flash(request,"Review added successfully !","success")
    return RedirectResponse("/",status_code=303)



@app.get("/product/{product_id}")
def product_detail(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db)
):

    product = db.query(Products).filter(Products.p_id == product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    user = get_current_user_optional(request, db)

    if user:
        view = ProductView(
            user_id=user.id,
            product_id=product.p_id
        )
        db.add(view)
        db.commit()
        thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)

        recent_views_count = db.query(ProductView).filter(
            ProductView.user_id == user.id,
            ProductView.viewed_at >= thirty_min_ago
        ).count()
        if recent_views_count == 1:
            try:
                requests.post(
                    "https://sahil9900.app.n8n.cloud/webhook-test/product-view",
                    json={
                        "user_id": user.id,
                        "email": user.email,
                        "product_id": product.p_id,
                        "category": product.category,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    timeout=2
                )
            except Exception as e:
                print("Webhook failed:", e)

    review_stats = (
        db.query(
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.r_id).label("review_count")
        )
        .filter(Review.product_id == product_id)
        .first()
    )

    avg_rating = round(review_stats.avg_rating, 1) if review_stats.avg_rating else 0
    review_count = review_stats.review_count or 0

    flash_message = request.session.pop("flash", None)

    return templates.TemplateResponse(
        "product_detail.html",
        {
            "request": request,
            "product": product,
            "user": user,
            "avg_rating": avg_rating,
            "review_count": review_count,
            "flash": flash_message,
        }
    )

@app.get("/check-purchase")
def check_purchase(user_id: int, product_id: int, db: Session = Depends(get_db)):
    count = db.query(Order).filter(
        Order.c_id == user_id,
        Order.p_id == product_id,
        Order.payment_status.in_(["PAID", "COD"])
    ).count()

    return {"purchase_count": count , "user_id":user_id , "product_id" : product_id}

@app.get("/check-email-log")
def check_email_log(user_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("""
        SELECT sent_at FROM email_logs
        WHERE user_id = :user_id
        ORDER BY sent_at DESC
        LIMIT 1
        """),
        {"user_id": user_id}
    ).fetchone()

    if not result:
        return {"send": True}

    last_email_time = result[0]

    if isinstance(last_email_time, str):
        try:
            last_email_time = datetime.fromisoformat(last_email_time)
        except Exception:
            return {"send": True}

    # if datetime.utcnow() - last_email_time > timedelta(hours=24):
    if datetime.utcnow() - last_email_time > timedelta(minutes=1):
        return {"send": True}

    return {"send": False}

@app.get("/recommend-products")
def recommend_products(
    category: str,
    product_id: int,
    email: str,
    user_id: int,
    db: Session = Depends(get_db)
):
    products = db.query(Products).filter(
        Products.category == category
    ).limit(3).all()

    return [
        {
            "title": p.title,
            "price": p.price,
            "discount": p.discount,
            "email": email,
            "user_id": user_id
        }
        for p in products
    ]


@app.post("/log-email-debug")
async def debug(request: Request):
    body = await request.json()
    print("BODY:", body)
    return body

@app.post("/log-email")
def log_email(data: EmailLogRequest, db: Session = Depends(get_db)):
    try:
        db.execute(
            text("""
                INSERT INTO email_logs (user_id, product_id, sent_at)
                VALUES (:user_id, :product_id, CURRENT_TIMESTAMP)
            """),
            {
                "user_id": data.user_id,
                "product_id": data.product_id
            }
        )
        db.commit()

        return {"status": "logged"}

    except Exception as e:
        print("ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)