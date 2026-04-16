# Multimodal Services

This folder documents the two downstream services that consume the published
AI 早报 data model.

## `card-renderer`

Consumes structured Issue data from SQLite through the export payload generated
by `ai_daily.export.card`. The service is expected to render:

- single information cards
- long-form posters
- consistent visual theming across issues

Primary contract:

- input: `CardRenderPayload`
- source: `export-card-payload` CLI
- output: PNG or poster assets

## `video-maker`

Consumes the published backup markdown for an Issue and turns it into a
timeline suitable for TTS, subtitles, and FFmpeg composition.

Primary contract:

- input: `BACKUP/issue_<n>.md`
- source: `build-video-plan` CLI
- output: `timeline.json`, `subtitles.srt`, `narration.txt`

The actual media render step stays intentionally separate so the content plan
can be validated before any audio/video work begins.
