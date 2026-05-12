"""Service factory for pluggable chat response generation."""
from typing import AsyncGenerator, Literal, Optional
from app.core.config import settings
from app.services.mock_service import generate_mock_response
from app.services.llm_service import generate_llm_response
from app.services.deepagent_service import generate_deepagent_response


# Define service types
ServiceType = Literal["mock", "llm", "agentic"]


def get_service_type() -> ServiceType:
    """
    Determine which service to use based on configuration.

    Priority:
    1. If MOCK_MODE=true -> use mock service
    2. If AGENTIC_MODE=true -> use DeepAgent with MCP tools
    3. Otherwise -> use simple LLM service

    Returns:
        Service type to use
    """
    if settings.mock_mode:
        return "mock"
    elif settings.agentic_mode:
        return "agentic"
    else:
        return "llm"


async def generate_response(
    message: str,
    session_id: str | None = None,
    user_id: str = "anonymous",
    timezone: Optional[str] = None,
    user_name: Optional[str] = None
) -> AsyncGenerator[dict, None]:
    """
    Generate chat response using the configured service.

    This is the main entry point for all chat response generation.
    It automatically routes to the appropriate service based on configuration.

    Args:
        message: User message
        session_id: Optional session ID
        user_id: User ID for session storage (defaults to 'anonymous')
        timezone: User's IANA timezone (e.g., 'Asia/Tokyo')
        user_name: User's given name for personalized responses

    Yields:
        SSE events as dictionaries with 'event' and 'data' keys
    """
    service_type = get_service_type()

    if service_type == "mock":
        # Use mock service
        async for event in generate_mock_response(message):
            yield event

    elif service_type == "llm":
        # Use simple LLM service
        async for event in generate_llm_response(message, session_id):
            yield event

    elif service_type == "agentic":
        # Use DeepAgent service with MCP tools
        async for event in generate_deepagent_response(
            message, session_id, user_id, timezone, user_name
        ):
            yield event

    else:
        # Fallback error
        yield {"event": "error", "data": f"Unknown service type: {service_type}"}
        yield {"event": "end", "data": ""}
