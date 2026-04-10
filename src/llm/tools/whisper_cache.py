from functools import lru_cache

from faster_whisper import WhisperModel


@lru_cache(maxsize=None)
def get_whisper_model(model_size: str = "base", device: str = "cpu", compute_type: str = "int8") -> WhisperModel:
    return WhisperModel(model_size, device=device, compute_type=compute_type)
