"""Debug tool to inspect the Knowledge Graph contents."""
import os
from pathlib import Path

from dotenv import load_dotenv
from hdbcli import dbapi

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GRAPH_URI = os.getenv("KG_GRAPH_URI", "WORKSHOP_KG")


def get_connection() -> dbapi.Connection:
    return dbapi.connect(
        address=os.getenv("HANA_DB_ADDRESS"),
        port=int(os.getenv("HANA_DB_PORT", "443")),
        user=os.getenv("HANA_DB_USER"),
        password=os.getenv("HANA_DB_PASSWORD"),
        autocommit=True,
        sslValidateCertificate=False,
    )


def main() -> None:
    print(f"Querying graph <{GRAPH_URI}>...\n")
    connection = get_connection()
    cursor = connection.cursor()
    
    # Query all triples in the graph
    sparql = f"""
    SELECT ?s ?p ?o
    FROM <{GRAPH_URI}>
    WHERE {{ ?s ?p ?o }}
    ORDER BY ?s ?p
    """
    
    try:
        # Use SPARQL_TABLE for SELECT queries
        sql = f"SELECT * FROM SPARQL_TABLE('{sparql.replace(chr(39), chr(39)+chr(39))}')"
        cursor.execute(sql)
        results = cursor.fetchall()
        
        print(f"Found {len(results)} triples:\n")
        print("-" * 80)
        for row in results:
            s, p, o = row
            # Shorten URIs for readability
            s = s.replace("http://workshop.example.org/", ":")
            p = p.replace("http://workshop.example.org/", ":")
            p = p.replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:")
            p = p.replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:")
            o = str(o).replace("http://workshop.example.org/", ":")
            print(f"{s:30} {p:30} {o}")
        print("-" * 80)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()


if __name__ == "__main__":
    main()