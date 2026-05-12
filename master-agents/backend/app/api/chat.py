"""Chat API endpoints with SSE streaming."""
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.services.service_factory import generate_response
from app.services.user_service import get_user_id_from_request, extract_user_info


router = APIRouter()


@router.post("/chat-stream")
async def chat_stream(chat_request: ChatRequest, request: Request):
    """
    Stream chat responses using Server-Sent Events (SSE).

    Automatically routes to the appropriate service (mock, llm, or agentic)
    based on configuration in .env file.

    Event types:
    - text: String content from the AI
    - table: JSON table data
    - tool_start: Tool invocation started (JSON with tool_id, tool_name, args)
    - tool_end: Tool invocation completed (JSON with tool_id, success)
    - error: Error messages
    - end: Signals end of stream
    """
    user_info = extract_user_info(request)
    user_id = user_info.user_id if user_info else "anonymous"

    async def event_generator():
        """Generate SSE events from the configured service."""
        try:
            # Use service factory to get the appropriate service
            async for event in generate_response(
                message=chat_request.message,
                session_id=chat_request.session_id,
                user_id=user_id,
                timezone=chat_request.timezone,
                user_name=user_info.given_name if user_info else None
            ):
                # Format as SSE
                event_type = event["event"]
                event_data = event["data"]

                # Serialize data to JSON ONLY for dict/table data
                # Text chunks should remain as plain strings
                if isinstance(event_data, dict):
                    event_data = json.dumps(event_data)
                elif not isinstance(event_data, str):
                    event_data = str(event_data)
                # For strings, keep them as-is (don't JSON encode)

                # Yield SSE formatted event
                yield f"event: {event_type}\n"

                # Handle multi-line data per SSE spec
                # If data contains newlines, send multiple data: lines
                if '\n' in event_data:
                    for line in event_data.split('\n'):
                        yield f"data: {line}\n"
                else:
                    yield f"data: {event_data}\n"

                yield "\n"  # Empty line to signal end of event

        except Exception as e:
            # Send error event
            yield "event: error\n"
            yield f"data: {str(e)}\n\n"
            yield "event: end\n"
            yield "data: \n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
