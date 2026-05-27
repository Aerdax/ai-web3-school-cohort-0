"""
Query the EIP knowledge base with structured output.

Usage:
    python query.py "How does ERC-20 approve work?"
    python query.py   # interactive mode
"""

import json
import sys
import chromadb
from groq import Groq
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import pathlib

_env = pathlib.Path(__file__).parent / ".env"
load_dotenv(_env)

SYSTEM_PROMPT = """\
You are a Web3 protocol documentation assistant. Answer questions based ONLY on the \
documentation chunks provided. Do not use any training knowledge beyond what is shown.

Respond with valid JSON only — no markdown fences, no extra text:
{
  "answer": "<answer based on docs, or null if not found>",
  "sources": ["EIP-XX | Section Name", ...],
  "uncertainties": ["<anything unclear or missing from the docs>"],
  "needs_version_check": <true if version-specific, otherwise false>
}

Rules:
- If the question cannot be answered from the provided chunks, set "answer" to null.
- Always list the EIP number and section for every claim in "answer".
- Set "needs_version_check" to true if the answer depends on a specific contract version \
or the docs contain version warnings.
- Never fabricate facts not present in the chunks.\
"""


def build_context(docs: list[str], metas: list[dict]) -> str:
    parts = []
    for doc, meta in zip(docs, metas):
        header = f"[EIP-{meta['eip_number']} | {meta['section']} | {meta['source_url']}]"
        parts.append(f"{header}\n{doc[:1000]}")
    return "\n\n---\n\n".join(parts)


def query(question: str, collection, model: SentenceTransformer, top_k: int = 5) -> dict:
    embedding = model.encode([question]).tolist()

    results = collection.query(
        query_embeddings=embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    context = build_context(docs, metas)

    user_message = f"Documentation chunks:\n\n{context}\n\nQuestion: {question}"

    ai = Groq()
    response = ai.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    raw = response.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "answer": raw,
            "sources": [],
            "uncertainties": ["Response was not valid JSON"],
            "needs_version_check": False,
        }


def print_result(result: dict) -> None:
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    print("Loading model and vector DB...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        collection = client.get_collection("eip-docs")
    except Exception:
        print("Error: knowledge base not found. Run ingest.py first.")
        sys.exit(1)

    print(f"Ready. Collection has {collection.count()} chunks.\n")

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print_result(query(question, collection, model))
        return

    print("EIP / OpenZeppelin RAG — type 'quit' to exit\n")
    while True:
        try:
            q = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("quit", "exit", "q"):
            break
        if not q:
            continue
        print()
        print_result(query(q, collection, model))
        print()


if __name__ == "__main__":
    main()
