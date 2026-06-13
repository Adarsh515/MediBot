import json
import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from backend.ingestion.chunker import build_chunks
from backend.ingestion.indexer import (
    create_collection,
    build_bm25_corpus,
    upsert_chunks,
    COLLECTION_NAME,
)

load_dotenv()

qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

COLLECTION_ROLES = {
    "general":   ["doctor", "nurse", "billing_executive", "technician", "admin"],
    "clinical":  ["doctor", "admin"],
    "nursing":   ["nurse", "doctor", "admin"],
    "billing":   ["billing_executive", "admin"],
    "equipment": ["technician", "admin"],
}

DATA_ROOT = Path("data")


def run():
    print("\n🔧 Starting MediBot ingestion...\n")

    # ── Phase 1: Parse and chunk all documents ────────────
    print("Phase 1: Parsing all documents...")
    all_records = []

    for collection, roles in COLLECTION_ROLES.items():
        folder = DATA_ROOT / collection
        if not folder.exists():
            continue

        for file in sorted(folder.iterdir()):
            if file.suffix.lower() not in (".pdf", ".md"):
                continue

            print(f"  Parsing {file.name}...")
            chunks = build_chunks(str(file))
            print(f"    → {len(chunks)} chunks")

            for chunk in chunks:
                all_records.append({
                    **chunk,
                    "_source": file.name,
                    "_collection": collection,
                    "_roles": roles,
                })

    print(f"\n  Total chunks: {len(all_records)}")

    # ── Phase 2: Build BM25 vocab from full corpus ────────
    print("\nPhase 2: Building BM25 vocabulary...")
    all_texts = [r["text"] for r in all_records]
    vocab, idf, avg_dl, tokenised = build_bm25_corpus(all_texts)
    print(f"  Vocabulary size: {len(vocab)} unique terms")

    vocab_data = {"vocab": vocab, "idf": idf, "avg_dl": avg_dl}
    with open("backend/bm25_vocab.json", "w") as f:
        json.dump(vocab_data, f)
    print("  BM25 vocab saved to backend/bm25_vocab.json")

    # ── Phase 3: Create collection and upsert ────────────
    print("\nPhase 3: Indexing into Qdrant...")
    create_collection()

    # Group chunks by source document
    grouped = {}
    for i, rec in enumerate(all_records):
        key = (rec["_source"], rec["_collection"], tuple(rec["_roles"]))
        if key not in grouped:
            grouped[key] = []
        grouped[key].append((i, rec))

    # Upsert each document's chunks — skip if already stored
    for (source, collection, roles), indexed in grouped.items():

        # Check if this file was already indexed
        try:
            existing = qdrant_client.count(
                collection_name=COLLECTION_NAME,
                count_filter=Filter(
                    must=[FieldCondition(
                        key="source_document",
                        match=MatchValue(value=source)
                    )]
                )
            )
            if existing.count > 0:
                print(f"  Skipping '{source}' — already indexed ({existing.count} chunks)")
                continue
        except Exception:
            pass  # if count fails, just try to upsert anyway

        indices = [i for i, _ in indexed]
        chunks  = [rec for _, rec in indexed]

        upsert_chunks(
            chunks=chunks,
            access_roles=list(roles),
            source_document=source,
            document_collection=collection,
            vocab=vocab,
            idf=idf,
            avg_dl=avg_dl,
            tokenised=tokenised,
            start_index=indices[0],
        )

    print(f"\n✅ Ingestion complete! {len(all_records)} chunks processed.")
    print("Check your Qdrant dashboard to verify point count.")


if __name__ == "__main__":
    run()