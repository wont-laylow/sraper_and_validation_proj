from pydantic import BaseModel, HttpUrl
from typing import List, Optional


class ProductEnrichment(BaseModel):
    product_name: str
    brand: str
    official_product_page: Optional[HttpUrl]
    brand_website: Optional[HttpUrl]
    barcode_or_sku: Optional[str]
    country_of_origin: Optional[str]
    external_description: Optional[str]
    external_ingredients: Optional[List[str]]
    source_urls: List[HttpUrl]