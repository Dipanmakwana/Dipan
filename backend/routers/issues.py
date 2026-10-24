
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_current_user, get_user_supabase
from schemas.issues import CreateIssueRequest

router = APIRouter(prefix="/issues", tags=["Issues"])

VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}


@router.post("", status_code=201)
def create_issue(
    payload: CreateIssueRequest,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    issue_data = payload.model_dump()
    issue_data["user_id"] = user["id"]
    issue_data["status"] = "open"

    try:
        response = supabase.table("issues").insert(issue_data).execute()
        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="The issue could not be created.",
            )

        return {
            "success": True,
            "message": "Issue reported successfully.",
            "issue": response.data[0],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to create the issue. Please try again.",
        )


@router.get("/mine")
def get_my_issues(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail="Invalid status filter.",
        )

    try:
        query = (
            supabase.table("issues")
            .select("*", count="exact")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if status is not None:
            query = query.eq("status", status)

        response = query.execute()

        return {
            "success": True,
            "issues": response.data or [],
            "count": response.count or 0,
            "limit": limit,
            "offset": offset,
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve your issues. Please try again.",
        )
