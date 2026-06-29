from TTS.api import TTS


class StreamingTTS:

    def __init__(self):

        self.tts = TTS(
            model_name="tts_models/en/ljspeech/tacotron2-DDC"
        )

    def speak_stream(self, token_stream):

        sentence = ""

        for token in token_stream:

            sentence += token

            if token.endswith(".") or token.endswith("?"):

                self.tts.tts_to_file(
                    text=sentence,
                    file_path="temp.wav"
                )

                self.play_audio("temp.wav")

                sentence = ""

    def play_audio(self, file):
        """Play audio file using system audio player.
        
        Args:
            file: Path to the audio file
        """
        import subprocess
        import logging
        import shutil
        
        logger = logging.getLogger(__name__)
        
        # Find the audio player executable
        aplay_path = shutil.which('aplay')
        if not aplay_path:
            logger.error("aplay not found in PATH")
            return
        
        try:
            # Use subprocess instead of os.system for security
            subprocess.run([aplay_path, str(file)], check=False, capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            logger.warning(f"Audio playback timeout for {file}")
        except (FileNotFoundError, OSError) as e:
            logger.error(f"Failed to play audio {file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error playing audio: {e}")