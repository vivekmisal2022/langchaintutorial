#pip install --upgrade pip
#pip install -qU langchain-hana
#pip install pypdf
#pip install google-auth
#pip install google-api-core[async_rest]
#echo "Done"

#export HANA_GROUNDING_DOCS='/Users/d061192/LLMGroundingFun'
#ls -lat $HANA_GROUNDING_DOCS
import pandas as pd 
import json
import time
from typing import Callable
import platform
#from hdbcli import dbapi
from fileinput import filename
import csv
from datetime import datetime
from datetime import date
import os
from langchain_hana import HanaInternalEmbeddings, HanaDB , HanaRdfGraph , HanaSparqlQAChain
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFDirectoryLoader
from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter , RecursiveCharacterTextSplitter
from hdbcli import dbapi
from gen_ai_hub.proxy.langchain.init_models import init_embedding_model
from gen_ai_hub.proxy.langchain.init_models import init_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_classic.memory import ConversationBufferMemory
from langchain_classic.chains import create_retrieval_chain 
from langchain_classic.chains.conversational_retrieval.base import ConversationalRetrievalChain , BaseConversationalRetrievalChain
#from langchain_community.vectorstores.hanavector import HanaDB
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_community import graph_vectorstores, graphs
from langchain_community.graphs.index_creator import GraphIndexCreator
from langchain_classic.memory.prompt import KNOWLEDGE_TRIPLE_EXTRACTION_PROMPT
import os
import uuid
from langchain_classic.prompts import PromptTemplate
from IPython.display import SVG
import networkx as nx
import matplotlib.pyplot as plt

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


llm = init_llm('gpt-4o-mini', max_tokens=4096, temperature=0.0)

_DEFAULT_KNOWLEDGE_TRIPLE_EXTRACTION_TEMPLATE = """
{history}
{input}
Output:
"""

# 2. Create the Prompt Template
KNOWLEDGE_TRIPLE_EXTRACTION_PROMPT = PromptTemplate(
    input_variables=["history", "input"],
    template=_DEFAULT_KNOWLEDGE_TRIPLE_EXTRACTION_TEMPLATE,
)


result = llm.invoke("who is oscar winner in india ?")
#print(result.content)
pdfdocuments = PyPDFDirectoryLoader(vpdffiles).load()
print(pdfdocuments)
for i in range(3):
    print("")
doc_content=""
for docs in pdfdocuments:
    doc_content = doc_content + docs.page_content

index_creator = GraphIndexCreator(llm=llm )
graph = index_creator.from_text(text=doc_content)
triples = graph.get_triples()
for triple in triples:
    print(triple)




result = " ".join(str(item) for item in triples)
#print(result)

# chain = LLMChain(llm=llm, prompt=KNOWLEDGE_TRIPLE_EXTRACTION_PROMPT)

# text = "The Eiffel Tower is a famous landmark in Paris, France."
# result = graph.run(history="", input=doc_content)
# print(result)

# 2. Create a directed graph
G = nx.MultiDiGraph() # MultiDiGraph allows multiple edges between same nodes

# 3. Add edges from triples
for subj, pred, obj in triples:
    G.add_edge(subj, obj, label=pred)

# 4. Define layout and draw
pos = nx.spring_layout(G)
plt.figure(figsize=(12, 10))

# Draw nodes and edges
nx.draw(G, pos, with_labels=True, node_color='skyblue', node_size=2000, font_size=10, font_weight='bold')

# Draw edge labels (the predicates)
edge_labels = nx.get_edge_attributes(G, 'label')
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)

plt.title("Knowledge Graph from Extracted Triples")
#plt.show()
plt.savefig("/Users/I871395/Downloads/VKExplore/LangchainTutorial/my_plot.svg")






import os
from hdbcli import dbapi
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI

# 1. Initialize SAP GenAI Hub LLM
proxy_client = get_proxy_client('gen-ai-hub')
llm = ChatOpenAI(proxy_client=proxy_client, model_name="gpt-4o-mini")

# 2. Connect to SAP HANA Cloud (Knowledge Graph Engine)
conn = dbapi.connect(
    address='://ondemand.com',
    port=443,
    user='DB_USER',
    password='DB_PASSWORD',
    encrypt=True
)

def get_graph_context(query_entity):
    """Fetch related nodes/triples from HANA Triple Store using SPARQL"""
    cursor = conn.cursor()
    # Example SPARQL query executed via HANA's GRAPH_QUERY
    sparql = f"""
    SELECT ?subject ?predicate ?object 
    WHERE {{ ?subject ?predicate ?object . FILTER(?subject = ) }}
    """
    cursor.execute(f"CALL sys.execute_graph_query('{sparql}')")
    results = cursor.fetchall()
    return "\n".join([f"{s} {p} {o}" for s, p, o in results])

# 3. GraphRAG Execution
user_query = "What are the dependencies for Project X?"
graph_context = get_graph_context("Project_X")

response = llm.invoke(f"""
Answer based on the following Knowledge Graph context:
{graph_context}

User Query: {user_query}
""")

print(response.content)
