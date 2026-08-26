---
name: markji
description: 用墨墨开放 API 读写墨墨记忆卡（Markji）卡片，并按 Markji 制卡语法生成有效且美观的卡片。当用户提到 markji、墨墨记忆卡、墨记、制卡、牌组 deck、章节 chapter、闪卡、挖空、答案线，或要求把学习材料做成卡片、批量导入卡片、修改已有卡片、上传卡片图片音频遮罩时使用。
---

# 墨墨记忆卡（Markji）制卡

用官方开放 API 把学习材料做成 Markji 卡片。核心难点不在调接口，而在**卡片内容必须是一整段合法的 Markji 专用语法**——语法写错不会报错，只会静默渲染成一团乱码。

## 起手动作

```bash
python3 .claude/skills/markji/scripts/markji.py whoami
```

凭证读取顺序：环境变量 `MAIMEMO_TOKEN` → 向上查找 `.env`。
凭证**绝不能**出现在代码、文档、提交信息或终端回显中。`.env` 已被 `.gitignore` 忽略，不要移除该规则。

## 必须先知道的三条边界

1. **开放 API 只能写卡片和媒体。** 不能建/删牌组，不能建/删章节，**也不能删卡片**。
   牌组和章节要用户先在 App 或网页端建好；写进去的卡片只能在 App 端删。
2. **写入是不可逆的。** 首次向某个牌组写卡前，先向用户确认目标牌组/章节和卡片内容。
3. **`content` 是一整段语法文本**，`grammar_version` 固定为 `3`。更新是全量替换而非增量补丁。

官方 OpenAPI 文档有两处与实现不符，`markji.py` 已处理，**直接手写 curl 时要注意**：
创建卡片的请求体**必须省略** `deck`/`chapter`（否则报 `not a valid ObjectId`）；
上传媒体必须用 `multipart/form-data` 而非 JSON。详见 `references/api.md`。

## 标准工作流

```bash
S=.claude/skills/markji/scripts/markji.py

python3 $S decks                      # 找到目标牌组，拿 mkjd_ 开头的 id
python3 $S chapters <deck>            # 拿 mkjch_ 开头的章节 id
python3 $S cards <deck>               # 看已有卡片，模仿该牌组既有的排版风格
python3 $S card <deck> <card>         # 读单张卡片的完整语法

# 把卡片内容写进文件（真实换行，UTF-8），先离线校验
python3 $S lint card.txt

# 校验通过后写入；create/update 内部会再校验一次，有错误直接中止
python3 $S create <deck> <chapter> --file card.txt --dry-run   # 先看要发什么，不写入
python3 $S create <deck> <chapter> --file card.txt
python3 $S update <deck> <card> --file card.txt

# 媒体：先上传拿 file.id，再把 id 写进卡片语法
python3 $S upload ./pic.png --deck <deck>
python3 $S query-files <fileId> ...
```

一次做多张卡时，**每张卡一个文件**，`lint` 全部通过后再逐张 `create`，请求间隔 ≥0.5s（频控 10 秒 20 次）。

## 生成卡片内容的规矩

写卡片前**必读** `references/card-syntax.md`。最容易翻车的几点：

- **真实换行是语法的一部分**。绝不能写成字面 `\n`，也不能把整张卡压成一行。
- **`---` 是答案线**，独占一行、前后无空格。标题标签不代替答案线。
- **块级语法必须顶格**：`[P#…]`、`[Choice#…`、`[Pic#…#]`、独立公式、`---`。行内公式不受此限。
- **样式合并进一个标签**：写 `[T#B,U,!e53935#重点]`，不要写 `[T#B#[T#U#重点]]`。
- **颜色是不带 `#` 的 6 位小写十六进制**：`!e53935` ✓，`!#E53935` ✗。
- **普通文字里的中括号写成 `\[` `\]`**，否则会提前闭合外层标签。
- **公式一律 `[E##LaTeX]`**（KaTeX 渲染），内部不再套 `$`、`$$`、`\(`、`\[`。
- **公式挖空是 `E` 内嵌 `F`**：`[E##k=[F#1#\frac{\Delta y}{\Delta x}]]`，不是反过来。
- **选择题类型由 `*` 的个数决定**：一个用 `[Choice##`，两个以上必须 `[Choice#multi#`；选项行以 `* ` / `- ` 开头（符号后有空格），结束的 `]` 独占一行。
- **媒体只能用上传返回的真实 `file.id`**，大小写敏感，绝不能填文件名、路径或 URL；不要编造 ID。
- **卡片引用填 `root_id`**（`mkjr_…`）而不是 `card.id`，最多 5 个、用 `-` 连接。

模板见 `templates/`，可直接复制后替换占位符——**所有 `<…>` 占位符都必须替换**。

## 「美观」的实际含义

Markji 卡片的可读性主要靠这几件事，照做即可：

- 正面用 `[P#H1,center#[T#B#…]]` 立标题；有外文对照时用 `[P#center#…]` 放第二行。
- 答案面只强调**真正的考点**：用 `[T#B,!e53935#…]` 标 2–4 处即可，标满等于没标。
- 补充信息（音标、词源、出处）用低饱和灰 `[T#!888888#…]` 降权。
- 需要罗列时用 `[P#L#…]` 配 `[P#L,I2#…]` 做层级，不要堆砌裸换行。
- 需要主动回忆时用 `[F#n#…]` 挖空，同一组用同一编号。
- 一张卡只考一个点。内容长就拆卡，不要靠缩小信息密度硬塞。

## 参考文件

- `references/card-syntax.md` — 制卡语法完整参考（语法表、嵌套规则、模板、常见错误、检查清单）
- `references/api.md` — API 端点、认证、频控、对象字段、能力边界
- `templates/` — 可直接复制的卡片模板
- `scripts/markji.py` — API 客户端 + 语法校验器（`lint` 覆盖检查清单的绝大部分）
