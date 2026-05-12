"""
Chat history API endpoints for session management.
Supports user-specific session storage.
"""
import logging
from datetime import datetime
from typing import List, Literal

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel

from app.models.schemas import ChatHistoryItem, ChatSession, ChatMessage, TableData, ChatAttachment
from app.services.session_storage import get_storage
from app.services.title_generation import generate_session_title as generate_title_with_llm
from app.services.user_service import get_user_id_from_request

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api", tags=["chat-history"])


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    title: str = "New Chat"


class GenerateTitleRequest(BaseModel):
    """Request to generate a title from chat history."""
    session_id: str
    messages: List[dict]  # Simplified for now


class GenerateTitleResponse(BaseModel):
    """Response with generated title."""
    title: str


class AddMessageRequest(BaseModel):
    """Request payload to append a message to a session."""
    role: Literal['user', 'assistant']
    content: str
    timestamp: datetime | None = None
    tables: list[TableData] | None = None
    attachments: list[ChatAttachment] | None = None


@router.get("/chat-history", response_model=List[ChatHistoryItem])
async def list_chat_history(request: Request):
    """
    List all chat sessions with metadata for the current user.
    Returns sessions sorted by most recent first.
    """
    user_id = get_user_id_from_request(request)
    storage = get_storage()
    return storage.list_sessions(user_id)


@router.get("/chat-history/{session_id}", response_model=ChatSession)
async def get_chat_session(session_id: str, request: Request):
    """
    Get a specific chat session by ID for the current user.
    Returns full session with all messages.
    """
    user_id = get_user_id_from_request(request)
    storage = get_storage()
    session = storage.get_session(user_id, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


async def _process_untitled_sessions(user_id: str):
    """
    Background task to generate titles for sessions that don't have LLM-generated titles.

    When user creates a new chat, we generate titles for old sessions with at least 2 messages
    (1 complete exchange). This ensures even single-exchange chats get proper titles.
    """
    try:
        storage = get_storage()
        sessions = storage.list_sessions(user_id)

        untitled_count = 0
        for session_item in sessions:
            # Get full session to check title_generated flag
            session = storage.get_session(user_id, session_item.session_id)
            # Generate title if: not generated yet AND has at least 2 messages (1 exchange)
            if session and not session.title_generated and len(session.messages) >= 2:
                untitled_count += 1
                logger.info(f"Generating title for old session {session.session_id} ({len(session.messages)} messages)")

                # Generate title
                title = await generate_title_with_llm(session)
                session.title = title
                session.title_generated = True
                storage.update_session(user_id, session)

                logger.info(f"Generated title for old session {session.session_id}: {title}")

        if untitled_count > 0:
            logger.info(f"Processed {untitled_count} untitled sessions for user {user_id}")
        else:
            logger.debug(f"No untitled sessions to process for user {user_id}")

    except Exception as e:
        logger.error(f"Error processing untitled sessions: {str(e)}", exc_info=True)


@router.post("/chat-history", response_model=ChatSession)
async def create_chat_session(
    request_body: CreateSessionRequest,
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Create a new chat session for the current user.

    Also triggers background processing of any old sessions without LLM-generated titles.
    """
    user_id = get_user_id_from_request(request)
    storage = get_storage()
    session = storage.create_session(user_id, title=request_body.title)

    # Process old sessions without titles in the background
    background_tasks.add_task(_process_untitled_sessions, user_id)

    return session


@router.delete("/chat-history/{session_id}")
async def delete_chat_session(session_id: str, request: Request):
    """
    Delete a chat session for the current user.

    If this is the last session, automatically creates a new "New Chat" session
    to ensure there's always an active session available.
    """
    user_id = get_user_id_from_request(request)
    storage = get_storage()
    success = storage.delete_session(user_id, session_id)

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if this was the last session
    remaining_sessions = storage.list_sessions(user_id)
    new_session_id = None

    if len(remaining_sessions) == 0:
        # Create a new default session if list is empty
        logger.info(f"Last session deleted for user {user_id}, creating new default session")
        new_session = storage.create_session(user_id, title="New Chat")
        new_session_id = new_session.session_id
        logger.info(f"Created new default session: {new_session_id}")

    return {
        "success": True,
        "session_id": session_id,
        "new_session_id": new_session_id  # Will be None if there are remaining sessions
    }


@router.post("/generate-title", response_model=GenerateTitleResponse)
async def generate_session_title(request_body: GenerateTitleRequest, request: Request):
    """
    Generate a title for a chat session based on its messages.
    For now, uses simple logic: first 10 words of first user message.
    Future: Use LLM to generate meaningful titles.
    """
    user_id = get_user_id_from_request(request)
    storage = get_storage()
    session = storage.get_session(user_id, request_body.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Simple title generation: first 10 words of first user message
    title = "New Chat"
    if session.messages:
        first_user_msg = next(
            (msg for msg in session.messages if msg.role == "user"),
            None
        )
        if first_user_msg:
            words = first_user_msg.content.split()[:10]
            title = " ".join(words)
            if len(first_user_msg.content.split()) > 10:
                title += "..."

    # Update session title
    session.title = title
    storage.update_session(user_id, session)

    return GenerateTitleResponse(title=title)


async def _generate_title_background(user_id: str, session_id: str):
    """Background task to generate title for a session using LLM."""
    try:
        storage = get_storage()
        session = storage.get_session(user_id, session_id)

        if not session:
            logger.warning(f"Session {session_id} not found for title generation")
            return

        # Generate title using LLM
        title = await generate_title_with_llm(session)

        # Update session with generated title
        session.title = title
        session.title_generated = True
        storage.update_session(user_id, session)

        logger.info(f"Background title generation completed for session {session_id}: {title}")
    except Exception as e:
        logger.error(f"Error in background title generation for session {session_id}: {str(e)}", exc_info=True)


@router.post("/chat-history/{session_id}/messages", response_model=ChatSession)
async def append_chat_message(
    session_id: str,
    request_body: AddMessageRequest,
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Append a message to the specified chat session and return the updated session.

    Automatically triggers title generation after 4-5 messages if not already generated.
    """
    user_id = get_user_id_from_request(request)
    storage = get_storage()

    session = storage.get_session(user_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message = ChatMessage(
        role=request_body.role,
        content=request_body.content,
        timestamp=request_body.timestamp or datetime.utcnow(),
        tables=request_body.tables,
        attachments=request_body.attachments,
    )

    success = storage.add_message(user_id, session_id, message)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    updated_session = storage.get_session(user_id, session_id)
    if not updated_session:
        raise HTTPException(status_code=500, detail="Failed to load updated session")

    # Trigger title generation if:
    # 1. Title hasn't been generated yet
    # 2. Session has at least 4 messages (2 exchanges)
    if not updated_session.title_generated and len(updated_session.messages) >= 4:
        logger.info(f"Triggering background title generation for session {session_id}")
        background_tasks.add_task(_generate_title_background, user_id, session_id)

    return updated_session
