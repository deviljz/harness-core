# （fixture 精简片段：移动端登录签发 JWT）

from datetime import datetime, timedelta
import jwt
from fastapi import APIRouter

router = APIRouter(prefix="/api/mobile/auth", tags=["移动端认证"])

# 签发用的密钥：硬编码默认值
SECRET_KEY = "miaofudao-secret-key-change-in-production"
ALGORITHM = "HS256"


@router.post("/login")
def mobile_login(username: str, password: str):
    # ... 校验账密略 ...
    payload = {"sub": username, "exp": datetime.utcnow() + timedelta(days=7)}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}
