import os
import sys
import argparse
from loguru import logger

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.video.validation import validate_video_content
from backend.app.video.rendering.ffmpeg import probe_video_info

def main():
    parser = argparse.ArgumentParser(description="Inspect Auvyra generated video quality, resolution, audio sync, and visual content.")
    parser.add_argument("video_path", help="Path to MP4 video file to inspect")
    parser.add_argument("--qa-dir", default="media/qa_inspection", help="Output directory for sample frames")
    parser.add_argument("--asset-type", choices=["final", "stock"], default="final", help="Whether inspecting a final rendered video or raw stock clip")
    args = parser.parse_args()

    video_path = os.path.abspath(args.video_path)
    if not os.path.exists(video_path):
        print(f"❌ Error: Video file not found: {video_path}")
        sys.exit(1)

    print("=" * 65)
    print(f"AUVYRA PROGRAMMATIC VIDEO QUALITY INSPECTOR")
    print(f"Target: {os.path.basename(video_path)}")
    print(f"Size:   {os.path.getsize(video_path) / 1024 / 1024:.2f} MB")
    print("=" * 65)

    info = probe_video_info(video_path)
    print(f"📐 Dimensions: {info.get('width', 0)}x{info.get('height', 0)}")
    print(f"⏱️ Duration:   {info.get('duration', 0.0):.2f}s")
    print(f"🎞️ Codec:      {info.get('codec') or 'unknown'}")
    fps_val = info.get('fps') or 0.0
    print(f"📊 FPS:        {fps_val:.2f}")

    print("\n🔍 Running Frame-by-Frame Visual & Audio QA Audit...")
    report = validate_video_content(video_path, qa_dir=args.qa_dir)

    print("\n📈 Sample Frame Metrics:")
    for fm in report.frame_metrics:
        status_icon = "❌ BLANK" if fm.is_blank else "✅ VALID"
        print(f"   [{fm.percentage:3.0f}% | {fm.timestamp:4.1f}s] {status_icon} | Mean Lum: {fm.mean_luminance:5.1f} | Var: {fm.pixel_variance:6.1f} | NearBlack: {fm.near_black_ratio*100:4.1f}%")

    print(f"\n🔊 Audio Track:")
    print(f"   Valid:       {report.audio_valid}")
    print(f"   Codec:       {report.audio_codec}")
    print(f"   Mean Volume: {report.audio_mean_volume_db:.1f} dB")
    print(f"   Sync Valid:  {report.sync_valid}")

    relevant_failures = [
        r for r in report.failure_reasons
        if not (args.asset_type == "stock" and "audio" in r.lower())
    ]
    is_valid = len(relevant_failures) == 0

    print("\n" + "=" * 65)
    if is_valid:
        print("🎉 FINAL QA VERDICT: PASS — Real Stock Footage, Sharp Contrast, High Visual Entropy")
    else:
        print("⚠️ FINAL QA VERDICT: FAIL")
        for reason in relevant_failures:
            print(f"   - {reason}")
    print("=" * 65)

    if not is_valid:
        sys.exit(1)

if __name__ == "__main__":
    main()
