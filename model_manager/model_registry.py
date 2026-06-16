MODELS = {
    "stt": {
        "small": "tiny",
        "medium": "base",
    },
    "llm": {
        "low_ram": "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "high_ram": "mistral-7b-instruct-v0.2.Q5_K_M.gguf",
    },
    "tts": {
        "default": "tts_models/en/ljspeech/tacotron2-DDC",
    },
}

LLM_HF_REPO = "TheBloke/Mistral-7B-Instruct-v0.2-GGUF"


def llm_download_url(filename: str) -> str:
    return f"https://huggingface.co/{LLM_HF_REPO}/resolve/main/{filename}"
