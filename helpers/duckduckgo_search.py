# from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

# def search(query: str, results = 5, region = "wt-wt", time="y") -> str:
#     # Create an instance with custom parameters
#     api = DuckDuckGoSearchAPIWrapper(
#         region=region,  # Set the region for search results
#         safesearch="off",  # Set safesearch level (options: strict, moderate, off)
#         time=time,  # Set time range (options: d, w, m, y)
#         max_results=results  # Set maximum number of results to return
#     )
#     # Perform a search
#     result = api.run(query)
#     return result

import warnings

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


def _create_ddgs_instance():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        original_warn = warnings.warn
        try:
            warnings.warn = lambda *args, **kwargs: None
            return DDGS()
        finally:
            warnings.warn = original_warn


def search(query: str, results = 5, region = "wt-wt", time="y") -> list[str]:

    ddgs = _create_ddgs_instance()
    src = ddgs.text(
        query,
        region=region,  # Specify region 
        safesearch="off",  # SafeSearch setting
        timelimit=time,  # Time limit (y = past year)
        max_results=results  # Number of results to return
    )
    results = []
    for s in src:
        results.append(str(s))
    return results