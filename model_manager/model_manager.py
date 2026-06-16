import os

from model_manager.hardware_detector import HardwareDetector
from model_manager.model_registry import MODELS, llm_download_url
from model_manager.model_downloader import ModelDownloader
from core.config import config
from core.logger import logger


class ModelManager:

    def __init__(self):

        self.detector = HardwareDetector()
        self.downloader = ModelDownloader()

        self.models_dir = config.models_directory

    def ensure_models(self, download: bool = True):

        info = self.detector.get_system_info()

        ram = info["ram_gb"]

        logger.info(f"Detected RAM: {ram} GB")

        os.makedirs(self.models_dir, exist_ok=True)

        if ram < config.max_ram_threshold:
            llm_model = MODELS["llm"]["low_ram"]
        else:
            llm_model = MODELS["llm"]["high_ram"]

        llm_path = os.path.join(self.models_dir, llm_model)

        if download and not os.path.exists(llm_path):
            url = llm_download_url(llm_model)
            logger.info(f"Downloading model from {url}")
            try:
                self.downloader.download_file(url, llm_path)
            except Exception as e:
                logger.warning(f"LLM download failed: {e}. VoiceOS will run without local GGUF.")

        return {
            "llm": llm_path,
            "stt": MODELS["stt"]["small"],
            "tts": MODELS["tts"]["default"],
        }