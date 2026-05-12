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
from fileinput import filename
import csv
from datetime import datetime
from datetime import date
import os
from langchain_hana import HanaInternalEmbeddings, HanaDB
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


llm = init_llm('gpt-4o-mini', max_tokens=4096, temperature=0.0)


connection = dbapi.connect(
    vdbaddress,
    port="443",
    user=vuser,
    password=vpassword,
    autocommit=True,
    sslValidateCertificate=False,
)

embeddings = init_embedding_model( 'text-embedding-ada-002' )

db = HanaDB(
    embedding=embeddings,
    connection=connection,
    #table_name="EMBEDDINGS_COLLECTION_DATA")
    table_name="EMBEDDINGS_COLLECTION_DATA5")

db.delete(filter={})

text_documents = PyPDFDirectoryLoader(vpdffiles).load()
text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
text_chunks = text_splitter.split_documents(text_documents)

#print(f"Number of document chunks: {len(text_chunks)}")
for chunk in text_chunks:
    #print(chunk.metadata)
    print(chunk.page_content)
 
db.add_documents(text_chunks)

cursor = connection.cursor()
sql = f'SELECT VEC_TEXT, TO_NVARCHAR(VEC_VECTOR) FROM "{db.table_name}"'
cursor.execute(sql)
vectors = cursor.fetchall()
#print(vectors)

#for vector in vectors:
#    print(vector)

retriever = db.as_retriever()
#print(retriever)

from langchain_core.prompts import ChatPromptTemplate
prompt = ChatPromptTemplate.from_template("""Provide answers based on context provided:

<context>
{context}
</context>

Question: {input}""")

#from langchain.chains import create_retrieval_chain
#from langchain.chains.combine_documents import create_stuff_documents_chain

document_chain = create_stuff_documents_chain(llm, prompt)
retrieval_chain = create_retrieval_chain(retriever, document_chain)

response = retrieval_chain.invoke({"input": "Who is husband of purvi?"})
print(response["answer"])
response = retrieval_chain.invoke({"input": "Who is father of purvi?"})
print(response["answer"])

response = retrieval_chain.invoke({"input": "Who is mother of shashank?"})
print(response["answer"])
response = retrieval_chain.invoke({"input": "What is name of purvi's sister?"})
print(response["answer"])
response = retrieval_chain.invoke({"input": "Who is Mother in Law of Shantanu?"})
print(response["answer"])
response = retrieval_chain.invoke({"input": "Who is Father in Law of Purvi?"})
print(response["answer"])
response = retrieval_chain.invoke({"input": "Who is GrandFather of Shantanu?"})
print(response["answer"])

sql = f'SELECT VEC_TEXT, TO_NVARCHAR(VEC_VECTOR) FROM "{db.table_name}"'
x = cursor.execute(sql)
print(x)
sql = f'DELETE FROM EMBEDDINGS_COLLECTION_DATA'
a=cursor.execute(sql)
print(a)
sql = f'DELETE FROM EMBEDDINGS_COLLECTION_DATA5'
b=cursor.execute(sql)
print(b)
sql = f'SELECT VEC_TEXT, TO_NVARCHAR(VEC_VECTOR) FROM "{db.table_name}"'
y = cursor.execute(sql)
print(y)
