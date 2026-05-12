import os
from langchain_openai import ChatOpenAI
from langchain_classic.agents import create_react_agent , AgentExecutor
#from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import PromptTemplate

from langchain_core.tools import tool
import pandas as pd 
import json
import os
import time
from typing import Callable
import platform
#from hdbcli import dbapi
from fileinput import filename
import csv
from datetime import datetime
from datetime import date


from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


#from gen_ai_hub.proxy import get_proxy_client
#from ai_core_sdk.ai_core_v2_client import AICoreV2Client
#from ai_api_client_sdk.models.status import Status
#from gen_ai_hub.orchestration.service import OrchestrationService
from gen_ai_hub.orchestration.models.llm import LLM
#from gen_ai_hub.orchestration.models.message import SystemMessage, UserMessage
#from gen_ai_hub.orchestration.models.template import Template, TemplateValue
#from gen_ai_hub.orchestration.models.config import OrchestrationConfig
#from gen_ai_hub.orchestration.models.data_masking import DataMasking
#from gen_ai_hub.orchestration.models.sap_data_privacy_integration import (
#    SAPDataPrivacyIntegration, MaskingMethod, ProfileEntity )
from gen_ai_hub.proxy.langchain.init_models import init_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

agent_scratchpad=""
input="What is 157 multiplied by 493?"
vaddress="" 
port=443
vuser=""
vpassword=""

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
    vaddress=svcKey["HANA_HOST"]
    vuser=svcKey["HANA_USER"]
    vpassword=svcKey["HANA_PASSWORD_VDB"]

    return vuser,vpassword,vaddress

a,b,c = load_ai_core_credentials()

# Ensure these variables are in your template

# 1. Define a tool the agent can use
@tool
def multiply(a: int, b: int) -> int:
    """Multiplies two integers together."""
    return a * b

# 2. Setup the LLM "Brain"
#llm = ChatOpenAI(model="gpt-4o-mini", api_key="YOUR_OPENAI_API_KEY")
llm = init_llm('gpt-5', max_tokens=4096, temperature=0.0)

# 3. Combine LLM and Tools into an Agent
tools = [multiply]
tool_names = [tool.name for tool in tools]
#agent = create_react_agent(llm, tools)

template = """Answer the following questions as best you can.
You have access to the following tools:

{tools}  <-- REQUIRED
{tool_names}  <-- REQUIRED

Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!
Question: {input}
Thought: {agent_scratchpad} <-- REQUIRED
"""


vtemplate = """Answer the following questions as best you can.
You have access to the following tools:

{tools}  <-- REQUIRED
{tool_names}  <-- REQUIRED

Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!
Question: {input}
Thought: {agent_scratchpad} <-- REQUIRED
"""



#agent = create_react_agent(llm, tools, PromptTemplate.from_template(template), stop_sequence=True)
#agent = create_react_agent(llm, tools )

agent = create_react_agent(llm, tools, vtemplate)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 4. Execute
agent_executor.invoke({"input": "Use the magic tool on the word 'LangChain'"})




# 4. Run the agent
query = {"messages": [("user", "What is 157 multiplied by 493?")]}
for chunk in agent.stream(query):
    print(chunk)
