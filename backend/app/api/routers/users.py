import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.schemas.auth import UserOut, UserUpdate, PasswordChange
from backend.app.core.deps import get_current_user
from backend.app.core.security import verify_password, get_password_hash
from backend.app.api.routers.auth import _USERS_STORE
from backend.app.db.session import get_db
from backend.app.db.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
async def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    db_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if db_user:
        return UserOut.model_validate(db_user)

    user_record = _USERS_STORE.get(current_user["email"].lower())
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**user_record)


@router.patch("/me", response_model=UserOut)
async def update_my_profile(
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email = current_user["email"].lower()
    user_id = uuid.UUID(str(current_user["id"]))
    db_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    user_record = _USERS_STORE.get(email)

    if not db_user and not user_record:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user:
        if update_data.full_name is not None:
            db_user.full_name = update_data.full_name
        if update_data.theme is not None:
            db_user.theme = update_data.theme
        if update_data.preferences is not None:
            db_user.preferences = {**db_user.preferences, **update_data.preferences}
        db.commit()
        db.refresh(db_user)

    if user_record:
        if update_data.full_name is not None:
            user_record["full_name"] = update_data.full_name
        if update_data.theme is not None:
            user_record["theme"] = update_data.theme
        if update_data.preferences is not None:
            user_record["preferences"].update(update_data.preferences)

    if db_user:
        return UserOut.model_validate(db_user)
    return UserOut(**user_record)


@router.post("/me/password")
async def change_password(
    passwords: PasswordChange,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email = current_user["email"].lower()
    user_id = uuid.UUID(str(current_user["id"]))
    db_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    user_record = _USERS_STORE.get(email)

    if not db_user and not user_record:
        raise HTTPException(status_code=404, detail="User not found")

    hashed_pw = db_user.hashed_password if db_user else user_record["hashed_password"]
    if not verify_password(passwords.current_password, hashed_pw):
        raise HTTPException(status_code=400, detail="Current password incorrect")

    new_hash = get_password_hash(passwords.new_password)
    if db_user:
        db_user.hashed_password = new_hash
        db.commit()
    if user_record:
        user_record["hashed_password"] = new_hash

    return {"status": "success", "message": "Password changed successfully"}
