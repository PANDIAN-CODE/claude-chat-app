from io import BytesIO

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

import models

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
TOP_K = 4
MIN_SIMILARITY = 0.05


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def retrieve_relevant_chunks(db: Session, user_id: int, query: str, top_k: int = TOP_K) -> list[dict]:
    rows = (
        db.query(models.DocumentChunk, models.Document.filename, models.Document.id)
        .join(models.Document, models.DocumentChunk.document_id == models.Document.id)
        .filter(models.Document.user_id == user_id)
        .all()
    )
    if not rows:
        return []

    contents = [row[0].content for row in rows]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(contents + [query])

    query_vector = matrix[-1]
    chunk_vectors = matrix[:-1]
    scores = cosine_similarity(query_vector, chunk_vectors)[0]

    ranked = sorted(zip(scores, rows), key=lambda pair: pair[0], reverse=True)
    results = []
    for score, (chunk, filename, document_id) in ranked[:top_k]:
        if score < MIN_SIMILARITY:
            continue
        results.append(
            {
                "content": chunk.content,
                "filename": filename,
                "document_id": document_id,
                "score": float(score),
            }
        )
    return results


def build_rag_system_prompt(chunks: list[dict]) -> str:
    if not chunks:
        return ""

    excerpts = "\n\n".join(
        f"[Source: {c['filename']}]\n{c['content']}" for c in chunks
    )
    return (
        "\n\nUse the following document excerpts to answer the user's question if "
        "relevant. Cite the source filename in your answer when you use one. If the "
        "excerpts don't contain the answer, say so and answer from general knowledge "
        f"instead.\n\n{excerpts}"
    )
