"""
script to scrape product links from a specific category listing page
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
import time
import csv

BASE_URL = "https://qudobeauty.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def clean_url(url):
    parsed = urlparse(url)

    # rebuild URL without query params or fragments
    clean = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip("/") + "/",  # normalize trailing slash
        "", "", ""
    ))

    return clean


def extract_skincare_categories(WHOLESALE_PREFIX = "https://qudobeauty.com/cat/wholesale-face-care/"):
    categories = []

    soup = get_soup(BASE_URL)

    for a in soup.select("ul.sub-menu li.menu-item a.cg-menu-link"):
        url = a.get("href")
        name = a.get_text(strip=True)

        if url and name:
            categories.append({
                "name": name,
                "url": url
            })

    # deduplicate by URL, preserve order
    seen = {}
    for c in categories:
        url = c.get("url", "")
        if url.startswith(WHOLESALE_PREFIX):
            seen[url] = c

    return list(seen.values())


def extract_first_n_cat_products(category, n=10):
    products = []
    page = 1

    while len(products) < n:
        if page == 1:
            url = category["url"]
        else:
            url = f"{category['url']}page/{page}/"

        soup = get_soup(url)

        anchors = soup.select(
            "a.woocommerce-LoopProduct-link.woocommerce-loop-product__link"
        )

        if not anchors:
            break  # no more pages

        for a in anchors:
            if len(products) >= n:
                break

            href = a.get("href")
            name = a.get_text(strip=True) or a.get("aria-label")

            if href and name:
                products.append({
                    "category": category["name"],
                    "product_name": name,
                    "product_url": clean_url(href)
                })

        page += 1

    return products


if __name__ == "__main__":

    all_products = []

    categories = extract_skincare_categories()

    for cat in categories:
        print(f"Scraping category: {cat['name']}")
        try:
            items = extract_first_n_cat_products(cat, n=10)
            print(f"  → Items found: {len(items)}")
            all_products.extend(items)
            time.sleep(1)
        except Exception as e:
            print(f"Failed on {cat['name']}: {e}")

    print(f"Total products before deduplication: {len(all_products)}")
    
    # deduplicate products by URL
    seen = {}
    for item in all_products:
        seen[item["product_url"]] = item

    all_products = list(seen.values())

    #  print summary
    print(f"Total unique products: {len(all_products)}")


    # save to CSV
    output_file = "qudobeauty_facecare_category_products.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category", "product_name", "product_url"]
        )
        writer.writeheader()
        writer.writerows(all_products)

    print(f"Saved {len(all_products)} products to {output_file}")



    





    