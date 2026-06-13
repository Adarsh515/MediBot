import os
import uuid
import math
import re
from collections import Counter
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams,
    SparseVectorParams, SparseIndexParams,
    PointStruct, SparseVector,
)
from dotenv import load_dotenv

load_dotenv()  # loads OPENAI_API_KEY from your .env file

# ── Clients ───────────────────────────────────────────────
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
from dotenv import load_dotenv
load_dotenv()

qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

COLLECTION_NAME = "medibot_chunks"
EMBED_MODEL     = "text-embedding-3-small"
DENSE_DIM       = 3072  # dimension of text-embedding-3-small


# ── Step 1: Create the Qdrant collection ─────────────────
def create_collection():
    """
    Create a Qdrant collection that holds both dense and sparse vectors.
    Safe to call multiple times — skips if collection already exists.
    """
    if qdrant_client.collection_exists(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' already exists, skipping.")
        return

    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": VectorParams(
                size=DENSE_DIM,
                distance=Distance.COSINE
            )
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False)
            )
        },
    )
    print(f"✅ Collection '{COLLECTION_NAME}' created.")


# ── Step 2: Get dense embeddings from OpenAI ─────────────
from google import genai
from google.genai import types

# TO THIS:
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

import time

def get_embeddings(texts: list[str]) -> list[list[float]]:
    all_vectors = []
    for i, text in enumerate(texts):
        
        # Retry up to 3 times with a wait between attempts
        for attempt in range(3):
            try:
                result = gemini_client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                )
                all_vectors.append(result.embeddings[0].values)
                break  # success — exit retry loop
            except Exception as e:
                if attempt < 2:
                    print(f"  Retrying chunk {i+1} (attempt {attempt+2}/3)...")
                    time.sleep(5)  # wait 5 seconds before retrying
                else:
                    raise e  # give up after 3 attempts
        
        # Small delay between every call to avoid rate limiting
        time.sleep(0.5)
        
        if (i + 1) % 50 == 0:
            print(f"  Embedded {i+1}/{len(texts)} texts")
    
    return all_vectors


# ── Step 3: Build BM25 sparse vectors ────────────────────
def tokenize(text: str) -> list[str]:
    """Simple tokenizer — lowercase words only."""
    return re.findall(r'\b[a-z0-9][a-z0-9\-]*\b', text.lower())


def build_bm25_corpus(all_texts: list[str]):
    """
    Build BM25 vocabulary from ALL chunks combined.
    Must be called with the full corpus, not one document at a time.
    Returns (vocab, idf, avg_dl, tokenised_docs)
    """
    tokenised = [tokenize(t) for t in all_texts]
    N = len(tokenised)
    avg_dl = sum(len(d) for d in tokenised) / max(N, 1)

    # Count how many documents each term appears in
    doc_freq = Counter()
    for doc in tokenised:
        doc_freq.update(set(doc))  # set() so we count each term once per doc

    # IDF = how rare a term is across all documents
    # Rare terms get higher IDF scores — they're more distinctive
    idf = {
        term: math.log((N - freq + 0.5) / (freq + 0.5) + 1)
        for term, freq in doc_freq.items()
    }

    # Vocabulary: term → integer index (Qdrant sparse vectors use integer indices)
    vocab = {term: idx for idx, term in enumerate(sorted(idf.keys()))}

    return vocab, idf, avg_dl, tokenised


def compute_bm25_vector(
    tokens: list[str],
    vocab: dict,
    idf: dict,
    avg_dl: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> SparseVector:
    """
    Compute a BM25 sparse vector for one document.
    Returns a SparseVector with only non-zero term scores.
    """
    dl = len(tokens)
    tf = Counter(tokens)

    indices = []
    values = []

    for term, freq in tf.items():
        if term not in vocab or term not in idf:
            continue

        # BM25 formula
        score = idf[term] * (freq * (k1 + 1)) / (
            freq + k1 * (1 - b + b * dl / max(avg_dl, 1))
        )

        if score > 0:
            indices.append(vocab[term])
            values.append(float(score))

    return SparseVector(indices=indices, values=values)


# ── Step 4: Upsert chunks into Qdrant ────────────────────
def upsert_chunks(
    chunks: list[dict],
    access_roles: list[str],
    source_document: str,
    document_collection: str,
    vocab: dict,
    idf: dict,
    avg_dl: float,
    tokenised: list[list[str]],
    start_index: int,
):
    """
    Store a list of chunks into Qdrant with both vector types and metadata.
    """
    texts = [c["text"] for c in chunks]

    # Get dense vectors from OpenAI
    dense_vectors = get_embeddings(texts)

    # Build points list
    points = []
    for i, (chunk, dense_vec) in enumerate(zip(chunks, dense_vectors)):

        # BM25 sparse vector for this chunk
        tokens = tokenised[start_index + i]
        sparse_vec = compute_bm25_vector(tokens, vocab, idf, avg_dl)

        point = PointStruct(
            id=str(uuid.uuid4()),  # unique ID for each chunk
            vector={
                "dense":  dense_vec,
                "sparse": sparse_vec,
            },
            payload={
                "text":            chunk["text"],
                "source_document": source_document,
                "collection":      document_collection,
                "access_roles":    access_roles,
                "section_title":   chunk["section_title"],
                "chunk_type":      chunk["chunk_type"],
            },
        )
        points.append(point)

    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )
    print(f"  ✅ Stored {len(points)} chunks from '{source_document}'")
    

    from qdrant_client.models import (
    Distance, VectorParams,
    SparseVectorParams, SparseIndexParams,
    PointStruct, SparseVector,
    PayloadSchemaType,  # add this import
)

def create_collection():
    if qdrant_client.collection_exists(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' already exists, skipping.")
        # Still ensure the index exists even if collection was already there
        _create_payload_index()
        return

    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": VectorParams(
                size=DENSE_DIM,
                distance=Distance.COSINE
            )
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False)
            )
        },
    )
    print(f"✅ Collection '{COLLECTION_NAME}' created.")
    _create_payload_index()


def _create_payload_index():
    """Create a keyword index on the 'collection' field for RBAC filtering."""
    qdrant_client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="collection",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    print("✅ Payload index created on 'collection' field.")