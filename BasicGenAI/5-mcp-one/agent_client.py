"""
LangGraph React Agent with MCP Tools.

This client connects to an MCP server (mcp_server.py) and uses a React agent
pattern to automatically call tools when needed to answer user questions.

The React (Reasoning + Acting) pattern works as follows:
1. User asks a question
2. LLM reasons about what tools to use
3. Agent executes the tool
4. LLM observes the result and decides next action
5. Repeat until the answer is complete

Run with:
    uv run python agent_client.py

Run with verbose logging to see tool calls:
    uv run python agent_client.py --verbose
"""

import argparse
import asyncio
import os
import sys
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Import the MCP tools adapter for LangChain/LangGraph
from langchain_mcp_adapters.tools import load_mcp_tools

# Load shared credentials and LLM_* config from repo root .env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Import the SAP AI Core LLM initialization
from gen_ai_hub.proxy.langchain.init_models import init_llm

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "5000"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
SYSTEM_PROMPT = os.getenv(
    "LLM_SYSTEM_PROMPT",
    """You are a helpful assistant with access to tools for calculations, querying S/4HANA product data, and looking up warehouse stock.

MEMORY RULES — follow these strictly:
1. At the very start of every conversation, call memory_load(). If memory contains the user's name, greet them by name.
2. You MUST call memory_save() whenever:
   - The user tells you their name, role, preferences, or any personal detail.
   - You discover something new about the API (e.g. which entity holds a field).
   - You find a query pattern that worked well.
   Do NOT wait to be asked — save immediately after learning something new.
3. Before saving, check if the same information is already in memory. Do NOT save duplicates.
4. If information in memory is outdated or wrong, use memory_delete() to remove it first, then memory_save() the correction.
5. NEVER tell the user that you are saving or loading memory. Just do it silently in the background. Act naturally as if you simply remember things.

When a user asks about data you don't have or fields you're unsure about:
1. Check your memory — you may have solved something similar before.
2. If memory doesn't help, fetch the OData $metadata (via the product_api tool with path="$metadata") or call get_product_api_documentation() to discover which entities and fields are available.
3. Never say "this data is not available" without first exploring the API metadata.

Always be helpful and explain what you're doing."""
)


messages=""
vdbaddress="" 
port=443
vuser=""
vpassword=""
vpdffiles=""

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
    #os.environ["HANA_GROUNDING_DOCS"] = svcKey["HANA_GROUNDING_DOCS"]
    vdbaddress=svcKey["HANA_HOST"]
    vuser=svcKey["HANA_USER"]
    vpassword=svcKey["HANA_PASSWORD_VDB"]
    #vpdffiles=svcKey["HANA_GROUNDING_DOCS"]

    return vuser,vpassword,vdbaddress

vuser,vpassword,vdbaddress = load_ai_core_credentials()






# Parse command line arguments
parser = argparse.ArgumentParser(description="React Agent with MCP Tools")
parser.add_argument(
    "--verbose", "-v",
    action="store_true",
    help="Enable verbose logging to see tool calls"
)
ARGS = parser.parse_args()


async def run_agent():
    """Run the React agent connected to the MCP calculator server."""
    
    # Initialize the LLM from SAP AI Core
    llm = init_llm(MODEL, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
    
    # Configure the MCP server connection via stdio
    # The server will be started as a subprocess
    server_params = StdioServerParameters(
        command=sys.executable,  # Use the current Python interpreter
        args=[str(Path(__file__).parent / "mcp_server.py")],
    )
    
    print("🔌 Connecting to MCP Calculator Server...")
    print("-" * 50)
    
    # Connect to the MCP server using stdio transport
    async with stdio_client(server_params) as (read, write):
        # Create a client session for MCP communication
        async with ClientSession(read, write) as session:
            # Initialize the MCP connection
            await session.initialize()
            
            # Load tools from the MCP server
            # This converts MCP tools to LangChain tool format
            tools = await load_mcp_tools(session)
            
            print(f"✅ Loaded {len(tools)} tools from MCP server:")
            for tool in tools:
                # Show just the first line of description for cleaner output
                desc = tool.description.split('\n')[0]
                print(f"   - {tool.name}: {desc}")
            print("-" * 50)
            
            # Create a React agent with the LLM and MCP tools
            # The React agent will automatically:
            # - Reason about which tools to use
            # - Call the tools
            # - Observe results
            # - Continue until the task is complete
            #
            # InMemorySaver enables chat history - the agent remembers previous messages
            checkpointer = InMemorySaver()
            agent = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer)
            
            # Config with thread_id to maintain conversation context
            config = {"configurable": {"thread_id": "chat-session"}}
            
            print("\n🤖 React Agent Ready!")
            print("Ask me math questions and I'll use the calculator tools.")
            if ARGS.verbose:
                print("📋 Verbose mode ON - showing tool calls")
            print("Type 'quit' or press Enter on empty line to exit.\n")
            
            # Interactive chat loop
            while True:
                try:
                    user_input = input("You: ").strip()
                except EOFError:
                    break
                    
                if not user_input or user_input.lower() in ("quit", "exit", "q"):
                    print("\nGoodbye! 👋")
                    break
                
                # Stream the agent's response to see tool calls in real-time
                if ARGS.verbose:
                    print()
                    async for event in agent.astream_events(
                        {"messages": [HumanMessage(content=user_input)]},
                        version="v2",
                        config=config,
                    ):
                        kind = event["event"]
                        
                        # Show when a tool is being called
                        if kind == "on_tool_start":
                            tool_name = event["name"]
                            tool_input = event["data"].get("input", {})
                            print(f"  🔧 Calling tool: {tool_name}({tool_input})")
                        
                        # Show tool results
                        elif kind == "on_tool_end":
                            tool_output = event["data"].get("output", "")
                            print(f"  ✅ Result: {tool_output}")
                        
                        # Show final response
                        elif kind == "on_chat_model_end":
                            output = event["data"]["output"]
                            if hasattr(output, "content") and output.content:
                                # Only print if it's the final answer (no tool calls)
                                if not hasattr(output, "tool_calls") or not output.tool_calls:
                                    print(f"\nAssistant: {output.content}\n")
                else:
                    # Simple mode: just show the final answer
                    print("\nAssistant: ", end="", flush=True)
                    result = await agent.ainvoke(
                        {"messages": [HumanMessage(content=user_input)]},
                        config=config,
                    )
                    final_message = result["messages"][-1]
                    print(final_message.content)
                    print()


def main():
    """Entry point for the agent client."""
    asyncio.run(run_agent())


if __name__ == "__main__":
    main()