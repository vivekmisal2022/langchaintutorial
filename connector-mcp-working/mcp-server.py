"""Part 2: MCP Server with Stock and News Tools (Complete)

This server exposes tools for fetching stock data and searching market news.

Run with MCP Inspector:
    uv run mcp dev mcp_server.py

Run as stdio server (for agent client):
    uv run python mcp_server.py
"""

import os
import sys
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

import pandas as pd 
import json
import time
from typing import Callable
import platform
from fileinput import filename
import csv
from datetime import datetime
from datetime import date
# import os
# from langchain_hana import HanaInternalEmbeddings, HanaDB
# from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFDirectoryLoader
# from langchain_core.documents import Document
# from langchain_text_splitters import CharacterTextSplitter , RecursiveCharacterTextSplitter
# from hdbcli import dbapi
from gen_ai_hub.proxy.langchain.init_models import init_embedding_model
from gen_ai_hub.proxy.langchain.init_models import init_llm
# from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
# from langchain_core.prompts import prompt , PromptTemplate
# from langchain_classic.memory import ConversationBufferMemory
# from langchain_classic.chains import create_retrieval_chain
# from langchain_classic.chains.conversational_retrieval.base import ConversationalRetrievalChain , BaseConversationalRetrievalChain 
# #from langchain_community.vectorstores.hanavector import HanaDB
# from langchain_classic.chains.combine_documents import create_stuff_documents_chain
import os
import uuid

messages=""
vdbaddress="" 
port=443
vuser=""
vpassword=""
vpdffiles=""

# STEP 1: Load AI Core credentials
def load_ai_core_credentials():
    #with open('/Users/I871395/Downloads/VKExplore/AgenticAI/azure-evm-config.json', 'r') as f:
    with open('/Users/I871395/Downloads/VKExplore/LangchainTutorial/config.json', 'r') as f:
        svcKey = json.load(f)

    os.environ["AICORE_AUTH_URL"] = svcKey["AICORE_AUTH_URL"]
    os.environ["AICORE_CLIENT_ID"] = svcKey["AICORE_CLIENT_ID"]
    os.environ["AICORE_CLIENT_SECRET"] = svcKey["AICORE_CLIENT_SECRET"]
    os.environ["AICORE_RESOURCE_GROUP"] = "default"
    os.environ["AICORE_BASE_URL"] = svcKey["AICORE_BASE_URL"]
    os.environ["HANA_ADDRESS"] = svcKey["HANA_HOST"]
    os.environ["HANA_USER"] = svcKey["HANA_USER"]
    os.environ["HANA_PASSWORD"] = svcKey["HANA_PASSWORD_VDB"]
    os.environ["HANA_GROUNDING_DOCS"] = svcKey["HANA_GROUNDING_DOCS"]
    vdbaddress=svcKey["HANA_HOST"]
    vuser=svcKey["HANA_USER"]
    vpassword=svcKey["HANA_PASSWORD_VDB"]
    vpdffiles=svcKey["HANA_GROUNDING_DOCS"]


    return vuser,vpassword,vdbaddress,vpdffiles

vuser,vpassword,vdbaddress,vpdffiles = load_ai_core_credentials()


#llm = init_llm('gpt-4o-mini', max_tokens=4096, temperature=0.0)



# Add parent directory to path to import genai module
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
#from genai.perplexity_sonar import create_perplexity_client

# Load environment variables from the repo root .env file
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Create an MCP server
mcp = FastMCP("DealCrafter Tools")


@mcp.tool()
def get_stock_info(ticker: str) -> dict:
    """Get current stock information for a given ticker symbol.
    
    Args:
        ticker: Stock ticker symbol (e.g., "3382.T" for Seven & i Holdings,
                "3778.T" for Sakura Internet)
    
    Returns:
        Dictionary with stock information including price, currency, etc.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "ticker": ticker,
            "company_name": info.get("longName") or info.get("shortName"),
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "currency": info.get("currency", "JPY"),
            "change_percent": info.get("regularMarketChangePercent"),
            "previous_close": info.get("previousClose"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


@mcp.tool()
def search_market_news(query: str, limit: int = 5) -> str:
    """Search for recent market news about a topic using Perplexity AI.
    
    Args:
        query: Search query (e.g., "Seven & i Holdings takeover bid")
        limit: Maximum number of news items to return
    
    Returns:
        String containing news summaries with sources
    """
    try:
        # Create Perplexity client using the dedicated Sonar integration
        llm = init_llm('gpt-4o-mini', max_tokens=4096, temperature=0.0)
        # perplexity = create_perplexity_client(
        #     model=os.getenv("PERPLEXITY_MODEL", "perplexity--sonar-pro"),
        #     temperature=0.1,
        #     max_tokens=4000,
        #     deployment_id=os.getenv("PERPLEXITY_DEPLOYMENT_ID")
        # )
        
        prompt = f"""Search for the {limit} most recent news articles about: {query}

For each article, provide:
- Title
- Brief summary (2-3 sentences)
- Source and date if available

Focus on financial and business news. Be concise."""
        
        #response = perplexity.invoke(prompt)
        response = llm.invoke(prompt)
        return response
    except Exception as e:
        return f"Error searching news: {str(e)}"


@mcp.tool()
def get_stock_history(ticker: str, period: str = "1mo") -> dict:
    """Get historical stock data for a ticker.
    
    Args:
        ticker: Stock ticker symbol
        period: Time period - 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    
    Returns:
        Dictionary with historical price data summary
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist.empty:
            return {"error": "No historical data available", "ticker": ticker}
        
        return {
            "ticker": ticker,
            "period": period,
            "start_date": str(hist.index[0].date()),
            "end_date": str(hist.index[-1].date()),
            "start_price": round(hist["Close"].iloc[0], 2),
            "end_price": round(hist["Close"].iloc[-1], 2),
            "high": round(hist["High"].max(), 2),
            "low": round(hist["Low"].min(), 2),
            "avg_volume": int(hist["Volume"].mean()),
            "price_change_percent": round(
                ((hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0]) * 100, 2
            ),
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


if __name__ == "__main__":
    mcp.run(transport="stdio")