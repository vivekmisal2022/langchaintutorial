import streamlit as st 
import pandas as pd 
from pandasai import SmartDataframe 
import json
import os
import time
from typing import Callable
import platform
from hdbcli import dbapi
from fileinput import filename
import csv
import platform
from datetime import datetime
from datetime import date
from authlib.integrations.requests_client import OAuth2Session
import msal
import requests
from requests.auth import HTTPBasicAuth
import configparser
import time




from gen_ai_hub.proxy import get_proxy_client
from ai_core_sdk.ai_core_v2_client import AICoreV2Client
from ai_api_client_sdk.models.status import Status
from gen_ai_hub.orchestration.service import OrchestrationService
#from gen_ai_hub.orchestration.models.llm import LLM
from gen_ai_hub.orchestration.models.message import SystemMessage, UserMessage
from gen_ai_hub.orchestration.models.template import Template, TemplateValue
from gen_ai_hub.orchestration.models.config import OrchestrationConfig
from gen_ai_hub.orchestration.models.data_masking import DataMasking
from gen_ai_hub.orchestration.models.sap_data_privacy_integration import (
    SAPDataPrivacyIntegration, MaskingMethod, ProfileEntity )
from gen_ai_hub.proxy.langchain.init_models import init_llm

redirect_uri = "http://localhost:8502"
vaddress="" 
port=443
vuser=""
vpassword=""
vclient_id=""
vauthority=""
vclient_secret=""

# STEP 1: Load AI Core credentials
def load_ai_core_credentials():
    with open('./azure-evm-config.json', 'r') as f:
        svcKey = json.load(f)

    os.environ["AICORE_AUTH_URL"] = svcKey["AICORE_AUTH_URL"]
    os.environ["AICORE_CLIENT_ID"] = svcKey["AICORE_CLIENT_ID"]
    os.environ["AICORE_CLIENT_SECRET"] = svcKey["AICORE_CLIENT_SECRET"]
    os.environ["AICORE_RESOURCE_GROUP"] = "default"
    os.environ["AICORE_BASE_URL"] = svcKey["AICORE_BASE_URL"]
    os.environ["HANA_ADDRESS"] = svcKey["HANA_HOST"]
    os.environ["HANA_USER"] = svcKey["HANA_USER"]
    os.environ["HANA_PASSWORD"] = svcKey["HANA_PASSWORD_VDB"]
    os.environ["client_id"] = svcKey["AUTH_CLIENT_ID"]
    os.environ["client_secret"] = svcKey["AUTH_CLIENT_SECRET"]
    os.environ["tenant_id"] = svcKey["AUTH_TENANT_ID"]
    os.environ["ENTRAID_BASE_URL"] = svcKey["ENTRAID_BASE_URL"]
    
    authority = f"{os.environ['ENTRAID_BASE_URL']}/{os.environ['tenant_id']}"
    scope = ["User.ReadBasic.All"]
    vaddress=svcKey["HANA_HOST"]
    vuser=svcKey["HANA_USER"]
    vpassword=svcKey["HANA_PASSWORD_VDB"]
    vclient_id=svcKey["AUTH_CLIENT_ID"]
    vclient_secret=svcKey["AUTH_CLIENT_SECRET"]
    vauthority=authority

    return vuser,vpassword,vaddress,vclient_id,vclient_secret,vauthority



def authenticate_user():
    # Replace these with your actual values
    print("Authenticating user...")
    st.title("MS Entra Login")

    print("Authenticating user...")
    scope = ["User.ReadBasic.All"]  
    print(vclient_id,vauthority,vclient_secret)
   
    # Create a confidential client app
    app = msal.ConfidentialClientApplication(
            client_id=vclient_id,
            authority=vauthority,
            client_credential=vclient_secret
    )

    params = st.query_params
    if "code" not in params:
        authorize_url = app.get_authorization_request_url(scopes=scope, redirect_uri=redirect_uri)
        st.markdown(f"[Click here to login]({authorize_url})")
        time.sleep(99999)
    else:
        code = params["code"]
        print("Authorization code received:", code)
        result = app.acquire_token_by_authorization_code(code, scopes=scope, redirect_uri=redirect_uri)
        if "access_token" in result:
            st.success("Login successful!")
            #st.write("Access token:", result["access_token"])
            display_login(result["access_token"])
        else:
            st.error("Login failed: " + result.get("error_description", "Unknown error"))

 

def display_login(access_token):

    headers = {
    'Authorization': f'Bearer {access_token}'}
    resp = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)

    if resp.status_code != 200:
            st.error("Failed to fetch user profile")
            st.write("Response:", resp.text)
            return
        
    profile = resp.json()

    st.write("Welcome!",profile.get("displayName","User"))
    st.write("Authenticated Email:", profile.get("mail", "Email not available"))
   

def chat_with_evm(df,query):
    llm = init_llm('gpt-4o-mini' , max_tokens=4096, temperature=0.0)
    pandas_ai = SmartDataframe(df, config={"llm": llm})
    result = pandas_ai.chat(query)
    return result

st.set_page_config(layout='wide')

st.header("EVM Analytics")

vuser, vpassword, vaddress, vclient_id, vclient_secret, vauthority = load_ai_core_credentials()
print("Loaded HANA Credentials")
print(vuser, vpassword, vaddress, vclient_id, vclient_secret, vauthority)


if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    authenticate_user()

con = dbapi.connect(
address=vaddress,
port=443,
user=vuser,
password=vpassword)
cur=con.cursor()
sql_query = "SELECT * FROM evm.evmdata"
df = pd.read_sql(sql_query, con)
con.close()

st.info("Ready to Interact with the EVMBot")
st.dataframe(df.head(2),use_container_width=True)

option = st.selectbox(
    '[1]Hints for your Query ...',
    ('show top 10 vulnerabilities ?',
     'show me all vulnerabilities owned by asset_owner Amudha?',
     'show me  vulnerabilities with the Patch_Age  greater than 2000  ?',
     'show me  vulnerabilities on java or openjdk  ?',
     'show me  vulnerabilities with the SAP_RATING high  ?',
     'draw Barchart for  vulnerabilities asset_owner as Satish Kandi  and distinct category?',
     'show me  vulnerabilities on java or openjdk  and application_name splunk?',
     'show me  vulnerabilities with the Risk_SLA_Age  greater than 1000  ?',
     'show me distinct asset_owners?',
     'show me  vulnerabilities asset_owner as Satish Kandi ?',
     'draw a piechart with status and count ?',
     'How SLA is calculated for a particular severity?',
     'Suggest vulnerability management policy?',
     'How many vulnerabilities are out of Ops SLA for <Application> ?',
     'How many are out of Risk SLA?',
     'How many vulnerabilities are due less than 30 days for  all applications?',
     'How many vulnerabilities are due greater than 30 days for all applications?',
     'What are top 10 high severity vulnerabilities?',
     'show me all the applications ?'), help="Select a Query from this Dropdown list , hint to autofill the query box", label_visibility="visible")


st.info("Ask the EVMBot Below with your Query")
if option:
    input_text = st.text_area("[2]Enter the query", option)
else:
    input_text = st.text_area("Enter the query")

#Perform analysis
if input_text:
    if st.button("[3]Ask the EVMBot"):
        st.info("Your Query: "+ input_text)
        result = chat_with_evm(df,input_text)
        #st.success(result)
        if result is not None and isinstance(result, pd.DataFrame):
            st.dataframe(result, use_container_width=True)
        else:
            st.success(result)


