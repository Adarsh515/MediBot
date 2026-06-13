from backend.sql_rag.sql_chain import sql_rag_chain

questions = [
    "How many escalated claims are there?",
    "What is the total claimed amount by department?",
    "How many open maintenance tickets are there per campus?",
    "Which insurer has the highest total claimed amount?",
]

for q in questions:
    print("\n" + "=" * 60)
    print(f"Q: {q}")
    print("=" * 60)
    answer = sql_rag_chain(q)
    print(f"A: {answer}")