import os
import sys
from pathlib import Path
import json

from dotenv import load_dotenv
from hdbcli import dbapi
from langchain_core.documents import Document
from langchain_hana import HanaDB
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter
from gen_ai_hub.proxy.langchain.init_models import init_embedding_model

# Load shared configuration from repo root .env
#load_dotenv(Path(__file__).resolve().parents[1] / ".env")
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "5000"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
SYSTEM_PROMPT = os.getenv("LLM_SYSTEM_PROMPT", "You are a helpful assistant.")

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




def get_connection() -> dbapi.Connection:

    return dbapi.connect(


        # address=os.getenv("HANA_DB_ADDRESS"),
        # port=int(os.getenv("HANA_DB_PORT", "443")),
        # user=os.getenv("HANA_DB_USER"),
        # password=os.getenv("HANA_DB_PASSWORD"),
        # autocommit=True,
        # sslValidateCertificate=False,

        address=vdbaddress,
        port=int("443"),
        user=vuser,
        password=vpassword,
        autocommit=True,
        sslValidateCertificate=False,
    )


def main() -> None:
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        file_path = Path("sample.txt")

    if not file_path.exists():
        print(f"Input file not found: {file_path}")
        sys.exit(1)

    text = file_path.read_text(encoding="utf-8")

    chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    docs = splitter.split_documents(
        [Document(page_content=text, metadata={"source": str(file_path)})]
    )

    connection = get_connection()

    embedding_model = os.getenv("LLM_EMBEDDING_MODEL", "text-embedding-ada-002")
    table_name = os.getenv("HANA_TABLE_NAME", "WORKSHOP_DOCS")

    embeddings = init_embedding_model(embedding_model)

    db = HanaDB(embedding=embeddings, connection=connection, table_name=table_name)

    # Avoid duplicates: remove existing chunks for this source file, then insert
    db.delete(filter={"source": str(file_path)})
    db.add_documents(docs)

    print(f"Ingested {len(docs)} chunks from {file_path} into table '{table_name}'.")


if __name__ == "__main__":
    main()