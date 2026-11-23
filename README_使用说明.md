# ShiftCorpus GUI — 使用说明 / User Guide

**中文 / English:** 在应用右上角的 **语言 / Language** 下拉菜单选择 **中文** 或 **English**。切换会立即更新图形界面文字，不会清空已设置的参数；运行日志中的采集引擎原始输出仍保持原文，便于核对问题。

**中文：** 这是一款用于从 Arctic Shift 收集 Reddit 评论的桌面图形界面，支持 macOS（也可在有 Tkinter 的其他系统运行）。GUI 调用随包附带的 Python 采集引擎。  
**English:** A desktop interface for collecting Reddit comments from Arctic Shift. It targets macOS and can also run on other systems with Tkinter. The GUI launches the bundled Python collection engine.

## 1. 启动 / Launch

**中文：**
1. 解压整个 `ShiftCorpus_GUI` 文件夹，不要单独移动 Python 文件。
2. 在 VS Code 中打开该文件夹，打开终端运行：
   ```bash
   python3 shift_corpus_gui.py
   ```
3. macOS 也可以尝试双击 `启动采集器.command`。
4. 如提示缺少 `_tkinter`，请使用含 Tkinter 的 Python 发行版（如 python.org 的 macOS 版本）。

**English:**
1. Extract the entire `ShiftCorpus_GUI` folder and keep the Python files together.
2. Open the folder in VS Code and run `python3 shift_corpus_gui.py` in Terminal.
3. On macOS, you can also try double-clicking `启动采集器.command`.
4. If `_tkinter` is missing, install a Python distribution with Tkinter support (such as the macOS installer from python.org).

## 2. 研究预设 / Research defaults

| Setting / 参数 | Default / 默认值 |
|---|---|
| Subreddit | `politics` |
| Start / 开始 | `2022-05-01` (inclusive / 包含当天) |
| End / 结束 | `2026-11-20` (inclusive / 包含当天) |
| Window / 窗口 | 180 days / 天 |
| Quota / 每完整窗口数量 | 180 comments / 条评论 |
| Seed / 随机种子 | `1` |
| Partial-window policy / 不足窗口处理 | `proportional` (proportional target / 按比例目标) |
| Filters / 过滤 | English only, bots, NSFW, near-duplicates / 英文、Bot、NSFW、近重复 |
| Parent post context / 关联帖子上下文 | Enabled / 开启 |

**中文：** `proportional` 表示最后一个不满 180 天的窗口按天数比例调整目标；`full` 表示仍使用完整配额。首尾日期采用 UTC。勾选关联帖子上下文会保留帖子标题，但不把帖文正文计入评论词频。

**English:** `proportional` scales the last incomplete window's target to its length; `full` uses the full quota. Date boundaries use UTC. Enabling parent-post context preserves post titles without including post body text in comment frequency counts.

## 3. 操作步骤 / Workflow

**中文：**
1. 在右上角选择界面语言。
2. 点击 **测试 API 连接**，验证当前网络和证书设置。
3. 建议先在 **仅采集指定窗口** 输入 `2022-05-01_2022-10-27`，测试 pilot 窗口。
4. 点击 **开始采集**，查看实时日志和进度。按钮 **停止** 会终止子进程。
5. 完成后点击 **打开输出文件夹**。

**English:**
1. Choose the interface language in the upper-right selector.
2. Click **Test API connection** to verify network connectivity and certificate trust.
3. To test the pilot first, enter `2022-05-01_2022-10-27` in **Single window (optional)**.
4. Click **Start collection** and monitor the live log/progress; **Stop** terminates the subprocess.
5. Use **Open output folder** to inspect results.

## 4. 输出数据 / Outputs

**中文：** 每个窗口会生成 AntConc 使用的 `.txt`、元数据 `.index.txt`、结构化 `.csv` 和 `.jsonl`，以及记录运行配置与统计信息的 `query.json`。目标数量不等于实际获得数量，检查日志中的 `kept`、`short` 等数字。采集引擎日志可能为英文或中文，切换 GUI 语言不会改写原始日志或数据文件。

**English:** Each window exports an AntConc `.txt`, `.index.txt` metadata, structured `.csv` and `.jsonl`, plus `query.json` with configuration and run statistics. Target quota is not a guarantee; inspect `kept`, `short`, and other logs. Engine-generated logs may remain in their original language; switching UI language does not modify them or the collected data.

## 5. API与SSL排查 / API and SSL troubleshooting

**中文：** 如果看到 `CERTIFICATE_VERIFY_FAILED`，先修复本地 Python 的证书信任配置（python.org 的 Mac 版本可以运行 `Install Certificates.command`）。如果出现 HTTP 403，可先对比 `curl` 与 Python 的请求结果。此版本已对 GUI 连接测试与采集引擎统一设置以下已验证的请求头：

**English:** For `CERTIFICATE_VERIFY_FAILED`, repair Python's local certificate trust store (the python.org macOS installer provides `Install Certificates.command`). For HTTP 403, compare results from `curl` and Python. This release uses the same tested request headers in GUI diagnostics and the collection engine:

```http
User-Agent: ShiftCorpus-Research/1.0 (academic corpus collection)
Accept: application/json
```

**中文：** 服务器限流或返回 5xx 时请检查详细日志。不要关闭 SSL 证书验证。  
**English:** Check the diagnostic log for server rate limits or 5xx responses. Do not disable SSL verification.

## 6. 局限与注意事项 / Limitations and notes

**中文：** GUI 不改变采集引擎的基本分层抽样算法，该算法不是对全部评论的严格等概率抽样。应用依赖第三方 Arctic Shift 服务；无法保证每个日期均有数据。点击停止不会保证未写入的数据可以恢复。应用只依赖 Python 标准库，不需要额外 Python 包。

**English:** The GUI does not change the collector's underlying stratified sampling method, which is not a uniform sample of every eligible comment. Arctic Shift is a third-party service and complete archive coverage is not guaranteed. Stop may interrupt work that has not yet been written to disk. Only Python's standard library is required.
