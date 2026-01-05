# Skincare Product Scraping & Enrichment Pipeline

## Overview
This project scrapes a representative sample of skincare products from Korean beauty retail websites (Qudo Beauty), structures the raw product data, and enriches it using the Google Custom Search API to improve completeness and reliability.

---

## Scraping Approach

### Source Discovery
- Identified navigation categories on Qudo Beauty  
- Filtered to skincare-related URL paths only  

### Data Collection
- Sampled product listings per category (with pagination)  
- Collected individual product URLs  
- Deduplicated products by URL to handle cross-category overlap  

### Product-Level Extraction
Each product page was scraped for:
- Product name, brand, size  
- Ingredients  
- Description  
- Images and product URLs  

### Output
- Structured datasets exported as CSV and JSON  

---

## Enrichment & Validation

Each scraped product was enriched via multiple targeted Google Search queries to retrieve:
- Official product pages  
- Brand website confirmation  
- Retailer listings (“where to buy”)  
- Country of origin  
- External ingredient references (INCI)  

### Validation Logic
- **Source-based checks:** official domains vs. marketplaces  
- **Content-based checks:** explicit labels and structural patterns  
- **Ingredient validation:** overlap with scraped ingredient lists  

Each enriched field was assigned a confidence level:
- **HIGH**
- **MEDIUM**
- **LOW**

---

## Quality-Based Selection

- Products were intentionally oversampled (e.g., 20 records)  
- An aggregate confidence score was computed per product  
- The top **10 highest-confidence enriched products** were selected programmatically  
- Only these 10 records were persisted as the final output  

---

## Final Output
- High-confidence, enriched skincare product dataset  
- Clean, structured CSV/JSON files  