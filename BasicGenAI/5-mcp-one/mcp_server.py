"""
MCP Server with Calculator and S/4HANA Product API Tools - Complete Solution

This server exposes tools via the Model Context Protocol:

Calculator Tools:
- add: Add two numbers
- multiply: Multiply two numbers
- subtract: Subtract two numbers
- divide: Divide two numbers

S/4HANA Product API Tools:
- get_product_api_documentation: Get API documentation for querying products
- query_products: Query S/4HANA Product Master API with OData parameters
- search_product_descriptions: Search products by description text
- product_api: Universal OData V4 gateway for Product Master
- stock_api: Universal OData V2 gateway for Material Stock

Memory Tools:
- memory_load: Read the agent's memory file
- memory_save: Append a note to the agent's memory file
- memory_delete: Delete a specific entry from memory

Run with:
    uv run python mcp_server.py
"""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load environment variables from parent directory
#load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# S/4HANA configuration
S4HANA_USER = os.getenv("S4HANA_USER", "")
S4HANA_PASSWORD = os.getenv("S4HANA_PASSWORD", "")
S4PRODUCT_ENDPOINT = os.getenv("S4PRODUCT_MASTER_ENDPOINT", "")
S4STOCK_ENDPOINT = os.getenv("S4MATERIAL_STOCK_ENDPOINT", "")

# Memory file lives next to this script
MEMORY_FILE = Path(__file__).resolve().parent / "agent_memory.md"

# Create an MCP server with a descriptive name
mcp = FastMCP("Calculator and S4HANA Server")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        The sum of a and b
    """
    return a + b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        The product of a and b
    """
    return a * b


@mcp.tool()
def subtract(a: int, b: int) -> int:
    """Subtract the second number from the first.
    
    Args:
        a: First number (minuend)
        b: Second number (subtrahend)
        
    Returns:
        The difference (a - b)
    """
    return a - b


@mcp.tool()
def divide(a: int, b: int) -> float:
    """Divide the first number by the second.
    
    Args:
        a: Dividend (number to be divided)
        b: Divisor (number to divide by)
        
    Returns:
        The quotient (a / b)
        
    Raises:
        ValueError: If b is zero (division by zero)
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


# =============================================================================
# S/4HANA Product API Tools
# =============================================================================

@mcp.tool()
def search_product_descriptions(
    search_text: str,
    language: str = "EN",
    top: int = 20,
) -> dict:
    """Search for products by their description text in a specific language.
    
    This is the BEST way to find products by name/text (e.g., "cat food", "battery").
    It searches the ProductDescription entity directly, which is much faster than
    fetching all products and scanning.
    
    Args:
        search_text: Text to search for in product descriptions.
            Examples: "cat", "food", "battery", "LED"
        language: Language code for the description. Default "EN" for English.
            Common codes: EN (English), DE (German), JA (Japanese), 
            FR (French), ES (Spanish), ZH (Chinese), KO (Korean)
        top: Maximum number of results (default: 20)
    
    Returns:
        Dictionary with products matching the search text in their description.
        Each result includes Product ID, Language, and ProductDescription.
    """
    if not S4PRODUCT_ENDPOINT:
        return {
            "success": False,
            "error": "S4PRODUCT_MASTER_ENDPOINT not configured in .env",
            "data": [],
            "count": 0,
        }
    
    if not S4HANA_USER or not S4HANA_PASSWORD:
        return {
            "success": False,
            "error": "S4HANA_USER or S4HANA_PASSWORD not configured in .env",
            "data": [],
            "count": 0,
        }
    
    # Query the ProductDescription entity directly
    url = f"{S4PRODUCT_ENDPOINT.rstrip('/')}/ProductDescription"
    
    # Build filter: search text in description AND specific language.
    # NOTE: Backend does not support tolower(), so we rely on its collation for case handling.
    # Escape single quotes in search text for OData
    safe_search = search_text.replace("'", "''")
    filter_expr = f"contains(ProductDescription,'{safe_search}') and Language eq '{language.upper()}'"
    
    params = {
        "$filter": filter_expr,
        "$select": "Product,Language,ProductDescription",
        "$top": str(top),
        "$count": "true",
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                url,
                params=params,
                auth=(S4HANA_USER, S4HANA_PASSWORD),
                headers={"Accept": "application/json"},
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("value", [])
                total_count = data.get("@odata.count", len(results))
                
                return {
                    "success": True,
                    "data": results,
                    "count": len(results),
                    "total_available": total_count,
                    "search_info": {
                        "search_text": search_text,
                        "language": language.upper(),
                    },
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}: {response.text[:500]}",
                    "data": [],
                    "count": 0,
                }
                
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out.",
            "data": [],
            "count": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Request failed: {str(e)}",
            "data": [],
            "count": 0,
        }


@mcp.tool()
def get_product_api_documentation() -> str:
    """Get documentation for the S/4HANA Product Master API.
    
    Call this tool FIRST to understand how to query products from S/4HANA.
    The documentation explains:
    - Available OData query parameters ($filter, $select, $top, etc.)
    - How to search for products using contains(), startswith(), eq
    - Common fields and their meanings
    - Example queries
    
    Returns:
        Comprehensive API documentation as a string
    """
    from s4hana_product_api_docs import PRODUCT_API_DOCUMENTATION
    return PRODUCT_API_DOCUMENTATION


@mcp.tool()
def query_products(
    filter_expression: str = "",
    select_fields: str = "",
    top: int = 10,
    skip: int = 0,
    orderby: str = "",
    expand: str = "",
) -> dict:
    """Query the S/4HANA Product Master API with flexible OData parameters.
    
    CRITICAL: The 'Product' field is just a technical ID (like 'APJ123'), NOT the readable name!
    To get human-readable product names, you MUST use expand="_ProductDescription".
    
    Args:
        filter_expression: OData $filter - works on Product entity fields ONLY.
            - "startswith(Product,'APJ')" - Products with ID starting with 'APJ'
            - "ProductType eq 'FERT'" - Only finished products
            - NOTE: Cannot filter on _ProductDescription! Fetch and scan instead.
        select_fields: Comma-separated fields. Example: "Product,ProductType,BaseUnit"
        top: Max results (default: 10). Use 20-50 when searching by description.
        skip: Skip N results for pagination (default: 0)
        orderby: Sort field. Example: "Product asc" or "CreationDate desc"
        expand: IMPORTANT! Use "_ProductDescription" to get readable product names.
            Without this, you only get technical IDs, not product names!
    
    Returns:
        Dictionary with 'success', 'data' (products), 'count', 'error'.
        When expand="_ProductDescription", each product has _ProductDescription array
        with Language and ProductDescription (the actual readable name).
    
    Example for searching products by name (e.g., "cat food"):
        expand="_ProductDescription", top=30
        Then scan _ProductDescription[].ProductDescription for "cat"
    """
    if not S4PRODUCT_ENDPOINT:
        return {
            "success": False,
            "error": "S4PRODUCT_MASTER_ENDPOINT not configured in .env",
            "data": [],
            "count": 0,
        }
    
    if not S4HANA_USER or not S4HANA_PASSWORD:
        return {
            "success": False, 
            "error": "S4HANA_USER or S4HANA_PASSWORD not configured in .env",
            "data": [],
            "count": 0,
        }
    
    # Build the query URL
    url = f"{S4PRODUCT_ENDPOINT.rstrip('/')}/Product"
    
    # Build query parameters
    params = {}
    if filter_expression:
        params["$filter"] = filter_expression
    if select_fields:
        params["$select"] = select_fields
    if top:
        params["$top"] = str(top)
    if skip:
        params["$skip"] = str(skip)
    if orderby:
        params["$orderby"] = orderby
    if expand:
        params["$expand"] = expand
    
    # Always request count
    params["$count"] = "true"
    
    try:
        # Make the API request with Basic Auth
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                url,
                params=params,
                auth=(S4HANA_USER, S4HANA_PASSWORD),
                headers={"Accept": "application/json"},
            )
            
            if response.status_code == 200:
                data = response.json()
                products = data.get("value", [])
                total_count = data.get("@odata.count", len(products))
                
                return {
                    "success": True,
                    "data": products,
                    "count": len(products),
                    "total_available": total_count,
                    "query_used": {
                        "filter": filter_expression or "(none)",
                        "select": select_fields or "(all fields)",
                        "top": top,
                        "skip": skip,
                    },
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}: {response.text[:500]}",
                    "data": [],
                    "count": 0,
                }
                
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out. Try reducing $top or simplifying the filter.",
            "data": [],
            "count": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Request failed: {str(e)}",
            "data": [],
            "count": 0,
        }


# =============================================================================
# Universal S/4HANA Product API Tool
# =============================================================================

@mcp.tool()
def product_api(path: str = "", accept: str = "application/json") -> dict:
    """Execute any OData V4 request against the S/4HANA Product Master API.

    This is a thin, universal HTTP gateway. You provide the URL path and query
    string that comes AFTER the service root — authentication and the base URL
    are handled automatically.

    If you are unsure which entities, fields, or query options exist, call
    get_product_api_documentation() first, or fetch the OData metadata by
    calling this tool with path="$metadata" (and accept="application/xml").

    Args:
        path: Everything after the service root URL.
            This is appended directly to the base endpoint, so it can include
            entity sets, keys, navigation, and query-string parameters — any
            valid OData V4 URL suffix.

            Examples:
              ""                        → service root document
              "$metadata"               → full EDMX schema (use accept="application/xml")
              "Product?$top=5&$expand=_ProductDescription"
              "Product('TG-17')"
              "Product('TG-17')/_ProductDescription"
              "ProductDescription?$filter=contains(ProductDescription,'cat') and Language eq 'EN'&$top=20"
              "ProductPlant?$filter=Product eq 'TG-17'&$select=Product,Plant"
              "Product?$filter=ProductType eq 'FERT'&$top=10&$count=true&$orderby=Product asc"

        accept: HTTP Accept header value.
            Use "application/json" (default) for data queries.
            Use "application/xml" when fetching $metadata.

    Returns:
        dict with keys:
          success (bool)  – True when the HTTP request returned status 200.
          data            – Parsed JSON (list or object), or raw text for XML.
          count (int)     – Number of items when data is a list.
          total_available – Value of @odata.count if present.
          request_url     – The full URL that was called (for debugging).
          error (str|None)– Error message on failure, else None.
    """
    if not S4PRODUCT_ENDPOINT:
        return {
            "success": False,
            "error": "S4PRODUCT_MASTER_ENDPOINT not configured in .env",
            "data": [],
            "count": 0,
        }
    if not S4HANA_USER or not S4HANA_PASSWORD:
        return {
            "success": False,
            "error": "S4HANA_USER or S4HANA_PASSWORD not configured in .env",
            "data": [],
            "count": 0,
        }

    base = S4PRODUCT_ENDPOINT.rstrip("/")
    separator = "/" if path and not path.startswith("$") else "/"
    url = f"{base}{separator}{path}" if path else base

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                url,
                auth=(S4HANA_USER, S4HANA_PASSWORD),
                headers={"Accept": accept},
            )

        request_url = str(response.request.url)

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:500]}",
                "data": [],
                "count": 0,
                "request_url": request_url,
            }

        # Non-JSON responses (e.g. $metadata XML)
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            return {
                "success": True,
                "data": response.text,
                "count": 1,
                "total_available": 1,
                "request_url": request_url,
                "error": None,
            }

        # JSON response
        data = response.json()

        # Collection response (has "value" array)
        if "value" in data and isinstance(data["value"], list):
            results = data["value"]
            return {
                "success": True,
                "data": results,
                "count": len(results),
                "total_available": data.get("@odata.count", len(results)),
                "request_url": request_url,
                "error": None,
            }

        # Single-entity response
        return {
            "success": True,
            "data": data,
            "count": 1,
            "total_available": 1,
            "request_url": request_url,
            "error": None,
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out.",
            "data": [],
            "count": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Request failed: {e}",
            "data": [],
            "count": 0,
        }


# =============================================================================
# S/4HANA Material Stock API Tool
# =============================================================================

@mcp.tool()
def stock_api(path: str = "", accept: str = "application/json") -> dict:
    """Execute any request against the S/4HANA Material Stock API (OData V2).

    This is a thin HTTP gateway — just like product_api but for material stock.
    You provide the URL path and query string; authentication and the base URL
    are handled automatically.

    NOTE: This is an OData **V2** service. Key differences from V4:
    - Collections are wrapped in {"d": {"results": [...]}} not {"value": [...]}
    - Single entities are wrapped in {"d": {...}}
    - Use $format=json or Accept: application/json for JSON responses
    This tool normalises the response so you always get a flat "data" list.

    If you are unsure which entities or fields exist, fetch the metadata first:
      path="$metadata", accept="application/xml"

    Args:
        path: Everything after the service root URL.

            Examples:
              "$metadata"                → full schema (use accept="application/xml")
              "A_MaterialStock?$top=5"   → material headers
              "A_MaterialStock('TG11')?$expand=to_MatlStkInAcctMod"
                                         → single material with stock detail
              "A_MatlStkInAcctMod?$filter=Material eq 'TG11'&$top=20"
                                         → stock by plant/location/batch
              "A_MatlStkInAcctMod?$filter=Plant eq '1710'&$select=Material,Plant,StorageLocation,MatlWrhsStkQtyInMatlBaseUnit,MaterialBaseUnit&$top=50"
              "A_MaterialSerialNumber?$filter=Material eq 'TG11'&$top=10"

        accept: HTTP Accept header.
            "application/json" (default) for data queries.
            "application/xml" for $metadata.

    Returns:
        dict with keys: success, data, count, request_url, error.
    """
    if not S4STOCK_ENDPOINT:
        return {
            "success": False,
            "error": "S4MATERIAL_STOCK_ENDPOINT not configured in .env",
            "data": [],
            "count": 0,
        }
    if not S4HANA_USER or not S4HANA_PASSWORD:
        return {
            "success": False,
            "error": "S4HANA_USER or S4HANA_PASSWORD not configured in .env",
            "data": [],
            "count": 0,
        }

    base = S4STOCK_ENDPOINT.rstrip("/")
    url = f"{base}/{path}" if path else base

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                url,
                auth=(S4HANA_USER, S4HANA_PASSWORD),
                headers={"Accept": accept},
            )

        request_url = str(response.request.url)

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:500]}",
                "data": [],
                "count": 0,
                "request_url": request_url,
            }

        # Non-JSON responses (e.g. $metadata XML)
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            return {
                "success": True,
                "data": response.text,
                "count": 1,
                "request_url": request_url,
                "error": None,
            }

        # JSON response — normalise OData V2 envelope
        data = response.json()

        # OData V2 collection: {"d": {"results": [...]}}
        if "d" in data:
            inner = data["d"]
            if isinstance(inner, dict) and "results" in inner:
                results = inner["results"]
                return {
                    "success": True,
                    "data": results,
                    "count": len(results),
                    "request_url": request_url,
                    "error": None,
                }
            # OData V2 single entity: {"d": {...}}
            return {
                "success": True,
                "data": [inner],
                "count": 1,
                "request_url": request_url,
                "error": None,
            }

        # Fallback for unexpected shapes
        return {
            "success": True,
            "data": data,
            "count": 1,
            "request_url": request_url,
            "error": None,
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out.",
            "data": [],
            "count": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Request failed: {e}",
            "data": [],
            "count": 0,
        }


# =============================================================================
# Memory Tools — numbered entries for easy reference and deletion
# =============================================================================

def _load_entries() -> list[str]:
    """Read memory file and return list of entry texts (without the number prefix)."""
    if not MEMORY_FILE.exists():
        return []
    entries = []
    for line in MEMORY_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip leading "N. " prefix if present
        parts = line.split(". ", 1)
        if len(parts) == 2 and parts[0].isdigit():
            entries.append(parts[1])
        else:
            entries.append(line)
    return entries


def _save_entries(entries: list[str]) -> None:
    """Write entries back to the memory file with numbered lines."""
    lines = [f"{i}. {text}" for i, text in enumerate(entries, start=1)]
    MEMORY_FILE.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


@mcp.tool()
def memory_load() -> str:
    """Load the agent's memory file.

    Returns numbered entries from agent_memory.md.  Call this at the start of
    every conversation to recall what you know from previous sessions.

    Returns:
        Numbered memory entries, or a message if empty.
        Example:
          1. User's name is Gunter.
          2. Sales text is in ProductSalesDeliveryText entity.
    """
    entries = _load_entries()
    if not entries:
        return "(memory is empty)"
    return "\n".join(f"{i}. {text}" for i, text in enumerate(entries, start=1))


@mcp.tool()
def memory_save(note: str) -> str:
    """Append a note to the agent's memory.

    Use this after you discover something useful. Keep notes short and factual.

    Args:
        note: A short piece of information to remember.
            Example: "Sales text is in ProductSalesDelivery entity, field ProductSalesText"

    Returns:
        Confirmation with the assigned entry number.
    """
    entries = _load_entries()
    entries.append(note)
    _save_entries(entries)
    return f"Saved as entry {len(entries)}: {note}"


@mcp.tool()
def memory_delete(entry_id: int) -> str:
    """Delete a memory entry by its number.

    Args:
        entry_id: The entry number to delete (as shown by memory_load).
            Example: 2 — deletes the second entry.

    Returns:
        Confirmation of what was deleted, or an error if the ID is invalid.
    """
    entries = _load_entries()
    if not entries:
        return "Memory is empty — nothing to delete."
    if entry_id < 1 or entry_id > len(entries):
        return f"Invalid entry ID {entry_id}. Valid range: 1–{len(entries)}."

    removed = entries.pop(entry_id - 1)
    _save_entries(entries)
    return f"Deleted entry {entry_id}: {removed}"


if __name__ == "__main__":
    # Run with stdio transport for local communication
    # This is the standard way to run MCP servers that will be called by agents
    mcp.run(transport="stdio")