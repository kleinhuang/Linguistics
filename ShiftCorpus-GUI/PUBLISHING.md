# Publishing status / 发布状态

## English

This project lives inside the multi-project repository `kleinhuang/Linguisitic`.

**Already published to `main`:**
- `ShiftCorpus-GUI/README.md`
- `ShiftCorpus-GUI/CHANGELOG.md`
- `ShiftCorpus-GUI/VERSION_HISTORY.md`
- This publishing note.

**Not yet published:** complete Python source history, ten version tags and downloadable ZIP release packages.

A separate publishing kit was prepared for the project. To publish the archived program without replacing the repository's `main`, run:

```bash
brew install gh                 # macOS, if needed
gh auth login
bash publish_to_existing_linguisitic.sh kleinhuang/Linguisitic
```

The script creates the separate `shiftcorpus-history` branch, pushes prefixed tags such as `shiftcorpus-v1.1.1`, and creates ten bilingual GitHub Releases. It does not force-push or overwrite `main`.

> Verify that the branch, tags, and Releases actually appear before marking publication complete. Do not upload raw research corpora or local credentials to this public repository.

---

## 中文

该项目位于多项目仓库 `kleinhuang/Linguisitic`。

**已经上传到 `main`：** `ShiftCorpus-GUI/` 内的双语README、CHANGELOG、版本历史和本发布说明。

**尚未上传：** 完整Python代码历史、十个正式Git标签和可下载ZIP Release附件。

为了不覆盖已有 `main` 分支，可以在Mac终端安装GitHub CLI，执行 `gh auth login` 后，在此前准备的发布包目录运行：

```bash
bash publish_to_existing_linguisitic.sh kleinhuang/Linguisitic
```

脚本将代码发布到独立的 `shiftcorpus-history` 分支，并用 `shiftcorpus-v1.1.1` 等标签建立十个双语Release。不会强制推送覆盖 `main`。

**注意：** 必须确认远端实际存在代码、标签及Release后，才能称为完整发布。公开仓库中不要上传原始研究数据、密钥或个人文件。
