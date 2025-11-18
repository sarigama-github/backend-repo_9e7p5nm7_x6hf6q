"""
Database Schemas for the Sportswear Shop

Each Pydantic model represents a collection in MongoDB. The collection name is
simply the lowercase of the class name (e.g., Product -> "product").
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product"
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category, e.g., 'Ropa', 'Accesorios'")
    in_stock: bool = Field(True, description="Whether product is in stock")
    image_url: Optional[str] = Field(None, description="Primary image URL")
    sizes: Optional[List[str]] = Field(default=None, description="Available sizes if applicable (e.g., S, M, L)")

class CartItem(BaseModel):
    product_id: str = Field(..., description="Referenced Product _id as string")
    quantity: int = Field(1, ge=1, description="Quantity in cart")
    size: Optional[str] = Field(None, description="Selected size if applicable")
    unit_price: float = Field(..., ge=0, description="Snapshot of product price at add-to-cart time")
    title: str = Field(..., description="Snapshot of product title")
    image_url: Optional[str] = Field(None, description="Snapshot of image URL")

class Cart(BaseModel):
    """
    Carts collection schema
    Collection name: "cart"
    """
    items: List[CartItem] = Field(default_factory=list)
    checked_out: bool = Field(False)

# You can extend with Order schema later if needed.
