from pydantic import BaseModel, HttpUrl
from typing import List, Optional


class Product(BaseModel):
    product_name: str
    brand: str
    category: str
    ingredients: List[str]
    size: str | None
    image_url: HttpUrl       
    product_url: HttpUrl      
