# This code is taken from Carlos' excellent blog,  with extra logging added: https://community.sap.com/t5/technology-blog-posts-by-sap/building-an-agentic-ai-system-with-sap-generative-ai-hub/ba-p/14078187
from pyexpat.errors import messages
#from tools import get_time_now, get_weather, retriever
#from utils import ToolRegistry
import json
import os
from gen_ai_hub.orchestration.models.message import SystemMessage, UserMessage, AssistantMessage
from gen_ai_hub.orchestration.models.template import Template, TemplateValue 
from gen_ai_hub.orchestration.models.config import OrchestrationConfig
from gen_ai_hub.orchestration.service import OrchestrationService
from gen_ai_hub.orchestration.models.response_format import ResponseFormatJsonSchema 
from gen_ai_hub.orchestration.models.llm import LLM
from gen_ai_hub.proxy.langchain.init_models import init_llm

from gen_ai_hub.orchestration.models.message import SystemMessage, UserMessage 
from gen_ai_hub.orchestration.models.template import Template, TemplateValue 

from gen_ai_hub.orchestration.models.message import SystemMessage, UserMessage
from gen_ai_hub.orchestration.models.template import Template, TemplateValue 
from gen_ai_hub.orchestration.models import llm
from gen_ai_hub.orchestration.models.config import OrchestrationConfig


from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage
from gen_ai_hub.orchestration_v2.models.template import Template , PromptTemplatingModuleConfig



vtemplate = Template(
    template=[
        SystemMessage(content="You are a helpful translation assistant."),
        UserMessage(content="Translate the following text to {{?to_lang}}: {{?user_query}}"),
    ],
    defaults={"to_lang": "hindi"}
    )


from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails

#v2llm = LLMModelDetails(name="gpt-5-nano", params={"max_completion_tokens": 512})
v2llm = LLMModelDetails(name="gpt-5-nano")
print(v2llm)
print(v2llm.model_config.items())
#print(v2llm.model_json_schema())
for i in v2llm.model_json_schema():
    print(i)


# from gen_ai_hub.proxy.native.openai import completions

# response = completions.create(
#     model_name="gpt-4o-mini",
#     prompt="The Answer to the Ultimate Question of Life, the Universe, and Everything is",
#     max_tokens=20,
#     temperature=0
# )
# print(response)


from gen_ai_hub.proxy.native.google_genai.clients import Client
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client

proxy_client = get_proxy_client('gen-ai-hub')
client = Client(proxy_client=proxy_client)

response = client.models.generate_content(model="gemini-2.5-flash",
    contents="How many paws are there for a dog?"
)

print(response)
# Using another model
response = client.models.generate_content(model="gemini-2.0-flash",contents="Explain the theory of relativity in simple terms.")
print(response)
