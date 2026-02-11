from fastapi import FastAPI, Form, Depends, Request,UploadFile ,File , HTTPException
from fastapi.responses import RedirectResponse , JSONResponse 
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import  Session
from pydantic import  ValidationError
from typing import List ,Optional
from jose import jwt , JWTError
from db import User , Products ,Order ,Transactions ,Payment,EmailCheck  , OrderResponse ,ProductManger , ProductCategory  , get_db ,ProductResponse , Review
import shutil 
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext 
import datetime
import uuid
from sqlalchemy import func , or_
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
        "exp" : datetime.datetime.now() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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


@app.get("/")
def products_home(request:Request,db:Session=Depends(get_db)):
    products = db.query(Products).all()
    user = get_current_user_optional(request,db)
    reviews=db.query(Review.product_id,func.avg(Review.rating).label("avg_rating"),func.count(Review.r_id).label("review_count")).group_by(Review.product_id).all()
    review_map={r.product_id : {"avg":round(r.avg_rating,1),"count":r.review_count} for r in reviews}
    flash_message=request.session.pop("flash",None)
    return templates.TemplateResponse("products.html",{"request":request,"products":products,"user":user, "user_id": user.id if user else None,"flash":flash_message,"review_map":review_map})

@app.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    if get_current_user_optional(request, db):
        return RedirectResponse("/", 303)
    return templates.TemplateResponse("index.html",{"request": request, "user": None})

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

    response = RedirectResponse("/",status_code=303)
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
def register_user(request:Request, email:str=Form(...),password:str=Form(...),db:Session=Depends(get_db),csrf=Depends(csrf_protect)):
    try :
        EmailCheck(email=email)
    except ValidationError :
        return templates.TemplateResponse("register.html",{"request":request ,"error":"Invalid email address"})
    
    if db.query(User).filter(User.email == email).first() :
        return templates.TemplateResponse("index.html",{"request":request,"message" :"User already exists"})
    hashed=hash_password(password)
    new_user = User(email=email,password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(new_user.id)
    csrf_token = generate_csrf_token()
    response = RedirectResponse("/",303)
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
    response= templates.TemplateResponse("addproduct.html",{"request":request,"user_id":current_user.id})
    return no_cache(response)

@app.post("/add-product", tags=["Add product endpoint"])
def addproduct(request: Request,title: Optional[str] = Form(None),description: Optional[str] = Form(None),price: Optional[float] = Form(None),discount: Optional[float] = Form(None),image: Optional[UploadFile] = File(None),category: Optional[str] = Form(None),quantity:Optional[int] = Form(None),current_user: Optional[User] = Depends(user_authentication),db: Session = Depends(get_db),csrf=Depends(csrf_protect)):
    if not current_user:
        return RedirectResponse("/login", status_code=303)

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

    new_product = Products(title=title.strip(),description=description.strip(),price=price,discount=discount,image=image_path,category=category.strip(),stock_quantity=quantity)

    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    flash(request, "Product added successfully", "success")

    return RedirectResponse("/products", status_code=303)
    
@app.post("/order",tags=["Order product endpoint"])
def create_order(request:Request,product_id : int =Form(...),quantity:int = Form(...),current_user: User = Depends(user_authentication),db:Session=Depends(get_db)):
    
    product=db.query(Products).filter(Products.p_id==product_id).first()
    if not product :
        return RedirectResponse(url="/products",status_code=303)
    
    if quantity <= 0 :
        flash(request, "Select valid quantity range", "error")
        return RedirectResponse(url="/products",status_code=303)

    if quantity>100 :
        flash(request, "Out of stock", "error")
        return RedirectResponse(url="/products",status_code=303)
    
    if quantity > product.stock_quantity :
        flash(request, "Thanks for adding the product , but we don't have stock right now . Stay tunned we will update it !", "error")
        return RedirectResponse(url="/products",status_code=303)
    
    
    product.stock_quantity = product.stock_quantity - quantity 

    if product.stock_quantity < 0 :
        flash(request, "This product is currently out of stock", "error")
        return RedirectResponse(url="/products",status_code=303)
    
    existing_order = db.query(Order).filter(Order.c_id==current_user.id,Order.p_id==product.p_id,Order.is_delivered==False).first()

    if existing_order :
        return RedirectResponse(url="/products",status_code=303)

    discounted_price = product.price - (product.price * product.discount) /100 
    total_price= quantity * discounted_price

    order=Order(c_id=current_user.id,p_id=product.p_id,total_price=total_price,payment_status="pending",is_delivered = False ,quantity=quantity)

    db.add(order)
    db.commit()
    flash(request, "Product added to cart successfully ", "success")

    return RedirectResponse(url="/",status_code=303)

@app.post("/checkout/start")
def start_checkout(request: Request,current_user: User = Depends(user_authentication),db: Session = Depends(get_db)):
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

    total_amount = round(sum(o.total_price for o in orders), 2)

    intent = stripe.PaymentIntent.create(amount=int(total_amount * 100),currency="inr",automatic_payment_methods={"enabled": True},metadata={"user_id": current_user.id})

    response = templates.TemplateResponse("payment.html",{"request": request,"total_amount": total_amount,"client_secret": intent.client_secret,"stripe_pk": os.getenv("STRIPE_PUBLISHABLE_KEY")})

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
       response.append(OrderResponse(o_id = o.o_id,p_id=p.p_id,title=p.title,description=p.description,total_price=o.total_price,quantity=o.quantity,is_delivered=o.is_delivered,payment_status=None if o.payment_status == "pending" else o.payment_status))
    
    flash_message = request.session.pop("flash", None)

    response= templates.TemplateResponse("second.html",{"request":request,"response":response,"order":orders,"user_id":user_id,"flash": flash_message})
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
    order_update = db.query(Order).filter(Order.p_id == productid,Order.c_id == current_user.id,Order.is_delivered == False,or_(Order.payment_status == "COD",Order.payment_status == "PAID")).first()
     
    if not order_update :
        raise HTTPException(status_code=404,detail="Order already delivered ")
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
        response.append(ProductManger(p_id=p.p_id,title=p.title,price=p.price,quantity=o.quantity,discount=p.discount,total_price=o.total_price))
    flash_message = request.session.pop("flash", None)
    response= templates.TemplateResponse("product_manager.html",{"request":request,"user_id":current_user.id,"pro":response,"flash": flash_message})
    return no_cache(response)
   

@app.get("/products/get-orders/{user_id}/category",response_model=List[ProductCategory], tags=["Category endpoint"])
def get_category(request:Request,user_id:int,current_user=Depends(user_authentication),db:Session=Depends(get_db)):
    
    if current_user.id != user_id :
        return RedirectResponse("/",status_code=303)
    product_category=db.query(Order,Products).join(Products,Order.p_id==Products.p_id).filter(Order.c_id==user_id).all()
    response=[]
    for o,p in product_category:
        response.append(ProductCategory(title=p.title,category=p.category,discount=p.discount,total_price=o.total_price))
    flash_message = request.session.pop("flash", None)
    response= templates.TemplateResponse("category.html",{"request":request,"user_id":current_user.id,"response":response,"flash": flash_message})
    return no_cache(response)

@app.get("/updatediscount" , tags=["update discount endpoint"])
def updatediscount(request:Request,current_user=Depends(user_authentication)):
    response = templates.TemplateResponse("Discount.html",{"request":request })
    return no_cache(response)

@app.post("/updatediscount" , tags=["update discount endpoint"])
def updatediscount(request:Request,product_id:int=Form(...), discount:int=Form(...),current_user=Depends(user_authentication),db:Session=Depends(get_db),csrf=Depends(csrf_protect)):
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
    return RedirectResponse(url="/products",status_code=303)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)