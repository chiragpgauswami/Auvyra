"""
QA Gate Engine for Autopilot Production Pipeline.
Enforces the mandatory QA gate (Requirement 5). QA failure strictly blocks publishing.
"""

import os
from typing import Dict, Any, Optional
from loguru import logger

from backend.app.autopilot.exceptions import QAGateError
from backend.app.video.validation import validate_video_content, VisualQAReport
from backend.app.video.subtitles.srt_parser import parse_srt

class QAEngine:
    """Mandatory quality gate verifying every dimension of rendered video before publishing."""

    @staticmethod
    def inspect_and_gate(
        video_path: str,
        subtitle_path: Optional[str] = None,
        expected_format: str = "shorts",
        min_duration: float = 25.0,
        max_duration: float = 65.0
    ) -> Dict[str, Any]:
        """
        Validates output video against strict production standards.
        Raises QAGateError on any failure. Returns QA summary on success.
        """
        if not video_path or not os.path.exists(video_path):
            raise QAGateError(
                message=f"Rendered video file not found: {video_path}",
                details={"error_code": "FILE_NOT_FOUND", "path": video_path}
            )

        file_size = os.path.getsize(video_path)
        if file_size < 100 * 1024:  # Under 100KB is definitely broken
            raise QAGateError(
                message=f"Rendered video file size is abnormally small ({file_size} bytes)",
                details={"error_code": "FILE_TOO_SMALL", "size_bytes": file_size}
            )

        # Run programmatic frame-by-frame and audio inspection
        report: VisualQAReport = validate_video_content(video_path)
        failures = list(report.failure_reasons)

        # 1. Video stream and container checks
        if report.width <= 0 or report.height <= 0:
            failures.append(f"Invalid video dimensions: {report.width}x{report.height}")

        # 2. Aspect ratio / resolution check
        if expected_format == "shorts":
            # YouTube Shorts requires vertical portrait (e.g. 1080x1920 or height > width)
            if report.height <= report.width:
                failures.append(f"Shorts requires vertical 9:16 aspect ratio, got {report.width}x{report.height}")
            if report.width < 720:
                failures.append(f"Video resolution too low for YouTube Shorts: width {report.width} < 720")

        # 3. Audio stream checks
        if not report.audio_valid:
            failures.append("Audio stream missing, silent, or unreadable")
        elif report.audio_mean_volume_db < -60.0:
            failures.append(f"Audio track is virtually silent ({report.audio_mean_volume_db:.1f} dB)")

        # 4. Duration sanity check
        if report.duration < min_duration or report.duration > max_duration:
            failures.append(
                f"Video duration {report.duration:.1f}s out of acceptable bounds [{min_duration}s, {max_duration}s]"
            )

        # 5. Audio / Video sync and alignment
        if report.audio_valid and report.duration > 0:
            dur_diff = abs(report.duration - report.audio_duration)
            if dur_diff > 1.5:  # Tolerance threshold
                failures.append(f"Audio/video duration misalignment ({dur_diff:.2f}s difference)")

        # 6. Subtitle existence and timing sanity
        if subtitle_path:
            if not os.path.exists(subtitle_path):
                failures.append(f"Subtitle file referenced but missing on disk: {subtitle_path}")
            else:
                try:
                    entries = parse_srt(subtitle_path)
                    if not entries:
                        failures.append("Subtitle file is empty (0 subtitle entries parsed)")
                    else:
                        first_entry = entries[0]
                        last_entry = entries[-1]
                        logger.info(f"QA Subtitle check: {len(entries)} entries, span: {first_entry[1]} -> {last_entry[1]}")
                except Exception as e:
                    failures.append(f"Failed to parse subtitle file: {e}")

        # Check frame analysis results
        blank_frames = sum(1 for fm in report.frame_metrics if fm.is_blank)
        total_sample_frames = len(report.frame_metrics)
        if total_sample_frames > 0 and (blank_frames / total_sample_frames) > 0.4:
            failures.append(f"Excessive blank or static black void frames ({blank_frames}/{total_sample_frames} sampled)")

        if failures:
            error_msg = f"QA verification failed with {len(failures)} issue(s): {'; '.join(failures)}"
            logger.error(f"QA Gate BLOCKED: {error_msg}")
            raise QAGateError(
                message=error_msg,
                details={
                    "failures": failures,
                    "video_path": video_path,
                    "duration": report.duration,
                    "dimensions": f"{report.width}x{report.height}",
                    "audio_volume_db": report.audio_mean_volume_db
                }
            )

        qa_summary = {
            "passed": True,
            "video_path": video_path,
            "duration": report.duration,
            "width": report.width,
            "height": report.height,
            "fps": report.fps,
            "audio_mean_volume_db": report.audio_mean_volume_db,
            "total_sampled_frames": total_sample_frames,
            "blank_frames": blank_frames
        }
        logger.info(f"QA Gate PASSED for {os.path.basename(video_path)} ({report.duration:.1f}s, {report.width}x{report.height})")
        return qa_summary

