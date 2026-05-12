import json
import os
from pathlib import Path

from dotenv import load_dotenv
from gen_ai_hub.proxy.langchain.init_models import init_llm

#load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "10000"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
SYSTEM_PROMPT = os.getenv("LLM_SYSTEM_PROMPT", "You are a helpful assistant.")

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




def main() -> None:
    llm = init_llm(MODEL, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
    while True:
        user = input("Prompt (empty to exit): ")
        if not user.strip():
            break
        text = f"{SYSTEM_PROMPT}\n\nUser: {user}"
        response = llm.invoke(text)
        data = {
            "content": getattr(response, "content", str(response)),
            "response_metadata": getattr(response, "response_metadata", None),
            "usage_metadata": getattr(response, "usage_metadata", None),
        }
        print("Reply:")
        print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    main()