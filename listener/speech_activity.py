class SpeechActivityDetector:

    def __init__(self):
        self.vad = None
        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(2)
        except ImportError:
            pass

    def is_speech(self, audio_chunk, sample_rate=16000):
        if self.vad is None:
            return False
        try:
            return self.vad.is_speech(audio_chunk, sample_rate)
        except Exception:
            return False
