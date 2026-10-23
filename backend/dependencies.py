
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from supabase_client import get_supabase_client

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in.",
        )

    token = credentials.credentials
    supabase = get_supabase_client()

    try:
        response = supabase.auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid access token.")

        return {
            "id": str(response.user.id),
            "email": response.user.email,
            "metadata": response.user.user_metadata or {},
            "token": token,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Your session is invalid or expired. Please log in again.",
        )


def get_user_supabase(
    user: dict = Depends(get_current_user),
) -> Client:
    supabase = get_supabase_client()
    supabase.postgrest.auth(user["token"])
    return supabase
