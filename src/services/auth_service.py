
import httpx

import config



async def _post(path: str, payload: dict) -> dict:
    base_url = config.API_BASE_URL.rstrip("/")

    async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_S) as client:
        response = await client.post(
            f"{base_url}{path}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()




def _normalize_session(data: dict) -> dict:
    user_data = data.get("user") or {}
    metadata = user_data.get("user_metadata") or {}

    return {
        "success": True,
        "access": data.get("access_token"),
        "refresh": data.get("refresh_token"),
        "user": {
            "id": user_data.get("id"),
            "name": metadata.get("full_name", ""),
            "email": user_data.get("email", ""),
            "role": metadata.get("role", "student"),
        },
    }


async def signup(
    full_name: str,
    email: str,
    password: str,
    roll_no: str | None = None,
    building_id: str | None = None,
) -> dict:
    return await _post(
        "/auth/signup",
        {
            "full_name": full_name,
            "email": email,
            "password": password,
            "roll_number": roll_no,
            "building_id": building_id,
        },
    )


async def login(email: str, password: str) -> dict:
    data = await _post(
        "/auth/login",
        {
            "email": email,
            "password": password,
        },
    )
    return _normalize_session(data)


async def verify_otp(email: str, code: str) -> dict:
    data = await _post(
        "/auth/verify-otp",
        {
            "email": email,
            "token": code,
        },
    )
    return _normalize_session(data)


async def resend_otp(email: str) -> dict:
    return await _post(
        "/auth/resend-otp",
        {
            "email": email,
        },
    )
