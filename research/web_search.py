import warnings
with warnings.catch_warnings():
    warnings.filterwarnings(
        'ignore',
        message=r'This package \(`duckduckgo_search`\) has been renamed to `ddgs`! Use `pip install ddgs` instead\.',
        category=RuntimeWarning,
    )
    from duckduckgo_search import DDGS


def _create_ddgs():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        original_warn = warnings.warn
        try:
            warnings.warn = lambda *args, **kwargs: None
            return DDGS()
        finally:
            warnings.warn = original_warn


def search_web(query, max_results=5):

    results = []

    with _create_ddgs() as ddgs:

        for r in ddgs.text(query, max_results=max_results):

            results.append({
                "title": r["title"],
                "link": r["href"]
            })

    return results