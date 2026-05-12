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







# Example 1: Image from a standard, publicly accessible URL
# Ensure the URL points directly to the image file (e.g., .png, .jpg, ...)
image_from_web = ImageItem(url="https://picsum.photos/id/1/200/300")  # example image URL

# Example 2: Image from a Data URL (base64-encoded)
# This is useful when you have the image content as a string.
# The format is "data:[<mediatype>][;base64],<data>"
image_from_data_url = ImageItem(
    url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAE0lEQVR4nGP8z4APMOGVZRip0gBBLAETee26JgAAAABJRU5ErkJggg=="
)



# Example: Image from a local file path
# To use this 'image_from_local_file' object, ensure it was successfully created.
try:
    image_from_local_file = ImageItem.from_file("/Users/I871395/Downloads/somethingforallages.png")
except FileNotFoundError:
    print("Error: The specified image file was not found.")
except Exception as e:
    print(f"An error occurred while loading the image: {e}")




vllm=LLMModelDetails(name="gpt-4o")



vtemplate = Template(
    template=[
        SystemMessage(content="You are an Expert and let me know how you achieved it ?"),
        UserMessage(content="whats in the image?"),
    ]
)

# Simple visual question answering
content_vqa = [image_from_web, "What objects are prominent in this image?"]

# Create a UserMessage with the mixed content
user_message = UserMessage(content=content_vqa)

# Create a Template containing the UserMessage
prompt_template = PromptTemplatingModuleConfig(prompt=vtemplate,model=vllm)

module_config = ModuleConfig(prompt_templating=prompt_template)

config = OrchestrationConfig(modules=module_config)
service = OrchestrationService(config=config)
response = service.run()
print(response.final_result.choices[0].message.content)
