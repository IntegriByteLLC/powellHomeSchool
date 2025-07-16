# utils/auth_utils.py
import jwt
import hmac
import time

import tiktoken
from fastapi import Request, HTTPException

from Postgres import config


def verify_token_header(request: Request):
    token = request.headers.get("x-chat-token")
    if not token:
        raise HTTPException(status_code=403, detail="Missing token")
    return verify_token(token)

def verify_token(token: str):
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise Exception("Token expired")
    except jwt.InvalidTokenError:
        raise Exception("Invalid token")

def get_current_token() -> str:
    current_hour = str(int(time.time()) // 3600)
    return hmac.new(config.MASTER_KEY.encode(), current_hour.encode(), digestmod="sha256").hexdigest()


def estimate_tokens( text: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    except:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def trim_context(self, text: str, max_tokens: int) -> str:
    lines = text.split("\n")
    trimmed = []
    total_tokens = 0

    for line in lines:
        line_tokens = self.estimate_tokens(line)
        if total_tokens + line_tokens >= max_tokens:
            break
        trimmed.append(line)
        total_tokens += line_tokens

    return "\n".join(trimmed)
