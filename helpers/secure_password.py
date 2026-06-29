"""
Secure password handling utilities

Provides secure password hashing, verification, and comparison functions.
Uses industry-standard algorithms to protect sensitive credentials.
"""

import hashlib
import hmac
import os
import secrets
from typing import Tuple

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False


def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
    """
    Hash a password using bcrypt or PBKDF2 fallback.
    
    Args:
        password: Plain text password
        salt: Optional salt value
        
    Returns:
        Tuple of (hashed_password, salt)
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    
    try:
        if HAS_BCRYPT:
            # Use bcrypt for production (recommended)
            if salt is None:
                salt = bcrypt.gensalt(rounds=12)
            else:
                salt = salt.encode() if isinstance(salt, str) else salt
            
            hashed = bcrypt.hashpw(password.encode(), salt)
            return hashed.decode(), salt.decode() if isinstance(salt, bytes) else salt
        else:
            # Fallback to PBKDF2 if bcrypt unavailable
            if salt is None:
                salt = secrets.token_hex(32)
            
            hashed = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt.encode() if isinstance(salt, str) else salt,
                100000,  # iterations
                dklen=32
            )
            return hashed.hex(), salt
    except Exception as e:
        raise RuntimeError(f"Password hashing failed: {e}")


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hash using constant-time comparison.
    
    Args:
        password: Plain text password to verify
        hashed_password: Previously hashed password
        
    Returns:
        True if password matches, False otherwise
    """
    if not isinstance(password, str) or not password:
        return False
    
    if not isinstance(hashed_password, str) or not hashed_password:
        return False
    
    try:
        if HAS_BCRYPT:
            # Use bcrypt verification
            return bcrypt.checkpw(
                password.encode(),
                hashed_password.encode() if isinstance(hashed_password, str) else hashed_password
            )
        else:
            # Fallback: this won't work with legacy hashes, use constant-time comparison
            # Extract salt from hashed password (assumes format: salt$hash)
            if '$' in hashed_password:
                parts = hashed_password.split('$', 1)
                salt = parts[0]
                try:
                    test_hash, _ = hash_password(password, salt)
                    # Use constant-time comparison
                    return hmac.compare_digest(test_hash, hashed_password)
                except Exception:
                    return False
            return False
    except Exception as e:
        # On any error, return False (fail secure)
        return False


def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings using constant-time comparison to prevent timing attacks.
    
    Args:
        a: First string
        b: Second string
        
    Returns:
        True if strings match, False otherwise
    """
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    
    return hmac.compare_digest(a, b)


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        length: Token length in bytes
        
    Returns:
        Hex-encoded random token
    """
    if length < 8 or length > 1024:
        raise ValueError("Token length must be between 8 and 1024 bytes")
    
    return secrets.token_hex(length)
