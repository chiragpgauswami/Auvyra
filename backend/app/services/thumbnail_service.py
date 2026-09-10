import os
import shutil
import subprocess
import tempfile
from typing import Optional, List
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from loguru import logger
from backend.app.video.rendering.ffmpeg import probe_video_info

class ThumbnailService:
    """Extracts optimal video frames and renders high-CTR mobile-optimized thumbnail graphics."""

    def __init__(self, output_dir: str = "media/thumbnails"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def extract_best_frame(self, video_path: str, output_image_path: str) -> str:
        """Samples multiple frames across video and selects the frame with highest visual entropy/contrast."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        info = probe_video_info(video_path)
        duration = float(info.get("duration", 0.0))
        if duration <= 0.5:
            duration = 3.0

        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
        temp_candidates: List[str] = []
        sample_times = [
            duration * 0.15,
            duration * 0.35,
            duration * 0.50,
            duration * 0.70,
            duration * 0.85
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            for idx, t in enumerate(sample_times):
                frame_out = os.path.join(temp_dir, f"cand_{idx}.jpg")
                cmd = [
                    ffmpeg_bin, "-y",
                    "-ss", f"{t:.2f}",
                    "-i", video_path,
                    "-vframes", "1",
                    "-q:v", "2",
                    frame_out
                ]
                res = subprocess.run(cmd, capture_output=True, timeout=30)
                if res.returncode == 0 and os.path.exists(frame_out) and os.path.getsize(frame_out) > 5000:
                    temp_candidates.append(frame_out)

            if not temp_candidates:
                # Direct grab of 1st frame fallback
                cmd = [ffmpeg_bin, "-y", "-i", video_path, "-vframes", "1", "-q:v", "2", output_image_path]
                subprocess.run(cmd, check=True, timeout=30)
                return output_image_path

            # Score each candidate: prioritize high contrast variance and clear luminance
            best_frame = temp_candidates[0]
            best_score = -1.0

            for cand in temp_candidates:
                try:
                    with Image.open(cand) as img:
                        arr = np.array(img.convert("L"), dtype=np.float32)
                        variance = float(np.var(arr))
                        mean_lum = float(np.mean(arr))
                        # Heavily penalize near-black frames (mean < 25)
                        if mean_lum < 25 or mean_lum > 240:
                            variance *= 0.1
                        score = variance
                        if score > best_score:
                            best_score = score
                            best_frame = cand
                except Exception as e:
                    logger.warning(f"Failed to inspect frame {cand}: {e}")

            shutil.copyfile(best_frame, output_image_path)

        return output_image_path

    def generate_thumbnail(
        self,
        video_path: Optional[str] = None,
        text_overlay: str = "",
        output_filename: str = "thumbnail.jpg",
        target_width: int = 1080,
        target_height: int = 1920
    ) -> str:
        """Generates a high-contrast thumbnail with bold typography and dark backdrop pill."""
        final_path = os.path.join(self.output_dir, output_filename)
        os.makedirs(os.path.dirname(final_path), exist_ok=True)

        # 1. Base Image
        if video_path and os.path.exists(video_path):
            temp_frame = os.path.join(self.output_dir, f"temp_{output_filename}")
            try:
                self.extract_best_frame(video_path, temp_frame)
                base_img = Image.open(temp_frame).convert("RGBA")
                if os.path.exists(temp_frame):
                    os.remove(temp_frame)
            except Exception as e:
                logger.warning(f"Could not extract frame from {video_path}: {e}. Creating canvas.")
                base_img = Image.new("RGBA", (target_width, target_height), (18, 24, 38, 255))
        else:
            base_img = Image.new("RGBA", (target_width, target_height), (18, 24, 38, 255))

        # Resize to target canvas size
        base_img = base_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # 2. Text Overlay
        text = text_overlay.strip().upper()
        if text:
            overlay_layer = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay_layer)

            # Choose font
            font_size = max(42, int(target_width * 0.075))
            font = None
            font_candidates = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/Supplemental/Impact.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            ]
            for fc in font_candidates:
                if os.path.exists(fc):
                    try:
                        font = ImageFont.truetype(fc, font_size)
                        break
                    except Exception:
                        pass
            if not font:
                font = ImageFont.load_default()

            # Word wrap text if too wide
            words = text.split()
            lines = []
            cur_line = []
            for w in words:
                cur_line.append(w)
                bbox = draw.textbbox((0, 0), " ".join(cur_line), font=font)
                if bbox[2] - bbox[0] > target_width * 0.85 and len(cur_line) > 1:
                    cur_line.pop()
                    lines.append(" ".join(cur_line))
                    cur_line = [w]
            if cur_line:
                lines.append(" ".join(cur_line))

            # Calculate total text box height
            line_height = int(font_size * 1.25)
            total_text_h = len(lines) * line_height
            y_start = int(target_height * 0.28)  # Position in upper third for Shorts

            # Draw contrast backdrop pill
            max_line_w = 0
            for l in lines:
                bb = draw.textbbox((0, 0), l, font=font)
                max_line_w = max(max_line_w, bb[2] - bb[0])

            padding_x = 40
            padding_y = 30
            pill_x0 = (target_width - max_line_w) // 2 - padding_x
            pill_y0 = y_start - padding_y
            pill_x1 = (target_width + max_line_w) // 2 + padding_x
            pill_y1 = y_start + total_text_h + padding_y

            # Semi-transparent dark background pill
            draw.rounded_rectangle(
                [(pill_x0, pill_y0), (pill_x1, pill_y1)],
                radius=24,
                fill=(0, 0, 0, 190)
            )

            # Draw text with yellow/white high-retention highlight
            cur_y = y_start
            for idx, line in enumerate(lines):
                bb = draw.textbbox((0, 0), line, font=font)
                w = bb[2] - bb[0]
                x = (target_width - w) // 2
                text_color = (255, 220, 0, 255) if idx == 0 else (255, 255, 255, 255)
                # Black stroke
                for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2)]:
                    draw.text((x + dx, cur_y + dy), line, font=font, fill=(0, 0, 0, 255))
                draw.text((x, cur_y), line, font=font, fill=text_color)
                cur_y += line_height

            base_img = Image.alpha_composite(base_img, overlay_layer)

        rgb_img = base_img.convert("RGB")
        rgb_img.save(final_path, "JPEG", quality=90, optimize=True)

        logger.info(f"Generated thumbnail saved to {final_path} ({os.path.getsize(final_path)} bytes)")
        return final_path
