"""
Chat with SAP HANA Knowledge Graph using natural language.

Uses a two-step approach:
1. LLM generates SPARQL from natural language question
2. Execute SPARQL and format results
3. LLM formulates natural language answer from cleaned results

Usage:
    uv run chat_kg.py [--verbose]
"""


						
import os
import re
import sys
import json
from pathlib import Path

from dotenv import load_dotenv
from hdbcli import dbapi
from gen_ai_hub.proxy.langchain.init_models import init_llm
from langchain_hana import HanaRdfGraph

# Load shared configuration from repo root .env
#load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "5000"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
GRAPH_URI = os.getenv("KG_GRAPH_URI", "WORKSHOP_KG")
BASE_URI = "http://workshop.example.org/"

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

llm = init_llm(MODEL, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)


# Prompt for generating SPARQL from natural language
SPARQL_GENERATION_PROMPT = """Given the following RDF schema, generate a SPARQL SELECT query to answer the user's question.

Schema (Turtle format):
{schema}

Rules:
- Use PREFIX ex: <http://workshop.example.org/>
- Always include FROM <{graph_uri}> clause
- Select human-readable labels (rdfs:label) when available
- Use CONTAINS() or REGEX() for partial string matching on labels, not exact equality
- When looking for "all products", use UNION to combine multiple product relationships (offers_product, develops, etc.)
- Return only the SPARQL query, no explanation

User question: {question}

SPARQL query:"""

# Prompt for formulating answer from query results
ANSWER_PROMPT = """Answer the user's question based on the data below.

Question: {question}

Data:
{data}

Instructions:
- Use the data provided to answer the question directly
- If the data contains names or values, include them in your answer
- Only say "I don't have that information" if the Data section shows "No results found"

Answer:"""


def get_connection() -> dbapi.Connection:
    """Create a connection to SAP HANA Cloud."""
    return dbapi.connect(
        # address=os.getenv("HANA_DB_ADDRESS"),
        # port=int(os.getenv("HANA_DB_PORT", "443")),
        # user=os.getenv("HANA_DB_USER"),
        # password=os.getenv("HANA_DB_PASSWORD"),
        # autocommit=True,
        # sslValidateCertificate=False,

        address=vvdbaddress,
        port=int("443"),
        user=vvuser,
        password=vvpassword,
        autocommit=True,
        sslValidateCertificate=False,



    )


def clean_uri(value: str) -> str:
    """Remove URI prefixes to get clean values for LLM."""
    if isinstance(value, str):
        # Remove our base URI
        value = value.replace(BASE_URI, "")
        # Remove common RDF prefixes
        value = re.sub(r"^http://[^/]+/", "", value)
    return value


def extract_sparql(response: str) -> str:
    """Extract SPARQL query from LLM response."""
    # Try to find SPARQL in code blocks
    match = re.search(r"```(?:sparql)?\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Otherwise return the whole response (might already be just SPARQL)
    return response.strip()


def execute_sparql_select(connection: dbapi.Connection, sparql: str) -> list[dict]:
    """Execute a SPARQL SELECT query and return results as list of dicts."""
    cursor = connection.cursor()
    try:
        # Escape single quotes for SQL
        escaped = sparql.replace("'", "''")
        #sql = f"SELECT * FROM SPARQL_TABLE('{escaped}')"
        sql = f"SELECT * FROM OPSFLOW_KG.KG_RELATIONSHIPS limit 5"
        cursor.execute(sql)
        
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        
        # Convert to list of dicts with cleaned values
        results = []
        for row in rows:
            cleaned_row = {}
            for col, val in zip(columns, row):
                cleaned_row[col] = clean_uri(str(val)) if val else ""
            results.append(cleaned_row)
        return results
    finally:
        cursor.close()


def format_results_for_llm(results: list[dict]) -> str:
    """Format query results as clean text for LLM."""
    if not results:
        return "No results found."
    
    lines = []
    for row in results:
        # Keep all values, URIs have already been cleaned
        values = [v for v in row.values() if v]
        if values:
            # Prefer the "Label" columns if present
            label_values = [v for k, v in row.items() if "label" in k.lower() and v]
            if label_values:
                lines.append(", ".join(label_values))
            else:
                lines.append(", ".join(values))
    
    # Deduplicate while preserving order
    seen = set()
    unique_lines = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)
    
    return "\n".join(unique_lines) if unique_lines else "No readable results found."


def main() -> None:
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    print(f"Connecting to HANA Knowledge Graph <{GRAPH_URI}>...")
    connection = get_connection()
    
    # Create the RDF graph instance with auto-extracted ontology
    # graph = HanaRdfGraph(
    #     connection=connection,
    #     graph_uri=GRAPH_URI,
    #     auto_extract_ontology=True,
    # )
    
    print(f"Initializing LLM ({MODEL})...")
    llm = init_llm(MODEL, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
    
    if verbose:
        print("\n[Verbose mode enabled - will show generated SPARQL queries]")
    
    print("\nKnowledge Graph Chat")
    print("=" * 40)
    print("Ask questions about the data in the knowledge graph.")
    print("Press Enter with empty input to exit.\n")
    
    # Get schema for SPARQL generation
    # schema_text = ""
    # try:
    #     schema = graph.get_schema
    #     if schema:
    #         schema_text = schema.serialize(format="turtle")
    #         print("Graph schema loaded. Ready to answer questions.")
    #         if verbose:
    #             print("\n[Schema (Turtle format)]:")
    #             print("-" * 40)
    #             print(schema_text)
    #             print("-" * 40)
    #         print()
    # except Exception as e:
    #     print(f"Warning: Could not load schema: {e}")
    #     print("The graph might be empty. Run ingest_kg.py first.\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if not user_input:
            print("Goodbye!")
            break
        
        try:
            # Step 1: Generate SPARQL from question
            # sparql_prompt = SPARQL_GENERATION_PROMPT.format(
            #     schema=schema_text,
            #     graph_uri=GRAPH_URI,
            #    question=user_input
            #)
            sparql_prompt = """ question=user_input """
            sparql_response = llm.invoke(sparql_prompt)
            sparql = extract_sparql(sparql_response.content)
            
            if verbose:
                print(f"\n[Generated SPARQL]:\n{sparql}\n")
            
            # Step 2: Execute SPARQL
            results = execute_sparql_select(connection, sparql)
            print(results)
            
            if verbose:
                print(f"[Query returned {len(results)} results]")
            
            # Step 3: Format results (clean URIs) and generate answer
            data_text = format_results_for_llm(results)
            
            if verbose:
                print(f"[Cleaned data for LLM]:\n{data_text}\n")
            
            answer_prompt = ANSWER_PROMPT.format(
                question=user_input,
                data=data_text
            )
            answer_response = llm.invoke(answer_prompt)
            
            print(f"Assistant: {answer_response.content}\n")
            
        except Exception as e:
            print(f"Error: {e}\n")
            if verbose:
                import traceback
                traceback.print_exc()
            print("Try rephrasing your question or check if data has been ingested.\n")


if __name__ == "__main__":
    main()