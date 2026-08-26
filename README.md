# my_markji

一个 Claude Code skill：用**墨墨开放 API** 读写**墨墨记忆卡（Markji）**卡片，
并按 Markji 制卡语法生成有效且美观的卡片。

## 这是哪个 API

墨墨记忆卡没有独立的开放平台。它的官方接口是**墨墨开放 API 的子集**，
路径为 `https://open.maimemo.com/open/api/v1/markji/*`，与墨墨背单词共用同一套凭证。

`https://www.markji.com/api/v1/*` 是 App/网页端的**内部私有接口**，用另一套登录 token，
本项目不使用。

## 快速开始

```bash
cp .env.example .env
# 编辑 .env 填入 MAIMEMO_TOKEN

python3 .claude/skills/markji/scripts/markji.py whoami
python3 .claude/skills/markji/scripts/markji.py decks
```

凭证读取顺序：环境变量 `MAIMEMO_TOKEN` → 当前目录向上找 `.env` → 脚本真实位置向上找 `.env`。
**`.env` 已被 `.gitignore` 忽略，token 不会进入版本库。**

获取 token：墨墨背单词 App → 我的 → 更多设置 → 实验功能 → 开放 API，
或打开 <https://open.maimemo.com/open/api/v1/tokens/openapi>。

## 两种制卡入口

- **单句/单个表达**：直接把英文句子交给 skill，一步生成一张卡（`create --file -` 读标准输入）。
  会自动沿用 Speaking 系列既有的房屋风格：中文标题在正面、英文在背面、关键表达标红、
  底部「常用短语」区。
- **整份文档**：给一个 Markdown 文件路径，按最小信息原则切成整套卡片，
  先传图记 manifest，再用 `batch` **一次建完所有卡**，最后 `verify` 收尾。

`batch` 的设计要点：整体校验后才动手（一张有错就全部不建，不留半套卡）、
增量写 manifest（中途挂掉也知道建到哪）、失败可用 `--start N` 续传不重复建卡、
终端只输出汇总以免刷屏。

## 全局启用

skill 默认只在本仓库目录下生效。软链到用户级 skills 目录即可在任何项目中使用：

```bash
ln -s ~/Documents/projects/my_markji/.claude/skills/markji ~/.claude/skills/markji
```

脚本会先从当前目录向上找 `.env`，找不到再从**脚本真实位置**向上找，
所以软链之后在别的项目里也能读到本仓库的 `.env`，无需额外设置环境变量。

## 命令

```
markji.py whoami                             验证凭证
markji.py folders                            列出文件夹
markji.py decks [--limit N] [--folder ID]    列出牌组
markji.py chapters <deck>                    列出章节
markji.py cards <deck> [--chapter ID]        列出卡片
markji.py card <deck> <card> [--json]        读取单张卡片
markji.py create <deck> <chapter> --file F   创建单张卡片（先校验语法，--dry-run 只预览）
markji.py batch  <deck> <chapter> --file F   一次创建多张（文件内用独占一行的 @@@ 分隔）
markji.py update <deck> <card> --file F      更新卡片（先校验语法）
markji.py upload <path> [--deck ID]          上传图片/音频/.msk1，返回 file.id
markji.py query-files <id>...                查询媒体
markji.py verify <deck> <chapter>            批量校验章节：卡片数、顺序、媒体关联、逐张语法
markji.py lint <file>...                     离线校验制卡语法
```

## 语法校验器

`lint` 覆盖官方发布前检查清单的绝大部分，包括：括号闭合与转义、答案线位置、
块级语法顶格、`T`/`P` 参数合法性、颜色格式、挖空编号、公式挖空嵌套方向、
残留 `$`/HTML、选择题单选/多选与 `*` 个数是否一致、`Pic` 的 `ID`/`MID` 顺序、
卡片引用数量上限、未替换的占位符等。

`create` 和 `update` 在提交前会自动跑一遍，有 ERROR 直接中止（`--force` 可跳过）。
写入后可用 `verify` 联网复核整个章节。请求遇 `429`/`5xx` 会自动退避重试。

回归基准：对账号内 218 张真实卡片全部通过，无误报。

## 实测状态

读、写、上传三条路径均已对生产环境验证：卡片创建后读回内容**逐字节一致**，
`[Pic#ID/…]` 引用被服务端正确解析进 `card.files`。

官方 OpenAPI 文档有两处与实现不符，本项目已按实际行为实现：

| 位置 | 文档说法 | 实际 |
|---|---|---|
| `POST …/cards` 创建卡片 | 请求体必填 `deck` / `chapter`（开放 ID） | 必须**省略**，否则按 24 位 ObjectId 校验而失败；牌组章节由路径决定 |
| `POST /files` 上传媒体 | `application/json`，`file` 为字符串 | 只接受 `multipart/form-data` |

`POST …/cards/{card}` 更新卡片按文档工作（请求体传开放 ID `deck_id` / `card_id`）。

## 目录

```
.claude/skills/markji/
├── SKILL.md                    skill 主文件
├── references/
│   ├── card-syntax.md          制卡语法完整参考
│   └── api.md                  API 端点与能力边界
├── templates/                  可复制的卡片模板
└── scripts/markji.py           API 客户端 + 语法校验器
```

## API 能力边界

开放 API **只能写卡片和媒体**：不能建/删牌组，不能建/删章节，**不能删卡片**。
牌组和章节需先在 App 或网页端建好；写入的卡片只能在 App 端删除。

频控：10 秒 20 次 / 60 秒 40 次 / 5 小时 8000 次。

## 参考

- 墨墨开放 API 文档 <https://open.maimemo.com/#/>
- 墨墨记忆卡 <https://www.markji.com/>
- 社区 FAQ · 制卡语法关键指南 <https://tutuji333.github.io/markji-faq/questions/content/card-syntax-guide/>
