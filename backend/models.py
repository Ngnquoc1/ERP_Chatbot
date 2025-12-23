from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    """Request model cho chat endpoint"""
    message: str
    history: List[dict] = []
    sales_rep_name: str = "Admin"

class ChatResponse(BaseModel):
    """Response model cho chat endpoint"""
    reply: str

class CustomerInfo(BaseModel):
    """Model thông tin khách hàng"""
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None

class ProductInfo(BaseModel):
    """Model thông tin sản phẩm"""
    id: int
    name: str
    list_price: float
    qty_available: float

class PricingResult(BaseModel):
    """Model kết quả suggest pricing"""
    is_ambiguous: bool = False
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    base_price: float = 0
    suggested_price: float = 0
    price_with_tax: float = 0
    tax_rate: float = 0
    quantity: int = 1
    pricelist: str = "Giá niêm yết (Mặc định)"
    message: str = ""