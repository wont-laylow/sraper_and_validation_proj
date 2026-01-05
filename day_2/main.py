"""
Main script for product enrichment pipeline.
"""

import requests
import re
from typing import List
from day_1.schema import Product
from day_2.schema import ProductEnrichment
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv(override=True)


class GoogleProductEnricher:
    """
    Enriches skincare products using Google Custom Search API.
    """

    def __init__(self, api_key: str, cx: str, results_per_query: int = 5):
        self.api_key = api_key
        self.cx = cx
        self.results_per_query = results_per_query
        self.endpoint = "https://www.googleapis.com/customsearch/v1"


    def _normalize_product_name(self, name: str) -> str:
        name = re.sub(r"\([^)]*\)", "", name)
        name = re.sub(
            r"\b\d+\s?(ml|g|oz|patches|pcs)\b",
            "",
            name,
            flags=re.I
        )
        return name.strip()
    

    def _build_queries(self, product: Product) -> List[str]:
        base = f"{self._normalize_product_name(product.product_name)}"
        return [
            f"{base} product official site",
            f"{base} ingredients or composition",
            f"{base} where to buy",
            f"{base} country of origin",
            f"{base} product information",
        ]
    
    def _google_search(self, query: str) -> List[dict]:
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": self.results_per_query,
        }

        print(query)

        response = requests.get(self.endpoint, params=params, timeout=10)

        response.raise_for_status()
        return response.json().get("items", [])
    
    # extraction utilities

    def _extract_barcode(self, text: str):
        match = re.search(r"\b(\d{8,14})\b", text)
        return match.group(1) if match else None

    def _extract_country(self, text: str):
        for key in ("made in", "manufactured in", "origin"):
            if key in text.lower():
                return text
        return None

    def _looks_official(self, link: str, brand: str) -> bool:
        return brand.lower().replace(" ", "") in link.lower()
    

    def enrich_product(self, product: Product) -> ProductEnrichment:
        queries = self._build_queries(product)

        sources = set()
        ingredients = []
        barcode = None
        origin = None
        official_page = None
        brand_site = None
        description = None

        for query in queries:
            results = self._google_search(query)

            for item in results:
                link = item.get("link")
                snippet = item.get("snippet", "")

                if not link:
                    continue

                sources.add(link)

                if not official_page and self._looks_official(link, product.brand):
                    official_page = link
                    brand_site = f"{link.split('/')[0]}//{link.split('/')[2]}"

                if not barcode:
                    barcode = self._extract_barcode(snippet)

                if not origin:
                    origin = self._extract_country(snippet)

                if "ingredient" in snippet.lower() or "inci" in snippet.lower():
                    ingredients.append(snippet)

                if not description:
                    description = snippet

        return ProductEnrichment(
            product_name=product.product_name,
            brand=product.brand,
            official_product_page=official_page,
            brand_website=brand_site,
            barcode_or_sku=barcode,
            country_of_origin=origin,
            external_description=description,
            external_ingredients=ingredients or None,
            source_urls=list(sources),
        )
    
    def enrich_products(self, products: List[Product], limit: int = 10) -> List[ProductEnrichment]:
        enriched = []
        for product in products[:limit]:
            enriched.append(self.enrich_product(product))
        return enriched
    

    def save_enriched_products(self, enriched_products, path: str):
        rows = []

        for e in enriched_products:
            rows.append({
                "product_name": e.product_name,
                "brand": e.brand,
                "official_product_page": e.official_product_page,
                "brand_website": e.brand_website,
                "barcode_or_sku": e.barcode_or_sku,
                "country_of_origin": e.country_of_origin,
                "external_description": e.external_description,
                "external_ingredients": "; ".join(e.external_ingredients) if e.external_ingredients else None,
                "source_urls": "; ".join(str(url) for url in e.source_urls),
            })

        df_out = pd.DataFrame(rows)
        df_out.to_csv(path, index=False)


def main():
    df = pd.read_csv("day_1/day_1_final_scraped.csv") 
    df_sample = df.sample(n=10, random_state=42)

    products = []

    for _, row in df_sample.iterrows():
        products.append(
            Product(
                product_name=row["product_name"],
                brand=row["brand"],
                category=row["category"],
                ingredients=[i.strip() for i in row["ingredients"].split(",")],
                size=row["size"],
                image_url=row["image_url"],
                product_url=row["product_url"],
            )
        )

    enricher = GoogleProductEnricher(
    api_key=os.getenv("GOOGLE_API_KEY"),
    cx=os.getenv("GOOGLE_CSE_ID"))



    enriched_products = []

    for product in products:
        enriched_products.append(enricher.enrich_product(product))


    enricher.save_enriched_products(enriched_products, "day_2/enriched_products.csv")

    print("DONE")

    
if __name__ == "__main__":

    main()

    







