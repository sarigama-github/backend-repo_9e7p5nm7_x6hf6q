import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Cart, CartItem

app = FastAPI(title="Sportswear Shop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility to convert Mongo ObjectIds to strings

def serialize_document(doc):
    if not doc:
        return doc
    doc = dict(doc)
    _id = doc.get("_id")
    if isinstance(_id, ObjectId):
        doc["id"] = str(_id)
        del doc["_id"]
    return doc


@app.get("/")
def read_root():
    return {"message": "Sportswear Shop Backend Running"}


# ---------------------- Products ----------------------

@app.post("/api/products", response_model=dict)
def create_product(product: Product):
    try:
        new_id = create_document("product", product)
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/products", response_model=List[dict])
def list_products(category: Optional[str] = None):
    try:
        filter_q = {"category": category} if category else {}
        products = get_documents("product", filter_q)
        return [serialize_document(p) for p in products]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/products/seed", response_model=dict)
def seed_products():
    """Create a small set of demo products if the collection is empty"""
    try:
        count = db["product"].count_documents({})
        if count > 0:
            return {"created": 0, "message": "Products already exist"}
        demo_products = [
            {
                "title": "Camiseta Running Pro",
                "description": "Tejido respirable y de secado rápido.",
                "price": 24.99,
                "category": "Ropa",
                "in_stock": True,
                "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80",
                "sizes": ["S", "M", "L", "XL"],
            },
            {
                "title": "Zapatillas Training X",
                "description": "Estabilidad y agarre para el gym.",
                "price": 79.99,
                "category": "Calzado",
                "in_stock": True,
                "image_url": "https://images.unsplash.com/photo-1542291026-7d3b7318f19b?w=800&q=80",
                "sizes": ["38", "39", "40", "41", "42", "43"],
            },
            {
                "title": "Mochila Deportiva",
                "description": "Compartimentos múltiples y resistente al agua.",
                "price": 39.99,
                "category": "Accesorios",
                "in_stock": True,
                "image_url": "https://images.unsplash.com/photo-1520975922313-b46f52b85072?w=800&q=80",
                "sizes": None,
            },
        ]
        for p in demo_products:
            db["product"].insert_one(p)
        return {"created": len(demo_products)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------- Cart ----------------------

class AddToCartPayload(BaseModel):
    cart_id: Optional[str] = None
    product_id: str
    quantity: int = 1
    size: Optional[str] = None


class RemovePayload(BaseModel):
    cart_id: str
    product_id: str
    size: Optional[str] = None


class QtyPayload(BaseModel):
    cart_id: str
    product_id: str
    size: Optional[str] = None
    quantity: int = 1


@app.post("/api/cart:add", response_model=dict)
def add_to_cart(payload: AddToCartPayload):
    try:
        # Fetch product to snapshot fields
        prod = db["product"].find_one({"_id": ObjectId(payload.product_id)})
        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        item = CartItem(
            product_id=str(prod["_id"]),
            quantity=max(1, payload.quantity or 1),
            size=payload.size,
            unit_price=float(prod.get("price", 0)),
            title=prod.get("title", "Producto"),
            image_url=prod.get("image_url"),
        )

        # Create or update cart
        if payload.cart_id:
            cart = db["cart"].find_one({"_id": ObjectId(payload.cart_id)})
            if not cart:
                raise HTTPException(status_code=404, detail="Carro no encontrado")
            items = cart.get("items", [])
            # If same product+size exists, increase quantity
            merged = False
            for it in items:
                if it.get("product_id") == item.product_id and it.get("size") == item.size:
                    it["quantity"] = int(it.get("quantity", 1)) + item.quantity
                    merged = True
                    break
            if not merged:
                items.append(item.model_dump())
            db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"items": items}})
            return {"cart_id": str(cart["_id"]) }
        else:
            cart_model = Cart(items=[item])
            new_id = create_document("cart", cart_model)
            return {"cart_id": new_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cart", response_model=dict)
def get_cart(cart_id: str):
    try:
        cart = db["cart"].find_one({"_id": ObjectId(cart_id)})
        if not cart:
            raise HTTPException(status_code=404, detail="Carro no encontrado")
        cart_ser = serialize_document(cart)
        return cart_ser
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cart:remove", response_model=dict)
def remove_from_cart(payload: RemovePayload):
    try:
        cart = db["cart"].find_one({"_id": ObjectId(payload.cart_id)})
        if not cart:
            raise HTTPException(status_code=404, detail="Carro no encontrado")
        items = cart.get("items", [])
        items = [i for i in items if not (i.get("product_id") == payload.product_id and i.get("size") == payload.size)]
        db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"items": items}})
        return {"cart_id": payload.cart_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cart:qty", response_model=dict)
def update_quantity(payload: QtyPayload):
    try:
        cart = db["cart"].find_one({"_id": ObjectId(payload.cart_id)})
        if not cart:
            raise HTTPException(status_code=404, detail="Carro no encontrado")
        items = cart.get("items", [])
        for it in items:
            if it.get("product_id") == payload.product_id and it.get("size") == payload.size:
                it["quantity"] = max(1, int(payload.quantity))
                break
        db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"items": items}})
        return {"cart_id": payload.cart_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
