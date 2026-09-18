import os
import hmac
import hashlib
import json
import base64
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header, Depends, status

# Configuration from Environment Variables or persisted owner config
OWNER_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "owner_config.json")

def get_owner_credentials() -> Dict[str, str]:
    default_id = os.getenv("OWNER_ADMIN_ID", "Sm_0629")
    default_pwd = os.getenv("OWNER_ADMIN_PASSWORD", "9973868328")
    if os.path.exists(OWNER_CONFIG_FILE):
        try:
            with open(OWNER_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "admin_user_id": data.get("admin_user_id", default_id),
                    "password_hash": data.get("password_hash"),
                    "password_plain": data.get("password_plain", default_pwd)
                }
        except Exception:
            pass
    return {
        "admin_user_id": default_id,
        "password_hash": None,
        "password_plain": default_pwd
    }

def get_owner_admin_id() -> str:
    return get_owner_credentials()["admin_user_id"]

OWNER_ADMIN_ID = get_owner_admin_id()
OWNER_ADMIN_PASSWORD = os.getenv("OWNER_ADMIN_PASSWORD", "9973868328")
SECRET_KEY = os.getenv("SECRET_KEY", "farmbuy_ai_secure_token_secret_key_2026_x89f")

def save_owner_credentials(new_admin_id: Optional[str] = None, new_password: Optional[str] = None) -> Dict[str, str]:
    global OWNER_ADMIN_ID, OWNER_ADMIN_PASSWORD
    creds = get_owner_credentials()
    if new_admin_id:
        creds["admin_user_id"] = new_admin_id.strip()
        OWNER_ADMIN_ID = creds["admin_user_id"]
    if new_password:
        creds["password_plain"] = new_password.strip()
        creds["password_hash"] = hash_password(new_password.strip())
        OWNER_ADMIN_PASSWORD = creds["password_plain"]
    
    with open(OWNER_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)
    return creds

def verify_owner_login(user_id_input: str, password_input: str) -> bool:
    creds = get_owner_credentials()
    if user_id_input.strip() != creds["admin_user_id"]:
        return False
    if creds.get("password_hash"):
        return verify_password(password_input, creds["password_hash"])
    return password_input == creds.get("password_plain")

TOKEN_EXPIRY_SECONDS = 86400 * 7  # 7 days session validity
PBKDF2_ITERATIONS = 200_000


def hash_password(plain_password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with random 16-byte salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        plain_password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS
    )
    salt_hex = salt.hex()
    key_hex = key.hex()
    return f"{salt_hex}${key_hex}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify candidate password against salted PBKDF2-HMAC-SHA256 hash."""
    if not password_hash or "$" not in password_hash:
        return False
    try:
        salt_hex, key_hex = password_hash.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        candidate_key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt,
            PBKDF2_ITERATIONS
        )
        return hmac.compare_digest(expected_key, candidate_key)
    except Exception:
        return False


def create_access_token(payload: Dict[str, Any]) -> str:
    """Create a signed HMAC-SHA256 token containing user claims."""
    token_data = payload.copy()
    token_data["exp"] = int(time.time()) + TOKEN_EXPIRY_SECONDS
    raw_payload = json.dumps(token_data, separators=(',', ':'), sort_keys=True).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(raw_payload).decode('utf-8').rstrip('=')
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"{payload_b64}.{signature}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """Verify HMAC signature and expiry, returning decoded token claims."""
    if not token or "." not in token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token."
        )
    
    parts = token.split(".", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token."
        )
    
    payload_b64, signature = parts
    expected_sig = hmac.new(
        SECRET_KEY.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_sig, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature. Access denied."
        )
    
    try:
        padded = payload_b64 + '=' * (-len(payload_b64) % 4)
        raw_json = base64.urlsafe_b64decode(padded).decode('utf-8')
        claims = json.loads(raw_json)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Corrupted token payload."
        )
    
    if claims.get("exp", 0) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please login again."
        )
    
    return claims


def get_current_user_payload(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Dependency: extracts and validates Bearer token from HTTP Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing. Please provide a valid Bearer token."
        )
    
    parts = authorization.strip().split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header format must be 'Bearer <token>'."
        )
    
    return decode_access_token(parts[1])


def require_admin(claims: Dict[str, Any] = Depends(get_current_user_payload)) -> Dict[str, Any]:
    """Dependency: allows access ONLY to users with role 'ADMIN' or 'OWNER'."""
    role = claims.get("role")
    if role not in ("ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires ADMIN or OWNER privileges."
        )
    return claims


def require_owner(claims: Dict[str, Any] = Depends(get_current_user_payload)) -> Dict[str, Any]:
    """Dependency: allows access ONLY to the Super Admin with role 'OWNER'."""
    role = claims.get("role")
    if role != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires OWNER / Super Admin authorization."
        )
    return claims
