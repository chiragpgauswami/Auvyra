from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CaptionStyleId(str, Enum):
    classic = "classic"
    bold = "bold"
    kinetic = "kinetic"
    minimal = "minimal"
    highlight_word = "highlight_word"
    typewriter = "typewriter"

class CaptionStyleConfig(BaseModel):
    channel_id: str = ""
    style_id: str = "bold"
    font_family: str = "Arial"
    font_weight: str = "bold"
    font_size: int = 54
    text_color: str = "#FFFFFF"
    highlight_color: str = "#FACC15"
    stroke_color: str = "#000000"
    outline_width: float = 2.0
    background_type: str = "pill"  # "pill", "box", "none"
    background_opacity: float = 0.82
    position: str = "safe_center"  # "safe_center", "lower_third", "upper_third"
    animation: str = "static"  # "static", "bounce", "pop", "typewriter"
    word_grouping: str = "cadence_1_3"  # "cadence_1_3", "single_word", "sentence"
    max_words_per_cue: int = 3
    version: int = 1
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CaptionStylePreset(BaseModel):
    style_id: str
    name: str
    description: str
    preview_sample: str
    config: CaptionStyleConfig

# Curated 6 Production Presets
PRESET_STYLES: List[Dict[str, Any]] = [
    {
        "style_id": "classic",
        "name": "Classic Clean",
        "description": "Crisp white uppercase text with dark translucent pill backing. Universal high readability.",
        "preview_sample": "CRISP CLEAN CAPTIONS",
        "config": {
            "style_id": "classic",
            "font_family": "Arial",
            "font_weight": "bold",
            "font_size": 52,
            "text_color": "#FFFFFF",
            "highlight_color": "#E2E8F0",
            "stroke_color": "#000000",
            "outline_width": 1.5,
            "background_type": "pill",
            "background_opacity": 0.82,
            "position": "safe_center",
            "animation": "static",
            "word_grouping": "cadence_1_3",
            "max_words_per_cue": 3,
            "version": 1
        }
    },
    {
        "style_id": "bold",
        "name": "Bold Voltage",
        "description": "High-voltage amber yellow text with thick black outline and contrast pill. Maximum retention.",
        "preview_sample": "BOLD HIGH RETENTION",
        "config": {
            "style_id": "bold",
            "font_family": "Impact",
            "font_weight": "bold",
            "font_size": 58,
            "text_color": "#FACC15",
            "highlight_color": "#FEF08A",
            "stroke_color": "#000000",
            "outline_width": 3.0,
            "background_type": "pill",
            "background_opacity": 0.85,
            "position": "safe_center",
            "animation": "pop",
            "word_grouping": "cadence_1_3",
            "max_words_per_cue": 2,
            "version": 1
        }
    },
    {
        "style_id": "kinetic",
        "name": "Kinetic Cyan",
        "description": "Electric cyan typography with punchy modern energy and dark slate backing.",
        "preview_sample": "ELECTRIC KINETIC CADENCE",
        "config": {
            "style_id": "kinetic",
            "font_family": "Helvetica",
            "font_weight": "bold",
            "font_size": 54,
            "text_color": "#38BDF8",
            "highlight_color": "#7DD3FC",
            "stroke_color": "#0F172A",
            "outline_width": 2.0,
            "background_type": "pill",
            "background_opacity": 0.88,
            "position": "safe_center",
            "animation": "bounce",
            "word_grouping": "cadence_1_3",
            "max_words_per_cue": 3,
            "version": 1
        }
    },
    {
        "style_id": "minimal",
        "name": "Minimalist Pure",
        "description": "Sleek borderless white text with subtle drop-shadow and no pill background.",
        "preview_sample": "SLEEK BORDERLESS STYLE",
        "config": {
            "style_id": "minimal",
            "font_family": "Arial",
            "font_weight": "bold",
            "font_size": 50,
            "text_color": "#FFFFFF",
            "highlight_color": "#CBD5E1",
            "stroke_color": "#000000",
            "outline_width": 1.0,
            "background_type": "none",
            "background_opacity": 0.0,
            "position": "safe_center",
            "animation": "static",
            "word_grouping": "cadence_1_3",
            "max_words_per_cue": 3,
            "version": 1
        }
    },
    {
        "style_id": "highlight_word",
        "name": "Neon Highlight",
        "description": "Vibrant emerald green keywords contrasting with crisp white text.",
        "preview_sample": "ACTIVE WORD HIGHLIGHT",
        "config": {
            "style_id": "highlight_word",
            "font_family": "Arial",
            "font_weight": "bold",
            "font_size": 56,
            "text_color": "#FFFFFF",
            "highlight_color": "#4ADE80",
            "stroke_color": "#000000",
            "outline_width": 2.5,
            "background_type": "pill",
            "background_opacity": 0.85,
            "position": "safe_center",
            "animation": "pop",
            "word_grouping": "cadence_1_3",
            "max_words_per_cue": 2,
            "version": 1
        }
    },
    {
        "style_id": "typewriter",
        "name": "Tech Typewriter",
        "description": "Monospace uppercase tech font with solid high-contrast dark box backing.",
        "preview_sample": "SYSTEM ALGORITHM PROMPT",
        "config": {
            "style_id": "typewriter",
            "font_family": "Courier",
            "font_weight": "bold",
            "font_size": 48,
            "text_color": "#F1F5F9",
            "highlight_color": "#64748B",
            "stroke_color": "#000000",
            "outline_width": 1.0,
            "background_type": "box",
            "background_opacity": 0.92,
            "position": "safe_center",
            "animation": "typewriter",
            "word_grouping": "cadence_1_3",
            "max_words_per_cue": 3,
            "version": 1
        }
    }
]

