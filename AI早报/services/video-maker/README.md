# video-maker

`video-maker` is the FFmpeg execution shell for AI Daily.

It consumes:
- `timeline.json` + `subtitles.srt` + `narration.txt` (from main pipeline)
- rendered frame images (from card renderer / design workflow)
- narration audio (from TTS)

And emits:
- `issue_<n>.mp4`

## 1) Build timeline artifacts

```bash
PYTHONPATH=src python -m ai_daily.cli build-video-plan \
  --issue-number 1 \
  --output-dir services/video-maker/output/issue_1
```

This produces:
- `services/video-maker/output/issue_1/timeline.json`
- `services/video-maker/output/issue_1/subtitles.srt`
- `services/video-maker/output/issue_1/narration.txt`

## 2) Prepare render inputs

Place assets under one issue folder:

```text
services/video-maker/output/issue_1/
  timeline.json
  subtitles.srt
  narration.wav
  frames/
    intro.png
    section_1.png
    article_101.png
    article_102.png
    closing.png
    default.png
```

Frame resolution strategy:
- article segment: `article_<article_id>.(png|jpg|jpeg|webp)`
- section segment: `section_<slug>` or `section_<index>`
- generic fallback: `default.*` / `fallback.*` / `cover.*`

## 3) Verify ffmpeg runtime

Check FFmpeg and encoder availability:

```bash
python3 services/video-maker/video_maker.py doctor
```

If `ffmpeg_source=missing`, provide one of:
- system ffmpeg in `PATH`
- local venv package binary (`imageio-ffmpeg` inside project `.venv`)

## 4) Generate aligned TTS audio (optional but recommended)

Before rendering, generate segment-level TTS and rewrite durations:

```bash
python3 services/video-maker/video_maker.py tts \
  --plan services/video-maker/examples/timeline.sample.json \
  --output-dir services/video-maker/output/demo/tts \
  --tts-base-url "$LLM_BASE_URL" \
  --tts-model "$TTS_MODEL" \
  --tts-api-key-env LLM_API_KEY
```

Outputs:
- `timeline.aligned.json` (duration_seconds/start_seconds rewritten)
- `subtitles.aligned.srt`
- `narration.aligned.wav`
- `audio_segments/*.wav`

Render (macOS will auto-prefer `h264_videotoolbox` if available):

```bash
python3 services/video-maker/video_maker.py render \
  --plan data/video_plan_1.json \
  --frames-dir services/video-maker/output/issue_1/frames \
  --auto-tts \
  --tts-output-dir services/video-maker/output/issue_1/tts \
  --tts-base-url "$LLM_BASE_URL" \
  --tts-model "$TTS_MODEL" \
  --tts-api-key-env LLM_API_KEY \
  --output services/video-maker/output/issue_1/issue_1.mp4
```

Dry-run (print final ffmpeg command only):

```bash
python3 services/video-maker/video_maker.py render \
  --plan data/video_plan_1.json \
  --frames-dir services/video-maker/output/issue_1/frames \
  --audio services/video-maker/output/issue_1/narration.wav \
  --subtitles services/video-maker/output/issue_1/subtitles.srt \
  --output services/video-maker/output/issue_1/issue_1.mp4 \
  --dry-run
```
