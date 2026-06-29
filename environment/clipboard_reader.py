import pyperclip
import logging

logger = logging.getLogger(__name__)

def get_clipboard():
    """Get text from system clipboard.
    
    Returns:
        Clipboard text, or None if unavailable
    """
    try:
        return pyperclip.paste()
    except (OSError, pyperclip.PyperclipException) as e:
        logger.warning(f"Clipboard access failed: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading clipboard: {e}")
        return None