import re
from typing import List, Tuple

def parse_timecode(timecode: str) -> Tuple[float, float]:
    """Parse '00:00:01,500 --> 00:00:03,200' to (1.5, 3.2) seconds."""
    parts = timecode.split("-->")
    def to_secs(s: str) -> float:
        s = s.strip().replace(".", ",")
        h, m, rest = s.split(":")
        sec, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000.0
    return to_secs(parts[0]), to_secs(parts[1])

def parse_srt(filename: str) -> List[Tuple[int, Tuple[float, float], str]]:
    """Parse an SRT file into [(index, (start_sec, end_sec), text), ...]"""
    results = []
    if not filename:
        return results
        
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return results
    
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
        if len(lines) >= 3:
            try:
                idx = int(lines[0])
                time_range = parse_timecode(lines[1])
                text = " ".join(lines[2:])
                results.append((idx, time_range, text))
            except Exception:
                continue
            
    return results

def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"

def text_to_srt(index: int, text: str, start: float, end: float) -> str:
    start_str = format_timestamp(start)
    end_str = format_timestamp(end)
    return f"{index}\n{start_str} --> {end_str}\n{text}\n\n"
