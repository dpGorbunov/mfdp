# app/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from app.auth.authenticate import authenticate
from app.auth.hash_password import HashPassword
from app.auth.jwt_handler import create_access_token
from app.database.database import get_session
from app.database.config import get_settings
from app.models.user import User
from app.schemas.auth import UserSignUp, UserSignIn, TokenResponse, UserResponse
from typing import Dict

# Получаем настройки приложения
settings = get_settings()
# Создаем экземпляр роутера
auth_route = APIRouter(prefix="/auth", tags=["authentication"])
# Создаем экземпляр для хеширования паролей
hash_password = HashPassword()


@auth_route.post("/create-test-user")
async def create_test_user(session: Session = Depends(get_session)):
    """
    Создает тестового пользователя admin@example.com с паролем admin123.
    Используйте этот endpoint для быстрого создания тестового пользователя.
    """
    # Проверяем, существует ли уже такой пользователь
    existing_user = session.exec(
        select(User).where(User.email == "admin@example.com")
    ).first()

    if existing_user:
        return {"message": "Test user already exists", "email": "admin@example.com"}

    # Создаем тестового пользователя
    test_user = User(
        email="admin@example.com",
        name="Admin User",
        password_hash=hash_password.create_hash("admin123")
    )

    session.add(test_user)
    session.commit()

    return {
        "message": "Test user created successfully",
        "email": "admin@example.com",
        "password": "admin123"
    }


@auth_route.post("/token")
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        session: Session = Depends(get_session)
) -> Dict[str, str]:
    """
    Создает access token для аутентифицированного пользователя (OAuth2 совместимый).

    Используйте email в поле username для входа.
    """
    # Проверяем существование пользователя по email
    user_exist = session.exec(
        select(User).where(User.email == form_data.username)
    ).first()

    if user_exist is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Проверяем правильность пароля
    if not user_exist.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User has no password set",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if hash_password.verify_hash(form_data.password, user_exist.password_hash):
        # Создаем JWT токен с ID пользователя
        access_token = create_access_token(str(user_exist.id))

        # Возвращаем токен в ответе
        return {"access_token": access_token, "token_type": "bearer"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@auth_route.post("/login", response_model=TokenResponse)
async def login(user_data: UserSignIn, session: Session = Depends(get_session)):
    """
    Вход пользователя - поддерживает email.
    """
    # Ищем пользователя по email
    user = session.exec(
        select(User).where(User.email == user_data.email)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Проверяем пароль
    if not user.password_hash or not hash_password.verify_hash(
        user_data.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Создаем токен
    access_token = create_access_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
    )


@auth_route.post("/signup", response_model=UserResponse)
async def sign_up(user_data: UserSignUp, session: Session = Depends(get_session)):
    """
    Регистрация нового пользователя.
    """
    # Проверяем, существует ли пользователь с таким email
    existing_user = session.exec(
        select(User).where(User.email == user_data.email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )

    # Создаем нового пользователя
    new_user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=hash_password.create_hash(user_data.password)
    )

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        name=new_user.name,
        is_active=new_user.is_active
    )


@auth_route.get("/me", response_model=UserResponse)
async def get_current_user(
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session)
):
    """
    Получить информацию о текущем пользователе.
    """
    user = session.get(User, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active
    )


@auth_route.get("/users")
async def list_users(session: Session = Depends(get_session)):
    """
    Получить список всех пользователей (для отладки).
    """
    users = session.exec(select(User)).all()
    return [
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "has_password": bool(user.password_hash),
            "is_active": user.is_active
        }
        for user in users
    ]


# Экспортируем роутер
router = auth_route