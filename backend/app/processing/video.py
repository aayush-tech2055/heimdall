"""Short video into review units (tasks 11.1, 11.2, 11.3, 11.5).

* 11.1 FFmpeg: clips of at most 60 s; mono 16 kHz audio; a frame every 2 s.
* 11.2 Speech to text with Groq Whisper (segments with timestamps), grouped into ~15 s units.
* 11.3 On-screen text per distinct frame (Tesseract if installed, else the vision model),
  repeated text merged into one unit spanning its time range.
* 11.5 Captions (SRT or WebVTT) parsed into timed cues.
Every unit's location is {start, end} in seconds (decision 15).
"""

import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import pymupdf

from app.review.segment import Unit

MAX_SECONDS = 60.0
FRAME_EVERY = 2.0
WINDOW_SECONDS = 15.0
MAX_OCR_FRAMES = 12
GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class VideoError(ValueError):
    """The video could not be processed (too long, unreadable, no FFmpeg)."""


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Frame:
    t: float
    png: bytes


def _ffmpeg(*args: str) -> subprocess.CompletedProcess:
    if shutil.which("ffmpeg") is None:
        raise VideoError("FFmpeg is not installed on the server")
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *args], capture_output=True, timeout=120
    )
    if result.returncode != 0:
        raise VideoError(f"FFmpeg failed: {result.stderr.decode(errors='replace')[:300]}")
    return result


def duration(path: Path) -> float:
    if shutil.which("ffprobe") is None:
        raise VideoError("FFmpeg (ffprobe) is not installed on the server")
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=30,
    )  # fmt: skip
    try:
        return float(out.stdout.strip())
    except ValueError as exc:
        raise VideoError("the file is not a readable video") from exc


def extract(data: bytes) -> tuple[float, bytes, list[Frame]]:
    """(duration, mp3 audio or b"" if silent, frames every 2 s) for a clip of at most 60 s."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "clip"
        src.write_bytes(data)
        seconds = duration(src)
        if seconds > MAX_SECONDS + 0.5:
            raise VideoError(f"the clip is {seconds:.0f} s long; the limit is {MAX_SECONDS:.0f} s")
        audio = Path(tmp) / "audio.mp3"
        try:
            _ffmpeg("-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(audio))
            audio_bytes = audio.read_bytes()
        except VideoError:
            audio_bytes = b""  # no audio track
        _ffmpeg("-i", str(src), "-vf", f"fps=1/{FRAME_EVERY:g},scale='min(1280,iw)':-2",
                str(Path(tmp) / "f%03d.png"))  # fmt: skip
        frames = [Frame(t=i * FRAME_EVERY, png=p.read_bytes())
                  for i, p in enumerate(sorted(Path(tmp).glob("f*.png")))]  # fmt: skip
    return seconds, audio_bytes, frames


def transcribe(
    audio: bytes, *, api_key: str, model: str, client: httpx.Client | None = None,
    sleep: callable = time.sleep,
) -> list[Segment]:  # fmt: skip
    """Groq Whisper with segment timestamps; retried on rate limits."""
    if not audio:
        return []
    if not api_key:
        raise VideoError("GROQ_API_KEY is needed for speech to text")
    client = client or httpx.Client(timeout=120)
    for attempt in range(4):
        resp = client.post(
            GROQ_TRANSCRIBE_URL, headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("audio.mp3", audio, "audio/mpeg")},
            data={"model": model, "response_format": "verbose_json", "temperature": "0"},
        )  # fmt: skip
        if resp.status_code == 429 and attempt < 3:
            sleep(min(30.0, float(resp.headers.get("retry-after", 2 ** (attempt + 1)))))
            continue
        if resp.is_error:
            raise VideoError(f"speech to text failed: HTTP {resp.status_code} {resp.text[:200]}")
        return [Segment(float(s["start"]), float(s["end"]), s["text"].strip())
                for s in resp.json().get("segments", []) if s.get("text", "").strip()]  # fmt: skip
    raise VideoError("speech to text is rate limited; try again shortly")


def speech_units(segments: list[Segment], window: float = WINDOW_SECONDS) -> list[Unit]:
    """Group transcript segments into units of about `window` seconds (never splitting one)."""
    units: list[Unit] = []
    group: list[Segment] = []

    def flush() -> None:
        if group:
            n = len(units)
            units.append(Unit(
                unit_id=f"s{n + 1}", position=n, text=" ".join(s.text for s in group),
                location={"start": round(group[0].start, 2), "end": round(group[-1].end, 2),
                          "source": "speech"},
            ))  # fmt: skip
            group.clear()

    for seg in segments:
        if group and seg.end - group[0].start > window:
            flush()
        group.append(seg)
    flush()
    return units


def _frame_hash(png: bytes) -> int:
    """Average hash of a frame (8x8 grey), to skip near-identical frames."""
    pix = pymupdf.Pixmap(png)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
    while pix.width > 16 and pix.height > 16:
        pix.shrink(1)
    w, h, s = pix.width, pix.height, pix.samples
    cells = []
    for gy in range(8):
        for gx in range(8):
            x, y = min(w - 1, gx * w // 8), min(h - 1, gy * h // 8)
            cells.append(s[y * w + x])
    avg = sum(cells) / len(cells)
    return sum(1 << i for i, c in enumerate(cells) if c > avg)


def distinct_frames(
    frames: list[Frame], limit: int = MAX_OCR_FRAMES, threshold: int = 6
) -> list[Frame]:
    """Frames that differ from the previous kept one (Hamming distance of the hash)."""
    kept: list[tuple[Frame, int]] = []
    for f in frames:
        h = _frame_hash(f.png)
        if not kept or bin(h ^ kept[-1][1]).count("1") > threshold:
            kept.append((f, h))
    if len(kept) > limit:  # spread the sample over the whole clip
        step = len(kept) / limit
        kept = [kept[int(i * step)] for i in range(limit)]
    return [f for f, _ in kept]


def screen_units(ocr: list[tuple[float, str]], first_index: int = 0) -> list[Unit]:
    """On-screen text per frame -> units; the same text on consecutive frames is one unit."""
    units: list[Unit] = []
    norm = lambda t: " ".join(t.lower().split())  # noqa: E731
    current: tuple[float, float, str] | None = None
    for t, text in sorted(ocr):
        text = " ".join(text.split())
        if not text:
            continue
        if current and norm(current[2]) == norm(text):
            current = (current[0], t + FRAME_EVERY, current[2])
            continue
        if current:
            units.append(current)  # type: ignore[arg-type]
        current = (t, t + FRAME_EVERY, text)
    if current:
        units.append(current)  # type: ignore[arg-type]
    return [Unit(unit_id=f"o{i + 1}", position=first_index + i, text=text,
                 location={"start": start, "end": end, "source": "screen"})
            for i, (start, end, text) in enumerate(units)]  # fmt: skip


def tesseract_text(png: bytes) -> str | None:
    """On-screen text with Tesseract, or None if Tesseract is not installed."""
    if shutil.which("tesseract") is None:
        return None
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        f.write(png)
        f.flush()
        out = subprocess.run(["tesseract", f.name, "-", "--psm", "11"], capture_output=True,
                             text=True, timeout=60)  # fmt: skip
    return out.stdout if out.returncode == 0 else ""


_TIME = r"(\d{1,2}:)?(\d{1,2}):(\d{2})[.,](\d{1,3})"


def _seconds(stamp: str) -> float:
    parts = re.split(r"[:.,]", stamp)
    *hm, s, ms = parts
    h, m = (0, int(hm[0])) if len(hm) == 1 else (int(hm[0]), int(hm[1]))
    return h * 3600 + m * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_captions(text: str) -> list[Segment]:
    """SRT or WebVTT cues as timed segments."""
    cues: list[Segment] = []
    pattern = re.compile(rf"({_TIME})\s*-->\s*({_TIME})[^\n]*\n(.*?)(?:\n\s*\n|\Z)", re.S)
    for m in pattern.finditer(text.replace("\r\n", "\n")):
        body = re.sub(r"<[^>]+>", "", m.group(11)).strip()
        if body:
            cues.append(Segment(_seconds(m.group(1)), _seconds(m.group(6)), " ".join(body.split())))
    return cues
