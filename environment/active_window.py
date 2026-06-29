import pygetwindow as gw
import logging

logger = logging.getLogger(__name__)

def get_active_window():
    """Get the title of the currently active window.
    
    Returns:
        Window title, or None if unavailable
    """
    try:
        window = gw.getActiveWindow()
        if window:
            return window.title
    except (AttributeError, OSError) as e:
        logger.warning(f"Failed to get active window: {type(e).__name__}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error getting active window: {e}")
    return None