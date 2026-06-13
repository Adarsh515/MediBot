import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter, FieldCondition, MatchAny,
    SparseVector, Prefetch, FusionQuery, Fusion,
)

load_dotenv()

# ── Clients ───────────────────────────────────────────────────────────────────
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

COLLECTION_NAME = "medibot_chunks"

# ── RBAC: role → allowed collections ─────────────────────────────────────────
ROLE_COLLECTIONS = {
    "doctor":            ["general", "clinical", "nursing"],
    "nurse":             ["general", "nursing"],
    "billing_executive": ["general", "billing"],
    "technician":        ["general", "equipment"],
    "admin":             ["general", "clinical", "nursing", "billing", "equipment"],
}


def get_allowed_collections(role: str) -> list[str]:
    if role not in ROLE_COLLECTIONS:
        raise ValueError(f"Unknown role: {role}")
    return ROLE_COLLECTIONS[role]


# ── BM25 vocab (saved during ingestion) ───────────────────────────────────────
_bm25_state = {}

def load_bm25_vocab():
    global _bm25_state
    if _bm25_state:
        return  # already loaded

    vocab_path = Path("backend/bm25_vocab.json")
    if not vocab_path.exists():
        raise FileNotFoundError(
            "backend/bm25_vocab.json not found. Run ingestion first."
        )
    with open(vocab_path) as f:
        _bm25_state = json.load(f)
    print(f"[Retriever] BM25 vocab loaded: {len(_bm25_state['vocab'])} terms")


def tokenize(text: str) -> list[str]:
    return re.findall(r'\b[a-z0-9][a-z0-9\-]*\b', text.lower())


def make_query_sparse_vector(query: str) -> SparseVector:
    """
    Build a BM25 sparse vector for the query.
    At query time we use TF=1 for each unique term — we just care
    about which terms appear in the query, weighted by their IDF.
    """
    load_bm25_vocab()
    vocab = _bm25_state["vocab"]
    idf   = _bm25_state["idf"]

    tokens = list(set(tokenize(query)))  # unique terms only
    indices = []
    values  = []

    for term in tokens:
        if term in vocab and term in idf:
            indices.append(vocab[term])
            values.append(float(idf[term]))

    # Fallback if no terms matched the vocab
    if not indices:
        indices, values = [0], [0.0001]

    return SparseVector(indices=indices, values=values)


def get_query_embedding(query: str) -> list[float]:
    """Convert query text to a dense vector using Gemini."""
    result = gemini_client.models.embed_content(
        model="gemini-embedding-001",
        contents=query,
    )
    return result.embeddings[0].values


def hybrid_search(query: str, role: str, top_k: int = 10) -> list[dict]:
    """
    Search Qdrant using both dense and BM25 sparse vectors simultaneously.
    RBAC filter applied INSIDE the Qdrant query — not in Python after the fact.

    Returns top_k candidate chunks.
    """
    # 1. Get allowed collections for this role
    allowed = get_allowed_collections(role)

    # 2. Build the RBAC filter
    #    This tells Qdrant: only return chunks where
    #    collection field is in the allowed list
    rbac_filter = Filter(
        must=[
            FieldCondition(
                key="collection",
                match=MatchAny(any=allowed),
            )
        ]
    )

    # 3. Build both vector types for the query
    dense_vector  = get_query_embedding(query)
    sparse_vector = make_query_sparse_vector(query)

    # 4. Query Qdrant with both vectors in ONE call
    #    Prefetch runs both searches internally
    #    FusionQuery(RRF) merges their rankings into one list
    results = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            Prefetch(
                query=dense_vector,
                using="dense",
                filter=rbac_filter,
                limit=top_k,
            ),
            Prefetch(
                query=sparse_vector,
                using="sparse",
                filter=rbac_filter,
                limit=top_k,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )

    # 5. Format results
    candidates = []
    for r in results.points:
        candidates.append({
            "text":            r.payload.get("text", ""),
            "source_document": r.payload.get("source_document", ""),
            "section_title":   r.payload.get("section_title", ""),
            "collection":      r.payload.get("collection", ""),
            "chunk_type":      r.payload.get("chunk_type", ""),
            "score":           r.score,
        })

    return candidates