import os

import requests

from core.logger import logger


class ModelDownloader:

    def download_file(self, url, path, min_bytes: int = 1024):
        logger.info(f"Downloading model from {url}")
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        size = os.path.getsize(path)
        if size < min_bytes:
            os.remove(path)
            raise ValueError(f"Download failed or truncated ({size} bytes): {url}")

        logger.info(f"Download complete ({size} bytes).")
