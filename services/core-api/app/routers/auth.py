import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import structlog

from app.database import get_db
from app.middleware.auth import (
    create_access_token,
    verify_password,
    get_password_hash,
    get_current_user,
    require_role,
)
from app.models import User, UserRole, Company
from app.schemas import LoginRequest, TokenResponse, RegisterRequest, PublicRegisterRequest, UserResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login endpoint - accepts email and password, returns JWT token."""
    from app.services.audit import log_action

    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Аккаунт деактивирован")

    if not verify_password(credentials.password, user.hashed_password):
        await log_action(db, user.id, "login_failed", details={"reason": "invalid_password"}, request=request)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")

    access_token = create_access_token(data={"sub": str(user.id)})

    await log_action(db, user.id, "login", resource_type="user", resource_id=str(user.id), request=request)
    await db.commit()

    logger.info("user_logged_in", user_id=str(user.id), email=user.email)
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.post("/login/form", response_model=TokenResponse)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login endpoint using OAuth2 password form (username=email)."""
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    logger.info("user_logged_in", user_id=str(user.id), email=user.email)
    
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user info."""
    return UserResponse.model_validate(current_user)


@router.post("/register", response_model=UserResponse)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Register a new user (admin only)."""
    # Check if user with email already exists
    result = await db.execute(select(User).where(User.email == data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    
    # Create new user
    company_id = uuid.UUID(data.company_id) if data.company_id else None
    
    new_user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=data.role,
        company_id=company_id,
        is_active=True,
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info(
        "user_created",
        user_id=str(new_user.id),
        email=new_user.email,
        created_by=str(current_user.id),
    )
    
    return UserResponse.model_validate(new_user)


@router.post("/register-public", response_model=TokenResponse)
async def register_public(
    data: PublicRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Public registration — anyone can register as a client."""
    from app.services.audit import log_action

    # Check uniqueness
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )

    # Create company if provided
    company_id = None
    if data.company_name and data.company_name.strip():
        company = Company(
            name=data.company_name.strip(),
            company_type="client",
        )
        db.add(company)
        await db.flush()
        company_id = company.id

    # Create user with client role
    new_user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=UserRole.CLIENT.value,
        company_id=company_id,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    # Audit log
    await log_action(
        db, new_user.id, "register",
        resource_type="user", resource_id=str(new_user.id),
        details={"email": data.email, "company_name": data.company_name},
        request=request,
    )
    await db.commit()

    # Auto-login: return token
    access_token = create_access_token(data={"sub": str(new_user.id)})

    logger.info("user_registered_public", user_id=str(new_user.id), email=data.email)

    return TokenResponse(access_token=access_token, token_type="bearer")


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None


@router.put("/profile")
async def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile: name and/or password."""
    if data.full_name is not None:
        current_user.full_name = data.full_name

    if data.new_password:
        if not data.old_password:
            raise HTTPException(status_code=400, detail="Укажите текущий пароль")
        if not verify_password(data.old_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Неверный текущий пароль")
        current_user.hashed_password = get_password_hash(data.new_password)

    await db.commit()
    return {"status": "updated", "full_name": current_user.full_name}
