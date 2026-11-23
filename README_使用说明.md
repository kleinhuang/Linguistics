# ShiftCorpus GUI 使用说明（macOS / VS Code）

## 启动
1. 解压整个 `ShiftCorpus_GUI.zip` 文件，保持 `shift_corpus_gui.py` 和 `shift_corpus_engine.py` 在同一个文件夹。
2. 在 VS Code 中打开该文件夹，打开 Terminal，输入：

   ```bash
   python3 shift_corpus_gui.py
   ```

3. 如果安装了支持 Tkinter 的 Python，也可以在 Mac Finder 双击 `启动采集器.command`。
4. 如提示 `No module named _tkinter`，当前 Python 未包含 Tkinter。可以安装 python.org 提供的 macOS Python 3，然后重新运行；某些 Homebrew Python 版本需要另外安装 Tcl/Tk 支持。

## 推荐设置
- Subreddit：`politics`
- 日期：`2022-05-01` 至 `2026-11-20`（含首尾两天；UTC）
- 窗口：180天，每个完整窗口180条，Seed=1
- 最后窗口：`proportional`，不足180天则按天数等比例调整目标
- 启用：仅英文、排除Bot、排除NSFW、近重复过滤、关联帖子标题
- 不会把关联帖子正文计入评论词频

建议先点击「测试 API 连接」，再使用「仅采集指定窗口」测试 `2022-05-01_2022-10-27`。注意：这是带实际网络请求的测试，不能保证归档服务器可用。

## 数据输出
运行结束后输出目录会包含每窗口的 `.txt`（AntConc）、`.index.txt`、`.csv`、`.jsonl`，以及记录参数与统计的 `query.json`。未成功收集足够评论时日志会显示 `short` 数量；目标值不等于实际值。

## 重要说明
- GUI调用原有Python采集引擎，不改变其抽样算法；该算法不是严格意义上从全部评论等概率抽样。
- Python脚本自带重试机制，遇到HTTP状态、超时、证书等错误会显示诊断信息。
- 停止按钮会终止进程；未成功写出的数据不一定能够自动恢复。建议先运行单窗口测试，再运行完整任务。
- 本软件依赖 Arctic Shift 在线服务，不能保证第三方服务持续在线或能提供全部日期的存档。
- 本应用仅使用Python标准库，不收集或上传你的任何额外账号信息。
