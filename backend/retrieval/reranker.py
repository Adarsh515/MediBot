import os
import json
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def score_chunk(query: str, chunk_text: str) -> float:
    """
    Score how well a chunk answers the query.
    Groq reads BOTH query and chunk together — joint scoring.
    Returns float 0.0 to 10.0.
    """
    prompt = f"""You are a relevance scoring engine for a medical knowledge base.
Score how well the passage below answers the query.

Query: {query}

Passage:
{chunk_text[:600]}

Rules:
- Score 9-10: passage directly and completely answers the query
- Score 6-8:  passage is clearly relevant and partially answers it  
- Score 3-5:  passage is related to the topic but doesn't answer directly
- Score 0-2:  passage is unrelated or barely relevant

Respond with ONLY a JSON object like this: {{"score": 7.5}}
No explanation. Just the JSON."""

    for attempt in range(3):
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=20,
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            return float(data.get("score", 0))

        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                print(f"  [Reranker] Failed to score chunk: {e}")
                return 0.0


def rerank(query: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
    """
    Score all candidates against the query, return top_n.
    Only top_n results go to the LLM — not the full candidate set.
    """
    print(f"\n[Reranker] Scoring {len(candidates)} candidates...")

    for candidate in candidates:
        candidate["rerank_score"] = score_chunk(query, candidate["text"])

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

    print("\n[Reranker] Scores (high → low):")
    for i, r in enumerate(ranked):
        marker = "✅" if i < top_n else "  "
        print(f"  {marker} #{i+1} score={r['rerank_score']:.1f} | "
              f"{r['source_document']} | {r['section_title'][:50]}")

    return ranked[:top_n]