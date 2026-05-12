"""DeepAgent service with MCP tools integration for agentic workflows."""
import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Optional
from collections.abc import Iterable
from textwrap import dedent
from zoneinfo import ZoneInfo

from deepagents import create_deep_agent
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain import init_llm
from gen_ai_hub.proxy.langchain.amazon import (
    init_chat_converse_model as amazon_init_converse_model
)
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.core.config import settings
from app.services.session_storage import SessionStorage

# Configure logger
logger = logging.getLogger(__name__)

# Enable Claude Sonnet 4.5 models in Amazon Bedrock initializers
model_name_amazon = 'anthropic--claude-4.5-sonnet'
model_id_amazon = 'anthropic.claude-sonnet-4-5-20250929-v1:0'

# Singleton instances
_mcp_client_instance: Optional[MultiServerMCPClient] = None
_model_instance: Optional[Any] = None
_mcp_tools: Optional[list] = None

# MCP server configuration - URL from settings (environment variable)
def _get_mcp_server_config() -> dict:
    """Get MCP server configuration with URL from settings."""
    return {
        "backend": {
            "transport": "streamable_http",
            "url": settings.mcp_server_url,
        }
    }

# Thread configuration for conversation persistence
THREAD_CONFIG = {"configurable": {"thread_id": "backend-session"}}


def _get_model() -> Any:
    """
    Get or initialize the LLM model instance (singleton pattern).
    
    Returns:
        Initialized LLM model
    """
    global _model_instance
    
    if _model_instance is None:
        logger.info(f"Initializing LLM model for DeepAgent with model {settings.llm_model}")
        proxy_client = get_proxy_client(proxy_version="gen-ai-hub")
        if settings.llm_model ==model_name_amazon:
            _model_instance = init_llm(
                model_name_amazon,
                proxy_client=proxy_client,
                temperature=settings.llm_temperature,
                top_p=None,
                max_tokens=settings.llm_max_tokens,
                model_id=model_id_amazon,
                init_func=amazon_init_converse_model
            )
        else:
            _model_instance = init_llm(
                model_name=settings.llm_model,
                proxy_client=proxy_client,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature
            )
        logger.info("LLM model initialized successfully")
    
    return _model_instance


async def _load_mcp_tools() -> tuple[list[Any], Optional[MultiServerMCPClient]]:
    """
    Connect to the local MCP server and retrieve available tools.

    Returns:
        Tuple of (tools list, mcp_client instance or None)
    """
    global _mcp_tools, _mcp_client_instance

    # Return cached tools if available
    if _mcp_tools is not None and _mcp_client_instance is not None:
        return _mcp_tools, _mcp_client_instance

    try:
        mcp_config = _get_mcp_server_config()
        logger.info(f"Connecting to MCP server at {mcp_config['backend']['url']}")
        mcp_client = MultiServerMCPClient(mcp_config)
        tools = await mcp_client.get_tools()
        logger.info(f"Loaded {len(tools)} MCP tool(s)")
        _mcp_tools = list(tools)
        _mcp_client_instance = mcp_client
        return _mcp_tools, _mcp_client_instance
    except Exception as exc:
        logger.warning(f"Unable to load MCP tools: {exc}", exc_info=True)
        return [], None


def _build_system_prompt(
    user_name: Optional[str] = None,
    timezone: Optional[str] = None,
    is_first_message: bool = False
) -> str:
    """
    Build a dynamic system prompt with user context.

    Args:
        user_name: User's given name for personalization
        timezone: User's IANA timezone
        is_first_message: Whether this is the first message in the session

    Returns:
        Complete system prompt string
    """
    # Get current time in user's timezone
    time_info = ""
    greeting_instruction = ""

    if timezone:
        try:
            tz = ZoneInfo(timezone)
            now = datetime.now(tz)
            hour = now.hour
            time_str = now.strftime("%Y-%m-%d %H:%M")

            # Determine time of day for greeting
            if 5 <= hour < 12:
                time_of_day = "morning"
            elif 12 <= hour < 17:
                time_of_day = "afternoon"
            elif 17 <= hour < 21:
                time_of_day = "evening"
            else:
                time_of_day = "night"

            time_info = f"\n\nUser Context:\n- Current time: {time_str} ({timezone})\n- Time of day: {time_of_day}"

            if user_name:
                time_info += f"\n- User's name: {user_name}"
        except Exception as e:
            logger.warning(f"Failed to parse timezone {timezone}: {e}")
    elif user_name:
        time_info = f"\n\nUser Context:\n- User's name: {user_name}"

    # Greeting instructions based on whether this is first message
    if is_first_message:
        if user_name:
            greeting_instruction = dedent(f"""

            IMPORTANT: This is the FIRST message of this conversation. Greet the user warmly:
            - Address them by name: "{user_name}"
            - Use an appropriate time-of-day greeting in the SAME LANGUAGE as their message
            - Keep the greeting brief and natural, then address their query
            """)
        else:
            greeting_instruction = dedent("""

            IMPORTANT: This is the FIRST message of this conversation. Greet the user with an appropriate
            time-of-day greeting in the SAME LANGUAGE as their message. Keep it brief and natural.
            """)
    else:
        if user_name:
            greeting_instruction = f"\n\nYou may address the user as \"{user_name}\" when appropriate, but do NOT greet them again - this is a continuation of an existing conversation."

    base_prompt = dedent(
        """You are a helpful AI assistant with access to various tools and data sources.

        IMPORTANT: Always respond in the SAME LANGUAGE as the user's message. If the user writes in English, respond in English. If they write in German, respond in German. Never assume a language based on timezone or location.

        MEMORY — DO THIS FIRST:
        Your VERY FIRST action in every conversation must be to call memory_load to recall what you know from previous sessions.
        Do this before answering the user's question, even if it seems simple.
        Throughout the conversation, proactively save noteworthy information to memory using memory_save. Things worth saving include:
        - The user's name, preferences, or role
        - API quirks you discovered (e.g. correct entity names, field mappings, which filters work)
        - Facts about the user's business context (e.g. which plant they work with, their cost center)
        - Corrections the user made to your answers
        - Anything you had to figure out the hard way that would save time next time
        Keep notes short, factual, and useful. Don't save trivial things.

        Make good use of the tools available to you. Be generous with tool calls — better more than less. Don't give up easily.
        When using S/4HANA Product API tools, call get_product_api_documentation first to understand the available fields and query options.
        You can use the "get_time_and_place" tool if you need to know the current time or location context.

        ERROR RECOVERY — THIS IS CRITICAL:
        When any API tool call returns an error (success=false), you MUST NOT give up or ask the user what to do.
        Instead, follow this recovery strategy:
        1. Read the error message carefully to understand what went wrong.
        2. If the error mentions an unknown property/field/entity, fetch the service metadata first
           (e.g. call stock_api or product_api with path="$metadata" and accept="application/xml")
           to discover the correct entity names, field names, and relationships.
        3. Save useful findings to memory (e.g. "Stock API: use A_MatlStkInAcctMod entity, field Material not Plant for filtering").
        4. Retry the query with corrected parameters based on what you learned from the metadata.
        5. Only ask the user for help after you have tried at least 2-3 different approaches on your own.
        You are an expert — users expect you to figure out API quirks autonomously."""
    )

    return base_prompt + time_info + greeting_instruction


async def _get_agent(
    user_name: Optional[str] = None,
    timezone: Optional[str] = None,
    is_first_message: bool = False
) -> tuple[Any, Optional[MultiServerMCPClient]]:
    """
    Create a DeepAgent instance with dynamic system prompt.

    Unlike other singletons, the agent is created per-request to allow
    dynamic system prompts based on user context.

    Args:
        user_name: User's given name for personalization
        timezone: User's IANA timezone
        is_first_message: Whether this is the first message in the session

    Returns:
        Tuple of (agent instance, mcp_client instance or None)
    """
    logger.info("Creating DeepAgent with dynamic system prompt")

    # Load model and MCP tools (these are cached)
    model = _get_model()
    mcp_tools, mcp_client = await _load_mcp_tools()

    # Build dynamic system prompt
    system_prompt = _build_system_prompt(user_name, timezone, is_first_message)
    logger.debug(f"System prompt: {system_prompt[:200]}...")

    # Create agent with tools
    agent = create_deep_agent(
        model=model,
        tools=mcp_tools,
        system_prompt=system_prompt,
    )

    logger.info("DeepAgent created successfully")
    return agent, mcp_client


def _text_from_chunk(chunk: object) -> Iterable[str]:
    """
    Yield text fragments from a LangGraph stream chunk.

    Only extracts text from AI/assistant messages, not tool messages.

    Args:
        chunk: Stream chunk from agent.astream()

    Yields:
        Text strings extracted from the chunk
    """
    if chunk is None:
        return []

    # Handle tuple format from stream_mode="messages": (message, metadata)
    actual_chunk = chunk
    if isinstance(chunk, tuple) and len(chunk) >= 1:
        actual_chunk = chunk[0]

    # Skip non-AI messages (tool messages, human messages, etc.)
    chunk_type = getattr(actual_chunk, "type", None)
    chunk_class = type(actual_chunk).__name__

    # Only extract text from AI messages
    if chunk_class not in ("AIMessage", "AIMessageChunk"):
        if chunk_type not in ("ai", "AIMessageChunk", None):
            return []

    # For AIMessageChunk, check if it has actual content (not just tool calls)
    content = getattr(actual_chunk, "content", None)
    if content is not None:
        # Skip if this chunk only contains tool call info (no actual text)
        if isinstance(content, str) and content:
            yield content
            return
        elif isinstance(content, list):
            # Handle content blocks (text blocks vs tool_use blocks)
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text" and part.get("text"):
                        yield part["text"]
                elif isinstance(part, str) and part:
                    yield part
            return

    # Dictionaries may contain "messages" with structured content
    if isinstance(actual_chunk, dict):
        if "messages" in actual_chunk and actual_chunk["messages"]:
            last = actual_chunk["messages"][-1]
            # Recursively process the last message
            yield from _text_from_chunk(last)
        elif "delta" in actual_chunk:
            delta = actual_chunk["delta"]
            yield from _text_from_chunk(delta)


def _extract_tool_calls(chunk: object) -> list[dict]:
    """
    Extract tool call information from a LangGraph stream chunk.

    Args:
        chunk: Stream chunk from agent.astream()

    Returns:
        List of tool call dicts with 'id', 'name', and optionally 'args'
    """
    tool_calls = []

    # Check for tool_calls attribute on message chunks (AIMessageChunk)
    if hasattr(chunk, "tool_calls") and chunk.tool_calls:
        for tc in chunk.tool_calls:
            tool_call = {
                "id": tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None),
                "name": tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None),
            }
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None)
            if args:
                tool_call["args"] = args
            if tool_call["id"] and tool_call["name"]:
                tool_calls.append(tool_call)

    # Check for tool_call_chunks (partial tool call streaming)
    if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
        for tc in chunk.tool_call_chunks:
            tool_call = {
                "id": tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None),
                "name": tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None),
            }
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None)
            if args:
                tool_call["args"] = args
            # Only add if we have a name (first chunk of a tool call)
            if tool_call["name"]:
                tool_calls.append(tool_call)

    return tool_calls


def _normalize_content(content: object) -> Iterable[str]:
    """
    Normalize various content formats into plain text strings.
    
    Args:
        content: Content object to normalize
        
    Returns:
        List of text strings
    """
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


async def generate_deepagent_response(
    message: str,
    session_id: str | None = None,
    user_id: str = "anonymous",
    timezone: Optional[str] = None,
    user_name: Optional[str] = None
) -> AsyncGenerator[dict, None]:
    """
    Generate streaming response using DeepAgent with MCP tools.

    Loads previous messages from the session and includes them as context
    for the agent to maintain conversation continuity.

    Args:
        message: User message
        session_id: Session ID to load chat history from
        user_id: User ID for session storage
        timezone: User's IANA timezone (e.g., 'Asia/Tokyo')
        user_name: User's given name for personalized responses

    Yields:
        SSE events as dictionaries with 'event' and 'data' keys
    """
    try:
        # Load chat history from session and determine if first message
        conversation = []
        is_first_message = True
        storage = SessionStorage()

        if session_id:
            logger.debug(f"Loading chat history for session: {session_id}, user: {user_id}")
            session = storage.get_session(user_id, session_id)
            if session and session.messages:
                logger.info(f"Loaded {len(session.messages)} messages from session {session_id}")
                # Check if user has already been greeted in this session
                is_first_message = not session.greeted

                for msg in session.messages:
                    # Check if message has image attachments (multimodal)
                    if msg.role == "user" and msg.attachments:
                        # Build multimodal content array (OpenAI format)
                        content = []

                        # Add text if present
                        if msg.content:
                            content.append({
                                "type": "text",
                                "text": msg.content
                            })

                        # Add images
                        for attachment in msg.attachments:
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{attachment.mime_type};base64,{attachment.data}"
                                }
                            })

                        conversation.append({
                            "role": msg.role,
                            "content": content
                        })
                        logger.debug(f"Added multimodal message with {len(msg.attachments)} attachment(s)")
                    else:
                        # Text-only message
                        conversation.append({
                            "role": msg.role,
                            "content": msg.content
                        })

                # Mark session as greeted if this is first message
                if is_first_message:
                    session.greeted = True
                    storage.update_session(user_id, session)
                    logger.debug(f"Marked session {session_id} as greeted")
            else:
                logger.warning(f"No session or messages found for session_id: {session_id}")
        else:
            logger.debug("No session_id provided, starting fresh conversation")

        # Get or initialize agent with dynamic system prompt
        agent, _ = await _get_agent(user_name, timezone, is_first_message)
        
        # Add current message
        conversation.append({"role": "user", "content": message})
        
        # Prepare payload for agent
        payload = {"messages": [dict(msg) for msg in conversation]}

        # Track active tool calls to avoid duplicate events
        active_tool_ids: set[str] = set()

        # Stream response chunks
        has_output = False
        async for chunk in agent.astream(
            payload,
            config=THREAD_CONFIG,
            stream_mode="messages",
        ):
            # Handle tuple format from stream_mode="messages": (message, metadata)
            actual_chunk = chunk
            if isinstance(chunk, tuple) and len(chunk) >= 1:
                actual_chunk = chunk[0]

            # Check for tool calls on the actual message chunk
            tool_calls = _extract_tool_calls(actual_chunk)
            for tc in tool_calls:
                tool_id = tc["id"]
                if tool_id and tool_id not in active_tool_ids:
                    active_tool_ids.add(tool_id)
                    logger.info(f"Tool call started: {tc['name']} (id={tool_id})")
                    yield {
                        "event": "tool_start",
                        "data": {
                            "tool_id": tool_id,
                            "tool_name": tc["name"],
                            "args": tc.get("args"),
                        }
                    }

            # Check if this is a ToolMessage (tool result) - signals tool completion
            chunk_class = type(actual_chunk).__name__
            msg_type = getattr(actual_chunk, "type", None)
            if msg_type == "tool" or chunk_class in ("ToolMessage", "ToolMessageChunk"):
                tool_call_id = getattr(actual_chunk, "tool_call_id", None)
                if tool_call_id and tool_call_id in active_tool_ids:
                    active_tool_ids.discard(tool_call_id)
                    logger.info(f"Tool call completed: {tool_call_id}")
                    yield {
                        "event": "tool_end",
                        "data": {
                            "tool_id": tool_call_id,
                            "success": True,
                        }
                    }

            # Extract text content
            for text in _text_from_chunk(chunk):
                if text:
                    has_output = True
                    yield {
                        "event": "text",
                        "data": text
                    }
                    # Small delay to make streaming visible
                    await asyncio.sleep(0.01)
        
        # If no streaming output, try invoke as fallback
        if not has_output:
            logger.warning("No streaming output, using invoke fallback")
            try:
                fallback = await agent.ainvoke(payload, config=THREAD_CONFIG)
                fallback_chunks = list(_text_from_chunk(fallback))
                if fallback_chunks:
                    fallback_text = "".join(fallback_chunks)
                    yield {
                        "event": "text",
                        "data": fallback_text
                    }
            except Exception as fallback_exc:
                logger.error(f"Invoke fallback error: {fallback_exc}", exc_info=True)
                yield {
                    "event": "error",
                    "data": f"Agent error: {str(fallback_exc)}"
                }
        
        # Signal end of stream
        yield {"event": "end", "data": ""}
        
    except Exception as e:
        # Log and send error event
        logger.error(f"DeepAgent error occurred: {str(e)}", exc_info=True)
        error_msg = f"DeepAgent Error: {str(e)}"
        yield {"event": "error", "data": error_msg}
        yield {"event": "end", "data": ""}


async def cleanup_deepagent_service() -> None:
    """
    Cleanup DeepAgent service resources.
    
    Should be called on application shutdown.
    """
    global _mcp_client_instance
    
    if _mcp_client_instance is not None:
        logger.info("Cleaning up MCP client connection")
        close = getattr(_mcp_client_instance, "aclose", None)
        if callable(close):
            try:
                await close()
                logger.info("MCP client closed successfully")
            except Exception as exc:
                logger.warning(f"Error closing MCP client: {exc}")
        _mcp_client_instance = None
