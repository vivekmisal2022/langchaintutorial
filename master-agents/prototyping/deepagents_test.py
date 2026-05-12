"""Simple CLI chat client using DeepAgents with streaming output and MCP tools."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Iterable
from typing import Any, Literal

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(filename="../backend/.env"))

from app.core.config import settings
from deepagents import create_deep_agent
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain import init_llm
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.messages import BaseMessage

# Web search tool
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Mock web search returning canned results for testing."""
    mock_results = [
        {
            "url": "https://example.com/langgraph-overview",
            "title": "LangGraph Overview",
            "content": "LangGraph is a framework for building multi-agent workflows "
            "with structured state management.",
        },
        {
            "url": "https://example.com/langgraph-docs",
            "title": "LangGraph Documentation",
            "content": "Official documentation covering LangGraph concepts, node types, "
            "and integration patterns.",
        },
    ]

    return {
        "query": query,
        "topic": topic,
        "max_results": max_results,
        "include_raw_content": include_raw_content,
        "results": mock_results[:max_results],
    }


# System prompt to steer the agent to be an expert researcher
research_instructions = """You are an expert researcher. Your job is to conduct thorough research, and then write a polished report.

You have access to an internet search tool as your primary means of gathering information.

## `internet_search`

Use this to run an internet search for a given query. You can specify the max number of results to return, the topic, and whether raw content should be included.
"""

logger = logging.getLogger(__name__)

THREAD_CONFIG = {"configurable": {"thread_id": "deepagents-cli"}}
MCP_SERVER_CONFIG = {
    "backend": {
        "transport": "streamable_http",
        "url": "http://localhost:3001/mcp",
    }
}


async def _load_model() -> Any:
    """Initialise the LangChain-wrapped model."""
    proxy_client = get_proxy_client(proxy_version="gen-ai-hub")
    return init_llm(
        model_name=settings.llm_model,
        proxy_client=proxy_client,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )


async def _load_mcp_tools() -> tuple[list[Any], MultiServerMCPClient | None]:
    """Connect to the local MCP server and retrieve available tools."""
    try:
        mcp_client = MultiServerMCPClient(MCP_SERVER_CONFIG)
        tools = await mcp_client.get_tools()
        logger.info("Loaded %d MCP tool(s)", len(tools))
        return list(tools), mcp_client
    except Exception as exc:
        logger.warning("Unable to load MCP tools: %s", exc, exc_info=True)
        return [], None


async def build_agent() -> tuple[Any, MultiServerMCPClient | None]:
    """Construct the DeepAgent with MCP tools."""
    model = await _load_model()
    mcp_tools, mcp_client = await _load_mcp_tools()
    all_tools: list[Any] = [*mcp_tools]

    agent = create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=research_instructions,
    )
    return agent, mcp_client


def _text_from_chunk(chunk: object) -> Iterable[str]:
    """Yield assistant text fragments from a LangGraph stream chunk."""

    if chunk is None:
        return []

    if isinstance(chunk, BaseMessage):
        if getattr(chunk, "type", None) != "ai":
            return []
        return _normalize_content(chunk.content)

    # LangGraph message chunks expose `.content`
    content = getattr(chunk, "content", None)
    if content is not None and getattr(chunk, "type", "ai") == "ai":
        yield from _normalize_content(content)
        return

    # Dictionaries may contain "messages" or "delta" with structured content
    if isinstance(chunk, dict):
        if "messages" in chunk and chunk["messages"]:
            for message in reversed(chunk["messages"]):
                if isinstance(message, BaseMessage):
                    if getattr(message, "type", None) != "ai":
                        continue
                    yield from _normalize_content(message.content)
                    return
                if isinstance(message, dict):
                    if message.get("type") not in {"ai", "assistant"}:
                        continue
                    yield from _normalize_content(message.get("content"))
                    return
        elif "delta" in chunk:
            delta = chunk["delta"]
            yield from _text_from_chunk(delta)
        return

    # Tuples can wrap (channels, payload) or (channel, payload)
    if isinstance(chunk, tuple):
        if len(chunk) == 3:
            _, channel, payload = chunk
        elif len(chunk) == 2:
            channel, payload = chunk
        else:
            return

        if channel != "messages":
            return
        yield from _text_from_chunk(payload)


def _normalize_content(content: object) -> Iterable[str]:
    """Normalize various content formats into plain text strings."""
    if content is None:
        return []

    if isinstance(content, str):
        return [content]

    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and part.get("text"):
                    texts.append(part["text"])
            elif isinstance(part, str):
                texts.append(part)
        return texts

    return [str(content)]


async def stream_agent_response(agent: Any, conversation: list[dict[str, str]]) -> AsyncGenerator[str, None]:
    """Stream the agent response for the current conversation state."""
    payload = {"messages": [dict(message) for message in conversation]}
    accumulated = ""
    try:
        async for chunk in agent.astream(
            payload,
            config=THREAD_CONFIG,
            stream_mode="values",
        ):
            for text in _text_from_chunk(chunk):
                if text:
                    if text.startswith(accumulated):
                        delta = text[len(accumulated):]
                    else:
                        delta = text
                    accumulated = text
                    if delta:
                        yield delta
    except Exception as exc:  # pragma: no cover - CLI feedback only
        logger.error("Streaming error", exc_info=True)
        yield f"[error: {exc}]"


async def chat_loop(agent: Any) -> None:
    """Interactive command-line chat loop."""
    print("DeepAgents CLI ready. Type 'exit' to quit.\n")

    conversation: list[dict[str, str]] = []

    while True:
        try:
            user_input = (await asyncio.to_thread(input, "You: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting DeepAgents CLI.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Exiting DeepAgents CLI.")
            break

        conversation.append({"role": "user", "content": user_input})

        print("Assistant:", end=" ")
        response_chunks: list[str] = []
        async for text in stream_agent_response(agent, conversation):
            if text:
                response_chunks.append(text)
                print(text, end="", flush=True)

        if response_chunks:
            conversation.append({"role": "assistant", "content": "".join(response_chunks)})
        else:
            try:
                fallback = await agent.ainvoke(
                    {"messages": [dict(message) for message in conversation]},
                    config=THREAD_CONFIG,
                )
                fallback_chunks = list(_text_from_chunk(fallback))
            except Exception as exc:  # pragma: no cover - CLI feedback only
                logger.error("Invoke error", exc_info=True)
                fallback_chunks = [f"[invoke error: {exc}]"]

            if fallback_chunks:
                fallback_text = "".join(fallback_chunks)
                conversation.append({"role": "assistant", "content": fallback_text})
                print(fallback_text, end="", flush=True)
            else:
                print("[no response]", end="")
                conversation.pop()  # remove user turn when nothing was produced
        print("\n")


async def run_cli() -> None:
    """Initialise resources and run the chat loop."""
    agent, mcp_client = await build_agent()
    try:
        await chat_loop(agent)
    finally:
        if mcp_client is not None:
            close = getattr(mcp_client, "aclose", None)
            if callable(close):
                await close()


if __name__ == "__main__":
    asyncio.run(run_cli())