import os
import re
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
DB_PATH = Path("data/db/mediassist.db")


# ── Step A: Read the real schema from the database ───────────────────────────
def get_schema() -> str:
    """
    Introspect the database and return a human-readable schema string.
    This gets injected into the LLM prompt so it knows what tables exist.
    """
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]

    schema_parts = []
    for table in tables:
        cur.execute(f"PRAGMA table_info({table});")
        columns = cur.fetchall()
        col_str = ", ".join(f"{c[1]} ({c[2]})" for c in columns)

        # Add 2 sample rows so the LLM understands real values
        cur.execute(f"SELECT * FROM {table} LIMIT 2;")
        samples = cur.fetchall()

        schema_parts.append(
            f"Table: {table}\n"
            f"Columns: {col_str}\n"
            f"Sample rows: {samples}"
        )

    conn.close()
    return "\n\n".join(schema_parts)


_SCHEMA = get_schema()  # load once at startup


# ── Step 1: Natural language → SQL ───────────────────────────────────────────
def generate_sql(question: str) -> str:
    """Ask the LLM to convert a question into a SQL query."""

    prompt = f"""You are a SQL expert for a hospital database.
Given the schema below, write a SQLite query to answer the question.
Return ONLY the raw SQL statement — no explanation, no markdown, no code fences.

Schema:
{_SCHEMA}

Important notes:
- claims.status values: 'pending', 'approved', 'rejected', 'submitted', 'escalated'
- maintenance_tickets.status values: 'in_progress', 'resolved', 'escalated', 'open'
- Dates are stored as TEXT in format 'YYYY-MM-DD'
- Use SQLite syntax only

Question: {question}
SQL:"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


# ── Step 2: Extract clean SQL from LLM output ────────────────────────────────
def extract_sql(raw: str) -> str:
    """
    LLMs sometimes wrap SQL in markdown or add explanation text.
    This function extracts just the raw SQL statement.
    """
    # Remove markdown code fences: ```sql ... ``` or ``` ... ```
    raw = re.sub(r'```(?:sql)?', '', raw, flags=re.IGNORECASE)
    raw = raw.strip('`').strip()

    # Find the first line that starts a SQL statement
    lines = raw.splitlines()
    sql_lines = []
    in_sql = False

    for line in lines:
        if re.match(r'^\s*(SELECT|WITH|INSERT|UPDATE|DELETE)', line, re.IGNORECASE):
            in_sql = True
        if in_sql:
            sql_lines.append(line)

    sql = "\n".join(sql_lines) if sql_lines else raw
    return sql.strip().rstrip(';')


# ── Step 3: Execute SQL and get natural language answer ───────────────────────
def execute_and_answer(question: str, sql: str) -> str:
    """Run the SQL against the database, then ask LLM to explain the result."""

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cur.execute(sql)
        rows    = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
        conn.close()

        if not rows:
            result_str = "The query returned no results."
        else:
            # Format as readable table (max 50 rows)
            header = " | ".join(columns)
            divider = "-" * len(header)
            row_strs = [" | ".join(str(r[col]) for col in columns) for r in rows]
            result_str = "\n".join([header, divider] + row_strs[:50])
            if len(rows) > 50:
                result_str += f"\n... ({len(rows)} total rows, showing 50)"

    except Exception as e:
        return f"Database error: {e}\n\nSQL attempted: {sql}"

    # Ask LLM to turn the raw result into a clear answer
    answer_prompt = f"""You are MediBot, an assistant for MediAssist Health Network.
A user asked: "{question}"

The database returned this result:
{result_str}

Give a clear, concise natural language answer. Include specific numbers.
If the result is empty, say so clearly."""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": answer_prompt}],
        temperature=0.2,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


# ── Main chain: ties all 3 steps together ─────────────────────────────────────
def sql_rag_chain(question: str) -> str:
    """
    Three explicit steps:
    1. NL → SQL via LLM
    2. Clean the raw LLM output → extract bare SQL
    3. Execute SQL → NL answer via LLM
    """
    print(f"\n[SQL RAG] Question: {question}")

    # Step 1
    raw_sql = generate_sql(question)
    print(f"[SQL RAG] Raw LLM output: {raw_sql[:100]}")

    # Step 2
    clean_sql = extract_sql(raw_sql)
    print(f"[SQL RAG] Executing: {clean_sql}")

    # Step 3
    answer = execute_and_answer(question, clean_sql)
    return answer