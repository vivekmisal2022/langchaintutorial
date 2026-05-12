import json
import os
#from tools import get_time_now, get_weather, retriever
#from utils import ToolRegistry

from gen_ai_hub.orchestration.models.message import SystemMessage, UserMessage, AssistantMessage
from gen_ai_hub.orchestration.models.template import Template, TemplateValue
from gen_ai_hub.orchestration.models.config import OrchestrationConfig
from gen_ai_hub.orchestration.service import OrchestrationService
from gen_ai_hub.orchestration.models.response_format import ResponseFormatJsonSchema 
from gen_ai_hub.orchestration.models.llm import LLM
from gen_ai_hub.proxy.langchain.init_models import init_llm
from hdbcli import dbapi

import requests
from datetime import datetime
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate
from langchain_community.vectorstores.hanavector import HanaDB
from gen_ai_hub.proxy.langchain import init_llm
from gen_ai_hub.proxy.langchain.init_models import init_embedding_model

vuser=""
vpassword=""
vdbaddress=""
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

class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name, function, description, parameters):
        self.tools[name] = {
            "function": function,
            "description": description,
            "parameters": parameters
        }

    def get_description_for_prompt(self):
        return {
            name: {
                "description": entry["description"],
                "parameters": entry["parameters"]
            } for name, entry in self.tools.items()
        }

    def get_callable(self, name):
        return self.tools.get(name, {}).get("function")


vuser,vpassword,vdbaddress,vpdffiles = load_ai_core_credentials()


llm = init_llm('gpt-4o-mini', max_tokens=4096, temperature=0.0)
#print(llm)

HANA_HOST = vdbaddress
HANA_USER = vuser
HANA_PASSWORD = vpassword

connection = dbapi.connect(
    HANA_HOST,
    port="443",
    user=HANA_USER,
    password=HANA_PASSWORD,
    autocommit=True,
    sslValidateCertificate=False,
)



def retriever(question: str):
    embedding_model = init_embedding_model('text-embedding-ada-002')
    llm = init_llm('gpt-4o-mini')
    
    
    prompt_template = """
    Use the following context to answer the question at the end. 
    If the answer is not directly stated, try your best based on the context. 
    Only say you don't know if the information is completely unavailable.

    {context}

    Question: {question}
    """

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )

    db = HanaDB(
        embedding=embedding_model,
        connection=connection,
        table_name="EMBEDDINGS_COLLECTION_DATA"
    )

    retriever = db.as_retriever(search_kwargs={'k': 10})
    qa = RetrievalQA.from_chain_type(
        llm= llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": prompt}
    )

    response = qa.invoke({"query": question})
    return {"answer": response}


def get_time_now():
    """Returns the current local time as a formatted string."""
    return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

def get_weather(latitude, longitude):
    """This is a publically available API that returns the weather for a given location."""
    response = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m"
    )
    data = response.json()
    return data["current"]


registry = ToolRegistry()
registry.register(
    "get_weather",
    get_weather,
    "Retrieves current weather data for a given set of geographic coordinates (latitude, longitude).",
    {
        "latitude": "float - The latitude of the location.",
        "longitude": "float - The longitude of the location."
    }
)

registry.register(
    "get_time_now",
    get_time_now,
    "Returns the current local time in YYYY-MM-DD HH:MM:SS format.",
    {}  # No parameters required
)

registry.register(
    "retriever",
    retriever,
    "Retrieves an answer using RAG from documents stored in SAP HANA Cloud for SAP Business Data Cloud and SAP Generative AI Hub in SAP AI Core content",
    {
        "question": "string - The question you want to ask based on the document context."
    }
)

# description = json.dumps(registry.get_description_for_prompt(), indent=2)
# print(description)


class AgentExecutor:
    def __init__(self, llm, tool_registry, verbose=True):
        self.llm = llm
        self.tool_registry = tool_registry
        self.verbose = verbose

    def _build_dynamic_schema(self):
        return {
            "title": "ToolCalls",
            "type": "object",
            "properties": {
                "tool_calls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "decision": {"type": "string"},
                            "reason": {"type": "string"},
                            "function": {"type": "string"},
                            "parameters": {"type": "object"}
                        },
                        "required": ["decision", "reason", "function", "parameters"]
                    }
                }
            },
            "required": ["tool_calls"]
        }

    def _generate_instruction(self):
        description = json.dumps(self.tool_registry.get_description_for_prompt(), indent=2)
        return f"""
                You are an intelligent AI assistant capable of deciding whether to invoke tools based on the user's request.

                Available tools:
                {description}

                Instructions:
                - For each relevant tool, return a JSON entry with the function name and parameters.
                - If no tool is relevant, return an entry with decision = "no_tool".

                Return ONLY valid JSON like:
                {{
                "tool_calls": [
                    {{
                    "decision": "tool",
                    "reason": "The user asked for weather.",
                    "function": "get_weather",
                    "parameters": {{
                        "latitude": 48.8566,
                        "longitude": 2.3522
                    }}
                    }},
                    {{
                    "decision": "tool",
                    "reason": "The user asked for time.",
                    "function": "get_time_now",
                    "parameters": {{}}
                    }}
                ]
                }}
                """

    def run(self, user_query: str):
        system_message = SystemMessage(self._generate_instruction())
        prompt = UserMessage(user_query)
        messages = [system_message, prompt]

        # Step 1: Ask which tools to use
        template = Template(
            messages=messages,
            response_format=ResponseFormatJsonSchema(
                name="ToolCall",
                description="Tool execution format",
                schema=self._build_dynamic_schema()
            )
        )
        config = OrchestrationConfig(template=template, llm=self.llm)
        response = OrchestrationService(config=config).run()
        
        decisions_json = json.loads(response.module_results.llm.choices[0].message.content)

        if self.verbose:
            print("\nLLM Reasoning:")
            print(json.dumps(decisions_json, indent=2))

        tool_results = []
        messages = [system_message, prompt]

        for decision in decisions_json.get("tool_calls", []):
            if decision.get("decision") == "tool":
                tool_response = self._execute_tool(decision)
                tool_results.append((decision["function"], tool_response))
                messages.append(AssistantMessage(json.dumps(decision)))
            else:
                messages.append(AssistantMessage(json.dumps(decision)))

        # Step 2: Final LLM synthesis
        return self._finalize_response(user_query, tool_results, messages)

    def _execute_tool(self, decision):
        func_name = decision["function"]
        args = decision.get("parameters", {})
        func = self.tool_registry.get_callable(func_name)
        
        if callable(func):
            try:
                result = func(**args)
                if self.verbose:
                    print(f"\nTool '{func_name}' executed with args {args}. Result: {result}")
                return result
            except Exception as e:
                return f"Error: {str(e)}"
        else:
            return f"Function '{func_name}' not found."

    def _finalize_response(self, original_query, tool_results, messages):
        # Append summary and results to LLM context
        # Give explicit instruction and reinforce tool results context
        messages.append(SystemMessage(
            """ 
            You now have access to the results provided by the tools. When the results are clear and complete, use only that information to answer the user's 
            question in a natural, helpful, and concise manner. However, if any result appears vague, incomplete, or states uncertainty (e.g., "I don't know"), 
            rely on your own knowledge to deliver an accurate and informative response.
            Always avoid requesting information already provided. Focus on clarity, relevance, and user value.

            """            
        ))

        messages.append(UserMessage(f"User question: {original_query}"))

        # Structured, clean summary of tool outputs
        tool_summary = "\n".join(
            [f"- Tool `{name}` returned: {json.dumps(result)}" for name, result in tool_results]
        )
        messages.append(UserMessage(f"Tool Results:\n{tool_summary}"))


        # Final orchestration
        template = Template(messages=messages, response_format="text")

        config = OrchestrationConfig(template=template, llm=self.llm)
        response = OrchestrationService(config=config).run()
        return llm.choices[0].message.content


# to print:
#llm = LLM(name="gpt-4o", version="latest", parameters={"max_tokens": 2000, "temperature": 0.2})
agent = AgentExecutor(llm=llm, tool_registry=registry, verbose=True)

prompt = "How's the weather in Paris?"
response = agent.run(prompt)
print("\n", response)