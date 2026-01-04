"""
script to scrape individual product descriptions from product pages
"""

import requests
from bs4 import BeautifulSoup
from pydantic import HttpUrl, ValidationError
import pandas as pd
from schema import Product
import re

# scraping constants
BASE_URL = "https://qudobeauty.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# stop markers for ingredient extraction
STOP_MARKERS = {
    "Product effects:",
    "Our cosmetologist recommends this product in case of:",
    "How to use:",
    "Capacity:",
}


# constants for scraping pipeline
INPUT_CSV = "qudobeauty_facecare_category_products.csv"
OUTPUT_CSV = "day_1_final_scraped.csv"
SAMPLE_SIZE = 40
RANDOM_SEED = 42
REQUEST_TIMEOUT = 15


class ScrapeIndContents:

    def __init__(self, url: HttpUrl):
        self.url = url

    def _get_soup(self):
        r = requests.get(self.url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")


    def extract_product_details_from_site(self):
        soup = self._get_soup()

        # description tab
        desc = soup.select_one(
            "div.woocommerce-Tabs-panel--description#tab-description"
        )

        description_text = (
            desc.decode_contents().strip()
            if desc else None
        )

        # main product image
        img = soup.select_one("img.wp-post-image")
        image_url = img.get("src") if img else None

        return description_text, image_url

    @staticmethod
    def _normalize(text: str) -> str:
        return text.replace("–", "-").strip()


    def _extract_brand(self, product_name: str) -> str:
        # Normalize dash variants
        name = product_name.replace("–", " - ")

        # Split ONLY on " - " (space-dash-space)
        parts = name.split(" - ")

        return parts[0].strip()
    

    def _extract_name_and_brand(self,  soup: BeautifulSoup):

        strong = soup.find("strong")
        if not strong:
            return {"product_name": None, "brand": None}

        product_name = strong.get_text(strip=True)
        
        brand = self._extract_brand(product_name)

        return product_name, brand


    def _extract_ingredients(self, soup: BeautifulSoup) -> list[str]:
        ingredients = []

        START_KEYS = ("product contains", "ingredients")
        STOP_KEYS = ("product effects", "recommended for", "how to use")

        # 1. Find the start marker
        start = soup.find(
            "strong",
            string=lambda x: x and any(k in x.lower() for k in START_KEYS)
        )

        if not start:
            return ingredients

        current = start.parent.find_next_sibling()

        # 2. Traverse siblings until stop marker
        while current:
            text = current.get_text(" ", strip=True).lower()

            if any(k in text for k in STOP_KEYS):
                break

            # CASE A: <ul><li> pattern (THIS PAGE)
            if current.name == "ul":
                for li in current.find_all("li"):
                    line = li.get_text(" ", strip=True).replace("–", "-")
                    if "-" in line:
                        name = line.split("-", 1)[0].strip()
                        ingredients.append(name)

            # CASE B: <p> pattern
            elif current.name == "p":
                line = current.get_text(" ", strip=True).replace("–", "-")
                if "-" in line:
                    name = line.split("-", 1)[0].strip()
                    ingredients.append(name)

            current = current.find_next_sibling()

        return ingredients

    
    def _extract_size(self, soup: BeautifulSoup) -> str | None:

        SIZE_LABELS = ("capacity", "quantity", "size", "net weight", "contents","volume", "weight")

        SIZE_PATTERN = re.compile(
            r"""
            (?:
                \d+(?:\.\d+)?        # number
                \s*
                (?:                  # unit group
                    ml|g|kg|oz|lb|
                    pcs?|pieces?|
                    patches?|tabs?|tablets?|
                    bottles?|packs?
                )
            )
            """,
            re.IGNORECASE | re.VERBOSE,
        )

        for tag in soup.find_all("strong"):
            label = tag.get_text(strip=True).lower()

            if not any(lbl in label for lbl in SIZE_LABELS):
                continue

            # Collect only text nodes until next <strong>
            parts = []
            for elem in tag.next_siblings:
                if getattr(elem, "name", None) == "strong":
                    break
                text = elem.get_text(" ", strip=True) if hasattr(elem, "get_text") else str(elem)
                parts.append(text)

            combined = " ".join(parts)
            combined = combined.replace("–", "-").strip()

            # Extract only size-like expressions
            matches = SIZE_PATTERN.findall(combined)
            if matches:
                return matches[0].strip()

        return None
    

    def extract_product_data(self, html: str, image_url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        product_name, brand = self._extract_name_and_brand(soup)

        return {
            "product_name": product_name,
            "brand": brand,
            "ingredients": self._extract_ingredients(soup),
            "size": self._extract_size(soup),
            "image_url": image_url,
        }



# main scrapping pipeline
def scrapping_pipeline():
    df = pd.read_csv(INPUT_CSV)

    # Sample deterministically
    sample_df = df.sample(
        n=SAMPLE_SIZE,
        random_state=RANDOM_SEED
    ).reset_index(drop=True)

    results = []
    failures = 0

    for idx, row in sample_df.iterrows():
        url = row["product_url"]

        try:
            scraper = ScrapeIndContents(url)
            html, image_url = scraper.extract_product_details_from_site()

            extracted = scraper.extract_product_data(html, image_url)

            product = Product(
                product_name=extracted["product_name"],
                brand=extracted["brand"],
                category=row["category"],          # from CSV
                ingredients=extracted["ingredients"],
                size=extracted["size"],
                image_url=extracted["image_url"],
                product_url=row["product_url"],    # from CSV
            )

            results.append(product.model_dump())

        except (requests.RequestException, ValidationError, KeyError) as e:
            failures += 1
            print(f"[FAIL] {url}")
            print(e)

    # 4. Save output
    output_df = pd.DataFrame(results)
    output_df.to_csv(OUTPUT_CSV, index=False)

    print("Done.")
    print(f"Successful: {len(results)}")
    print(f"Failed: {failures}")



if __name__ == "__main__":
    scrapping_pipeline()

    # url = "https://qudobeauty.com/product/vt-cica-care-spot-patch-1pack48-patches/"

    # scraper = ScrapeIndContents(url)
    # html, image_url = scraper.extract_product_details_from_site()

    # print(html)

    # extracted = scraper.extract_product_data(html, image_url)

    # print(extracted)