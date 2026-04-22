from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import Products, Base  # assuming your file is named db.py

# Database URL
DATABASE_URL = "sqlite:///./data/test.db"

# Create engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def update_product_category(product_id: int, new_category: str):
    db: Session = SessionLocal()
    try:
        # Fetch product
        product = db.query(Products).filter(Products.p_id == product_id).first()

        if not product:
            print(f"Product with p_id={product_id} not found.")
            return

        # Update category
        product.category = new_category
        db.commit()
        db.refresh(product)

        print(f"Updated Product ID {product_id} → Category set to '{new_category}'")

    except Exception as e:
        db.rollback()
        print("Error:", e)

    finally:
        db.close()


if __name__ == "__main__":
    update_product_category(6, "Lifestyle & Misc")