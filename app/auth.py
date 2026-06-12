from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .models import UserRole, User
from .database import UserDB

SECRET_KEY = "sxd-club-materials-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(username: str, password: str) -> Optional[User]:
    user = UserDB.get_by_username(username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = UserDB.get_by_username(username)
    if user is None:
        raise credentials_exception
    return user


def require_roles(*roles: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {[r.value for r in roles]}"
            )
        return current_user
    return role_checker


def init_default_users():
    users = UserDB.get_all()
    if not users:
        default_users = [
            User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role=UserRole.ADMIN,
                full_name="系统管理员"
            ),
            User(
                username="operator",
                password_hash=get_password_hash("operator123"),
                role=UserRole.OPERATOR,
                full_name="操作员小王"
            ),
            User(
                username="auditor",
                password_hash=get_password_hash("auditor123"),
                role=UserRole.AUDITOR,
                full_name="审核员小李"
            ),
        ]
        for u in default_users:
            UserDB.add(u)
