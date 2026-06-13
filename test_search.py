from backend.retrieval.retriever import hybrid_search

# Test 1 — Doctor asking a clinical question
print("=" * 60)
print("ROLE: doctor | QUERY: first line treatment for diabetes")
print("=" * 60)
results = hybrid_search(
    query="first line treatment for diabetes",
    role="doctor",
    top_k=5,
)
for i, r in enumerate(results, 1):
    print(f"\n#{i} [{r['collection']}] {r['source_document']}")
    print(f"    Section: {r['section_title']}")
    print(f"    Score:   {r['score']:.4f}")
    print(f"    Preview: {r['text'][:120]}...")

# Test 2 — RBAC test: nurse asking about billing
print("\n" + "=" * 60)
print("ROLE: nurse | QUERY: insurance billing codes")
print("=" * 60)
results = hybrid_search(
    query="insurance billing codes",
    role="nurse",
    top_k=5,
)
for i, r in enumerate(results, 1):
    print(f"\n#{i} [{r['collection']}] {r['source_document']}")
    print(f"    Section: {r['section_title']}")

    from backend.retrieval.reranker import rerank

print("\n" + "=" * 60)
print("RERANKING TEST")
print("=" * 60)

query = "first line treatment for diabetes"
candidates = hybrid_search(query=query, role="doctor", top_k=10)

print(f"\nBefore reranking — top 5 from hybrid search:")
for i, r in enumerate(candidates[:5], 1):
    print(f"  #{i} {r['source_document']} | {r['section_title'][:50]}")

top_chunks = rerank(query=query, candidates=candidates, top_n=3)

print(f"\nAfter reranking — top 3 passed to LLM:")
for i, r in enumerate(top_chunks, 1):
    print(f"  #{i} score={r['rerank_score']:.1f} | "
          f"{r['source_document']} | {r['section_title'][:50]}")