from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
DEFAULT_FALLBACK_STEMS = ("default", "fallback", "cover")
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
DEFAULT_TTS_RESPONSE_FORMAT = "wav"
DEFAULT_SUBTITLE_FORCE_STYLE = "Fontname=Noto Sans CJK SC"


@dataclass
class TimelineSegment:
    index: int
    kind: str
    duration_seconds: float
    section: str = ""
    article_id: int | None = None
    text: str = ""


@dataclass
class FrameEntry:
    frame_path: Path
    duration_seconds: float


@dataclass
class TtsConfig:
    base_url: str
    model: str
    voice: str
    speed: float
    timeout_seconds: int
    max_retries: int
    api_key: str
    response_format: str = DEFAULT_TTS_RESPONSE_FORMAT


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^\w\-]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "section"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_payload_source(
    *,
    plan_path: Path | None,
    timeline_path: Path | None,
) -> tuple[dict[str, Any], Path]:
    source = plan_path or timeline_path
    if source is None:
        raise ValueError("Either --plan or --timeline is required")
    if not source.exists():
        raise FileNotFoundError(f"Input JSON not found: {source}")

    raw = _read_json(source)
    if isinstance(raw, list):
        payload = {"timeline": raw}
    elif isinstance(raw, dict):
        payload = copy.deepcopy(raw)
    else:
        raise ValueError(f"Unsupported JSON shape in {source}; expected object or timeline list")

    timeline = payload.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        raise ValueError(f"timeline is missing or empty in {source}")
    return payload, source


def _load_timeline_segments_from_payload(payload: dict[str, Any]) -> list[TimelineSegment]:
    raw_segments = payload.get("timeline")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise ValueError("Timeline is empty or invalid")

    segments: list[TimelineSegment] = []
    for raw in raw_segments:
        if not isinstance(raw, dict):
            continue
        duration = raw.get("duration_seconds", 0)
        segment = TimelineSegment(
            index=int(raw.get("index", len(segments) + 1)),
            kind=str(raw.get("kind", "frame")).strip() or "frame",
            duration_seconds=max(float(duration), 0.2),
            section=str(raw.get("section", "")).strip(),
            article_id=int(raw["article_id"]) if raw.get("article_id") is not None else None,
            text=str(raw.get("text", "")).strip(),
        )
        segments.append(segment)
    if not segments:
        raise ValueError("No valid timeline segment found")
    return segments


def _load_timeline_segments(
    *,
    plan_path: Path | None,
    timeline_path: Path | None,
) -> list[TimelineSegment]:
    payload, _ = _resolve_payload_source(plan_path=plan_path, timeline_path=timeline_path)
    return _load_timeline_segments_from_payload(payload)


def _extract_issue_number(plan_path: Path | None, timeline_path: Path | None) -> int:
    payload, _ = _resolve_payload_source(plan_path=plan_path, timeline_path=timeline_path)
    issue_number = payload.get("issue_number")
    if issue_number is None:
        return 1
    return int(issue_number)


def _frame_candidates(segment: TimelineSegment) -> list[str]:
    candidates: list[str] = []
    if segment.kind == "article" and segment.article_id is not None:
        candidates.extend([f"article_{segment.article_id}", f"article-{segment.article_id}"])
    if segment.kind == "section":
        if segment.section:
            candidates.append(f"section_{_slugify(segment.section)}")
        candidates.append(f"section_{segment.index}")

    candidates.extend([f"{segment.kind}_{segment.index}", segment.kind])
    candidates.extend(DEFAULT_FALLBACK_STEMS)

    deduped: list[str] = []
    seen: set = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _resolve_frame(frames_dir: Path, segment: TimelineSegment) -> Path | None:
    for stem in _frame_candidates(segment):
        for ext in IMAGE_EXTENSIONS:
            candidate = frames_dir / f"{stem}{ext}"
            if candidate.exists():
                return candidate
    return None


def _escape_ffconcat_path(path: Path) -> str:
    escaped = str(path.resolve()).replace("'", "'\\''")
    return f"'{escaped}'"


def build_concat_manifest(
    *,
    plan_path: Path | None,
    timeline_path: Path | None,
    frames_dir: Path,
    output_path: Path,
    strict: bool = False,
) -> list[FrameEntry]:
    segments = _load_timeline_segments(plan_path=plan_path, timeline_path=timeline_path)
    entries: list[FrameEntry] = []

    for segment in segments:
        frame = _resolve_frame(frames_dir, segment)
        if frame is None:
            message = (
                f"Missing frame for segment index={segment.index} kind={segment.kind} "
                f"article_id={segment.article_id}"
            )
            if strict:
                raise FileNotFoundError(message)
            fallback = None
            for stem in DEFAULT_FALLBACK_STEMS:
                for ext in IMAGE_EXTENSIONS:
                    candidate = frames_dir / f"{stem}{ext}"
                    if candidate.exists():
                        fallback = candidate
                        break
                if fallback is not None:
                    break
            if fallback is None:
                raise FileNotFoundError(f"{message}; no fallback frame found in {frames_dir}")
            frame = fallback

        entries.append(FrameEntry(frame_path=frame, duration_seconds=segment.duration_seconds))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ffconcat version 1.0"]
    for entry in entries:
        lines.append(f"file {_escape_ffconcat_path(entry.frame_path)}")
        lines.append(f"duration {entry.duration_seconds:.3f}")
    lines.append(f"file {_escape_ffconcat_path(entries[-1].frame_path)}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return entries


def _find_ffmpeg_from_local_venv() -> str | None:
    project_root = Path(__file__).resolve().parents[2]
    binaries = sorted(
        (project_root / ".venv").glob("lib/python*/site-packages/imageio_ffmpeg/binaries/ffmpeg-*")
    )
    for binary in binaries:
        if binary.is_file():
            return str(binary)
    return None


def _find_ffmpeg() -> tuple[str | None, str]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg, "system"

    ffmpeg = _find_ffmpeg_from_local_venv()
    if ffmpeg:
        return ffmpeg, "local-venv"

    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe(), "python-package"
    except Exception:
        pass
    return None, "missing"


def _require_ffmpeg() -> tuple[str, str]:
    ffmpeg, source = _find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError(
            "ffmpeg not found; install a system ffmpeg or add imageio-ffmpeg into runtime env"
        )
    return ffmpeg, source


def _list_encoders(ffmpeg_bin: str) -> set:
    result = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-encoders"],
        check=True,
        text=True,
        capture_output=True,
    )
    encoders: set = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].startswith("h264"):
            encoders.add(parts[1])
        if len(parts) >= 2 and parts[1] == "libx264":
            encoders.add(parts[1])
    return encoders


def _pick_encoder(ffmpeg_bin: str, preferred: str | None) -> str:
    if preferred:
        return preferred

    available = _list_encoders(ffmpeg_bin)
    if platform.system() == "Darwin" and "h264_videotoolbox" in available:
        return "h264_videotoolbox"
    for candidate in ("h264_nvenc", "h264_qsv", "h264_vaapi", "libx264"):
        if candidate in available:
            return candidate
    return "libx264"


def _default_encoder_without_probe() -> str:
    if platform.system() == "Darwin":
        return "h264_videotoolbox"
    return "libx264"


def _escape_subtitles_path(path: Path) -> str:
    value = str(path.resolve())
    value = value.replace("\\", "\\\\")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    return value


def _escape_subtitle_style(style: str) -> str:
    return style.replace("'", r"\'")


def _build_ffmpeg_command(
    *,
    ffmpeg_bin: str,
    concat_path: Path,
    audio_path: Path,
    output_path: Path,
    subtitles_path: Path | None,
    encoder: str,
    fps: int,
) -> list[str]:
    filters = [f"fps={fps}"]
    if subtitles_path is not None:
        subtitle_style = (
            os.getenv("VIDEO_SUBTITLE_FORCE_STYLE", DEFAULT_SUBTITLE_FORCE_STYLE).strip()
            or DEFAULT_SUBTITLE_FORCE_STYLE
        )
        filters.append(
            "subtitles='"
            + _escape_subtitles_path(subtitles_path)
            + "':force_style='"
            + _escape_subtitle_style(subtitle_style)
            + "'"
        )
    filters.append("format=yuv420p")
    vf = ",".join(filters)

    command = [
        ffmpeg_bin,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        vf,
        "-c:v",
        encoder,
    ]

    if encoder == "libx264":
        command.extend(["-preset", "medium", "-crf", "21"])
    elif encoder == "h264_videotoolbox":
        command.extend(["-b:v", "8M", "-maxrate", "12M", "-bufsize", "24M", "-allow_sw", "1"])
    elif encoder == "h264_nvenc":
        command.extend(["-preset", "p5", "-cq", "23", "-b:v", "0"])

    command.extend(
        [
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
    )
    return command


def _format_timestamp(total_seconds: float) -> str:
    total_milliseconds = int(round(max(total_seconds, 0) * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _render_srt_from_segments(segments: Sequence[TimelineSegment]) -> str:
    lines: list[str] = []
    current_start = 0.0
    for offset, segment in enumerate(segments, start=1):
        start = _format_timestamp(current_start)
        end = _format_timestamp(current_start + segment.duration_seconds)
        text = segment.text.strip() or f"{segment.kind} #{segment.index}"
        lines.append(f"{offset}\n{start} --> {end}\n{text}")
        current_start += segment.duration_seconds
    if not lines:
        return ""
    return "\n\n".join(lines).strip() + "\n"


def _update_payload_with_durations(
    payload: dict[str, Any],
    durations: Sequence[float],
) -> dict[str, Any]:
    timeline = payload.get("timeline")
    if not isinstance(timeline, list):
        raise ValueError("payload.timeline must be a list")
    if len(timeline) != len(durations):
        raise ValueError(
            f"Duration count mismatch: timeline={len(timeline)} durations={len(durations)}"
        )

    current_start = 0.0
    for offset, raw in enumerate(timeline):
        if not isinstance(raw, dict):
            raise ValueError(f"timeline[{offset}] must be an object")
        duration = max(float(durations[offset]), 0.2)
        raw["index"] = int(raw.get("index", offset + 1))
        raw["duration_seconds"] = round(duration, 3)
        raw["start_seconds"] = round(current_start, 3)
        current_start += duration

    payload["estimated_duration_seconds"] = round(current_start, 3)
    return payload


def _resolve_tts_config(
    *,
    base_url: str | None,
    model: str | None,
    voice: str,
    speed: float,
    timeout_seconds: int,
    max_retries: int,
    api_key_env: str,
) -> TtsConfig:
    resolved_base_url = (
        base_url
        or os.getenv("TTS_BASE_URL")
        or os.getenv("LLM_BASE_URL")
        or ""
    ).strip()
    resolved_model = (model or os.getenv("TTS_MODEL") or "").strip()
    resolved_api_key = (
        os.getenv(api_key_env)
        or os.getenv("TTS_API_KEY")
        or os.getenv("LLM_API_KEY")
        or ""
    ).strip()

    if not resolved_base_url:
        raise ValueError(
            "TTS base URL is required "
            "(--tts-base-url or env TTS_BASE_URL/LLM_BASE_URL)"
        )
    if not resolved_model:
        raise ValueError("TTS model is required (--tts-model or env TTS_MODEL)")
    if not resolved_api_key:
        key_sources = [api_key_env, "TTS_API_KEY", "LLM_API_KEY"]
        unique_sources = []
        seen: set[str] = set()
        for item in key_sources:
            if item and item not in seen:
                seen.add(item)
                unique_sources.append(item)
        raise ValueError(
            "TTS API key is required (env "
            + " or ".join(unique_sources)
            + ")"
        )

    return TtsConfig(
        base_url=resolved_base_url.rstrip("/"),
        model=resolved_model,
        voice=voice,
        speed=float(speed),
        timeout_seconds=int(timeout_seconds),
        max_retries=max(int(max_retries), 1),
        api_key=resolved_api_key,
    )


def _tts_cache_key(*, config: TtsConfig, text: str) -> str:
    seed = "|".join(
        [
            config.base_url,
            config.model,
            config.voice,
            f"{config.speed:.2f}",
            text.strip(),
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _decode_chat_completion_audio(raw_response: bytes) -> bytes:
    try:
        payload = json.loads(raw_response.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"Invalid JSON response from chat/completions: {exc}") from exc

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("chat/completions response missing choices")

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    audio = message.get("audio") if isinstance(message, dict) else None
    encoded_audio = audio.get("data") if isinstance(audio, dict) else None
    if not isinstance(encoded_audio, str) or not encoded_audio.strip():
        raise RuntimeError("chat/completions response missing message.audio.data")

    try:
        return base64.b64decode(encoded_audio, validate=True)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"Invalid base64 audio payload: {exc}") from exc


def _call_tts_via_chat_completions(config: TtsConfig, text: str) -> bytes:
    endpoint = f"{config.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload_variants = [
        {
            "model": config.model,
            "modalities": ["audio"],
            "audio": {"voice": config.voice, "format": config.response_format},
            "messages": [{"role": "assistant", "content": text}],
        },
        {
            "model": config.model,
            "messages": [{"role": "assistant", "content": text}],
        },
    ]

    last_error = "unknown tts fallback error"
    for payload in payload_variants:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        for attempt in range(config.max_retries):
            request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
                    return _decode_chat_completion_audio(response.read())
            except urllib.error.HTTPError as exc:
                raw = exc.read()
                message = raw.decode("utf-8", errors="ignore")[:240]
                last_error = f"HTTP {exc.code}: {message}"
                if exc.code in RETRYABLE_HTTP_STATUS and attempt < config.max_retries - 1:
                    time.sleep((2**attempt) + 0.25)
                    continue
                break
            except urllib.error.URLError as exc:
                last_error = str(exc)
                if attempt < config.max_retries - 1:
                    time.sleep((2**attempt) + 0.25)
                    continue
                break
            except RuntimeError as exc:
                last_error = str(exc)
                break

    raise RuntimeError(f"TTS chat-completions fallback failed: {last_error}")


def _call_tts(config: TtsConfig, text: str) -> bytes:
    endpoint = f"{config.base_url}/audio/speech"
    payload = {
        "model": config.model,
        "voice": config.voice,
        "input": text,
        "speed": config.speed,
        "response_format": config.response_format,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "Accept": "audio/wav,application/octet-stream",
    }

    last_error = "unknown tts error"
    for attempt in range(config.max_retries):
        request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            message = raw.decode("utf-8", errors="ignore")[:240]
            if exc.code == 404:
                return _call_tts_via_chat_completions(config=config, text=text)
            last_error = f"HTTP {exc.code}: {message}"
            if exc.code in RETRYABLE_HTTP_STATUS and attempt < config.max_retries - 1:
                time.sleep((2**attempt) + 0.25)
                continue
            break
        except urllib.error.URLError as exc:
            last_error = str(exc)
            if attempt < config.max_retries - 1:
                time.sleep((2**attempt) + 0.25)
                continue
            break

    raise RuntimeError(f"TTS request failed: {last_error}")


def _write_binary(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
    if rate <= 0:
        raise ValueError(f"Invalid wav sample rate in {path}")
    return max(frames / float(rate), 0.0)


def _merge_wav_files(inputs: Sequence[Path], output_path: Path) -> None:
    if not inputs:
        raise ValueError("No audio segments to merge")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as writer:
        reference_params = None
        for path in inputs:
            with wave.open(str(path), "rb") as reader:
                params = (
                    reader.getnchannels(),
                    reader.getsampwidth(),
                    reader.getframerate(),
                    reader.getcomptype(),
                    reader.getcompname(),
                )
                if reference_params is None:
                    reference_params = params
                    writer.setnchannels(params[0])
                    writer.setsampwidth(params[1])
                    writer.setframerate(params[2])
                elif params != reference_params:
                    raise ValueError(
                        f"WAV format mismatch: {path} has {params}, expected {reference_params}"
                    )
                writer.writeframes(reader.readframes(reader.getnframes()))


def synthesize_timeline_audio(
    *,
    plan_path: Path | None,
    timeline_path: Path | None,
    output_dir: Path,
    timeline_output: Path | None,
    subtitles_output: Path | None,
    narration_output: Path | None,
    base_url: str | None,
    model: str | None,
    voice: str,
    speed: float,
    timeout_seconds: int,
    max_retries: int,
    api_key_env: str,
) -> dict[str, Any]:
    config = _resolve_tts_config(
        base_url=base_url,
        model=model,
        voice=voice,
        speed=speed,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        api_key_env=api_key_env,
    )
    payload, source_path = _resolve_payload_source(plan_path=plan_path, timeline_path=timeline_path)
    segments = _load_timeline_segments_from_payload(payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "tts_cache"
    segment_dir = output_dir / "audio_segments"
    cache_dir.mkdir(parents=True, exist_ok=True)
    segment_dir.mkdir(parents=True, exist_ok=True)

    segment_audio_files: list[Path] = []
    duration_values: list[float] = []
    cache_hits = 0

    for offset, segment in enumerate(segments, start=1):
        text = segment.text.strip() or f"{segment.kind} #{segment.index}"
        digest = _tts_cache_key(config=config, text=text)
        cached_audio = cache_dir / f"{digest}.wav"
        if cached_audio.exists():
            cache_hits += 1
        else:
            audio_blob = _call_tts(config=config, text=text)
            _write_binary(cached_audio, audio_blob)

        segment_filename = f"{offset:03d}_{segment.kind}_{segment.index}.wav"
        segment_audio = segment_dir / segment_filename
        shutil.copyfile(cached_audio, segment_audio)
        segment_audio_files.append(segment_audio)
        duration_values.append(max(_wav_duration_seconds(segment_audio), 0.2))

    aligned_payload = _update_payload_with_durations(copy.deepcopy(payload), duration_values)
    aligned_timeline_path = timeline_output or (output_dir / "timeline.aligned.json")
    _write_json(aligned_timeline_path, aligned_payload)

    aligned_segments = _load_timeline_segments_from_payload(aligned_payload)
    aligned_subtitles_path = subtitles_output or (output_dir / "subtitles.aligned.srt")
    aligned_subtitles_path.parent.mkdir(parents=True, exist_ok=True)
    aligned_subtitles_path.write_text(
        _render_srt_from_segments(aligned_segments),
        encoding="utf-8",
    )

    merged_audio_path = narration_output or (output_dir / "narration.aligned.wav")
    _merge_wav_files(segment_audio_files, merged_audio_path)
    merged_audio_duration = _wav_duration_seconds(merged_audio_path)

    return {
        "source_path": str(source_path),
        "aligned_timeline_path": str(aligned_timeline_path),
        "aligned_subtitles_path": str(aligned_subtitles_path),
        "narration_path": str(merged_audio_path),
        "segment_dir": str(segment_dir),
        "segment_count": len(segment_audio_files),
        "cache_hits": cache_hits,
        "total_duration_seconds": round(sum(duration_values), 3),
        "merged_audio_duration_seconds": round(merged_audio_duration, 3),
        "tts_voice": config.voice,
        "tts_model": config.model,
    }


def render_video(
    *,
    plan_path: Path | None,
    timeline_path: Path | None,
    frames_dir: Path | None,
    audio_path: Path | None,
    output_path: Path | None,
    subtitles_path: Path | None = None,
    concat_path: Path | None = None,
    encoder: str | None = None,
    fps: int = 30,
    strict: bool = False,
    dry_run: bool = False,
    auto_tts: bool = False,
    tts_output_dir: Path | None = None,
    tts_base_url: str | None = None,
    tts_model: str | None = None,
    tts_voice: str = "alloy",
    tts_speed: float = 1.0,
    tts_timeout: int = 60,
    tts_max_retries: int = 3,
    tts_api_key_env: str = "TTS_API_KEY",
) -> dict[str, Any]:
    if plan_path is None and timeline_path is None:
        raise ValueError("render requires --plan or --timeline")

    issue_number = _extract_issue_number(plan_path, timeline_path)
    default_output_dir = Path("services/video-maker/output") / f"issue_{issue_number}"
    resolved_frames_dir = frames_dir or (default_output_dir / "frames")
    resolved_output_path = output_path or (default_output_dir / f"issue_{issue_number}.mp4")
    resolved_audio_dir = resolved_output_path.parent / "audio"

    resolved_audio_path = audio_path or (default_output_dir / "narration.wav")
    resolved_timeline_path = timeline_path or plan_path
    resolved_subtitles_path = subtitles_path
    tts_result: dict[str, Any] | None = None

    # CI runners start from a clean filesystem. Ensure output tree exists before checks.
    resolved_frames_dir.mkdir(parents=True, exist_ok=True)
    resolved_audio_dir.mkdir(parents=True, exist_ok=True)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    has_frame_files = any(
        path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        for path in resolved_frames_dir.iterdir()
    )
    if not has_frame_files and not auto_tts:
        raise FileNotFoundError(
            f"No frames found in {resolved_frames_dir} and auto_tts is disabled"
        )

    if auto_tts or resolved_audio_path is None:
        if dry_run and (tts_base_url is None and tts_model is None):
            # Keep dry-run non-blocking when TTS credentials are not provided.
            pass
        else:
            tts_result = synthesize_timeline_audio(
                plan_path=plan_path,
                timeline_path=timeline_path,
                output_dir=tts_output_dir or (resolved_output_path.parent / "tts"),
                timeline_output=None,
                subtitles_output=resolved_subtitles_path,
                narration_output=resolved_audio_path,
                base_url=tts_base_url,
                model=tts_model,
                voice=tts_voice,
                speed=tts_speed,
                timeout_seconds=tts_timeout,
                max_retries=tts_max_retries,
                api_key_env=tts_api_key_env,
            )
            resolved_timeline_path = Path(tts_result["aligned_timeline_path"])
            resolved_audio_path = Path(tts_result["narration_path"])
            if resolved_subtitles_path is None:
                resolved_subtitles_path = Path(tts_result["aligned_subtitles_path"])

    if resolved_audio_path is None:
        raise ValueError("render requires --audio/--auto-tts or a default narration.wav")
    if not resolved_audio_path.exists() and not dry_run:
        raise FileNotFoundError(f"Audio file not found: {resolved_audio_path}")

    ffmpeg_from_path, ffmpeg_source = _find_ffmpeg()
    if dry_run:
        ffmpeg_bin = ffmpeg_from_path or "ffmpeg"
        if encoder:
            resolved_encoder = encoder
        elif ffmpeg_from_path:
            resolved_encoder = _pick_encoder(ffmpeg_bin, None)
        else:
            resolved_encoder = _default_encoder_without_probe()
    else:
        ffmpeg_bin, ffmpeg_source = _require_ffmpeg()
        resolved_encoder = _pick_encoder(ffmpeg_bin, encoder)

    resolved_concat = concat_path or resolved_output_path.with_suffix(".ffconcat")
    entries = build_concat_manifest(
        plan_path=None if resolved_timeline_path is not None else plan_path,
        timeline_path=resolved_timeline_path,
        frames_dir=resolved_frames_dir,
        output_path=resolved_concat,
        strict=strict,
    )

    command = _build_ffmpeg_command(
        ffmpeg_bin=ffmpeg_bin,
        concat_path=resolved_concat,
        audio_path=resolved_audio_path,
        output_path=resolved_output_path,
        subtitles_path=resolved_subtitles_path,
        encoder=resolved_encoder,
        fps=fps,
    )

    result: dict[str, Any] = {
        "ffmpeg": ffmpeg_bin,
        "ffmpeg_source": ffmpeg_source,
        "encoder": resolved_encoder,
        "frames": len(entries),
        "concat_path": str(resolved_concat),
        "timeline_path": str(resolved_timeline_path) if resolved_timeline_path else "",
        "frames_dir": str(resolved_frames_dir),
        "audio_path": str(resolved_audio_path),
        "output_path": str(resolved_output_path),
        "command": " ".join(shlex.quote(part) for part in command),
    }
    if resolved_subtitles_path is not None:
        result["subtitles_path"] = str(resolved_subtitles_path)
    if tts_result is not None:
        result["tts"] = tts_result

    if dry_run:
        return result

    subprocess.run(command, check=True)
    result["status"] = "ok"
    return result


def doctor() -> dict[str, Any]:
    ffmpeg, source = _find_ffmpeg()
    if ffmpeg is None:
        return {
            "ffmpeg": "",
            "ffmpeg_source": "missing",
            "encoders": [],
            "recommended_encoder": _default_encoder_without_probe(),
        }

    encoders = sorted(_list_encoders(ffmpeg))
    return {
        "ffmpeg": ffmpeg,
        "ffmpeg_source": source,
        "encoders": encoders,
        "recommended_encoder": _pick_encoder(ffmpeg, None),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Daily video maker shell")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Show ffmpeg and encoder availability")
    doctor_parser.set_defaults(handler=lambda args: doctor())

    concat_parser = subparsers.add_parser("build-concat", help="Generate ffconcat manifest")
    concat_parser.add_argument("--plan", type=Path, help="Video plan JSON path")
    concat_parser.add_argument("--timeline", type=Path, help="timeline JSON path")
    concat_parser.add_argument("--frames-dir", type=Path, required=True, help="Frame directory")
    concat_parser.add_argument("--output", type=Path, required=True, help="Output ffconcat path")
    concat_parser.add_argument("--strict", action="store_true", help="Fail on missing frame")
    concat_parser.set_defaults(
        handler=lambda args: {
            "concat_path": str(args.output),
            "frames": len(
                build_concat_manifest(
                    plan_path=args.plan,
                    timeline_path=args.timeline,
                    frames_dir=args.frames_dir,
                    output_path=args.output,
                    strict=args.strict,
                )
            ),
        }
    )

    tts_parser = subparsers.add_parser("tts", help="Generate timeline-aligned TTS audio")
    tts_parser.add_argument("--plan", type=Path, help="Video plan JSON path")
    tts_parser.add_argument("--timeline", type=Path, help="timeline JSON path")
    tts_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="TTS artifact output dir",
    )
    tts_parser.add_argument(
        "--timeline-output",
        type=Path,
        help="Aligned timeline JSON output path",
    )
    tts_parser.add_argument(
        "--subtitles-output",
        type=Path,
        help="Aligned subtitle output path",
    )
    tts_parser.add_argument(
        "--narration-output",
        type=Path,
        help="Merged narration wav output path",
    )
    tts_parser.add_argument("--tts-base-url", help="TTS API base URL")
    tts_parser.add_argument("--tts-model", help="TTS model id")
    tts_parser.add_argument("--tts-voice", default="alloy", help="TTS voice id")
    tts_parser.add_argument("--tts-speed", type=float, default=1.0, help="TTS speed")
    tts_parser.add_argument(
        "--tts-timeout",
        type=int,
        default=60,
        help="TTS request timeout seconds",
    )
    tts_parser.add_argument("--tts-max-retries", type=int, default=3, help="TTS retry attempts")
    tts_parser.add_argument(
        "--tts-api-key-env",
        default="TTS_API_KEY",
        help="Environment variable name for API key",
    )
    tts_parser.set_defaults(
        handler=lambda args: synthesize_timeline_audio(
            plan_path=args.plan,
            timeline_path=args.timeline,
            output_dir=args.output_dir,
            timeline_output=args.timeline_output,
            subtitles_output=args.subtitles_output,
            narration_output=args.narration_output,
            base_url=args.tts_base_url,
            model=args.tts_model,
            voice=args.tts_voice,
            speed=args.tts_speed,
            timeout_seconds=args.tts_timeout,
            max_retries=args.tts_max_retries,
            api_key_env=args.tts_api_key_env,
        )
    )

    render_parser = subparsers.add_parser("render", help="Compose MP4 from timeline and assets")
    render_parser.add_argument("--plan", type=Path, help="Video plan JSON path")
    render_parser.add_argument("--timeline", type=Path, help="timeline JSON path")
    render_parser.add_argument("--frames-dir", type=Path, help="Frame directory")
    render_parser.add_argument("--audio", type=Path, help="Narration audio path")
    render_parser.add_argument("--output", type=Path, help="Output mp4 path")
    render_parser.add_argument("--subtitles", type=Path, help="Optional SRT subtitle path")
    render_parser.add_argument("--concat-path", type=Path, help="Optional ffconcat output path")
    render_parser.add_argument("--encoder", help="Force video encoder")
    render_parser.add_argument("--fps", type=int, default=30, help="Output frame rate")
    render_parser.add_argument("--strict", action="store_true", help="Fail on missing frame")
    render_parser.add_argument("--dry-run", action="store_true", help="Do not execute ffmpeg")
    render_parser.add_argument("--auto-tts", action="store_true", help="Generate aligned TTS audio")
    render_parser.add_argument(
        "--tts-output-dir",
        type=Path,
        help="Directory for generated TTS artifacts",
    )
    render_parser.add_argument("--tts-base-url", help="TTS API base URL")
    render_parser.add_argument("--tts-model", help="TTS model id")
    render_parser.add_argument("--tts-voice", default="alloy", help="TTS voice id")
    render_parser.add_argument("--tts-speed", type=float, default=1.0, help="TTS speed")
    render_parser.add_argument(
        "--tts-timeout",
        type=int,
        default=60,
        help="TTS request timeout seconds",
    )
    render_parser.add_argument("--tts-max-retries", type=int, default=3, help="TTS retry attempts")
    render_parser.add_argument(
        "--tts-api-key-env",
        default="TTS_API_KEY",
        help="Environment variable name for API key",
    )
    render_parser.set_defaults(
        handler=lambda args: render_video(
            plan_path=args.plan,
            timeline_path=args.timeline,
            frames_dir=args.frames_dir,
            audio_path=args.audio,
            output_path=args.output,
            subtitles_path=args.subtitles,
            concat_path=args.concat_path,
            encoder=args.encoder,
            fps=args.fps,
            strict=args.strict,
            dry_run=args.dry_run,
            auto_tts=args.auto_tts,
            tts_output_dir=args.tts_output_dir,
            tts_base_url=args.tts_base_url,
            tts_model=args.tts_model,
            tts_voice=args.tts_voice,
            tts_speed=args.tts_speed,
            tts_timeout=args.tts_timeout,
            tts_max_retries=args.tts_max_retries,
            tts_api_key_env=args.tts_api_key_env,
        )
    )

    return parser


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    try:
        payload = args.handler(args)
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from error

    if isinstance(payload, dict):
        output = {"ok": True, **payload}
    else:
        output = {"ok": True, "result": payload}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
