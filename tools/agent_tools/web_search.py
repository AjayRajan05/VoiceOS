"""
Web Search Tool - For agent use in research tasks
Provides web search capabilities with result filtering
"""

import asyncio
import logging
import warnings
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

with warnings.catch_warnings():
    warnings.filterwarnings(
        'ignore',
        message=r'This package \(`duckduckgo_search`\) has been renamed to `ddgs`! Use `pip install ddgs` instead\.',
        category=RuntimeWarning,
    )
    from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
import time

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    timestamp: float

class WebSearch:
    def __init__(self):
        self.ddgs = self._create_ddgs_instance()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VoiceOS-Agent/1.0 (Research Mode)'
        })

    def _create_ddgs_instance(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            original_warn = warnings.warn
            try:
                warnings.warn = lambda *args, **kwargs: None
                return DDGS()
            finally:
                warnings.warn = original_warn
    
    async def search(self, query: str, max_results: int = 10, 
                   region: str = "wt-wt", safesearch: str = "moderate") -> List[SearchResult]:
        """
        Perform web search and return results
        """
        try:
            logger.info(f"Searching for: {query}")
            
            # Perform search
            results = []
            with self.ddgs.text(query, region=region, safesearch=safesearch, 
                               max_results=max_results) as ddgs_results:
                for result in ddgs_results:
                    search_result = SearchResult(
                        title=result.get('title', ''),
                        url=result.get('href', ''),
                        snippet=result.get('body', ''),
                        source='duckduckgo',
                        timestamp=time.time()
                    )
                    results.append(search_result)
            
            logger.info(f"Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []
    
    async def get_page_content(self, url: str, max_length: int = 5000) -> Optional[str]:
        """
        Extract content from a web page
        """
        try:
            logger.info(f"Fetching content from: {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Limit length
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return text
            
        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            return None
    
    async def search_and_extract(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Search and extract content from top results
        """
        try:
            # Perform search
            search_results = await self.search(query, max_results)
            
            if not search_results:
                return {"results": [], "content": {}, "error": "No results found"}
            
            # Extract content from top results
            content = {}
            for i, result in enumerate(search_results[:3]):  # Limit to top 3 for performance
                page_content = await self.get_page_content(result.url)
                if page_content:
                    content[f"result_{i+1}"] = {
                        "title": result.title,
                        "url": result.url,
                        "content": page_content
                    }
            
            return {
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet
                    } for r in search_results
                ],
                "content": content,
                "query": query,
                "total_results": len(search_results)
            }
            
        except Exception as e:
            logger.error(f"Search and extract failed: {e}")
            return {"results": [], "content": {}, "error": str(e)}
