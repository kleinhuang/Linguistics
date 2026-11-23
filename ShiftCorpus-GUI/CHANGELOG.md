# Changelog / 更新日志

## English

> Alpha/Beta/RC labels were assigned retrospectively to archived development snapshots. The original app windows did not necessarily display these numbers.

### v1.1.1 — Bilingual output README
- Generated a README.txt for each output folder, English first and Chinese second.
- Documented collection parameters, output files, counts, and warnings in both languages.

### v1.1.0 — Per-run output archiving
- Created a unique output folder for each collection.
- Added run_manifest.json and collection.log.
- Prevented subsequent runs from overwriting earlier collections.

### v1.0.0 — Stable baseline
- Designated the automatic-window-picker release candidate as the first stable release.
- No extra features beyond v1.0.0-rc.1.

### v1.0.0-rc.1 — Automatic window picker
- Automatically generated selectable date windows from start/end dates and window length.
- Supported single-window selection and partial-window target counts.

### v1.0.0-beta.4 — Network recovery
- Added bounded retries for connection resets and incomplete responses.
- Improved API error reporting without counting failed requests as successful samples.

### v1.0.0-beta.3 — TLS certificate setup
- Added certificate trust-store configuration for the GUI and collection engine.
- Kept HTTPS certificate verification enabled.

### v1.0.0-beta.2 — GUI startup fix
- Fixed a scope error involving the main_font variable that could crash GUI startup.

### v1.0.0-beta.1 — Cross-platform support
- Added macOS, Windows, and Linux launchers.
- Adapted file paths, fonts, and folder-opening actions.

### v1.0.0-alpha.2 — Bilingual GUI
- Added Chinese and English interface switching.
- Introduced bilingual project documentation.

### v1.0.0-alpha.1 — First macOS GUI
- Introduced a Tkinter desktop frontend for Arctic Shift corpus collection.
- Added sampling settings, progress output, API testing, and export controls.

---

## 中文

> Alpha、Beta、RC版本号是根据历史开发快照追溯整理的；早期界面显示的版本号不一定与归档标签相同。

### v1.1.1 — 输出README双语化
- 每次采集的README.txt改为英文在上、中文在下。
- 两种语言均说明采集参数、输出文件、数据量与警告。

### v1.1.0 — 采集结果独立归档
- 每次运行自动创建唯一输出文件夹。
- 新增run_manifest.json和collection.log。
- 防止后续采集覆盖先前结果。

### v1.0.0 — 首个正式基准版
- 将自动时间窗口选择器候选版确立为正式基准版本。
- 相较v1.0.0-rc.1没有增加额外功能。

### v1.0.0-rc.1 — 自动窗口选择
- 根据起止日期与窗口长度自动计算可选窗口。
- 支持单窗口采集和不完整窗口目标数量展示。

### v1.0.0-beta.4 — 网络断线恢复
- 为连接重置和不完整HTTP响应添加有限次数重试。
- 增强API故障诊断，失败请求不会记为成功样本。

### v1.0.0-beta.3 — TLS证书处理
- 为GUI和采集引擎添加可信CA证书配置。
- 继续验证HTTPS证书，不通过关闭验证解决问题。

### v1.0.0-beta.2 — GUI启动错误修复
- 修复main_font作用域错误造成的启动崩溃。

### v1.0.0-beta.1 — 跨平台支持
- 提供macOS、Windows与Linux启动脚本。
- 适配操作系统路径、字体和打开目录功能。

### v1.0.0-alpha.2 — 中英双语界面
- 增加中文/英文切换。
- 将项目文档改为中英双语。

### v1.0.0-alpha.1 — 初版macOS图形界面
- 使用Tkinter提供Arctic Shift语料采集桌面界面。
- 提供采样参数、进度日志、API测试和导出控制。
