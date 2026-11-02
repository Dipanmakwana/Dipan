
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from config import settings
from schemas.auth import (
    LoginRequest,
    ResendOTPRequest,
    SignupRequest,
    VerifyOTPRequest,
)
from dependencies import get_current_user
from supabase_client import get_supabase_client

router = APIRouter(prefix="/auth", tags=["Authentication"])


def validate_institute_email(email: str):
    domain = settings.allowed_email_domain.strip().lower().lstrip("@")
    if email.rsplit("@", 1)[-1].lower() != domain:
        raise HTTPException(
            status_code=400,
            detail=f"Use an email address ending in @{domain}",
        )


def load_profile(user_id: str) -> dict:
    """Role + campus details from public.profiles (the source of truth, NOT user_metadata).

    Uses a fresh service-role client, so it works right after sign-in and is not
    affected by RLS. Returns {} if the profile row is missing.
    """
    client = get_supabase_client()
    try:
        rows = (
            client.table("profiles")
            .select("full_name, roll_number, building_id, role")
            .eq("id", str(user_id))
            .limit(1)
            .execute()
        ).data or []
    except Exception:
        return {}
    if not rows:
        return {}

    profile = rows[0]
    profile["building_name"] = None
    if profile.get("building_id"):
        try:
            building = (
                client.table("buildings")
                .select("name")
                .eq("id", profile["building_id"])
                .limit(1)
                .execute()
            ).data or []
            profile["building_name"] = building[0]["name"] if building else None
        except Exception:
            pass
    return profile


def user_payload(user_id, email, metadata: dict | None) -> dict:
    """User object returned to the app. role/profile come from public.profiles."""
    metadata = metadata or {}
    profile = load_profile(user_id)
    return {
        "id": str(user_id),
        "email": email,
        "user_metadata": metadata,
        "role": profile.get("role") or "student",
        "full_name": profile.get("full_name") or metadata.get("full_name", ""),
        "roll_number": profile.get("roll_number") or metadata.get("roll_number"),
        "building_id": profile.get("building_id") or metadata.get("building_id"),
        "building_name": profile.get("building_name"),
    }


def session_response(session, user):
    return {
        "success": True,
        "user": user_payload(user.id, user.email, user.user_metadata),
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": session.token_type,
        "expires_in": session.expires_in,
    }


@router.get("/buildings")
def public_buildings():
    """Building list for the signup screen (no login needed; buildings are public)."""
    try:
        rows = (
            get_supabase_client().table("buildings").select("id, name, zone").order("name").execute()
        ).data or []
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to load buildings. Please try again.")
    return {"success": True, "buildings": rows}


@router.post("/signup")
def signup(payload: SignupRequest):
    validate_institute_email(str(payload.email))
    supabase = get_supabase_client()

    try:
        response = supabase.auth.sign_up({
            "email": str(payload.email),
            "password": payload.password,
            "options": {
                "email_redirect_to": "http://localhost:8000/api/auth/verified",
                "data": {
                    "full_name": payload.full_name.strip(),
                    "roll_number": payload.roll_number.strip() if payload.roll_number else None,
                    "building_id": payload.building_id.strip() if payload.building_id else None,
                    "role": "student",
                }
            },
        })

        return {
            "success": True,
            "message": "If registration succeeds, check your email for the verification code.",
            "user_id": response.user.id if response.user else None,
            "requires_email_verification": True,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/verify-otp")
def verify_otp(payload: VerifyOTPRequest):
    validate_institute_email(str(payload.email))
    supabase = get_supabase_client()

    try:
        response = supabase.auth.verify_otp({
            "email": str(payload.email),
            "token": payload.token,
            "type": "signup",
        })

        if not response.user or not response.session:
            raise HTTPException(
                status_code=400,
                detail="Verification did not return an active session",
            )

        return session_response(response.session, response.user)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/resend-otp")
def resend_otp(payload: ResendOTPRequest):
    validate_institute_email(str(payload.email))
    supabase = get_supabase_client()

    try:
        supabase.auth.resend({
            "type": "signup",
            "email": str(payload.email),
        })

        return {
            "success": True,
            "message": "If the account is eligible, a new verification code will be sent.",
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/login")
def login(payload: LoginRequest):
    validate_institute_email(str(payload.email))
    supabase = get_supabase_client()

    try:
        response = supabase.auth.sign_in_with_password({
            "email": str(payload.email),
            "password": payload.password,
        })

        if not response.user or not response.session:
            raise HTTPException(
                status_code=401,
                detail="Login failed or email verification is required",
            )

        return session_response(response.session, response.user)
    except Exception as exc:
        detail = str(exc)
        lowered = detail.lower()

        if "email not confirmed" in lowered or "email not verified" in lowered:
            raise HTTPException(
                status_code=401,
                detail="Your email is not verified. Please verify your email using the link sent to your inbox.",
            )

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password. Your account may not exist.",
        )


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Profile of the logged-in user (used by the app's Profile screen)."""
    return {
        "success": True,
        "user": user_payload(user["id"], user["email"], user.get("metadata")),
    }


@router.get("/verified", response_class=HTMLResponse)
def email_verified():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CampusCare - Email Verified</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="font-family: sans-serif; text-align: center; padding: 60px 20px;">
        <h1>CampusCare</h1>
        <h2>Email verification complete</h2>
        <p>Your email verification process has finished.</p>
        <p>Return to the CampusCare app and sign in.</p>
    </body>
    </html>
    """