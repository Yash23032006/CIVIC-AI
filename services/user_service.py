
from config import supabase


def load_users():
    """Load citizen accounts from Supabase."""
    result = (
        supabase.table("citizen_users")
        .select("id, name, email, mobile, password_hash")
        .execute()
    )

    return [
        {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "mobile": user["mobile"],
            "password": user["password_hash"],
        }
        for user in (result.data or [])
    ]


def save_users(users):
    """
    Kept for compatibility with existing code.
    Citizen registration should use insert/upsert operations
    directly rather than rewriting the entire user list.
    """
    raise RuntimeError(
        "Bulk user-file saving is disabled. "
        "Use Supabase insert for new citizen accounts."
    )