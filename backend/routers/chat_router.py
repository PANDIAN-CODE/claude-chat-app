import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

import models
import schemas
from auth import get_current_user
from database import get_db
from services.claude_service import run_agent_turn
from services.rag_service import retrieve_relevant_chunks

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/conversations", response_model=list[schemas.ConversationOut])
def list_conversations(
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == user.id)
        .order_by(models.Conversation.id.desc())
        .all()
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[schemas.MessageOut])
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    conv = (
        db.query(models.Conversation)
        .filter(models.Conversation.id == conversation_id, models.Conversation.user_id == user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.messages


def _persist_assistant_reply(conversation_id: int, generator, bind):
    full_text = ""
    try:
        for chunk in generator:
            full_text += chunk
            yield chunk
    finally:
        session = sessionmaker(bind=bind)()
        try:
            session.add(
                models.Message(conversation_id=conversation_id, role="assistant", content=full_text)
            )
            session.commit()
        finally:
            session.close()


@router.post("/stream")
def chat_stream(
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if payload.conversation_id:
        conv = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.id == payload.conversation_id,
                models.Conversation.user_id == user.id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = models.Conversation(user_id=user.id, title=payload.message[:40])
        db.add(conv)
        db.commit()
        db.refresh(conv)

    db.add(models.Message(conversation_id=conv.id, role="user", content=payload.message))
    db.commit()
    db.refresh(conv)

    history = [{"role": m.role, "content": m.content} for m in conv.messages]

    def search_fn(query: str) -> list[dict]:
        return retrieve_relevant_chunks(db, user.id, query)

    # Agent loop: Claude itself decides whether this question needs a document
    # search (calling the search_documents tool), executes it, and only then
    # produces its final answer - rather than us always injecting context.
    text_chunks, citations = run_agent_turn(history, search_fn)

    generator = _persist_assistant_reply(conv.id, text_chunks, db.get_bind())

    return StreamingResponse(
        generator,
        media_type="text/plain",
        headers={
            "X-Conversation-Id": str(conv.id),
            "X-Citations": json.dumps(citations),
        },
    )
