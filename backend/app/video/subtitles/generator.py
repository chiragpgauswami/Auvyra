import os
import re
from typing import List, Dict, Any, Optional
from edge_tts import SubMaker
from loguru import logger

def format_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int(round((seconds - int(seconds)) * 1000))
    if msecs >= 1000:
        msecs = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"

def group_words_into_shorts_cues(
    words: List[Dict[str, Any]],
    target_words_min: int = 1,
    target_words_max: int = 3,
    hard_max_words: int = 5,
    target_duration_min: float = 0.6,
    target_duration_max: float = 1.2,
    hard_max_duration: float = 1.4,
    pause_threshold: float = 0.35
) -> List[Dict[str, Any]]:
    """
    Groups word-level timestamps into high-retention YouTube Shorts subtitle cues.
    
    Invariants:
    - 1-3 words normal target, hard limit 5 words.
    - 0.6s - 1.2s normal cadence, hard limit 1.4s.
    - Punctuation-aware: Hard break at sentence terminators (. ! ? ...).
    - Pause-aware: Pauses > 0.35s between words start a new cue.
    - Monotonic: Each cue start >= previous cue end, start < end.
    - No fabricated timestamps: Clamped to real word timings.
    """
    if not words:
        return []

    # Clean and filter words
    cleaned_words: List[Dict[str, Any]] = []
    last_end = 0.0
    for w in words:
        text = str(w.get("word", "")).strip()
        if not text:
            continue
        try:
            w_start = float(w.get("start", 0.0))
            w_end = float(w.get("end", 0.0))
        except (ValueError, TypeError):
            continue

        if w_start < last_end:
            w_start = last_end
        if w_end <= w_start:
            w_end = w_start + 0.08

        last_end = w_end
        cleaned_words.append({
            "word": text,
            "start": w_start,
            "end": w_end,
            "probability": w.get("probability", 1.0)
        })

    if not cleaned_words:
        return []

    cues: List[Dict[str, Any]] = []
    current_cue_words: List[Dict[str, Any]] = []

    def close_current_cue():
        nonlocal current_cue_words, cues
        if not current_cue_words:
            return

        c_start = current_cue_words[0]["start"]
        c_end = current_cue_words[-1]["end"]

        # Ensure minimum visible duration of 0.15s
        if c_end <= c_start:
            c_end = c_start + 0.15

        # Monotonicity with previous cue
        if cues:
            prev_end = cues[-1]["end"]
            if c_start < prev_end:
                c_start = prev_end
            if c_end <= c_start:
                c_end = c_start + 0.15

        cue_text = " ".join(item["word"] for item in current_cue_words)
        cues.append({
            "index": len(cues) + 1,
            "start": round(c_start, 3),
            "end": round(c_end, 3),
            "text": cue_text,
            "word_count": len(current_cue_words),
            "duration": round(c_end - c_start, 3)
        })
        current_cue_words = []

    terminal_punct = re.compile(r"[.!?…]+$")
    clause_punct = re.compile(r"[,;:\—\-]+$")

    for i, word_item in enumerate(cleaned_words):
        if not current_cue_words:
            current_cue_words.append(word_item)
            # Check if single word ends with terminal punctuation
            if terminal_punct.search(word_item["word"]):
                close_current_cue()
            continue

        prev_word = current_cue_words[-1]
        gap = word_item["start"] - prev_word["end"]
        potential_dur = word_item["end"] - current_cue_words[0]["start"]
        potential_count = len(current_cue_words) + 1

        # Check grouping break conditions:
        should_break = False

        # 1. Hard ceilings: count >= 5 or duration >= 1.4s
        if len(current_cue_words) >= hard_max_words:
            should_break = True
        elif potential_dur >= hard_max_duration:
            should_break = True
        # 2. Pause threshold between words
        elif gap >= pause_threshold:
            should_break = True
        # 3. Previous word had terminal punctuation (. ! ?)
        elif terminal_punct.search(prev_word["word"]):
            should_break = True
        # 4. Previous word had clause punctuation (, ; :) and we have at least 1-2 words or >= min duration
        elif clause_punct.search(prev_word["word"]) and (
            len(current_cue_words) >= target_words_min or (prev_word["end"] - current_cue_words[0]["start"]) >= target_duration_min
        ):
            should_break = True
        # 5. Target cadence reached (2-3 words AND duration in 0.6s - 1.2s range)
        elif len(current_cue_words) >= target_words_max and (prev_word["end"] - current_cue_words[0]["start"]) >= target_duration_min:
            should_break = True

        if should_break:
            close_current_cue()
            current_cue_words.append(word_item)
            if terminal_punct.search(word_item["word"]):
                close_current_cue()
        else:
            current_cue_words.append(word_item)
            if terminal_punct.search(word_item["word"]):
                close_current_cue()

    if current_cue_words:
        close_current_cue()

    return cues

def cues_to_srt(cues: List[Dict[str, Any]]) -> str:
    """Converts structured cue list into standard SRT text format."""
    lines = []
    for idx, c in enumerate(cues, start=1):
        s_str = format_timestamp(c["start"])
        e_str = format_timestamp(c["end"])
        text = c["text"].strip()
        lines.append(f"{idx}\n{s_str} --> {e_str}\n{text}\n")
    return "\n".join(lines)


class SubtitleGenerator:
    """Generates high-retention, word-level subtitles using faster-whisper or TTS metadata."""

    def transcribe_with_words(self, audio_file: str, model_size: str = "base") -> List[Dict[str, Any]]:
        """Transcribes audio using faster-whisper with exact word timestamps."""
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_file, word_timestamps=True)

        words: List[Dict[str, Any]] = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    words.append({
                        "word": w.word.strip(),
                        "start": w.start,
                        "end": w.end,
                        "probability": getattr(w, "probability", 1.0)
                    })
            else:
                # Fallback if no word level returned for this segment
                words.append({
                    "word": segment.text.strip(),
                    "start": segment.start,
                    "end": segment.end,
                    "probability": 1.0
                })
        return words

    def create_from_audio(
        self,
        audio_file: str,
        output_srt: str,
        word_level: bool = True,
        shorts_cadence: bool = True,
        max_words_per_cue: int = 3
    ):
        """Creates SRT file from audio. If shorts_cadence is True, applies 1-3 word cadence grouping."""
        try:
            if shorts_cadence:
                words = self.transcribe_with_words(audio_file, model_size="base")
                cues = group_words_into_shorts_cues(words, target_words_max=max_words_per_cue)
                srt_content = cues_to_srt(cues)
            else:
                from faster_whisper import WhisperModel
                model = WhisperModel("base", device="cpu", compute_type="int8")
                segments, info = model.transcribe(audio_file, word_timestamps=word_level)
                lines = []
                for i, segment in enumerate(segments, start=1):
                    start = format_timestamp(segment.start)
                    end = format_timestamp(segment.end)
                    lines.append(f"{i}\n{start} --> {end}\n{segment.text.strip()}\n")
                srt_content = "\n".join(lines)

            os.makedirs(os.path.dirname(os.path.abspath(output_srt)), exist_ok=True)
            with open(output_srt, "w", encoding="utf-8") as f:
                f.write(srt_content)
        except Exception as e:
            logger.error(f"SubtitleGenerator create_from_audio error: {e}")
            raise

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
                lines.append(f"{idx}\n{format_timestamp(start)} --> {format_timestamp(end)}\n{s}\n")
            srt_content = "\n".join(lines)

        os.makedirs(os.path.dirname(os.path.abspath(output_srt)), exist_ok=True)
        with open(output_srt, "w", encoding="utf-8") as f:
            f.write(srt_content)

    def _format_timestamp(self, seconds: float) -> str:
        return format_timestamp(seconds)
