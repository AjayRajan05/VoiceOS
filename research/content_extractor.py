from bs4 import BeautifulSoup
from readability import Document
import logging

logger = logging.getLogger(__name__)

def extract_content(html):
    """Extract content from HTML using readability and BeautifulSoup.
    
    Args:
        html: The HTML content to extract from
        
    Returns:
        Extracted text, or empty string if extraction fails
    """
    try:
        doc = Document(html)
        summary = doc.summary()
        soup = BeautifulSoup(summary, "html.parser")
        return soup.get_text()
    except (AttributeError, ValueError) as e:
        logger.warning(f"Failed to extract content: {type(e).__name__}: {e}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error extracting content: {e}")
        return ""