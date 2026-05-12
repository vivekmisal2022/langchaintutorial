from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
#from langchain.chains import RetrievalQA
from langchain_hana import HanaInternalEmbeddings, HanaDB

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
from langchain_hana import HanaInternalEmbeddings, HanaDB
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFDirectoryLoader
from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter , RecursiveCharacterTextSplitter
from hdbcli import dbapi
from gen_ai_hub.proxy.langchain.init_models import init_embedding_model
from gen_ai_hub.proxy.langchain.init_models import init_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_classic.memory import ConversationBufferMemory
from langchain_classic.chains.conversational_retrieval.base import ConversationalRetrievalChain


messages=""
vdbaddress="" 
port=443
vuser=""
vpassword=""
vpdffiles=""

# STEP 1: Load AI Core credentials
def load_ai_core_credentials():
    with open('/Users/I871395/Downloads/VKExplore/AgenticAI/azure-evm-config.json', 'r') as f:
        svcKey = json.load(f)

    os.environ["AICORE_AUTH_URL"] = svcKey["AICORE_AUTH_URL"]
    os.environ["AICORE_CLIENT_ID"] = svcKey["AICORE_CLIENT_ID"]
    os.environ["AICORE_CLIENT_SECRET"] = svcKey["AICORE_CLIENT_SECRET"]
    os.environ["AICORE_RESOURCE_GROUP"] = "default"
    os.environ["AICORE_BASE_URL"] = svcKey["AICORE_BASE_URL"]
    os.environ["HANA_ADDRESS"] = svcKey["HANA_HOST"]
    os.environ["HANA_USER"] = svcKey["HANA_USER"]
    os.environ["HANA_PASSWORD"] = svcKey["HANA_PASSWORD_VDB"]
    #os.environ["HANA_GROUNDING_DOCS"] = svcKey["HANA_GROUNDING_DOCS"]
    vdbaddress=svcKey["HANA_HOST"]
    vuser=svcKey["HANA_USER"]
    vpassword=svcKey["HANA_PASSWORD_VDB"]
    #vpdffiles=svcKey["HANA_GROUNDING_DOCS"]

    return vuser,vpassword,vdbaddress

vuser,vpassword,vdbaddress = load_ai_core_credentials()

connection = dbapi.connect(
    vdbaddress,
    port="443",
    user=vuser,
    password=vpassword,
    autocommit=True,
    sslValidateCertificate=False,
)

sapllm = init_llm('gpt-4o-mini', max_tokens=4096, temperature=0.0)
response = sapllm.invoke("whos is president of US")
print(response.content)