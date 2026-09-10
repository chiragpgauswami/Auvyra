from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

class VideoMetadataPackage(BaseModel):
    title: str = Field(..., max_length=100)
    title_candidates: List[str] = Field(default_factory=list)
    description: str = Field(..., max_length=5000)
    tags: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    thumbnail_concept: str = ""
    thumbnail_text_overlay: str = Field(default="", max_length=50)
    category_id: str = "28"  # YouTube Category 28: Science & Technology

    @model_validator(mode="before")
    @classmethod
    def clean_metadata(cls, data: dict) -> dict:
        if isinstance(data, dict):
            # Clean title
            title = data.get("title") or "Untitled Video"
            data["title"] = title.replace("\n", " ").strip()[:100]

            # Clean tags (YouTube tag limit total 500 chars)
            tags = data.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            data["tags"] = [str(t).strip() for t in tags if str(t).strip()][:25]

            # Clean hashtags
            hts = data.get("hashtags") or []
            if isinstance(hts, str):
                hts = [h.strip() for h in hts.split() if h.strip()]
            clean_hts = []
            for h in hts:
                tag = str(h).strip()
                if not tag.startswith("#"):
                    tag = f"#{tag}"
                clean_hts.append(tag)
            data["hashtags"] = clean_hts[:10]

            # Clean thumbnail text overlay
            text_overlay = data.get("thumbnail_text_overlay") or ""
            data["thumbnail_text_overlay"] = str(text_overlay).strip()[:50]

        return data
