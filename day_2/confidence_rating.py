"""
module for confidence rating logic.
"""

class ConfidenceScorer:
    """
    Centralized confidence scoring logic for enrichment fields.
    """

    def official_page_confidence(self, link: str, brand: str) -> str:
        if not link:
            return "LOW"

        brand_key = brand.lower().replace(" ", "").replace("-", "")
        return "HIGH" if brand_key in link.lower() else "MEDIUM"

    def brand_website_confidence(self, brand_website: str) -> str:
        return "HIGH" if brand_website else "LOW"

    def barcode_confidence(self, barcode: str, source_is_retailer: bool) -> str:
        if not barcode:
            return "LOW"
        return "HIGH" if source_is_retailer else "MEDIUM"

    def origin_confidence(self, origin: str) -> str:
        if not origin:
            return "LOW"
        return "HIGH"

    def _normalize_ingredient(self, ing: str) -> str:
        return ing.lower().strip()

    def ingredients_confidence(self, external: list, scraped: list) -> str:
        if not external or not scraped:
            return "LOW"

        scraped_norm = {self._normalize_ingredient(i) for i in scraped if i}
        external_norm = {self._normalize_ingredient(i) for i in external if i}

        if not scraped_norm or not external_norm:
            return "LOW"

        overlap = scraped_norm & external_norm
        ratio = len(overlap) / len(scraped_norm)

        if ratio >= 0.7:
            return "HIGH"
        if ratio >= 0.3:
            return "MEDIUM"
        return "LOW"
