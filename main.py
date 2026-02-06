from fastapi import FastAPI, Form, Depends, Request,UploadFile ,File , HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import  Session
from pydantic import  ValidationError
from typing import List ,Optional
from db import User , Products ,Order ,Transactions ,Payment,EmailCheck  , OrderResponse ,ProductManger , ProductCategory  , get_db ,ProductResponse
import shutil 
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext 
import datetime
import uuid
from sqlalchemy import func

import os



app = FastAPI(
    title="Order portal")


app.add_middleware(SessionMiddleware,secret_key=os.getenv("SESSION_SECRET", "dev-secret"),same_site="lax",https_only=False,session_cookie="session",)


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

templates = Jinja2Templates(directory="Template")


pwd=CryptContext(schemes=["bcrypt"],deprecated = "auto")

def hash_password(password:str)->str :
    if len(password.encode("utf-8")) > 72 :
        raise HTTPException(status_code=400,detail="Password to long ")
    return pwd.hash(password)

def verify_password(plain_password:str,hashed_password:str) -> bool :
    return pwd.verify(plain_password,hashed_password)

def user_authentication(request:Request,db:Session=Depends(get_db))-> User:
    user_id = request.session.get("user_id")
    if not user_id :
        raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id==user_id).first()
    if not user :
        request.session.clear()
        raise  HTTPException(status_code=401, detail="Invalid session")
    return user

def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response



@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and request.url.path != "/login":
        return RedirectResponse(url="/login", status_code=303)
    raise exc

from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse

@app.exception_handler(StarletteHTTPException)
async def not_found_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html",{"request": request,"path": request.url.path},status_code=404)
    return JSONResponse(status_code=exc.status_code,content={"detail": exc.detail},)



@app.get("/")
def products_home(request: Request, db: Session = Depends(get_db)):
    products = db.query(Products).all()
    try:
        user_id = request.session.get("user_id")
    except :
        user_id : None
    success = request.session.pop("success", None)
    error = request.session.pop("error", None)

    return templates.TemplateResponse("products.html",{  "request": request,"products": products,"user_id": user_id,"success": success,"error": error})

@app.get("/login",tags=["Login User endpoint"])
def login_page(request:Request):
    return  templates.TemplateResponse("index.html",{"request":request})


@app.post("/login",tags=["Login User endpoint"])
def login_form(request: Request,email: str = Form(...),password: str = Form(...),db: Session = Depends(get_db)):
    try :
        EmailCheck(email=email)
    except ValidationError :
        return templates.TemplateResponse("index.html",{"request":request ,"error":"Invalid email address"})
    
    user=db.query(User).filter(User.email == email).first()
    if not user :
        error = "Email not found please register"
        return templates.TemplateResponse("register.html",{"request":request,"error":error})
    
    if user and not verify_password(password,user.password):
        return templates.TemplateResponse("index.html",{"request":request,"error":"Password does not match"})
    request.session["user_id"]=user.id
    request.session["success"] = "Login successful"
    return RedirectResponse(url="/products",status_code=303)

@app.get("/register",tags=["Register User endpoint"])
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register",tags=["Register User endpoint"])
def register_user(request:Request, email:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
    try :
        EmailCheck(email=email)
    except ValidationError :
        return templates.TemplateResponse("register.html",{"request":request ,"error":"Invalid email address"})
    user=db.query(User).filter(User.email == email).first()
    if user :
        message="User exists please login"
        return templates.TemplateResponse("index.html",{"request":request,"message":message})
    if user and verify_password(password,user.password):
        return templates.TemplateResponse("index.html",{"request":request,"message":"Valid credentials Please login"})
    if len(password)<5 :
        error="The length of password should be greater than 5"
        return templates.TemplateResponse("register.html",{"request":request,"error":error})

    hashed_pw=hash_password(password)
    new_user = User(email=email,password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    request.session["user_id"] = new_user.id
    request.session["success"] = "Account created successfully"
    return RedirectResponse(url="/products", status_code=303)

@app.get("/logout",tags=["logout"])
def logout(request:Request,current_user:User=Depends(user_authentication)):
    if current_user : 
        request.session.clear()
        response = RedirectResponse(url="/", status_code=303)
        response.delete_cookie("session")
        return no_cache(response)

@app.get("/products",tags=["Products dashboard endpoint"])
def products_page(request: Request,db: Session = Depends(get_db)):
    products=db.query(Products).all()
    try:
        user_id =request.session.get("user_id")
    except :
        user_id : None
    
    if user_id :
        return no_cache(RedirectResponse("/",status_code=303))

    success= request.session.pop("success",None)
    error=request.session.pop("error",None)
    products = db.query(Products).all()
    response= templates.TemplateResponse("products.html",{"request": request, "products": products, "user_id": user_id,"success":success,"error":error})
    return response


@app.get("/forget-password",tags=["Forget Password endpoint"])
def display_forget_password(request:Request):
    return templates.TemplateResponse("forget-password.html",{"request":request})

@app.post("/password",tags=["Forget Password endpoint"])
def update_password(request:Request,email:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):

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
    m="Fill the details for adding a product"
    response= templates.TemplateResponse("addproduct.html",{"request":request,"m":m,"user_id":current_user.id})
    return no_cache(response)

@app.post("/add-product", tags=["Add product endpoint"])
def addproduct(request: Request,title: Optional[str] = Form(None),description: Optional[str] = Form(None),price: Optional[float] = Form(None),discount: Optional[float] = Form(None),image: Optional[UploadFile] = File(None),category: Optional[str] = Form(None),current_user: Optional[User] = Depends(user_authentication),db: Session = Depends(get_db)):
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

    new_product = Products(title=title.strip(),description=description.strip(),price=price,discount=discount,image=image_path,category=category.strip())

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    products = db.query(Products).all()
    message = "Product added successfully"

    return templates.TemplateResponse("products.html",{"request": request, "products": products, "message": message})

@app.post("/order",tags=["Order product endpoint"])
def create_order(request:Request,product_id : int =Form(...),quantity:int = Form(...),current_user: User = Depends(user_authentication),db:Session=Depends(get_db)):
    
    product=db.query(Products).filter(Products.p_id==product_id).first()
    if not product :
        return RedirectResponse(url="/products",status_code=303)
    
    if quantity <= 0 :
        return RedirectResponse(url="/products",status_code=303)
    
    existing_order = db.query(Order).filter(Order.c_id==current_user.id,Order.p_id==product.p_id,Order.is_delivered==False).first()

    if existing_order :
        request.session["error"] = " Product already in a bag"
        return RedirectResponse(url="/products",status_code=303)

    discounted_price = product.price - (product.price * product.discount) /100 
    total_price= quantity * discounted_price

    order=Order(c_id=current_user.id,p_id=product.p_id,total_price=total_price,payment_status="pending",is_delivered = False ,quantity=quantity)

    db.add(order)
    db.commit()
    
    request.session["success"] = "Products added successfully"
    return RedirectResponse(url="/",status_code=303)

@app.post("/checkout/start")
def start_checkout(request: Request,current_user: User = Depends(user_authentication),db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.c_id == current_user.id,Order.payment_status == "pending").first()

    if not orders:
        return RedirectResponse("/", status_code=303)

    request.session["can_pay"] = True

    return RedirectResponse("/payment", status_code=303)

@app.get("/payment")
def payment_page(request: Request,current_user: User = Depends(user_authentication),db: Session = Depends(get_db)):

    if not request.session.get("can_pay"):
        return RedirectResponse("/", status_code=303)

    orders = db.query(Order).filter(Order.c_id == current_user.id,Order.payment_status == "pending").all()

    if not orders:
        return RedirectResponse("/", status_code=303)

    total_amount = sum(o.total_price for o in orders)

    response = templates.TemplateResponse("payment.html",{"request": request, "total_amount": total_amount})

    return no_cache(response)

@app.post("/payment")
def process_payment(request: Request,method: str = Form(...),current_user: User = Depends(user_authentication),db: Session = Depends(get_db)):
    orders = (db.query(Order).filter(Order.c_id == current_user.id,Order.payment_status == "pending").all())

    if not orders:
        return RedirectResponse("/", status_code=303)

    total_amount = sum(o.total_price for o in orders)

    transaction = None

    if method != "COD":
        transaction = Transactions(created_at=datetime.datetime.now(),mount=total_amount,status="success")
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

    for order in orders:
        existing_payment = (db.query(Payment).filter(Payment.o_id == order.o_id).first())

        if existing_payment:
            continue

        payment = Payment(o_id=order.o_id,t_id=transaction.t_id if transaction else None,amount=order.total_price,method="Cash on Delivery" if method == "COD" else method,status="completed")
        db.add(payment)
        order.payment_status = "COD" if method == "COD" else "PAID"

    db.commit()
    request.session.pop("can_pay", None)

    request.session["success"] = "Order successful! Keep shopping more 🛒"
    return RedirectResponse("/", status_code=303)


@app.get("/products/get-orders/{user_id}",response_model=List[OrderResponse],tags=["Cart endpoint"])
def order(request:Request,user_id:int,current_user:User=Depends(user_authentication),db:Session=Depends(get_db)):
    if current_user.id != user_id : 

        return RedirectResponse(url="/",status_code=303)

    orders=db.query(Order,Products).join(Products,Order.p_id==Products.p_id).filter(Order.c_id==user_id).all()
    response = [] 

    for o,p in orders :
       response.append(OrderResponse(o_id = o.o_id,p_id=p.p_id,title=p.title,description=p.description,total_price=o.total_price,quantity=o.quantity,is_delivered=o.is_delivered,payment_status=None if o.payment_status == "pending" else o.payment_status))
    
    response= templates.TemplateResponse("second.html",{"request":request,"response":response,"order":orders,"user_id":user_id})
    return no_cache(response)

@app.post("/orders/cancel/{o_id}", tags=["Cancel order"])
def cancel_order(request:Request,o_id: int,current_user: User = Depends(user_authentication),db: Session = Depends(get_db)):
    order = (db.query(Order).filter(Order.o_id == o_id, Order.c_id == current_user.id,Order.payment_status == "pending").first())

    if not order:
        message="Order not found"
        request.session["error"]=message
        return RedirectResponse(f"/products/get-orders/{current_user.id}",status_code=303)
        

    db.delete(order)
    db.commit()
    message="Order removed successfully"
    request.session["success"]=message
    return RedirectResponse(f"/products/get-orders/{current_user.id}",status_code=303)
 


@app.put("/updatedeliver/{productid}")
def update_delivery(request: Request,productid: int,current_user: User = Depends(user_authentication),db: Session = Depends(get_db)):
    order_update = (db.query(Order).filter(Order.p_id == productid,Order.c_id == current_user.id,func.lower(Order.payment_status).in_(["cod", "paid"])).first())

    if not order_update:
        raise HTTPException(status_code=404, detail="Order not found or unpaid")

    if order_update.is_delivered:
        raise HTTPException(status_code=400, detail="Order already delivered")

    order_update.is_delivered = True
    db.commit()

    return RedirectResponse(f"/products/get-orders/{current_user.id}",status_code=303)


@app.get("/products/get-orders/{user_id}/productmanager",response_model=list[ProductManger],tags=["Product manager endpoint"])
def product_manager(request:Request,user_id:int,current_user:User = Depends(user_authentication),db:Session=Depends(get_db)):

    if current_user.id != user_id:
        return RedirectResponse("/", 303)

    pro=db.query(Order,Products).join(Products,Order.p_id==Products.p_id).filter(Order.c_id==current_user.id).all()
    response=[]
    for o,p in pro :
        response.append(ProductManger(p_id=p.p_id,title=p.title,price=p.price,quantity=o.quantity,discount=p.discount,total_price=o.total_price))
    response= templates.TemplateResponse("product_manager.html",{"request":request,"user_id":current_user.id,"pro":response})
    return no_cache(response)
   

@app.get("/products/get-orders/{user_id}/category",response_model=List[ProductCategory], tags=["Category endpoint"])
def get_category(request:Request,user_id:int,current_user=Depends(user_authentication),db:Session=Depends(get_db)):
    
    if current_user.id != user_id :
        return RedirectResponse("/",status_code=303)
    product_category=db.query(Order,Products).join(Products,Order.p_id==Products.p_id).filter(Order.c_id==user_id).all()
    response=[]
    for o,p in product_category:
        response.append(ProductCategory(title=p.title,category=p.category,discount=p.discount,total_price=o.total_price))

    response= templates.TemplateResponse("category.html",{"request":request,"user_id":current_user.id,"response":response})
    return no_cache(response)

@app.get("/updatediscount" , tags=["update discount endpoint"])
def updatediscount(request:Request,current_user=Depends(user_authentication)):
    response = templates.TemplateResponse("Discount.html",{"request":request })
    return no_cache(response)

@app.post("/updatediscount" , tags=["update discount endpoint"])
def updatediscount(request:Request,product_id:int=Form(...), discount:int=Form(...),current_user=Depends(user_authentication),db:Session=Depends(get_db)):
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

    request.session["success"] = "Discount updated successfully"
    return RedirectResponse(url="/products",status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
