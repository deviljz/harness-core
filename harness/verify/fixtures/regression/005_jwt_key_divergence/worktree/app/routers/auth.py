# （fixture 精简片段：上传接口依赖的 token 验签）

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer
from app.config import get_settings

security = HTTPBearer()

# 验签用的密钥：从配置读（生产经 .env 的 SECRET_KEY 覆盖）
SECRET_KEY = get_settings().SECRET_KEY
ALGORITHM = "HS256"


def verify_token(cred=Security(security)):
    try:
        payload = jwt.decode(cred.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        # 移动端 token 用硬编码 key 签发，这里用 settings.SECRET_KEY 验签 → 生产换密钥即 401
        raise HTTPException(status_code=401, detail="Token 无效")
    return payload["sub"]
