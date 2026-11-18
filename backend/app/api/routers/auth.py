import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from backend.app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserOut
from backend.app.core.security import get_password_hash, verify_password, create_access_token
from backend.app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory store fallback before DB integration in Milestone 5
# Designed with exact DB schema contracts
_USERS_STORE = {}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserRegister):
    email = user_in.email.lower()
    if email in _USERS_STORE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    hashed_pw = get_password_hash(user_in.password)

    user_record = {
        "id": user_id,
        "email": email,
        "hashed_password": hashed_pw,
        "full_name": user_in.full_name,
        "theme": "light",
        "preferences": {"default_provider": "local"},
        "created_at": now,
        "last_login_at": now,
    }
    _USERS_STORE[email] = user_record

    token = create_access_token({
        "sub": str(user_id),
        "email": email,
        "full_name": user_in.full_name,
    })

    user_out = UserOut(**user_record)
    return TokenResponse(access_token=token, token_type="bearer", user=user_out)


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    email = credentials.email.lower()
    user_record = _USERS_STORE.get(email)
    if not user_record or not verify_password(credentials.password, user_record["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    user_record["last_login_at"] = datetime.now(timezone.utc)

    token = create_access_token({
        "sub": str(user_record["id"]),
        "email": email,
        "full_name": user_record["full_name"],
    })

    user_out = UserOut(**user_record)
    return TokenResponse(access_token=token, token_type="bearer", user=user_out)
