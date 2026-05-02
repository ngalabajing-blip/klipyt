"""Clip cutting with stream copy (low memory) and optional reframe.

Default mode uses ``-c copy`` (stream copy) which requires almost no memory
and is extremely fast.  9:16 reframe is available as an opt-in but disabled
by default to stay within Railway's 512 MB memory limit.
"""

from __future__ import annotations

import logging
import math
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

TARGET_W = 1080
TARGET_H = 1920


@dataclass(slots=True)
class CutOptions:
    start: float
    end: float
    out_path: Path
    aspect: str = "9:16"  # "9:16" | "1:1" | "16:9"
    target_w: int = TARGET_W
    target_h: int = TARGET_H


def _probe_resolution(video_path: Path) -> tuple[int, int]:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(video_path),
        ]
    )
    w_str, h_str = out.decode().strip().split(",")[:2]
    return int(w_str), int(h_str)


def _detect_face_centres(video_path: Path, fps: float = 1.0) -> list[tuple[float, float]]:
    """Return (timestamp, normalized_x_centre) samples — best-effort.

    Tries the legacy ``mediapipe.solutions.face_detection`` API first (faster,
    simpler) and falls back to the new ``mediapipe.tasks`` API or to a static
    centre crop if neither is available.
    """
    try:
        import cv2  # type: ignore
        import mediapipe as mp  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dep
        logger.warning("MediaPipe unavailable, falling back to centre crop: %s", exc)
        return []

    # Mediapipe 0.10.x dropped the legacy `solutions` namespace by default.
    face_detection = None
    try:
        face_detection = mp.solutions.face_detection.FaceDetection(  # type: ignore[attr-defined]
            model_selection=1, min_detection_confidence=0.5
        )
    except AttributeError:
        logger.info(
            "mediapipe.solutions.face_detection unavailable on this build; "
            "using centre-crop fallback"
        )
        return []

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []
    try:
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        step = max(1, int(round(video_fps / max(0.1, fps))))
        idx = 0
        samples: list[tuple[float, float]] = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = face_detection.process(rgb)
                t = idx / video_fps
                if result.detections:
                    cx = max(
                        result.detections,
                        key=lambda d: d.score[0] if d.score else 0,
                    ).location_data.relative_bounding_box
                    centre_x = cx.xmin + cx.width / 2.0
                    samples.append((t, float(centre_x)))
                else:
                    samples.append((t, 0.5))
            idx += 1
        return samples
    finally:
        cap.release()


def _smooth(samples: list[tuple[float, float]], window: int = 5) -> list[tuple[float, float]]:
    if not samples:
        return samples
    smoothed: list[tuple[float, float]] = []
    n = len(samples)
    for i, (t, _x) in enumerate(samples):
        lo = max(0, i - window // 2)
        hi = min(n, i + window // 2 + 1)
        avg = sum(s[1] for s in samples[lo:hi]) / (hi - lo)
        smoothed.append((t, avg))
    return smoothed


def _build_crop_filter(
    src_w: int,
    src_h: int,
    aspect: str,
    target_w: int,
    target_h: int,
    centres: Sequence[tuple[float, float]] | None,
) -> str:
    """Return an ffmpeg ``-vf`` filter string that crops + scales to target.

    For now we use a single static crop centre (the median of detected centres) —
    this produces stable output without needing per-frame ffmpeg expressions.
    Future iteration can use sendcmd / zoompan for animated reframing.
    """
    if aspect == "16:9":
        crop_w, crop_h = src_w, int(src_w * 9 / 16)
        if crop_h > src_h:
            crop_h = src_h
            crop_w = int(src_h * 16 / 9)
        x_expr = f"(in_w-{crop_w})/2"
        y_expr = "(in_h-out_h)/2"
    elif aspect == "1:1":
        side = min(src_w, src_h)
        crop_w = crop_h = side
        if centres:
            xs = sorted(c[1] for c in centres)
            mid = xs[len(xs) // 2]
            x_expr = f"max(0,min(in_w-{crop_w},{int(mid * src_w)}-{crop_w}/2))"
        else:
            x_expr = "(in_w-out_w)/2"
        y_expr = "(in_h-out_h)/2"
    else:  # default "9:16"
        crop_h = src_h
        crop_w = int(round(src_h * 9 / 16))
        if crop_w > src_w:
            crop_w = src_w
            crop_h = int(round(src_w * 16 / 9))
        if centres:
            xs = sorted(c[1] for c in centres)
            mid = xs[len(xs) // 2]
        else:
            mid = 0.5
        target_x = int(mid * src_w - crop_w / 2)
        target_x = max(0, min(src_w - crop_w, target_x))
        x_expr = str(target_x)
        y_expr = f"(in_h-{crop_h})/2"

    return (
        f"crop={crop_w}:{crop_h}:{x_expr}:{y_expr},"
        f"scale={target_w}:{target_h}:flags=lanczos,setsar=1"
    )


def cut_clip(video_path: str | Path, opts: CutOptions) -> Path:
    """Cut a clip from *video_path* using stream copy (no re-encode).

    This is extremely fast and uses almost no memory — perfect for Railway's
    512 MB limit.  The output container is always MP4 with faststart flag.
    """
    video_path = Path(video_path)
    opts.out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.1, opts.end - opts.start)

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{opts.start:.3f}",
        "-i", str(video_path),
        "-t", f"{duration:.3f}",
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        str(opts.out_path),
    ]
    logger.info("ffmpeg cut_clip (stream copy): %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return opts.out_path


def make_thumbnail(clip_path: str | Path, out_path: str | Path, t: float = 1.0) -> Path:
    """Extract a single JPEG thumbnail at ``t`` seconds into the clip."""
    clip_path = Path(clip_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(clip_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path


def quick_extract_window(
    video_path: str | Path,
    start: float,
    end: float,
    out_path: str | Path,
) -> Path:
    """Stream-copy a [start, end) window — used to feed Omni a small clip."""
    video_path = Path(video_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.1, end - start)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{duration:.3f}",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path


def estimate_duration(path: str | Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    try:
        return float(out.decode().strip())
    except ValueError:
        return math.nan
