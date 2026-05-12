"""
Ingest text into SAP HANA Knowledge Graph.

Reads a text file, uses an LLM to extract entities and relationships,
then stores them as RDF triples in the HANA Knowledge Graph.

Usage:
    uv run ingest_kg.py <text_file>
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from hdbcli import dbapi
from gen_ai_hub.proxy.langchain.init_models import init_llm

# Load shared configuration from repo root .env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MODEL = os.getenv("LLM_MODEL", "gpt-4.1")
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "5000"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
GRAPH_URI = os.getenv("KG_GRAPH_URI", "WORKSHOP_KG")

# Prompt for extracting entities and relationships from text
EXTRACTION_PROMPT = """Extract ALL entities and relationships from the following text.

Output a JSON object with two arrays:

1. "entities": Each entity has:
   - "id": lowercase identifier with underscores (e.g., "maria_chen", "cloudsync")
   - "type": category (Person, Organization, Product, Location, etc.)
   - "name": the full name as it appears in the text

2. "relationships": Each relationship has:
   - "subject": entity id (must match an entity's id)
   - "predicate": relationship type in lowercase with underscores
   - "object": either another entity id OR a literal string value

IMPORTANT:
- Extract EVERY entity mentioned (people, companies, products, locations, etc.)
- Extract EVERY relationship (who founded what, who works where, what products exist, etc.)
- For organizations, include relationships like: founded_by, headquartered_in, offers_product, has_employee_count
- For products, include relationships like: developed_by, launched_in, has_feature
- For people, include relationships like: role_at, founded, works_at

Text to analyze:
---
{text}
---

Return ONLY valid JSON, no markdown formatting or explanation."""


def get_connection() -> dbapi.Connection:
    """Create a connection to SAP HANA Cloud."""
    return dbapi.connect(
        address=os.getenv("HANA_DB_ADDRESS"),
        port=int(os.getenv("HANA_DB_PORT", "443")),
        user=os.getenv("HANA_DB_USER"),
        password=os.getenv("HANA_DB_PASSWORD"),
        autocommit=True,
        sslValidateCertificate=False,
    )


def extract_knowledge(llm, text: str) -> dict:
    """Use LLM to extract entities and relationships from text."""
    prompt = EXTRACTION_PROMPT.format(text=text)
    response = llm.invoke(prompt)
    content = response.content.strip()
    
    # Handle potential markdown code blocks in response
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first and last lines (```json and ```)
        content = "\n".join(lines[1:-1])
    
    return json.loads(content)


def build_sparql_insert(knowledge: dict, graph_uri: str) -> str:
    """Convert extracted knowledge to SPARQL INSERT DATA statement."""
    triples = []
    base_uri = "http://workshop.example.org/"
    
    # Create entity triples
    for entity in knowledge.get("entities", []):
        entity_uri = f"<{base_uri}{entity['id']}>"
        entity_type = f"<{base_uri}{entity['type']}>"
        
        # Type triple
        triples.append(f"{entity_uri} a {entity_type} .")
        # Label triple
        escaped_name = entity["name"].replace('"', '\\"')
        triples.append(f'{entity_uri} <http://www.w3.org/2000/01/rdf-schema#label> "{escaped_name}" .')
    
    # Create relationship triples
    for rel in knowledge.get("relationships", []):
        subject_uri = f"<{base_uri}{rel['subject']}>"
        predicate_uri = f"<{base_uri}{rel['predicate']}>"
        
        # Check if object is an entity reference or a literal
        obj = rel["object"]
        if any(e["id"] == obj for e in knowledge.get("entities", [])):
            # Object is an entity reference
            object_value = f"<{base_uri}{obj}>"
        else:
            # Object is a literal value
            escaped_obj = str(obj).replace('"', '\\"')
            object_value = f'"{escaped_obj}"'
        
        triples.append(f"{subject_uri} {predicate_uri} {object_value} .")
    
    triples_str = "\n            ".join(triples)
    
    return f"""INSERT DATA {{
        GRAPH <{graph_uri}> {{
            {triples_str}
        }}
    }}"""


def execute_sparql(connection: dbapi.Connection, sparql: str) -> None:
    """Execute a SPARQL update statement via SPARQL_EXECUTE."""
    cursor = connection.cursor()
    try:
        cursor.callproc(
            "SYS.SPARQL_EXECUTE",
            (sparql, "Content-Type: application/sparql-update", "?", "?")
        )
        print("SPARQL update executed successfully.")
    except dbapi.Error as e:
        print(f"Error executing SPARQL: {e}")
        raise
    finally:
        cursor.close()


def clear_graph(connection: dbapi.Connection, graph_uri: str) -> None:
    """Clear all triples from the specified graph."""
    sparql = f"CLEAR GRAPH <{graph_uri}>"
    cursor = connection.cursor()
    try:
        cursor.callproc(
            "SYS.SPARQL_EXECUTE",
            (sparql, "Content-Type: application/sparql-update", "?", "?")
        )
        print(f"Cleared existing data from graph <{graph_uri}>.")
    except dbapi.Error as e:
        # Graph might not exist yet, which is fine
        print(f"Note: Could not clear graph (may not exist yet): {e}")
    finally:
        cursor.close()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run ingest_kg.py <text_file>")
        print("  Extracts entities and relationships from text and stores them in HANA Knowledge Graph.")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    print(f"Reading text from: {file_path}")
    text = file_path.read_text(encoding="utf-8")
    
    print(f"Initializing LLM ({MODEL})...")
    llm = init_llm(MODEL, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
    
    print("Extracting entities and relationships...")
    knowledge = extract_knowledge(llm, text)
    
    entity_count = len(knowledge.get("entities", []))
    rel_count = len(knowledge.get("relationships", []))
    print(f"Extracted {entity_count} entities and {rel_count} relationships.")
    
    # Show extracted knowledge
    print("\nEntities:")
    for e in knowledge.get("entities", []):
        print(f"  - {e['id']} ({e['type']}): {e['name']}")
    
    print("\nRelationships:")
    for r in knowledge.get("relationships", []):
        print(f"  - {r['subject']} --[{r['predicate']}]--> {r['object']}")
    
    print(f"\nConnecting to HANA and storing in graph <{GRAPH_URI}>...")
    connection = get_connection()
    
    # Clear existing data in the graph (optional, for clean re-ingestion)
    clear_graph(connection, GRAPH_URI)
    
    # Build and execute SPARQL INSERT
    sparql = build_sparql_insert(knowledge, GRAPH_URI)
    execute_sparql(connection, sparql)
    
    print(f"\nSuccessfully ingested knowledge graph from {file_path}")
    print(f"Graph URI: {GRAPH_URI}")


if __name__ == "__main__":
    main()