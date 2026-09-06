from abc import ABC, abstractmethod
from ..models import TTSResult

class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice_name: str, voice_rate: float,
                         output_path: str) -> TTSResult:
        pass
    
    @abstractmethod
    def list_voices(self) -> list[str]:
        pass
