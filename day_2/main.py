"""
Main script for product enrichment pipeline.
"""

import requests
import time
import re
from typing import List
from day_1.schema import Product
from day_2.schema import ProductEnrichment
import os
from dotenv import load_dotenv
import pandas as pd
from day_2.confidence_rating import ConfidenceScorer

load_dotenv(override=True)

SITES = (
    # global SITES
    "amazon.",
    "ebay.",
    "aliexpress.",
    "alibaba.",
    "temu.",
    "shein.",
    "wish.",

    # beauty retailers / aggregators
    "yesstyle.",
    "stylekorean.",
    "oliveyoung.",
    "sephora.",
    "ulta.",
    "cultbeauty.",
    "lookfantastic.",
    "beautybay.",
    "feelunique.",
    "skinstore.",
    "dermstore.",
    "stylevana.",
    "sokoglam.",
    "beautynet.",

    # regional / local ecommerce
    "jumia.",
    "ksisters.",
    "elbeauty.",
    "notino.",

    # forums / community / UGC
    "reddit.",
    "reddit.com",
    "quora.",
    "stackexchange.",
    "forum.",

    # blogs / reviews / databases
    "incidecoder.",
    "skincarisma.",
    "cosdna.",
    "ewg.",
    "medium.",
    "wordpress.",
    "blogspot.",

    # social platforms
    "instagram.",
    "facebook.",
    "twitter.",
    "tiktok.",
    "youtube.",
)


# confidence scoring weights
CONF_SCORE = {
    "HIGH": 2,
    "MEDIUM": 1,
    "LOW": 0,
}

def overall_confidence_score(e):
    return (
        CONF_SCORE[e.official_page_confidence]
        + CONF_SCORE[e.brand_website_confidence]
        + CONF_SCORE[e.barcode_confidence]
        + CONF_SCORE[e.origin_confidence]
        + CONF_SCORE[e.ingredients_confidence]
    )


class GoogleProductEnricher(ConfidenceScorer):
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
        """
        Extract barcode / SKU only when explicitly labeled.
        Accepts EAN, UPC, GTIN, SKU patterns.
        """

        if not text:
            return None

        text = text.lower()

        # Require barcode context
        KEYWORDS = ("barcode", "sku", "ean", "upc", "gtin")

        if not any(k in text for k in KEYWORDS):
            return None

        # Extract numeric candidates
        matches = re.findall(r"\b\d{8,14}\b", text)

        for m in matches:
            # Extra safety: ensure pure digits
            if m.isdigit():
                return m  # return FIRST valid barcode

        return None


    def _extract_country(self, text: str):
        if not text:
            return None

        match = re.search(
            r"(made in|manufactured in|country of origin)\s*[:\-]?\s*([A-Za-z\s]+)",
            text,
            flags=re.I,
        )

        if match:
            return match.group(2).strip()

        return None

    def _looks_official(self, link: str, brand: str) -> bool:
        if any(m in link.lower() for m in SITES):
            return False

        brand_key = brand.lower().replace(" ", "").replace("-", "")
        return brand_key in link.lower()
        
    def _extract_external_ingredients(self, text: str):
        """
        Extract INCI-style ingredient lists from snippet text.
        """
        if not text:
            return None

        text_lower = text.lower()

        # Require INCI context
        if "ingredient" not in text_lower:
            return None

        # Try to split at 'ingredients' or 'ingredients (inci)'
        parts = re.split(r"ingredients?\s*(?:\(inci\))?\s*[:.\-]", text, flags=re.I)

        if len(parts) < 2:
            return None

        candidate = parts[1]

        # Cut off common non-ingredient sections
        candidate = re.split(
            r"(how to use|key ingredients|skin concern|area of application|cruelty)",
            candidate,
            flags=re.I,
        )[0]

        # Remove dates
        candidate = re.sub(r"\b[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b", "", candidate)

        # Keep only comma-separated chemical-style lists
        ingredients = [i.strip() for i in candidate.split(",") if len(i.strip()) > 3]

        # Heuristic: INCI lists usually have multiple ingredients
        if len(ingredients) < 3:
            return None

        return ingredients


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
                    raw_barcode = self._extract_barcode(snippet)
                    barcode = str(raw_barcode) if raw_barcode else None

                if not origin:
                    origin = self._extract_country(snippet)

                extracted = self._extract_external_ingredients(snippet)
                if extracted:
                    ingredients.extend(extracted)

                if not description:
                    if any(x in snippet.lower() for x in ("privacy", "cookie", "acknowledge")):
                        continue
                    if len(snippet) < 40:
                        continue
                    description = snippet


        official_conf = self.official_page_confidence(
        official_page, product.brand
        )

        brand_conf = self.brand_website_confidence(
            brand_site
        )

        barcode_conf = (
            self.barcode_confidence(barcode, source_is_retailer=True)
            if barcode and barcode.isdigit()
            else "LOW"
        )

        origin_conf = self.origin_confidence(
            origin
        )

        ingredients_conf = (
            self.ingredients_confidence(ingredients, product.ingredients)
            if ingredients else "LOW"
        )


        return ProductEnrichment(
            product_name=product.product_name,
            brand=product.brand,

            official_product_page=official_page,
            official_page_confidence=official_conf,

            brand_website=brand_site,
            brand_website_confidence=brand_conf,

            barcode_or_sku=barcode,
            barcode_confidence=barcode_conf,

            country_of_origin=origin,
            origin_confidence=origin_conf,

            external_ingredients=ingredients or None,
            ingredients_confidence=ingredients_conf,

            external_description=description,
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
            # core identifiers
            "product_name": e.product_name,
            "brand": e.brand,

            # official / brand information
            "official_product_page": e.official_product_page,
            "official_page_confidence": e.official_page_confidence,

            "brand_website": e.brand_website,
            "brand_website_confidence": e.brand_website_confidence,

            # commercial identifiers
            "barcode_or_sku": str(e.barcode_or_sku) if e.barcode_or_sku else None,
            "barcode_confidence": e.barcode_confidence,

            # origin information
            "country_of_origin": e.country_of_origin,
            "origin_confidence": e.origin_confidence,

            # descriptive enrichment
            "external_description": e.external_description,
            "external_ingredients": (
                "; ".join(e.external_ingredients) if e.external_ingredients else None
            ),
            "ingredients_confidence": e.ingredients_confidence,

            "overall_confidence_score": overall_confidence_score(e),

            # provenance
            "source_urls": "; ".join(str(url) for url in e.source_urls),
            })

        df_out = pd.DataFrame(rows)
        df_out.to_csv(path, index=False)


def main():
    df = pd.read_csv("day_1/day_1_final_scraped.csv") 
    df_sample = df.sample(n=10, random_state=int(time.time()))
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


    ranked = sorted(
        enriched_products,
        key=overall_confidence_score,
        reverse=True
    )

    top_10 = ranked[:10]

    enricher.save_enriched_products(
        top_10,
        "day_2/day_2_final_enriched.csv"
    )

    print("DONE")

if __name__ == "__main__":

    main()

    







