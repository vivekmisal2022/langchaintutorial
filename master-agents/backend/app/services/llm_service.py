"""LLM service using SAP Generative AI Hub SDK with chat history support."""
import asyncio
import logging
from typing import AsyncGenerator, Optional
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models.chat_models import BaseChatModel
from gen_ai_hub.proxy.langchain import init_llm
from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from app.core.config import settings
from app.services.session_storage import SessionStorage

# Configure logger
logger = logging.getLogger(__name__)

# Singleton LLM instance
_llm_instance: Optional[BaseChatModel] = None
_proxy_client_instance: Optional[BaseProxyClient] = None


def _get_llm() -> BaseChatModel:
    """
    Get or initialize the LLM instance (singleton pattern).
    
    Returns:
        Initialized LLM instance
    """
    global _llm_instance, _proxy_client_instance
    
    if _llm_instance is None:
        logger.info("Initializing LLM instance (first time)")
        
        # Initialize proxy client
        _proxy_client_instance = get_proxy_client(
            proxy_server_url=settings.aicore_base_url or None,
            auth_url=settings.aicore_auth_url or None,
            client_id=settings.aicore_client_id or None,
            client_secret=settings.aicore_client_secret or None,
            resource_group=settings.aicore_resource_group or None,
        )
        
        # Initialize LLM with LangChain wrapper
        _llm_instance = init_llm(
            model_name=settings.llm_model,
            proxy_client=_proxy_client_instance,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )
        
        logger.info(f"LLM initialized successfully with model: {settings.llm_model}")
    else:
        logger.debug("Reusing existing LLM instance")
    
    return _llm_instance


async def generate_llm_response(message: str, session_id: str | None = None) -> AsyncGenerator[dict, None]:
    """
    Generate streaming response using SAP Generative AI Hub with chat history.
    
    Loads previous messages from the session and includes them as context
    for the LLM to maintain conversation continuity.
    
    Args:
        message: User message
        session_id: Session ID to load chat history from
        
    Yields:
        SSE events as dictionaries with 'event' and 'data' keys
    """
    try:
        # Get or initialize LLM (singleton)
        llm = _get_llm()
        
        # Load chat history from session
        chat_history = []
        if session_id:
            logger.debug(f"Loading chat history for session: {session_id}")
            storage = SessionStorage()
            session = storage.get_session(session_id)
            if session and session.messages:
                # Convert stored messages to LangChain message format
                logger.info(f"Loaded {len(session.messages)} messages from session {session_id}")
                for msg in session.messages:
                    logger.debug(f"Message: {msg.role} - {msg.content[:50]}...")
                    if msg.role == "user":
                        # Check if message has image attachments
                        if msg.attachments:
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
                            
                            chat_history.append(HumanMessage(content=content))
                            logger.debug(f"Added multimodal message with {len(msg.attachments)} attachment(s)")
                        else:
                            # Text-only message
                            chat_history.append(HumanMessage(content=msg.content))
                    elif msg.role == "assistant":
                        # Assistant messages remain text-only
                        chat_history.append(AIMessage(content=msg.content))
                logger.info(f"Chat history prepared with {len(chat_history)} messages")
            else:
                logger.warning(f"No session or messages found for session_id: {session_id}")
        else:
            logger.debug("No session_id provided, starting fresh conversation")
        
        # Create prompt with chat history
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful AI assistant for financial data analysis. You can analyze both text and images. Answer questions clearly and concisely. When providing tables, use proper markdown table format with newlines between rows."),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}")
        ])
        
        # Create chain
        chain = prompt | llm | StrOutputParser()
        
        # Stream response chunks
        async for chunk in chain.astream({
            "input": message,
            "chat_history": chat_history
        }):
            if chunk:
                yield {
                    "event": "text",
                    "data": chunk
                }
                # Small delay to make streaming visible
                await asyncio.sleep(0.01)
        
        # Signal end of stream
        yield {"event": "end", "data": ""}
        
    except Exception as e:
        # Log and send error event
        logger.error(f"LLM error occurred: {str(e)}", exc_info=True)
        error_msg = f"LLM Error: {str(e)}"
        yield {"event": "error", "data": error_msg}
        yield {"event": "end", "data": ""}
