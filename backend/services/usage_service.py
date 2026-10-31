from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models

# Guardrail against runaway cost / abuse: cap how many messages one user can
# send in a rolling window. Deliberately generous for a demo app - tune down
# for anything production-facing.
RATE_LIMIT_MAX_MESSAGES = 20
RATE_LIMIT_WINDOW_MINUTES = 10


def enforce_rate_limit(db: Session, user_id: int) -> None:
    window_start = datetime.now(timezone.utc) - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)

    recent_count = (
        db.query(models.Message)
        .join(models.Conversation, models.Message.conversation_id == models.Conversation.id)
        .filter(
            models.Conversation.user_id == user_id,
            models.Message.role == "user",
            models.Message.created_at >= window_start,
        )
        .count()
    )

    if recent_count >= RATE_LIMIT_MAX_MESSAGES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded: max {RATE_LIMIT_MAX_MESSAGES} messages per "
                f"{RATE_LIMIT_WINDOW_MINUTES} minutes. Please wait before sending more."
            ),
        )


def record_usage(
    db: Session,
    user_id: int,
    conversation_id: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    db.add(
        models.UsageLog(
            user_id=user_id,
            conversation_id=conversation_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
    )
    db.commit()
