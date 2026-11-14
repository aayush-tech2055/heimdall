"""Video processing (tasks 11.1, 11.2, 11.3, 11.5)."""

import shutil
import subprocess

import httpx
import pymupdf
import pytest

from app.processing.video import (
    Frame,
    Segment,
    VideoError,
    distinct_frames,
    extract,
    parse_captions,
    screen_units,
    speech_units,
    transcribe,
)

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg not installed")


def clip(seconds: int) -> bytes:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=10:d={seconds}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-shortest",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-f", "mp4",
         "-movflags", "frag_keyframe+empty_moov", "pipe:1"],
        capture_output=True, check=True,
    )  # fmt: skip
    return out.stdout


@needs_ffmpeg
def test_extract_audio_and_a_frame_every_two_seconds():
    seconds, audio, frames = extract(clip(6))
    assert 5.5 <= seconds <= 6.5
    assert len(audio) > 1000
    assert [f.t for f in frames] == [0.0, 2.0, 4.0]
    assert all(f.png.startswith(b"\x89PNG") for f in frames)


@needs_ffmpeg
def test_clips_over_sixty_seconds_are_refused():
    with pytest.raises(VideoError, match="limit is 60"):
        extract(clip(62))


def test_not_a_video():
    if shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg not installed")
    with pytest.raises(VideoError):
        extract(b"not a video")


def test_speech_units_group_segments_into_about_fifteen_seconds():
    segs = [Segment(i * 4.0, i * 4.0 + 3.5, f"Line {i}.") for i in range(10)]  # 0..39.5 s
    units = speech_units(segs)
    assert [(u.location["start"], u.location["end"]) for u in units] == [
        (0.0, 11.5),
        (12.0, 23.5),
        (24.0, 35.5),
        (36.0, 39.5),
    ]
    assert units[0].text == "Line 0. Line 1. Line 2."
    assert all(u.location["source"] == "speech" for u in units)


def test_screen_units_merge_repeated_text_across_frames():
    ocr = [
        (0.0, "Python  bootcamp"),
        (2.0, "python bootcamp"),
        (4.0, ""),
        (6.0, "Join today"),
        (8.0, "Python bootcamp"),
    ]
    units = screen_units(ocr, first_index=3)
    assert [(u.text, u.location["start"], u.location["end"], u.position) for u in units] == [
        ("Python bootcamp", 0.0, 4.0, 3),
        ("Join today", 6.0, 8.0, 4),
        ("Python bootcamp", 8.0, 10.0, 5),
    ]


def _png(rgb: tuple[int, int, int], stripe: bool = False) -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 64, 64), False)
    pix.set_rect(pix.irect, rgb)
    if stripe:
        pix.set_rect(pymupdf.IRect(0, 0, 32, 64), (255, 255, 255))
    return pix.tobytes("png")


def test_distinct_frames_skip_near_identical_ones():
    a, b = _png((10, 10, 10)), _png((10, 10, 10), stripe=True)
    frames = [Frame(0, a), Frame(2, a), Frame(4, b), Frame(6, b), Frame(8, a)]
    assert [f.t for f in distinct_frames(frames)] == [0, 4, 8]


def test_parse_srt_and_vtt_captions():
    srt = "1\n00:00:01,000 --> 00:00:03,500\nHello <i>there</i>\n\n2\n00:00:04,000 --> 00:00:06,000\nJoin us\ntoday\n"
    vtt = "WEBVTT\n\n00:01.000 --> 00:03.500 align:start\nHello there\n\n00:04.000 --> 00:06.000\nJoin us today\n"
    for text in (srt, vtt):
        cues = parse_captions(text)
        assert [(c.start, c.end, c.text) for c in cues] == [
            (1.0, 3.5, "Hello there"),
            (4.0, 6.0, "Join us today"),
        ]


def test_transcribe_retries_rate_limits_and_returns_segments():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(
            200,
            json={
                "segments": [
                    {"start": 0, "end": 2.5, "text": " Hi! "},
                    {"start": 2.5, "end": 3, "text": " "},
                ]
            },
        )

    sleeps = []
    segs = transcribe(
        b"mp3",
        api_key="k",
        model="whisper-large-v3",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
    )
    assert segs == [Segment(0.0, 2.5, "Hi!")] and sleeps == [1.0]
    assert b'name="model"' in calls[1].content and b"verbose_json" in calls[1].content
    assert transcribe(b"", api_key="k", model="m") == []
