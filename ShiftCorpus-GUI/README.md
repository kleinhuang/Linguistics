# ShiftCorpus GUI

A bilingual, cross-platform desktop application for collecting and sampling Reddit comments via the Arctic Shift API.

**Latest archived version:** v1.1.1  
**Platforms:** macOS / Windows / Linux  
**Languages:** English / 中文

## Features

- Date-range and subreddit configuration
- Time-stratified sampling with a selectable computed window
- Automatic output archiving and run metadata
- AntConc-compatible corpus exports, CSV, JSONL, index files
- API diagnostics and retries for transient failures
- English/Chinese interface and bilingual output README

## Installation

Python 3.10+ with Tkinter is required. The full source and historical distribution bundles are maintained in the separate [publishing kit](../PUBLISHING.md) until the versioned source snapshots have been uploaded.

Once the full program files are present:

```bash
python3 shift_corpus_gui.py
```

Use `Launch_macOS.command`, `Launch_Windows.bat`, or `Launch_Linux.sh` where available.

## Versions

See [CHANGELOG.md](CHANGELOG.md) and [VERSION_HISTORY.md](VERSION_HISTORY.md). Alpha/Beta/RC labels were applied retrospectively to archived development snapshots.

**Publication status:** The repository documentation is published; historical source snapshots and binary release packages are not yet uploaded. Do not mistake this page for a complete runnable distribution.

---

# ShiftCorpus GUI（中文）

ShiftCorpus GUI 是一款支持中文与英文的跨平台桌面工具，使用 Arctic Shift API 采集和抽样 Reddit 评论语料。

**最新归档版本：** v1.1.1  
**平台：** macOS / Windows / Linux  
**语言：** 中文 / English

## 功能

- 设置 Subreddit、日期范围和采样参数
- 自动生成时间窗口并选择指定窗口
- 每次采集自动归档，保存运行参数和日志
- 导出 AntConc TXT、CSV、JSONL 与索引文件
- API诊断、临时网络故障重试
- 中英文界面、输出README双语说明

## 使用

需要 Python 3.10+ 和 Tkinter。完整代码上传后，在程序目录运行：

```bash
python3 shift_corpus_gui.py
```

也可以使用不同系统对应的启动脚本。

版本记录见 [CHANGELOG.md](CHANGELOG.md) 和 [VERSION_HISTORY.md](VERSION_HISTORY.md)。

**发布状态：** 当前已发布说明文档，历史源代码和ZIP发行包尚未全部上传，所以暂时不能把此目录视为完整可运行版本。
