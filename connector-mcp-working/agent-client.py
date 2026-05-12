"""Part 2: LangGraph Agent with MCP Tools (Complete)

This client connects to the MCP server and uses a React agent
to automatically call tools when answering questions.

Run with:
    uv run python agent_client.py

Run with verbose mode to see tool calls:
    uv run python agent_client.py --verbose

uv sync

# Test with MCP Inspector
uv run mcp dev mcp_server.py

After setup you can test the MCP server **on its own** using the MCP Inspector web UI.
This is useful for debugging your tools before wiring them into the agent.

1. In the Inspector UI:
   - **Transport type**: `STDIO`
   - **Command**: `python`
   - **Arguments**: `mcp_server.py`
2. Click **Connect**, then use the **Tools** tab to call your MCP tools interactively.

# Or run the agent client
uv run python agent_client.py --verbose

"""

import argparse
import asyncio
import os
import sys
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
#from langgraph.prebuilt import create_react_agent
from langchain.agents import create_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from gen_ai_hub.proxy.langchain.init_models import init_llm


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



# Load environment variables from the repo root .env file
##load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Configuration
MODEL = os.getenv("LLM_MODEL", "gpt-4.1")
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "5000"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
COMPANY_NAME = os.getenv("COMPANY_NAME", "the company")
TICKER = os.getenv("TICKER", "")

SYSTEM_PROMPT = f"""You are a financial analyst assistant helping with research on {COMPANY_NAME} ({TICKER}).

You have access to tools for:
- Fetching real-time stock prices (get_stock_info)
- Getting historical stock data (get_stock_history)
- Searching for market news (search_market_news)

Use these tools to provide accurate, up-to-date information.
Always cite your sources when presenting news or data.
If a tool fails, try a different approach before giving up."""

# Parse command line arguments
parser = argparse.ArgumentParser(description="Agent with MCP Tools")
parser.add_argument("--verbose", "-v", action="store_true", help="Show tool calls")
ARGS = parser.parse_args()


async def run_agent():
    """Run the agent connected to the MCP server."""
    
    # Initialize the LLM
    #llm = init_llm(MODEL, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
    llm = init_llm('gpt-4o-mini', max_tokens=4096, temperature=0.0)
    
    # Configure MCP server connection
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).parent / "mcp-server.py")],
    )
    
    print("🔌 Connecting to MCP Server...")
    print("-" * 50)
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Load tools from MCP server
            tools = await load_mcp_tools(session)
            
            print(f"✅ Loaded {len(tools)} tools from MCP server:")
            for tool in tools:
                desc = tool.description.split('\n')[0]
                print(f"   - {tool.name}: {desc}")
            print("-" * 50)
            
            # Create React agent
            checkpointer = InMemorySaver()
            #agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT, checkpointer=checkpointer)
            agent = create_agent(llm, system_prompt=SYSTEM_PROMPT, tools=tools, checkpointer=checkpointer)

            config = {"configurable": {"thread_id": "chat-session"}}
            
            print(f"\n🤖 DealCrafter Agent Ready!")
            print(f"   Analyzing: {COMPANY_NAME} ({TICKER})")
            if ARGS.verbose:
                print("   📋 Verbose mode ON")
            print("Type 'quit' or empty line to exit.\n")
            
            # Chat loop
            while True:
                try:
                    user_input = input("You: ").strip()
                except EOFError:
                    break
                
                if not user_input or user_input.lower() in ("quit", "exit", "q"):
                    print("\nGoodbye! 👋")
                    break
                
                if ARGS.verbose:
                    print()
                    async for event in agent.astream_events(
                        {"messages": [HumanMessage(content=user_input)]},
                        version="v2",
                        config=config,
                    ):
                        kind = event["event"]
                        
                        if kind == "on_tool_start":
                            tool_name = event["name"]
                            tool_input = event["data"].get("input", {})
                            print(f"  🔧 Calling tool: {tool_name}({tool_input})")
                        
                        elif kind == "on_tool_end":
                            tool_output = event["data"].get("output", "")
                            output_str = str(tool_output)[:200]
                            if len(str(tool_output)) > 200:
                                output_str += "..."
                            print(f"  ✅ Result: {output_str}")
                        
                        elif kind == "on_chat_model_end":
                            output = event["data"]["output"]
                            if hasattr(output, "content") and output.content:
                                if not hasattr(output, "tool_calls") or not output.tool_calls:
                                    print(f"\nAssistant: {output.content}\n")
                else:
                    print("\nAssistant: ", end="", flush=True)
                    result = await agent.ainvoke(
                        {"messages": [HumanMessage(content=user_input)]},
                        config=config,
                    )
                    final_message = result["messages"][-1]
                    print(final_message.content)
                    print()


def main():
    """Entry point."""
    asyncio.run(run_agent())


if __name__ == "__main__":
    main()