import os, warnings
from jose import JWTError, jwt
from fastapi import HTTPException
from datetime import datetime, timedelta
from passlib.context import CryptContext

SECRET_KEY: str = os.getenv("JWT_SECRET_KEY") or "docrag-super-secret-key-2024-xyz"
if SECRET_KEY == "docrag-super-secret-key-2024-xyz":
    warnings.warn(
        "JWT_SECRET_KEY not set in environment/.env — using an insecure default. "
        "Set JWT_SECRET_KEY in your .env file before deploying this anywhere."
    )
ALGORITHM  = "HS256"

# Proper bcrypt hashing
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please login again.")
