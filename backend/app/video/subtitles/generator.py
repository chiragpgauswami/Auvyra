import os
import re
from edge_tts import SubMaker

class SubtitleGenerator:
    def create_from_audio(self, audio_file: str, output_srt: str, word_level: bool = False):
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, info = model.transcribe(audio_file, word_timestamps=word_level)
            
            with open(output_srt, "w", encoding="utf-8") as f:
                for i, segment in enumerate(segments, start=1):
                    start = self._format_timestamp(segment.start)
                    end = self._format_timestamp(segment.end)
                    f.write(f"{i}\n{start} --> {end}\n{segment.text.strip()}\n\n")
        except Exception:
            with open(output_srt, "w", encoding="utf-8") as f:
                f.write("1\n00:00:00,000 --> 00:00:05,000\n(Subtitles not generated)\n\n")
            
    def create_from_tts(self, subtitle_data: SubMaker, script: str, output_srt: str, word_level: bool = False):
        srt_content = ""
        if hasattr(subtitle_data, "get_srt"):
            srt_content = subtitle_data.get_srt()
        elif hasattr(subtitle_data, "generate_subs"):
            srt_content = subtitle_data.generate_subs()
            
        if not srt_content.strip() and script:
            # Fallback: slice script into readable subtitles
            sentences = [s.strip() for s in re.split(r"(?<=[.?!,])\s+", script) if s.strip()]
            if not sentences:
                sentences = [script.strip()]
            duration_per_sentence = 4.0
            lines = []
            for idx, s in enumerate(sentences, start=1):
                start = (idx - 1) * duration_per_sentence
                end = start + duration_per_sentence
                lines.append(f"{idx}\n{self._format_timestamp(start)} --> {self._format_timestamp(end)}\n{s}\n")
            srt_content = "\n".join(lines)
            
        with open(output_srt, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
    def _format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        msecs = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"
