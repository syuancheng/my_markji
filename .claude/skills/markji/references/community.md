# 社区与站外资源索引

墨墨记忆卡官方**没有制卡语法的正式文档**，可用知识散落在官方论坛
<https://markji.discourse.group/> 和几个社区维护的站点里。本文件是一份**索引**：
只给「标题 + 链接 + 一句话」，不抄全文。

> ⚠️ 除「官方开放 API 文档」外，以下多为**社区讨论帖或第三方整理**，
> 非官方规范，可能过时或有误。真正的语法基准以本 skill 的
> [`card-syntax.md`](card-syntax.md) 和 [`api.md`](api.md) 为准（那两份是实测过的）；
> 下列资料仅作补充参考，采纳前对照实测。

## 站外文档

- [墨墨记忆卡使用手册](https://tutuji333.github.io/markji-manual/) — 社区维护的图文使用手册，覆盖新建牌组、章节、答案线等基础操作。
- [墨墨记忆卡 FAQ](https://tutuji333.github.io/markji-faq/) — 社区 FAQ 合集。
- [制卡语法指南（面向 AI）](https://tutuji333.github.io/markji-faq/questions/content/card-syntax-guide/) — FAQ 里专门给 AI 看的语法速查，内容与本 skill 的 `card-syntax.md` 高度重合，后者更细。
- [墨墨开放 API 文档](https://open.maimemo.com/#/) — 官方，唯一正式文档；端点/字段已整理进 `api.md`。

## 论坛：语法与格式

- [交流分享：墨墨记忆卡制卡语法说明](https://markji.discourse.group/t/topic/662) — 2021 年官方帖，最早介绍文字样式 `[T#B#…]`、挖空 `[F##…]`、选择题 `[Choice##…]`；官方本意是让多数人用可视化编辑器而非手写语法。
- [制卡语法：能否同时对文字加粗、背景、变换颜色](https://markji.discourse.group/t/topic/91) — 多种样式要合并进同一个 `[T#…#…]` 的参数里，别套多层。
- [编辑语法：卡片内容中出现方括号 \[\]](https://markji.discourse.group/t/topic/53) — 正文里的中括号必须转义成 `\[` `\]`，否则提前闭合外层标签。
- [求助：关于句子词组的标记功能](https://markji.discourse.group/t/topic/375) — 给句子里的短语加色/加粗的写法讨论。
- [墨记指南002期｜答案线教程 & 在官网新建牌组](https://markji.discourse.group/t/topic/481) — 答案线 `---` 的规则演示，以及网页端建牌组步骤。
- [请求互助：为什么我的大部分卡片答案线不起效](https://markji.discourse.group/t/topic/633) — 答案线写错的常见原因排查（前后有空格、非独占一行等）。

## 论坛：公式与理工科

- [分享交流：公式新语法指南](https://markji.discourse.group/t/topic/991) — 2026-08 更新：行内公式、公式挖空（`[E##…[F#n#…]…]`）、嵌套选择题；注意**官方可视化编辑器并不提供公式内部挖空**，只能手写语法且需自测。
- [使用指南：卡片编辑理工科相关公式技巧](https://markji.discourse.group/t/topic/319) — KaTeX 公式、化学方程式、上下标等 STEM 排版技巧。
- [经验交流：理工科特殊符号分享](https://markji.discourse.group/t/topic/87) — 特殊符号的 LaTeX 写法整理。
- [请求互助：怎么把公式里面的一部分「挖空」](https://markji.discourse.group/t/topic/470) — 公式挖空是 `E` 内嵌 `F`，方向别写反。

## 论坛：排版与内容设计

- [卡片内容过多：美观卡片内容的排版](https://markji.discourse.group/t/topic/57) — 官方回应：内容太密就**拆卡**，不要在一张卡里靠排版硬塞。
- [制卡经验：牌组创作者经验分享](https://markji.discourse.group/t/topic/41) — 创作者的通用制卡经验。
- [创作者相关：制卡编辑经验分享](https://markji.discourse.group/t/topic/384) — 同上，另一位创作者的经验帖。

## 论坛：批量制卡

- [使用答疑：制卡时如何实现批量编辑](https://markji.discourse.group/t/topic/515) — 网页端批量编辑入口与用法。
- [请求互助：批量制卡中专业与简单的区别](https://markji.discourse.group/t/topic/414) — 网页端「简单 / 专业」两种批量导入模式的差异。
- [请求互助：批量制卡中专业模式的用法](https://markji.discourse.group/t/topic/421) — 专业模式导入格式说明。
- [异常反馈：文本批量导入创建章节逻辑](https://markji.discourse.group/t/topic/601) — 批量导入时章节是怎么切分/创建的。

## 论坛：AI 制卡

- [分享交流：豆包 + 墨墨记忆卡 保姆级 AI 制卡教程](https://markji.discourse.group/t/topic/871) — 全站置顶精华，零门槛 AI 制卡全流程。
- [分享交流：墨墨 AI 制卡提示词以及全流程](https://markji.discourse.group/t/topic/717) — 一套较完整的 AI 制卡提示词 + 操作流程。
- [分享交流：分享一个自用的 AI 制卡提示词](https://markji.discourse.group/t/topic/981) — 另一份提示词，指向上面的「制卡语法指南（面向 AI）」。
- [分享 skill 技能](https://markji.discourse.group/t/topic/993) — 社区分享的 skill / 工具帖。

## 论坛：API 与语音

- [分享交流：有和墨背一样的 API 开放计划吗](https://markji.discourse.group/t/topic/501) — 开放 API 的讨论（现已有，见 `api.md`）。
- [请求互助：如何语音大量生成](https://markji.discourse.group/t/topic/591) — 批量配音：目前**只能实现第 ③ 步**（把音频 id 写进语法），① 文字转语音 ② 上传音频 需自己写程序走开放 API；官方称年内会出批量配音功能。与本 skill 结论一致。

## 官方公告（仅制卡相关）

- [创作公告：创作福利发放及精选牌组制卡指南](https://markji.discourse.group/t/topic/546) — 官方对「精选牌组」的制卡质量要求。
- [创作者及制卡相关帖子整理](https://markji.discourse.group/t/topic/654) — 社区自己维护的制卡帖索引，本文件的主要来源。
