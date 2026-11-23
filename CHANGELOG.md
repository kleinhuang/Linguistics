# Changelog / 更新日志

## English

Version labels for Alpha/Beta/RC releases were assigned retrospectively to archived snapshots. Earlier builds were not necessarily labeled with those versions inside the GUI.

### v1.1.1 — Bilingual output README
- Generated a README.txt for each output run with English first and Chinese second.
- Included collection parameters, output descriptions, counts, and warnings in both languages.

### v1.1.0 — Per-run output archiving
- Created a unique output folder for each collection run.
- Added run_manifest.json and collection.log for reproducibility and diagnostics.
- Prevented subsequent runs from overwriting prior output folders.

### v1.0.0 — Stable baseline
- Marked the window-selector release candidate as the stable baseline.
- No additional functionality relative to v1.0.0-rc.1.

### v1.0.0-rc.1 — Automatic window picker
- Generated selectable date windows from the start date, end date, and window length.
- Supported single-window selection and partial-window target display.

### v1.0.0-beta.4 — Network recovery
- Added bounded retries for transient connection resets and incomplete responses.
- Improved API error logging without treating failed requests as successful samples.

### v1.0.0-beta.3 — TLS certificate handling
- Added certificate trust-store setup for the GUI and engine.
- Kept HTTPS certificate verification enabled.

### v1.0.0-beta.2 — GUI startup fix
- Fixed the undefined main_font variable that could crash window initialization.

### v1.0.0-beta.1 — Cross-platform support
- Added platform-specific launchers for macOS, Windows, and Linux.
- Adjusted paths, platform fonts, and output-folder opening behavior.

### v1.0.0-alpha.2 — Bilingual interface
- Added Chinese/English language switching.
- Updated the project README with bilingual usage instructions.

### v1.0.0-alpha.1 — Initial macOS GUI
- Introduced a Tkinter desktop interface for Arctic Shift corpus collection.
- Added sampling settings, progress logs, API testing, and export controls.

---

## 中文

Alpha/Beta/RC 版本号是根据存档快照追溯整理的，早期应用内部显示的版本号可能与本次归档名称不同。

### v1.1.1 — 输出README双语化
- 每次采集生成的README.txt改为英文在上、中文在下。
- 两种语言均说明采集参数、导出文件、数据量和警告。

### v1.1.0 — 每次采集独立归档
- 为每次采集创建独立且唯一的输出文件夹。
- 增加run_manifest.json和collection.log，记录运行信息及故障。
- 避免后续采集覆盖已有输出文件夹。

### v1.0.0 — 首个正式基准版
- 将时间窗口选择器候选版确立为首个正式基准版本。
- 与v1.0.0-rc.1相比未增加新功能。

### v1.0.0-rc.1 — 自动采集窗口选择
- 根据起止日期和窗口长度自动生成可选时间窗口。
- 支持仅采集指定窗口及显示不完整窗口的目标样本数。

### v1.0.0-beta.4 — 网络断线恢复
- 为临时连接重置和响应中断加入有限次数的重试。
- 增强API错误日志，避免把失败请求误记为成功样本。

### v1.0.0-beta.3 — TLS证书处理
- 为GUI和采集引擎增加证书信任库配置。
- 保留HTTPS证书验证，不采用不安全的跳过验证方式。

### v1.0.0-beta.2 — GUI启动修复
- 修复main_font变量未定义导致的GUI启动崩溃。

### v1.0.0-beta.1 — 跨平台支持
- 新增macOS、Windows和Linux平台的启动脚本。
- 适配文件路径、字体和打开输出文件夹的功能。

### v1.0.0-alpha.2 — 中英双语界面
- 新增中文和英文界面切换。
- 将项目README更新为中英双语说明。

### v1.0.0-alpha.1 — 初始macOS图形界面
- 首次提供Tkinter桌面界面，用于Arctic Shift语料采集。
- 提供抽样参数、进度日志、API测试和导出控制。
