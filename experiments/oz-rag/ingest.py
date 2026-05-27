"""
Ingest EIP standard documents (the standards OpenZeppelin implements) into ChromaDB.

Usage:
    python ingest.py
"""

import re
import time
import requests
import chromadb
from sentence_transformers import SentenceTransformer

# EIPs that correspond to core OpenZeppelin contracts
EIPS = {
    "20":   "ERC-20: Token Standard",
    "165":  "ERC-165: Standard Interface Detection",
    "721":  "ERC-721: Non-Fungible Token Standard",
    "1155": "ERC-1155: Multi Token Standard",
    "1167": "ERC-1167: Minimal Proxy Contract",
    "1967": "ERC-1967: Standard Proxy Storage Slots",
    "2612": "ERC-2612: Permit Extension for ERC-20 Signed Approvals",
    "4626": "ERC-4626: Tokenized Vault Standard",
    "712":  "EIP-712: Typed Structured Data Hashing and Signing",
    "2981": "ERC-2981: NFT Royalty Standard",
    "4337": "ERC-4337: Account Abstraction Using Alt Mempool",
}

# ERCs moved to ethereum/ERCs repo; EIPs (non-ERC) stay in ethereum/EIPs
ERC_URL = "https://raw.githubusercontent.com/ethereum/ERCs/master/ERCS/erc-{}.md"
EIP_URL = "https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-{}.md"

# Numbers that are EIPs (not ERCs)
NON_ERC = {"712", "1167", "1967", "4337"}


def fetch_eip(number: str) -> str | None:
    url = EIP_URL.format(number) if number in NON_ERC else ERC_URL.format(number)
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        text = r.text
        # Skip redirect stubs
        if "This file was moved" in text or len(text.strip()) < 200:
            # Try the other repo as fallback
            fallback = ERC_URL.format(number) if number in NON_ERC else EIP_URL.format(number)
            r2 = requests.get(fallback, timeout=15)
            r2.raise_for_status()
            text = r2.text
        return text
    except Exception as e:
        print(f"  [skip] EIP-{number}: {e}")
        return None


def chunk_by_sections(text: str, eip_number: str, eip_title: str) -> list[dict]:
    """Split markdown by ## headings; keep heading inside each chunk."""
    chunks = []
    # Split on level-2 headings (keep the heading line)
    parts = re.split(r"\n(?=## )", text)

    for part in parts:
        part = part.strip()
        if len(part) < 80:
            continue

        first_line = part.splitlines()[0].strip()
        if first_line.startswith("##"):
            section = first_line.lstrip("#").strip()
        else:
            section = "Preamble"

        chunks.append({
            "content": part,
            "eip_number": eip_number,
            "eip_title": eip_title,
            "section": section,
            "source_url": f"https://eips.ethereum.org/EIPS/eip-{eip_number}",
        })

    return chunks


def main():
    print("Loading embedding model (first run downloads ~90 MB)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        client.delete_collection("eip-docs")
        print("Cleared existing collection.")
    except Exception:
        pass
    collection = client.create_collection(
        "eip-docs",
        metadata={"hnsw:space": "cosine"},
    )

    all_chunks: list[dict] = []

    for number, title in EIPS.items():
        print(f"Fetching EIP-{number}: {title}...")
        text = fetch_eip(number)
        if not text:
            continue
        chunks = chunk_by_sections(text, number, title)
        all_chunks.extend(chunks)
        print(f"  {len(chunks)} chunks")
        time.sleep(0.3)

    print(f"\nTotal: {len(all_chunks)} chunks across {len(EIPS)} EIPs")
    print("Embedding (this takes ~30s on CPU)...")

    texts = [c["content"] for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    collection.add(
        ids=[f"chunk_{i}" for i in range(len(all_chunks))],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {
                "eip_number": c["eip_number"],
                "eip_title": c["eip_title"],
                "section": c["section"],
                "source_url": c["source_url"],
            }
            for c in all_chunks
        ],
    )

    print(f"\nDone. {len(all_chunks)} chunks stored in ./chroma_db")
    print("Run query.py to start asking questions.")


if __name__ == "__main__":
    main()
