from pydantic import BaseModel, HttpUrl
from typing import List, Optional


class ProductEnrichment(BaseModel):
    product_name: str
    brand: str

    official_product_page: Optional[str]
    official_page_confidence: str

    brand_website: Optional[str]
    brand_website_confidence: str

    barcode_or_sku: Optional[str]
    barcode_confidence: str

    country_of_origin: Optional[str]
    origin_confidence: str

    external_ingredients: Optional[list]
    ingredients_confidence: str

    external_description: Optional[str]
    source_urls: list
