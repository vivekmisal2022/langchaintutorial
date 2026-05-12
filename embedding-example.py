from pyexpat.errors import messages
import json
import os
from gen_ai_hub.orchestration.models.message import SystemMessage, UserMessage, AssistantMessage
from gen_ai_hub.orchestration.models.template import Template, TemplateValue 
from gen_ai_hub.orchestration.models.config import OrchestrationConfig
from gen_ai_hub.orchestration.service import OrchestrationService
from gen_ai_hub.orchestration_v2.service import OrchestrationService
from gen_ai_hub.orchestration.models.response_format import ResponseFormatJsonSchema 
from gen_ai_hub.orchestration.models.llm import LLM
from gen_ai_hub.proxy.langchain.init_models import init_llm
from gen_ai_hub.orchestration.models.message import SystemMessage, UserMessage 
from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage
from gen_ai_hub.orchestration_v2.models.template import Template , PromptTemplatingModuleConfig
from gen_ai_hub.orchestration.models.template import Template, TemplateValue 
from gen_ai_hub.orchestration_v2.models.template import Template
from gen_ai_hub.orchestration.models import llm
from gen_ai_hub.orchestration.models.config import OrchestrationConfig
from gen_ai_hub.orchestration_v2.models.config import ModuleConfig, OrchestrationConfig
from gen_ai_hub.orchestration_v2.models.response_format import ResponseFormatText
from gen_ai_hub.orchestration_v2.models.response_format import ResponseFormatText
from gen_ai_hub.orchestration_v2.models.response_format import ResponseFormatJsonSchema, JSONResponseSchema
from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails
from gen_ai_hub.orchestration_v2.models.tools import function_tool
from gen_ai_hub.orchestration_v2.models.tools import FunctionTool, FunctionObject
from typing import List
from gen_ai_hub.orchestration_v2.models.message import ChatMessage, SystemMessage, UserMessage, ToolChatMessage
from gen_ai_hub.orchestration_v2.models.message import UserMessage
from gen_ai_hub.orchestration_v2.models.template import Template
from gen_ai_hub.orchestration_v2.models.multimodal_items import ImageItem

from gen_ai_hub.orchestration_v2.service import OrchestrationService
from gen_ai_hub.orchestration_v2.models.embeddings import (
    EmbeddingsOrchestrationConfig,
    EmbeddingsModuleConfigs,
    EmbeddingsModelConfig,
    EmbeddingsModelDetails,
    EmbeddingsInput,
)


vuser=""
vpassword=""
vdbaddress=""
vpdffiles=""
#STEP 1: Load AI Core credentials
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






service = OrchestrationService()

# Minimal configuration - just specify the model
embeddings_config = EmbeddingsOrchestrationConfig(
    modules=EmbeddingsModuleConfigs(
        embeddings=EmbeddingsModelConfig(
            model=EmbeddingsModelDetails(name="text-embedding-3-large")
        )
    )
)

response = service.embed(
    config=embeddings_config,
    input=EmbeddingsInput(text="Hello World!")
)

embedding = response.final_result.data[0].embedding
print(f"Embedding dimensions: {len(embedding)}")
print(f"First 5 values: {embedding[:5]}")