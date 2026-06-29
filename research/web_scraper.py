import requests
import logging

logger = logging.getLogger(__name__)

def fetch_page(url):
    """Fetch a page from a URL with error handling.
    
    Args:
        url: The URL to fetch
        
    Returns:
        The page text, or None if fetch fails
    """
    try:
        r = requests.get(url, timeout=10)
        return r.text
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return None