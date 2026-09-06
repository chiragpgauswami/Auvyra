import edge_tts
from edge_tts import SubMaker
from loguru import logger
from .base import TTSProvider
from ..models import TTSResult
from .duration import get_audio_duration

class EdgeTTSProvider(TTSProvider):
    def _clean_voice_name(self, voice_name: str) -> str:
        return voice_name.replace("-Female", "").replace("-Male", "").strip()
        
    def _format_voice_rate(self, voice_rate: float) -> str:
        rate_percent = round((voice_rate - 1.0) * 100)
        return f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"

    async def synthesize(self, text: str, voice_name: str = "en-US-AriaNeural", voice_rate: float = 1.0, output_path: str = "") -> TTSResult:
        clean_voice = self._clean_voice_name(voice_name)
        rate_str = self._format_voice_rate(voice_rate)
        
        communicate = edge_tts.Communicate(text, clean_voice, rate=rate_str, boundary="WordBoundary")
        sub_maker = SubMaker()
        
        with open(output_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                    sub_maker.feed(chunk)
                    
        duration = get_audio_duration(output_path)
        return TTSResult(
            audio_path=output_path,
            duration=duration,
            subtitle_data=sub_maker
        )
        
    def list_voices(self) -> list[str]:
        return [
            "en-US-AriaNeural-Female",
            "en-US-GuyNeural-Male",
            "en-US-JennyNeural-Female",
            "en-GB-SoniaNeural-Female"
        ]
