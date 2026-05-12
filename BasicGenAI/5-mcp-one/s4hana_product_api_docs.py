"""
S/4HANA Product API Documentation for AI Agent

This module contains structured documentation that the AI agent can query
to understand how to use the S/4HANA Product Master API.
"""

PRODUCT_API_DOCUMENTATION = """
# S/4HANA Cloud Product Master API (OData V4)

## Overview
This API enables reading product master data from SAP S/4HANA Cloud.
It uses OData V4 protocol with Basic Authentication.

## CRITICAL: Product ID vs Product Description
- **Product** field = Technical ID only (e.g., 'APJ123', 'TG-17') - NOT human-readable!
- **ProductDescription** = Human-readable name/text (e.g., "Cat Food Premium 500g")

## How to Search for Products by Name/Text

### BEST METHOD: Use search_product_descriptions tool
The ProductDescription is a separate entity that CAN be filtered directly.
Use the `search_product_descriptions(search_text, language)` tool:
- `search_text`: The text to search for (e.g., "cat", "food", "battery")
- `language`: Language code - "EN" (English), "DE" (German), "JA" (Japanese), etc.

This queries the ProductDescription entity with:
```
ProductDescription?$filter=contains(ProductDescription,'cat') and Language eq 'EN'
```

### Language Codes
- **EN**: English
- **DE**: German (Deutsch)
- **JA**: Japanese (日本語)
- **FR**: French (Français)
- **ES**: Spanish (Español)
- **ZH**: Chinese (中文)
- **KO**: Korean (한국어)

### Alternative: Query Product entity with expand
If you need full product details, use `query_products` with `expand="_ProductDescription"`.
You **cannot** filter on `_ProductDescription` in `$filter`; filter on Product fields only,
then use the expanded descriptions for display.

## OData V4 Query Options

### $filter - Filter on Product entity fields ONLY
- **eq**: `$filter=Product eq 'TG-17'`
- **contains()**: `$filter=contains(Product,'APJ')` - searches Product ID only!
- **startswith()**: `$filter=startswith(Product,'APJ')`
- **and/or**: `$filter=ProductType eq 'FERT' and startswith(Product,'APJ')`

**CANNOT filter on**: `_ProductDescription` navigation property when querying `Product`.
To filter by description text, use the `ProductDescription` entity as shown above.

### $expand - ESSENTIAL for product names!
Include product descriptions: `$expand=_ProductDescription`

The _ProductDescription contains:
- **Language**: Language code (EN, DE, JA, etc.)
- **ProductDescription**: The actual human-readable product name

### $select - Choose fields to return
`$select=Product,ProductType,ProductGroup,BaseUnit`

### $top - Limit results (ALWAYS USE THIS!)
`$top=20` - Recommended: 10-50 for performance

### $skip - Pagination
`$skip=20` - Skip first N results

### $orderby - Sort results
`$orderby=Product asc` or `$orderby=CreationDate desc`

## Recommended Query Patterns

### Pattern 1: Browse products with descriptions
```
expand="_ProductDescription", top=20
```

### Pattern 2: Search by Product ID prefix + get descriptions
```
filter_expression="startswith(Product,'APJ')", expand="_ProductDescription", top=30
```

### Pattern 3: Get specific product with full details
```
filter_expression="Product eq 'APJ123'", expand="_ProductDescription"
```

### Pattern 4: Filter by product type + get descriptions
```
filter_expression="ProductType eq 'FERT'", expand="_ProductDescription", top=30
```

## Response Structure

### Product fields:
- **Product**: Technical ID (e.g., "APJPIL202411100725")
- **ProductType**: FERT (finished), ROH (raw), HALB (semi-finished)
- **ProductGroup**: Category code
- **BaseUnit**: EA, ST, KG, TO, etc.

### _ProductDescription (array of translations):
```json
"_ProductDescription": [
  {"Language": "EN", "ProductDescription": "Greenies Cat Grill Tuna Flavor 130g"},
  {"Language": "DE", "ProductDescription": "Greenies Katzen Grill Thunfisch 130g"},
  {"Language": "JA", "ProductDescription": "グリニーズ 猫用 グリルまぐろ味 130g"}
]
```

## Product Types
- **FERT**: Finished Product
- **HALB**: Semi-Finished Product
- **ROH**: Raw Material
- **HAWA**: Trading Goods
- **DIEN**: Service

## Important Notes
1. To search by name/text, query the `ProductDescription` entity.
2. When querying `Product`, use `$expand=_ProductDescription` to show readable names.
3. Product IDs are often uppercase technical codes, NOT readable names.
4. Use `$top` to limit results (recommended: 20-50).
"""

# Structured data for common product types
PRODUCT_TYPES = {
    "FERT": "Finished Product",
    "HALB": "Semi-Finished Product", 
    "ROH": "Raw Material",
    "HIBE": "Operating Supplies",
    "NLAG": "Non-Stock Material",
    "DIEN": "Service",
    "UNBW": "Non-Valuated Material",
    "VERP": "Packaging Material",
    "HAWA": "Trading Goods",
}

# Common fields to select for a concise response
RECOMMENDED_SELECT_FIELDS = [
    "Product",
    "ProductType", 
    "ProductGroup",
    "BaseUnit",
    "GrossWeight",
    "NetWeight",
    "WeightUnit",
    "CreationDate",
    "LastChangeDate",
    "Division",
    "IndustrySector",
]