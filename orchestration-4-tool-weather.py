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
#print(llm.invoke("who is trump?").content)
#v2llm = LLMModelDetails(name="gpt-5-nano", params={"max_completion_tokens": 512})
v2llm = LLMModelDetails(name="gpt-4o-mini", params={"max_completion_tokens": 512, "temperature": 0.0})


def get_weather(location: str) -> str:
    """Get current temperature for a given location."""
    # Replace with your actual implementation
    return "22°C"

weather_tool_func = FunctionObject(
    name="get_weather",
    description="Get current temperature for a given location.",
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City and country e.g. mumbai , India"
            }
        },
        "required": ["location"],
        "additionalProperties": False
    },
    strict=True,
    function=get_weather
)

weather_tool = FunctionTool(function=weather_tool_func)

tools = [weather_tool]


#Attach the tools to the prompttemplate



toolstemplate = Template(
    template=[
        SystemMessage(content="You are an Expert and let me know how you achieved it ?"),
        UserMessage(content="What is the temperature in {{?location}}?"),
    ],
    tools=tools,
)

# Assume 'template' and 'weather_tool' are defined as above

prompt_template = PromptTemplatingModuleConfig(prompt=toolstemplate, model=v2llm)
module_config = ModuleConfig(prompt_templating=prompt_template)

config = OrchestrationConfig(modules=module_config)

client = OrchestrationService(config=config)
template_values = {"location": "Mumbai , India"}

# First run: triggers tool call
service = OrchestrationService()
response = service.run(config=config, placeholder_values=template_values)
tool_calls = response.final_result.choices[0].message.tool_calls

# Execute tool(s) and build new history
history: List[ChatMessage] = []
history.extend(response.intermediate_results.templating)
history.append(response.final_result.choices[0].message)

for tool_call in tool_calls:
    # For FunctionTool, use .execute(**tool_call.function.parse_arguments())
    result = weather_tool.execute(**tool_call.function.parse_arguments())
    tool_message = ToolChatMessage(
        content=str(result),
        tool_call_id=tool_call.id,
    )
    history.append(tool_message)

# Second run: LLM receives tool result and produces final answer
response2 = service.run(
    config=config,
    placeholder_values=template_values,
    history=history,
)
print(response2.final_result.choices[0].message.content)
