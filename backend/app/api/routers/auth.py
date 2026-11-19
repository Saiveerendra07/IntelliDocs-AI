import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserOut
from backend.app.core.security import get_password_hash, verify_password, create_access_token
from backend.app.core.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.db.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Cache maintained for fast lookup
_USERS_STORE = {}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserRegister, db: Session = Depends(get_db)):
    email = user_in.email.lower()

    # Check database or store
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing or email in _USERS_STORE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    hashed_pw = get_password_hash(user_in.password)

    db_user = User(
        id=user_id,
        email=email,
        hashed_password=hashed_pw,
        full_name=user_in.full_name,
        theme="light",
        preferences={"default_provider": "local"},
        last_login_at=now,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

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
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    email = credentials.email.lower()
    db_user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    user_record = _USERS_STORE.get(email)

    if db_user:
        if not verify_password(credentials.password, db_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password."
            )
        db_user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        user_id = db_user.id
        full_name = db_user.full_name
        user_out = UserOut.model_validate(db_user)
    elif user_record:
        if not verify_password(credentials.password, user_record["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password."
            )
        user_id = user_record["id"]
        full_name = user_record["full_name"]
        user_out = UserOut(**user_record)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    token = create_access_token({
        "sub": str(user_id),
        "email": email,
        "full_name": full_name,
    })

    return TokenResponse(access_token=token, token_type="bearer", user=user_out)


@router.get("/me", response_model=UserOut)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    return UserOut(**current_user)
