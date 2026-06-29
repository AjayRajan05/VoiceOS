from helpers import dotenv
from helpers.secure_password import verify_password, constant_time_compare
import hashlib


def get_credentials_hash():
    """Get hash of credentials for session verification.
    
    Returns:
        SHA256 hash of stored credentials
    """
    user = dotenv.get_dotenv_value(dotenv.KEY_AUTH_LOGIN)
    password = dotenv.get_dotenv_value(dotenv.KEY_AUTH_PASSWORD)
    if not user:
        return None
    return hashlib.sha256(f"{user}:{password}".encode()).hexdigest()


def verify_credentials(username: str, password: str) -> bool:
    """Verify credentials using constant-time comparison.
    
    Args:
        username: Username to verify
        password: Password to verify
        
    Returns:
        True if credentials are valid, False otherwise
    """
    if not isinstance(username, str) or not isinstance(password, str):
        return False
    
    stored_user = dotenv.get_dotenv_value(dotenv.KEY_AUTH_LOGIN)
    stored_password = dotenv.get_dotenv_value(dotenv.KEY_AUTH_PASSWORD)
    
    # Use constant-time comparison to prevent timing attacks
    user_match = constant_time_compare(username, stored_user) if stored_user else False
    pass_match = constant_time_compare(password, stored_password) if stored_password else False
    
    return user_match and pass_match


def is_login_required():
    user = dotenv.get_dotenv_value(dotenv.KEY_AUTH_LOGIN)
    return bool(user)
