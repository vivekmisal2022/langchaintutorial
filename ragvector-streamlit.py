import streamlit as st
from streamlit import session_state
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from gen_ai_hub.proxy.langchain.openai import OpenAIEmbeddings
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from langchain_community.vectorstores.hanavector import HanaDB
from gen_ai_hub.proxy.langchain.init_models import init_llm
from dotenv import load_dotenv
from hdbcli import dbapi
from langchain.memory import ConversationBufferMemory
from langchain.chains import conversational_retrieval
from langchain.chains import create_retrieval_chain
from langchain.chains.conversational_retrieval.base import ConversationalRetrievalChain
from langchain.chains.conversational_retrieval.base import ConversationalRetrievalChain
#from htmlTemplates import css, bot_template, user_template
import json

#from htmltemplates import css,bot_template,user_template
import os
import uuid






with open("/Users/I871395/Downloads/VKExplore/LangchainTutorial/config.json", "r") as key_file:
    #svcKey = json.load(key_file)
    svcKey = json.loads(key_file.read())

# env_vars = {       
#     "AICORE_AUTH_URL": svcKey["url"],
#     "AICORE_CLIENT_ID":svcKey["clientid"],
#     "AICORE_CLIENT_SECRET": svcKey["clientsecret"],
#     "AICORE_RESOURCE_GROUP": svcKey["identityzoneid"],
#     "AICORE_BASE_URL": svcKey["serviceurls"]["AI_API_URL"],
#     "HANA_USER": svcKey["hana_user_vdb"],
#     "HANA_PASSWORD_VDB": svcKey["hana_password_vdb"],
#     "HANA_HOST": svcKey["hana_host"],
# }
# #print(env_vars)
# os.environ.update(env_vars)

def load_ai_core_credentials():
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
HANA_VHOST = vdbaddress
HANA_USER_VVDB=vuser
HANA_PASSWORD_VVDB=vpassword
print(vuser,vdbaddress,vpassword,vpdffiles)



# for key,value in env_vars.items():
#     if key == "HANA_USER":
#         HANA_USER_VVDB = value
#     if key == "HANA_PASSWORD_VDB":
#         HANA_PASSWORD_VVDB = value
#     if key == "HANA_HOST":
#         HANA_VHOST = value


#vivek load_dotenv()
# Use connection settings from the environment
# connection = dbapi.connect(
#     address=os.environ.get("HANA_HOST_VECTOR"),
#     port=os.environ.get("HANA_PORT_VECTOR"),
#     user=os.environ.get("HANA_VECTOR_USER"),
#     password=os.environ.get("HANA_VECTOR_PASS"),
#     autocommit=True,
#     sslValidateCertificate=False,
# )


#vivek load_dotenv()
# Use connection settings from the environment
connection = dbapi.connect(
    address= HANA_VHOST,
    port= 443,
    user=HANA_USER_VVDB,
    password=HANA_PASSWORD_VVDB,
    autocommit=True,
    sslValidateCertificate=False,
)

def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text


def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter (
        chunk_size = 1000,
        chunk_overlap = 200,
        length_function = len )
    chunks = text_splitter.split_text(text)
    return chunks


class Document:
    def __init__(self, text, metadata=None):
        self.page_content = text
        self.metadata = metadata if metadata is not None else {}


def get_vectorstore(chunks,table_name):
    embeddings = OpenAIEmbeddings(proxy_model_name='text-embedding-ada-002', chunk_size=200)

    documents = [Document(chunk) for chunk in chunks] if chunks else None

    vectordb = HanaDB.from_documents(connection=connection, documents=documents, embedding=embeddings, table_name=table_name)
    return vectordb

def get_conversation_chain(vectordb):
    #vivek llm = init_llm('gpt-4o', max_tokens=4096)
        #     "temperature": 0.0,
        # "frequency_penalty": 0,
        # "presence_penalty": 0,
        # "stop": "null"

    llm = init_llm('gpt-4o' , max_tokens=4096, temperature=0.0)
    memory = ConversationBufferMemory(memory_key='chat_history',return_messages=True)
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm =llm,
        retriever = vectordb.as_retriever(),
        memory=memory
   )
    return conversation_chain

def handle_user_input(user_question):
    response = st.session_state.conversation({'question':user_question})
    st.session_state.chat_history = response['chat_history']
    for i, message in enumerate (st.session_state.chat_history):
        if i % 2 == 0:
            #st.write(user_template.replace("{{MSG}}",message.content), unsafe_allow_html=True)
            st.image("human.png",width=50)
            st.write(( message.content), unsafe_allow_html=True)
           
            
        else:
            ##st.write(bot_template.replace("{{MSG}}",message.content), unsafe_allow_html=True)
            st.image("robot1.png",width=50)
            st.write((message.content), unsafe_allow_html=True)


def button_click():
    st.session_state.button_clicked = True

###New Function start
    #with st.sidebar:
    #    st.subheader("Your documents")
    #    pdf_docs = st.file_uploader("Upload your PDF's here and click on 'Process'",accept_multiple_files=True)
def upload_docs():
        #arr = os.listdir("/Users/i871395/Downloads/OnBoarding/")
        arr = os.listdir("/Users/i871395/Downloads/VKExplore/LangchainTutorial/")
        pdf_docs = []
        for fl in arr:
            #pdf_docs.append(("/Users/i871395/Downloads/OnBoarding/"+fl))
            print(fl)
            pdf_docs.append(("/Users/i871395/Downloads/VKExplore/LangchainTutorial/"+fl))
        
        #pdf_docs = ["/Users/i871395/Downloads/Onboarding/Onboarding/ComplianceFormUpdates.pdf"]
        unique_id = str(uuid.uuid4())
        table_name = "Embeddings" + unique_id if pdf_docs else None

        vectordb = None

#new code
        # Initialize the session state for the button
        if 'button_clicked' not in st.session_state:
            st.session_state.button_clicked = False
        print("Before click")
        print(st.session_state)

        # Display a message or other content after the button is clicked
        #if st.session_state.button_clicked:
        #    st.write('Button has been clicked!')

        # Display the button if it hasn't been clicked yet
        if not st.session_state.button_clicked:
#            #if st.button('Click me'):

                st.button("Process Knowledge Base", key="processb", on_click=button_click())
                with st.spinner("Processing... Preparing Knowledge Base for SAP Community !!!"):
                    print('z')
                print("After click")
                print(st.session_state)
                raw_text = get_pdf_text(pdf_docs)
                text_chunks = get_text_chunks(raw_text)
                with st.empty():
                     print('x')
                #st.write(text_chunks)

                vectordb = get_vectorstore(text_chunks, table_name)
                    
                st.session_state.conversation = get_conversation_chain(vectordb)
            
                #button_click()
                    #st.session_state.conversation 



        #if vectordb and table_name and st.button("Delete Embeddings"):
        #    with st.spinner("Deleting"):
        #        vectordb.delete_embeddings(table_name=table_name) 



## new code




        # if st.button("Process Knowledge Base", key="processb"):
        #     st.spinner("Processing... Preparing Knowledge Base for SAP Community !!!")
        #     #st.button("Process Knowledge Base", key="processb", disabled=True)
        #     st.empty()







        
###New Function here








def main():
    st.session_state.button_clicked = False
    st.set_page_config(page_title="chat with multiple PDF", page_icon="‌‌")
    #st.image('Robot-Image.jpg', width=200 , caption='SAP Community Assistant' )
    if not st.session_state.button_clicked:
        upload_docs()
    
    #st.write(css,unsafe_allow_html=True)
    st.write(unsafe_allow_html=True)

    if "conversation" not in st.session_state:
        st.session_state.conversation = None

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = None

    all_params = st.query_params.get_all(key="params")
    
    q1 = ""
    q1 = str(st.query_params.get("asked_question"))
    

    st.header("SAP Community Assistant ‌‌")
    user_question = st.text_input("Hey User: Will Answer this question. You can ask more if you are not satisfied with the Answer:", value=q1)
    # st.write(user_question)
    # st.write(user_question.isalpha())
    if user_question:
        handle_user_input(user_question)
    

###vk start
    # with st.sidebar:
    #     st.subheader("Your documents")
    #     pdf_docs = st.file_uploader("Upload your PDF's here and click on 'Process'",accept_multiple_files=True)

    #     unique_id = str(uuid.uuid4())
    #     table_name = "Embeddings" + unique_id if pdf_docs else None

    #     vectordb = None

    #     if st.button("Process"):
    #         with st.spinner("Processing"):

    #             raw_text = get_pdf_text(pdf_docs)
    #             text_chunks = get_text_chunks(raw_text)
    #             #st.write(text_chunks)

    #             vectordb = get_vectorstore(text_chunks, table_name)
                
    #             st.session_state.conversation = get_conversation_chain(vectordb)
        
    #             #st.session_state.conversation 



    #     if vectordb and table_name and st.button("Delete Embeddings"):
    #         with st.spinner("Deleting"):
    #             vectordb.delete_embeddings(table_name=table_name) 

###vk here

    

if __name__ == '__main__':
    main()                                                