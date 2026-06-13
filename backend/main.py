import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from dotenv import load_dotenv
from groq import Groq

from backend.retrieval.retriever import hybrid_search
from backend.retrieval.reranker import rerank
from backend.retrieval.rbac import get_allowed_collections, can_use_sql_rag
from backend.sql_rag.sql_chain import sql_rag_chain

load_dotenv()

app = FastAPI(title="MediBot API")

# Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth setup ────────────────────────────────────────────────────────────────
SECRET_KEY  = os.getenv("JWT_SECRET", "medibot-secret-key")
ALGORITHM   = "HS256"
EXPIRE_MINS = 480

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Demo users — matches assignment credentials exactly
USERS = {
    "dr.mehta":     {"password": "doctor",            "role": "doctor"},
    "nurse.priya":  {"password": "nurse",             "role": "nurse"},
    "billing.ravi": {"password": "billing_executive", "role": "billing_executive"},
    "tech.anand":   {"password": "technician",        "role": "technician"},
    "admin.sys":    {"password": "admin",             "role": "admin"},
}

# ── LLM for final answer generation ──────────────────────────────────────────
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Pydantic schemas ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    question: str
    role: str
    token: str

class SourceItem(BaseModel):
    source_document: str
    section_title: str
    collection: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    retrieval_type: str
    role: str

# ── Helper: detect analytical questions ──────────────────────────────────────
ANALYTICAL_KEYWORDS = [
    "how many", "count", "total", "sum", "average",
    "list all claims", "list all tickets",
    "last month", "this year", "escalated claims",
    "pending claims", "open tickets", "by department",
    "by insurer", "by campus", "which insurer", "which department",
]

def is_analytical(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in ANALYTICAL_KEYWORDS)

# ── Helper: create and decode JWT tokens ──────────────────────────────────────
def create_token(username: str, role: str) -> str:
    payload = {
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

# ── /health ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "MediBot API"}

# ── /login ────────────────────────────────────────────────────────────────────
@app.post("/login")
def login(req: LoginRequest):
    user = USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_token(req.username, user["role"])
    collections = get_allowed_collections(user["role"])

    return {
        "token": token,
        "role": user["role"],
        "username": req.username,
        "accessible_collections": collections,
    }

# ── /collections/{role} ───────────────────────────────────────────────────────
@app.get("/collections/{role}")
def get_collections(role: str):
    try:
        collections = get_allowed_collections(role)
        return {
            "role": role,
            "collections": collections,
            "sql_rag_access": can_use_sql_rag(role),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ── /chat ─────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):

    # 1. Validate JWT — always done server-side
    try:
        claims = decode_token(req.token)
        role = claims["role"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    question = req.question.strip()

    # 2. SQL RAG branch
    if is_analytical(question):
        if not can_use_sql_rag(role):
            allowed = get_allowed_collections(role)
            return ChatResponse(
                answer=f"As a {role}, you do not have access to analytical "
                       f"database queries. I can only answer questions from "
                       f"the following collections: {', '.join(allowed)}.",
                sources=[],
                retrieval_type="rbac_blocked",
                role=role,
            )
        answer = sql_rag_chain(question)
        return ChatResponse(
            answer=answer,
            sources=[],
            retrieval_type="sql_rag",
            role=role,
        )

    # 3. Hybrid RAG branch
    # RBAC filter applied inside hybrid_search at Qdrant level
    candidates = hybrid_search(query=question, role=role, top_k=10)

    if not candidates:
        allowed = get_allowed_collections(role)
        return ChatResponse(
            answer=f"I could not find relevant information in your accessible "
                   f"collections: {', '.join(allowed)}.",
            sources=[],
            retrieval_type="hybrid_rag",
            role=role,
        )

    # 4. Rerank: top-10 → top-3
    top_chunks = rerank(query=question, candidates=candidates, top_n=3)

    # 5. Build LLM prompt from top-3 chunks only
    context = "\n\n---\n\n".join(
        f"[Source: {c['source_document']} | Section: {c['section_title']}]\n{c['text']}"
        for c in top_chunks
    )

    allowed = get_allowed_collections(role)
    system_prompt = (
        f"You are MediBot, an internal assistant for MediAssist Health Network.\n"
        f"The user's role is '{role}' with access to: {', '.join(allowed)}.\n"
        f"Answer using ONLY the provided context. Be precise with doses, "
        f"protocols, and clinical values. Always mention your source document.\n"
        f"If the context doesn't contain enough information, say so clearly."
    )

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0.1,
        max_tokens=500,
    )

    answer = response.choices[0].message.content.strip()
    sources = [
        SourceItem(
            source_document=c["source_document"],
            section_title=c["section_title"],
            collection=c["collection"],
        )
        for c in top_chunks
    ]

    return ChatResponse(
        answer=answer,
        sources=sources,
        retrieval_type="hybrid_rag",
        role=role,
    )