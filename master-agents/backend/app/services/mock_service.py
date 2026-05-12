"""Mock service for testing without LLM integration."""
import asyncio
from typing import AsyncGenerator
from app.models.schemas import TableColumn, TableData


async def generate_mock_response(message: str) -> AsyncGenerator[dict, None]:
    """
    Generate mock streaming response based on keywords in the message.
    
    Yields SSE events as dictionaries with 'event' and 'data' keys.
    """
    message_lower = message.lower()
    
    # Check for table-triggering keywords
    if any(keyword in message_lower for keyword in ["excel", "product", "inventory"]):
        # Stream text first
        text_chunks = [
            "Here's the product inventory data you requested:\n\n"
        ]
        for chunk in text_chunks:
            yield {"event": "text", "data": chunk}
            await asyncio.sleep(0.05)
        
        # Stream table data
        table_data = TableData(
            columns=[
                TableColumn(header="Product ID", accessor="productId"),
                TableColumn(header="Product Name", accessor="productName"),
                TableColumn(header="Category", accessor="category"),
                TableColumn(header="Stock", accessor="stock"),
                TableColumn(header="Price", accessor="price"),
            ],
            rows=[
                {
                    "productId": "P001",
                    "productName": "Laptop Pro 15",
                    "category": "Electronics",
                    "stock": 45,
                    "price": "$1,299.00"
                },
                {
                    "productId": "P002",
                    "productName": "Wireless Mouse",
                    "category": "Accessories",
                    "stock": 230,
                    "price": "$29.99"
                },
                {
                    "productId": "P003",
                    "productName": "USB-C Hub",
                    "category": "Accessories",
                    "stock": 120,
                    "price": "$49.99"
                },
                {
                    "productId": "P004",
                    "productName": "Monitor 27\"",
                    "category": "Electronics",
                    "stock": 18,
                    "price": "$399.00"
                },
                {
                    "productId": "P005",
                    "productName": "Keyboard Mechanical",
                    "category": "Accessories",
                    "stock": 67,
                    "price": "$89.99"
                },
            ]
        )
        
        yield {"event": "table", "data": table_data.model_dump()}
        await asyncio.sleep(0.1)
        
    elif any(keyword in message_lower for keyword in ["sales", "revenue", "financial"]):
        # Stream text first
        text_chunks = [
            "Here's the sales performance data:\n\n"
        ]
        for chunk in text_chunks:
            yield {"event": "text", "data": chunk}
            await asyncio.sleep(0.05)
        
        # Stream sales table
        table_data = TableData(
            columns=[
                TableColumn(header="Month", accessor="month"),
                TableColumn(header="Region", accessor="region"),
                TableColumn(header="Revenue", accessor="revenue"),
                TableColumn(header="Units Sold", accessor="units"),
                TableColumn(header="Growth %", accessor="growth"),
            ],
            rows=[
                {
                    "month": "January",
                    "region": "North America",
                    "revenue": "$2,450,000",
                    "units": 12500,
                    "growth": "+15.3%"
                },
                {
                    "month": "January",
                    "region": "Europe",
                    "revenue": "$1,890,000",
                    "units": 9800,
                    "growth": "+8.7%"
                },
                {
                    "month": "January",
                    "region": "Asia Pacific",
                    "revenue": "$3,120,000",
                    "units": 18200,
                    "growth": "+22.1%"
                },
                {
                    "month": "February",
                    "region": "North America",
                    "revenue": "$2,680,000",
                    "units": 13800,
                    "growth": "+9.4%"
                },
                {
                    "month": "February",
                    "region": "Europe",
                    "revenue": "$2,010,000",
                    "units": 10500,
                    "growth": "+6.3%"
                },
            ]
        )
        
        yield {"event": "table", "data": table_data.model_dump()}
        await asyncio.sleep(0.1)
        
    else:
        # Default text-only response
        responses = [
            "I'm a mock AI assistant. ",
            "I can help you with:\n",
            "- Product inventory (try asking about 'products' or 'excel')\n",
            "- Sales data (try asking about 'sales' or 'revenue')\n",
            "- Financial reports\n\n",
            "This is mock mode. Real LLM integration coming soon!"
        ]
        
        for chunk in responses:
            yield {"event": "text", "data": chunk}
            await asyncio.sleep(0.1)
    
    # Signal end of stream
    yield {"event": "end", "data": ""}
