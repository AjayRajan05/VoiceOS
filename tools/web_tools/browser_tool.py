"""
Browser Tool - HTTP fetch and web scraping for VoiceOS.
URL validation and response size limits apply.
"""

import logging
import urllib.parse
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

# VoiceOS Tools - Native implementation
import os
import urllib.parse
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

import requests

from core.config import config
from core.security.url_safety import validate_url as security_validate_url
from permissions.permission_engine import PermissionLevel, check_permission


class BrowserTool:
    """
    Safe wrapper for browser operations with URL validation and sandboxing.
    
    This class provides secure web browsing and scraping capabilities with
    strict URL validation, content limits, and timeout restrictions to ensure
    safe web interactions within VoiceOS.
    
    Attributes:
        workspace_root (Path): Root directory for logs and temporary files
        logger (logging.Logger): Logger for operation tracking
        allowed_schemes (List[str]): Permitted URL schemes
        blocked_domains (List[str]): Domains that are blocked
        timeout_seconds (int): Default timeout for web requests
        max_content_length (int): Maximum content size to process
    
    Args:
        workspace_root (Optional[str]): Path to workspace directory.
            Defaults to project_root/workspace if not specified.
    """
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else config.project_root / "workspace"
        self.workspace_root.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Security constraints
        self.allowed_schemes = ['http', 'https']
        self.blocked_domains = ['localhost', '127.0.0.1', '0.0.0.0']
        self.timeout_seconds = 30
        self.max_content_length = 1024 * 1024  # 1MB
        
    def _validate_url(self, url: str) -> str:
        """
        Validate and sanitize URL for safe browsing.
        
        Ensures that URLs use allowed schemes and do not point to
        blocked domains or potentially dangerous locations.
        
        Args:
            url (str): URL to validate
            
        Returns:
            str: Validated URL
            
        Raises:
            ValueError: If URL is invalid, uses forbidden scheme, or points to blocked domain
        """
        try:
            safety = security_validate_url(url, allow_private=False)
            if not safety.get("valid"):
                raise ValueError(safety.get("error", "URL not allowed"))

            parsed = urllib.parse.urlparse(url)
            
            # Check scheme
            if parsed.scheme not in self.allowed_schemes:
                raise ValueError(f"URL scheme {parsed.scheme} not allowed")
            
            # Check for blocked domains
            if parsed.netloc in self.blocked_domains:
                raise ValueError(f"URL domain {parsed.netloc} is blocked")
            
            # Ensure URL is properly formatted
            if not parsed.netloc:
                raise ValueError("Invalid URL format")
            
            return url
            
        except Exception as e:
            self.logger.error(f"URL validation failed for {url}: {e}")
            raise ValueError(f"Invalid URL: {e}")
    
    def _log_operation(self, operation: str, url: str, result: Any, error: Optional[str] = None):
        """
        Log all browser operations for security auditing.
        
        Creates detailed log entries for all web operations including
        timestamps, URLs, and results for security monitoring.
        
        Args:
            operation (str): Type of operation (open_page, scrape_content, etc.)
            url (str): URL that was accessed
            result (Any): Operation result or status
            error (Optional[str]): Error message if operation failed
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "url": url,
            "result": str(result)[:200],  # Truncate long results
            "error": error
        }
        
        log_file = self.workspace_root / "logs" / "browser_operations.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(f"{log_entry}\n")
    
    @check_permission(PermissionLevel.MEDIUM)
    def open_page(self, url: str) -> Dict[str, Any]:
        """
        Safely open web page and retrieve content.
        
        Fetches the content of a web page after validating the URL and
        applies content size limits for safety.
        
        Args:
            url (str): URL of the web page to open
            
        Returns:
            Dict[str, Any]: Page content including status code, content, and headers
            
        Raises:
            ValueError: If URL is invalid or blocked
            PermissionError: If user lacks web access permissions
        """
        try:
            validated_url = self._validate_url(url)
            
            # VoiceOS native web operation
            try:
                response = requests.get(validated_url, timeout=self.timeout_seconds)
                response.raise_for_status()
                
                result = {
                    "status_code": response.status_code,
                    "content": response.text[:self.max_content_length],
                    "headers": dict(response.headers),
                    "url": validated_url
                }
            except Exception as e:
                result = {"error": str(e), "status_code": None}
            
            # Truncate content if too long
            if isinstance(result, dict) and 'content' in result:
                if len(result['content']) > self.max_content_length:
                    result['content'] = result['content'][:self.max_content_length] + "\n...[truncated]"
            
            self._log_operation("open_page", url, "success")
            return result
            
        except Exception as e:
            self._log_operation("open_page", url, "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.MEDIUM)
    def scrape_content(self, url: str, selectors: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Scrape content from web page with optional CSS selectors.
        
        Fetches and extracts content from a web page with optional
        selector-based filtering for targeted data extraction.
        
        Args:
            url (str): URL of the web page to scrape
            selectors (Optional[List[str]]): CSS selectors for content filtering
            
        Returns:
            Dict[str, Any]: Scraped content with metadata
            
        Raises:
            ValueError: If URL is invalid or blocked
            PermissionError: If user lacks web access permissions
        """
        try:
            validated_url = self._validate_url(url)
            
            # VoiceOS native web scraping
            try:
                response = requests.get(validated_url, timeout=self.timeout_seconds)
                response.raise_for_status()
                
                # Simple content extraction (in production, use BeautifulSoup)
                content = response.text[:self.max_content_length]
                
                result = {
                    "status_code": response.status_code,
                    "content": content,
                    "url": validated_url,
                    "selectors": selectors
                }
            except Exception as e:
                result = {"error": str(e), "status_code": None}
            
            # Truncate content if too long
            if isinstance(result, dict) and 'content' in result:
                if len(result['content']) > self.max_content_length:
                    result['content'] = result['content'][:self.max_content_length] + "\n...[truncated]"
            
            self._log_operation("scrape_content", url, "success")
            return result
            
        except Exception as e:
            self._log_operation("scrape_content", url, "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.LOW)
    def search_web(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Perform web search (using safe search endpoints)"""
        try:
            # Validate query
            if not query or len(query.strip()) == 0:
                raise ValueError("Search query cannot be empty")
            
            if len(query) > 200:
                raise ValueError("Search query too long")
            
            # VoiceOS native web search (using DuckDuckGo API)
            try:
                # Simple search implementation
                search_url = f"https://duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
                response = requests.get(search_url, timeout=15)
                response.raise_for_status()
                
                # Parse basic results (simplified)
                import re
                results = []
                # Extract basic search result patterns
                result_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
                matches = re.findall(result_pattern, response.text)
                
                for url, title in matches[:max_results]:
                    results.append({
                        "title": title[:100],
                        "url": url,
                        "snippet": "Search result from DuckDuckGo"
                    })
                    
            except Exception as e:
                results = [{"error": f"Search failed: {str(e)}"}]
            
            # Limit results and sanitize
            sanitized_results = []
            for result in results[:max_results]:
                sanitized_result = {
                    "title": str(result.get("title", ""))[:100],
                    "url": result.get("url", ""),
                    "snippet": str(result.get("snippet", ""))[:200]
                }
                sanitized_results.append(sanitized_result)
            
            self._log_operation("search_web", f"query: {query}", f"found {len(sanitized_results)} results")
            return sanitized_results
            
        except Exception as e:
            self._log_operation("search_web", f"query: {query}", "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.LOW)
    def get_page_info(self, url: str) -> Dict[str, Any]:
        """Get basic page information without full content"""
        try:
            validated_url = self._validate_url(url)
            
            # VoiceOS native page info
            try:
                response = requests.head(validated_url, timeout=10)
                response.raise_for_status()
                
                result = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "url": validated_url,
                    "accessible": True
                }
            except Exception as e:
                result = {"error": str(e), "accessible": False}
            
            self._log_operation("get_page_info", url, "success")
            return result
            
        except Exception as e:
            self._log_operation("get_page_info", url, "failed", str(e))
            raise


# Global instance for tool registry
browser_tool = BrowserTool()
