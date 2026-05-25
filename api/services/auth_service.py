import os
from datetime import datetime, timedelta

import jwt

SECRET = os.getenv("JWT_SECRET")


def create_token(user_id: int):
    payload = {"user_id": user_id, "exp": datetime.utcnow() + timedelta(days=7)}

    return jwt.encode(payload, SECRET, algorithm="HS256")
