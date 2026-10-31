from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user
from database import get_db
from services.rag_service import chunk_text, extract_text_from_pdf

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("", response_model=list[schemas.DocumentOut])
def list_documents(
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.Document)
        .filter(models.Document.user_id == user.id)
        .order_by(models.Document.id.desc())
        .all()
    )


@router.post("/upload", response_model=schemas.DocumentOut)
async def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    text = extract_text_from_pdf(contents)
    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Could not extract any text from this PDF")

    document = models.Document(user_id=user.id, filename=file.filename)
    db.add(document)
    db.commit()
    db.refresh(document)

    for i, chunk in enumerate(chunks):
        db.add(models.DocumentChunk(document_id=document.id, chunk_index=i, content=chunk))
    db.commit()

    return document


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.user_id == user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    db.delete(document)
    db.commit()
