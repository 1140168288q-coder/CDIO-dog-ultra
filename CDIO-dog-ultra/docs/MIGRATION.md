# 项目整合记录

## 最终来源与目录映射

| 来源 | 新位置 |
|---|---|
| `CDIO癫疯对决/红方/main.py` | `main.py` |
| `CDIO癫疯对决/红方/motion_test.py` | `motion_test.py` |
| `CDIO癫疯对决/红方/main (1).py` | `reference/final-variants/main_debug.py` |
| `CDIO癫疯对决/红方/课堂整合代码参考.py` | `reference/classroom_code.py` |
| `CDIO癫疯对决/红方/CLAUDE.md` | `reference/final-variants/CLAUDE.original.md` |
| `ASFM` 顶层全部文件 | `docs/asfm/`，其中 `CLAUDE.md` 改名为 `CLAUDE.original.md` |
| `CDIO-dog-pro` 最后提交全部文件 | `archive/CDIO-dog-pro/` |
| `CDIO-dog-pro-max` 最后提交全部文件 | `archive/CDIO-dog-pro-max/` |

没有纳入 `.claude/settings.local.json`，因为它是本地编辑器配置。没有改变来源程序、Word、PDF、drawio 或 PNG 的内容；README 与本说明为新增文档。

所有文件对应关系与 SHA-256 见 [`migration-manifest.json`](migration-manifest.json)。不将旧控制器模块混入根目录运行路径，以保留最终版独立的单文件结构。

## Git 历史

| 历史分支 | 原默认分支提交 | 提交数 |
|---|---|---:|
| `history/CDIO-dog-pro` | `efc2e8a89482ef91c74b1c332e6d80795fe85457` | 2 |
| `history/CDIO-dog-pro-max` | `35c69c6301b8738b76c7811314e4df76e172723e` | 4 |

原提交对象、树对象和文件对象恢复后均检查了原 SHA；包括 GitHub 签名提交。整合提交同时连接上述两个历史分支，使 6 次旧提交在新 `main` 历史中可达。两个旧仓库在检查时各有一个 `main` 分支，没有 issues 或 releases。

删除旧仓库之前，应先确认新仓库的 `main` 和两条 `history/` 分支均上传成功，所有最终文件与历史快照的远端 blob SHA 与本地一致。

## GitHub 发布

本地整合完成不等于 GitHub 已创建新仓库或已删除旧仓库。提供的 [`tools/publish_github.py`](../tools/publish_github.py) 使用 GitHub API 与 Git 完成发布，只有远端分支与完整文件树通过核对后，才执行指定的旧仓库删除。

在可访问 GitHub 的普通终端中，从本仓库运行：

```powershell
python tools/publish_github.py --delete-legacy
```

脚本优先使用 `GH_TOKEN` / `GITHUB_TOKEN` 或 `gh auth token`，否则通过隐藏输入读取令牌。令牌不会写入仓库或打印。需要具备新建本人仓库、写入内容和删除指定旧仓库的权限；classic PAT 对应 `public_repo`（或 `repo`）以及 `delete_repo`。

脚本固定目标账号为 `1140168288q-coder`，固定新仓库为 `CDIO-dog-ultra`，固定旧仓库 ID；若账号、源提交或新仓库内容不符合预期则停止。重复执行可继续核验，已删除的旧仓库会跳过。省略 `--delete-legacy` 时只发布和验证。
