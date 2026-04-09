from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class VideoError(RuntimeError):
    pass


@dataclass
class VideoRecorder:
    width: int = 1080
    height: int = 1920

    def capture_scroll(self, page_url: str, output_dir: Path, duration_seconds: float = 6.7) -> Path:
        if not page_url.strip():
            raise VideoError("Page URL is required for video capture.")
        if not page_url.startswith("http"):
            raise VideoError("Page URL must start with http/https.")
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError as exc:
            raise VideoError("playwright is not installed. Run: pip install playwright") from exc

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": self.width, "height": self.height},
                record_video_dir=str(output_dir),
                record_video_size={"width": self.width, "height": self.height},
            )
            page = context.new_page()
            page.goto(page_url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollTo(0, 0)")

            steps = max(20, int(duration_seconds * 6))
            wait_ms = max(80, int((duration_seconds * 1000) / steps))

            for index in range(steps):
                ratio = (index + 1) / steps
                page.evaluate(
                    """
                    (r) => {
                        const maxScroll = Math.max(
                            document.body.scrollHeight,
                            document.documentElement.scrollHeight
                        ) - window.innerHeight;
                        const y = Math.max(0, Math.floor(maxScroll * r));
                        window.scrollTo(0, y);
                    }
                    """,
                    ratio,
                )
                page.wait_for_timeout(wait_ms)

            page.wait_for_timeout(1000)
            context.close()
            browser.close()
            return Path(page.video.path()).resolve()


def _escape_drawtext(text: str) -> str:
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace("%", "\\%")
    escaped = escaped.replace("\n", " ")
    return escaped


def add_text_layer(input_video: Path, output_video: Path, text: str) -> Path:
    if not input_video.exists():
        raise VideoError(f"Input video not found: {input_video}")
    if not text.strip():
        raise VideoError("Text layer content cannot be empty.")
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise VideoError("ffmpeg is required but was not found in PATH.")

    output_video.parent.mkdir(parents=True, exist_ok=True)
    drawtext = (
        "drawtext="
        f"text='{_escape_drawtext(text)}':"
        "fontcolor=white:fontsize=56:"
        "box=1:boxcolor=black@0.55:boxborderw=24:"
        "x=(w-text_w)/2:y=h*0.08"
    )
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_video),
        "-vf",
        drawtext,
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_video),
    ]
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise VideoError(f"ffmpeg failed: {proc.stderr[-800:]}")
    return output_video.resolve()
