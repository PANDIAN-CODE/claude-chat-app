"""
Standalone evaluation harness for the chat app's RAG + agent loop.

This is intentionally NOT a pytest test: it makes real calls to the Claude API
(both to generate answers and to judge them), so it costs real tokens every
time you run it. Run it manually when you want to measure answer quality,
not on every commit.

Usage:
    cd backend && venv\\Scripts\\activate
    cd ..\\eval
    python run_eval.py

Requires a real ANTHROPIC_API_KEY with credit in backend/.env.
"""

import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)  # so backend/.env is found by load_dotenv

from dotenv import load_dotenv  # noqa: E402

# load_dotenv() with no args locates .env via the caller's own file location
# (stack-frame inspection), not the cwd - since this script lives in eval/,
# not backend/, that silently finds nothing. Pass the path explicitly instead.
load_dotenv(dotenv_path=BACKEND_DIR / ".env")

import anthropic  # noqa: E402

from services.claude_service import MOCK_MODE, MODEL, run_agent_turn  # noqa: E402
from services.rag_service import rank_chunks  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"

JUDGE_PROMPT = """You are grading a chatbot's answer against a reference answer.

Question: {question}
Reference answer: {reference_answer}
Chatbot's answer: {actual_answer}

Score the chatbot's answer from 1-5:
5 = fully correct and matches the reference answer's meaning
3 = partially correct or missing some detail
1 = wrong or irrelevant

Respond with ONLY a JSON object: {{"score": <1-5>, "reason": "<one sentence>"}}"""


def load_dataset() -> dict:
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


def make_search_fn(all_chunks: list[dict]):
    def search_fn(query: str) -> list[dict]:
        return rank_chunks(query, all_chunks)

    return search_fn


def judge_answer(client: anthropic.Anthropic, question: str, reference: str, actual: str) -> dict:
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": JUDGE_PROMPT.format(
                        question=question, reference_answer=reference, actual_answer=actual
                    ),
                }
            ],
        )
    except anthropic.APIError as e:
        return {"score": 0, "reason": f"Judge call failed: {e}"}

    text = "".join(b.text for b in response.content if b.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"score": 0, "reason": f"Judge returned unparseable output: {text[:200]}"}


def run() -> None:
    if MOCK_MODE:
        print(
            "ANTHROPIC_API_KEY is not set (or is the placeholder) in backend/.env.\n"
            "This eval needs a real, funded API key to generate and judge answers - "
            "mock mode would just produce canned text with nothing to grade."
        )
        return

    dataset = load_dataset()
    all_chunks = dataset["document_chunks"]
    search_fn = make_search_fn(all_chunks)
    judge_client = anthropic.Anthropic()

    results = []
    print(f"Running {len(dataset['questions'])} eval cases against model: {MODEL}\n")

    for case in dataset["questions"]:
        history = [{"role": "user", "content": case["question"]}]
        chunks, citations, usage = run_agent_turn(history, search_fn)
        answer = "".join(chunks).strip()

        cited_filenames = {c["filename"] for c in citations}
        citation_correct = (
            not case["expects_citation"]
            or case["expected_filename"] in cited_filenames
        )

        judged = judge_answer(judge_client, case["question"], case["reference_answer"], answer)

        results.append(
            {
                "question": case["question"],
                "answer": answer,
                "score": judged.get("score", 0),
                "reason": judged.get("reason", ""),
                "citation_correct": citation_correct,
                "cost_usd": usage["cost_usd"],
            }
        )

        print(f"Q: {case['question']}")
        print(f"A: {answer}")
        print(f"Score: {judged.get('score')}/5 - {judged.get('reason')}")
        print(f"Citation correct: {citation_correct}")
        print(f"Cost: ${usage['cost_usd']:.6f}\n")

    avg_score = sum(r["score"] for r in results) / len(results)
    citation_accuracy = sum(r["citation_correct"] for r in results) / len(results)
    total_cost = sum(r["cost_usd"] for r in results)

    print("=" * 50)
    print(f"Average answer quality: {avg_score:.2f}/5")
    print(f"Citation accuracy: {citation_accuracy:.0%}")
    print(f"Total eval cost: ${total_cost:.6f} (generation + judging)")


if __name__ == "__main__":
    run()
