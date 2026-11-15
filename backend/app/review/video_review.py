"""Prepare a short video for review (task 11.4): transcript units, on-screen text units and
frames for the visual layer, all located by {start, end} seconds."""

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import UUID

from app.config import Settings
from app.llm import prompts
from app.llm.call_log import CallLogger, CallRecord
from app.llm.client import LLMClient
from app.llm.errors import LLMUnavailableError
from app.processing.video import (
    Segment,
    distinct_frames,
    extract,
    parse_captions,
    screen_units,
    speech_units,
    tesseract_text,
    transcribe,
)
from app.review.segment import Unit
from app.review.visuals import ImageInput


@dataclass
class PreparedVideo:
    units: list[Unit]  # speech (s1…) then on-screen text (o1…)
    images: list[ImageInput]  # distinct frames, timed
    text: str  # a readable transcript with timestamps
    cues: list[Segment] | None  # captions, or None if no captions file
    seconds: float


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def prepare_video(
    data: bytes,
    captions: str | None,
    *,
    settings: Settings,
    client: LLMClient,
    logger: CallLogger,
    brand_id: UUID | None = None,
    version_id: UUID | None = None,
) -> PreparedVideo:
    seconds, audio, frames = extract(data)

    started = time.perf_counter()
    try:
        segments = transcribe(
            audio, api_key=settings.groq_api_key, model=settings.groq_whisper_model
        )
        ok, error = True, None
    except Exception as exc:
        ok, error = False, str(exc)[:500]
        raise
    finally:
        if audio:
            logger.log(CallRecord(
                provider="groq", model=settings.groq_whisper_model, purpose="transcription",
                ok=ok, error=error, latency_ms=int((time.perf_counter() - started) * 1000),
                brand_id=brand_id, content_version_id=version_id,
            ))  # fmt: skip
    speech = speech_units(segments)

    distinct = distinct_frames(frames)

    def read(frame) -> tuple[float, str]:  # noqa: ANN001
        local = tesseract_text(frame.png)
        if local is not None:
            return frame.t, local
        p = prompts.screen_text(frame.t)
        try:
            out = client.json(p.schema, p.system, p.prompt, purpose=p.purpose, brand_id=brand_id,
                              content_version_id=version_id, images=[frame.png])  # fmt: skip
        except LLMUnavailableError:
            return frame.t, ""  # on-screen text is best effort; speech and visuals still run
        return frame.t, out.text

    with ThreadPoolExecutor(max_workers=2) as pool:
        ocr = list(pool.map(read, distinct))
    screen = screen_units(ocr, first_index=len(speech))

    images = [ImageInput(f"f{int(f.t)}", f.png, start=f.t, end=f.t + 2.0) for f in distinct]
    lines = [
        f"[{_clock(u.location['start'])}–{_clock(u.location['end'])}] {u.text}" for u in speech
    ]
    lines += [f"[on screen {_clock(u.location['start'])}–{_clock(u.location['end'])}] {u.text}"
              for u in screen]  # fmt: skip
    return PreparedVideo(
        units=[*speech, *screen], images=images, text="\n\n".join(lines) or "(no speech or text)",
        cues=parse_captions(captions) if captions else None, seconds=seconds,
    )  # fmt: skip
