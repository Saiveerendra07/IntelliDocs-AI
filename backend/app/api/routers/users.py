import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.schemas.auth import UserOut, UserUpdate, PasswordChange
from backend.app.core.deps import get_current_user
from backend.app.core.security import verify_password, get_password_hash
from backend.app.api.routers.auth import _USERS_STORE

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    email = current_user["email"].lower()
    user_record = _USERS_STORE.get(email)
    if not user_record:
        # Construct fallback UserOut
        return UserOut(
            id=current_user["id"],
            email=current_user["email"],
            full_name=current_user.get("full_name", "Student User"),
            theme="light",
            preferences={},
            created_at=datetime.now(timezone.utc),
        )
    return UserOut(**user_record)


@router.patch("/me", response_model=UserOut)
async def update_my_profile(update_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    email = current_user["email"].lower()
    user_record = _USERS_STORE.get(email)
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")

    if update_data.full_name is not None:
        user_record["full_name"] = update_data.full_name
    if update_data.theme is not None:
        user_record["theme"] = update_data.theme
    if update_data.preferences is not None:
        user_record["preferences"].update(update_data.preferences)

    return UserOut(**user_record)


@router.post("/me/password")
async def change_password(passwords: PasswordChange, current_user: dict = Depends(get_current_user)):
    email = current_user["email"].lower()
    user_record = _USERS_STORE.get(email)
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(passwords.current_password, user_record["hashed_password"]):
        raise HTTPException(status_code=400, detail="Current password incorrect")

    user_record["hashed_password"] = get_password_hash(passwords.new_password)
    return {"status": "success", "message": "Password changed successfully"}
