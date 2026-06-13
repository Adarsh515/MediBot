ROLE_COLLECTIONS = {
    "doctor":            ["general", "clinical", "nursing"],
    "nurse":             ["general", "nursing"],
    "billing_executive": ["general", "billing"],
    "technician":        ["general", "equipment"],
    "admin":             ["general", "clinical", "nursing", "billing", "equipment"],
}

SQL_RAG_ROLES = {"billing_executive", "admin"}

def get_allowed_collections(role: str) -> list[str]:
    if role not in ROLE_COLLECTIONS:
        raise ValueError(f"Unknown role: '{role}'")
    return ROLE_COLLECTIONS[role]

def can_use_sql_rag(role: str) -> bool:
    return role in SQL_RAG_ROLES