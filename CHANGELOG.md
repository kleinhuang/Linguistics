# ShiftCorpus GUI — Changelog / 更新日志

## v1.1.0 — Run folder archiving / 每次采集独立归档
- Create a unique, descriptive run folder under the selected output root on each Start.
- Use subreddit, effective date span, all/single selection, and start timestamp in folder names.
- Save `run_manifest.json` with parameters, app version, command, timestamps, and final status.
- Save the engine's complete streamed output to `collection.log`.
- Open Output now opens the latest run directory; past runs are not overwritten.
- Preserve all existing collection filters, window picker, bilingual UI, TLS validation, and retries.

## v1.0.0 — Baseline / 基准版本
- Cross-platform Tkinter GUI; Chinese/English switching; auto-generated window selector.
- Arctic Shift API connectivity diagnostics, SSL setup, and transient connection retries.
