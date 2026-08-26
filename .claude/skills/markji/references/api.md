# 墨墨记忆卡（Markji）开放 API 参考

## 0. 先厘清一件事

墨墨记忆卡（Markji）**没有独立的开放平台**。它的官方 API 是**墨墨开放 API 的一个子集**，
挂在 `open.maimemo.com` 下的 `/api/v1/markji/*` 路径，与墨墨背单词共用同一套凭证和文档。

- 文档：<https://open.maimemo.com/#/>（左侧「墨墨记忆卡」分组）
- OpenAPI 原始定义：<https://open.maimemo.com/api_bundle.yaml>
- 产品站：<https://www.markji.com/>

`https://www.markji.com/api/v1/*` 是 App/网页端的**内部私有接口**，用另一套登录 token，
**不要用开放 API 的凭证去调**（会返回 `user_unauthorized`）。本 skill 一律走开放 API。

---

## 1. 认证

```
Authorization: Bearer <MAIMEMO_TOKEN>
Accept: application/json
```

取得凭证的两种方式：
1. 墨墨背单词 App → 我的 → 更多设置 → 实验功能 → 开放 API
2. 浏览器打开 <https://open.maimemo.com/open/api/v1/tokens/openapi>

凭证从 `MAIMEMO_TOKEN` 环境变量或仓库根目录 `.env` 读取。`.env` 已在 `.gitignore` 中，
**任何情况下都不要把 token 写进代码、文档、提交信息或日志。**

---

## 2. Base URL

```
生产：https://open.maimemo.com/open/api/v1/markji
测试：https://open-dev.maimemo.com/open/api/v1/markji
```

## 3. 频控

| 窗口 | 上限 |
|---|---|
| 10 秒 | 20 次 |
| 60 秒 | 40 次 |
| 5 小时 | 8000 次（墨墨记忆卡） |

批量制卡时请求之间建议留 ≥0.5s 间隔。

## 4. 响应信封

所有响应统一为：

```json
{ "errors": [], "data": { ... }, "success": true }
```

出错时 `errors` 为 `[{"code": "...", "message": "...", "info": ""}]`，HTTP 状态码非 2xx。

---

## 5. 端点一览

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/decks/folders` | 列出文件夹及其包含的牌组 |
| GET | `/decks` | 列出牌组（`offset` / `limit` / `folder_id`） |
| GET | `/decks/{deck}` | 单个牌组（`with_root`） |
| GET | `/decks/{deck}/chapters` | 列出章节（`with_cards` / `updated_time`） |
| GET | `/decks/{deck}/chapters/{chapter}` | 单个章节（`with_cards` / `updated_time`） |
| GET | `/decks/{deck}/cards/{card}` | 单张卡片 |
| POST | `/decks/{deck}/chapters/{chapter}/cards` | **创建卡片** |
| POST | `/decks/{deck_id}/cards/{card_id}` | **更新卡片** |
| POST | `/files` | **上传媒体**，返回 `file.id` |
| POST | `/files/query` | 按 id 批量查询媒体（`expires` 控制 URL 有效期） |

### ⚠️ API 能力边界（重要）

开放 API **只能写卡片和媒体**：

- **不能**创建 / 重命名 / 删除**牌组**
- **不能**创建 / 重命名 / 删除**章节**
- **不能删除卡片** —— 没有 DELETE 端点

所以：**牌组和章节必须先在 Markji App 或网页端手工建好**，再用 API 往里写卡片。
且**通过 API 创建的卡片只能在 App/网页端删除**，写入前务必确认内容和目标章节。

---

## 6. 创建卡片

```
POST /decks/{deck}/chapters/{chapter}/cards
```

```json
{
  "card": {
    "content": "[P#H1,center#[T#B#标题]]\n---\n正文\n",
    "grammar_version": 3
  },
  "order": 0
}
```

> ### ⚠️ 与 OpenAPI 文档不符（已实测）
> 文档把 `deck` / `chapter` 标为请求体**必填**，说明写的是「牌组 OpenAPI ID」。
> 但服务端会把请求体里的这两个字段按 **24 位 ObjectId** 校验，传开放 ID 会得到
> `common_invalid_param: deck not a valid ObjectId`，而开放 API 从不暴露 ObjectId。
>
> **正确做法：请求体里完全省略 `deck` 和 `chapter`**，牌组与章节由 URL 路径决定。
> 路径参数必须用开放 ID（`mkjd_…` / `mkjch_…`）；传 ObjectId 会得到 `common_invalid_res_id`。

- `content` 与 `grammar_version` 都是必填。**`grammar_version` 当前为 `3`**。
- `order` 可选，控制卡片在章节中的位置；不传则追加到章节末尾。
- 返回 `{ "card": MarkjiCard, "chapter": MarkjiChapter }`。
  新卡的 `root_id` 在响应里，写 `[Card#ID/...]` 引用时要用它。
- 服务端会解析 `content` 中的 `[Pic#ID/…]` / `[Audio#ID/…]`，把对应媒体填进返回的 `card.files`。
  可据此确认 `file.id` 是否被正确引用。

## 7. 更新卡片

```
POST /decks/{deck_id}/cards/{card_id}
```

```json
{
  "deck_id": "mkjd_...",
  "card_id": "mkjc_...",
  "card": { "content": "...", "grammar_version": 3 }
}
```

与 `create` 不同，**更新接口按文档工作**：请求体里的 `deck_id` / `card_id` 要传开放 ID，与路径一致。

`content` 是**全量替换**，不是增量补丁。改卡前先 `GET` 取回原内容，在原有语法骨架上局部修改。

## 8. 上传媒体

> ### ⚠️ 与 OpenAPI 文档不符（已实测）
> 文档声明请求体为 `application/json`、`file` 为字符串。实际服务端只接受
> **`multipart/form-data`**：裸 base64、data URI、urlsafe base64 一律返回
> `common_invalid_param … info: "missing file"`。

```
POST /files
Content-Type: multipart/form-data; boundary=...

--boundary
Content-Disposition: form-data; name="deck_id"

mkjd_...
--boundary
Content-Disposition: form-data; name="file"; filename="pic.png"
Content-Type: image/png

<原始二进制>
--boundary--
```

- `file` 必填，`deck_id` 可选。
- 同一份内容重复上传会返回**同一个 `file.id`**（按内容去重），不会产生重复文件。
- `.msk1` 遮罩文件的 mime 是 `markji/mask`。
- 返回 `{ "file": { "id", "url", "mime", "size", "info", "expire_time" } }`。
- **`file.id` 大小写敏感**，取回后逐字符原样写进 `[Pic#ID/...]` / `[Audio#ID/...]`。
- `url` 是带有效期的临时地址（`expire_time`），不要长期缓存或写进卡片。

---

## 9. 对象与 ID 前缀

| 前缀 | 对象 |
|---|---|
| `mkjfo_` | 文件夹 MarkjiFolder |
| `mkjd_` | 牌组 MarkjiDeck |
| `mkjcs_` | 章节集 MarkjiChapterset |
| `mkjch_` | 章节 MarkjiChapter |
| `mkjc_` | 卡片 MarkjiCard（`card.id`） |
| `mkjr_` | 卡片根 ID（`card.root_id`，用于 `[Card#ID/…]` 引用） |
| `mkjf_` | 媒体文件 MarkjiFile（`file.id`，用于 `[Pic#ID/…]` / `[Audio#ID/…]`） |

ID 中含有 `.` 和 `_`，放进 URL 路径时**必须做 URL 编码**（`markji.py` 已处理）。

### 关键字段

| 对象 | 必有字段 |
|---|---|
| MarkjiDeck | `id, source, status, name, description, creator, authors, revision, is_private, card_count, chapter_count, created_time, updated_time` |
| MarkjiChapterset | `id, deck_id, revision, chapter_ids, created_time, updated_time` |
| MarkjiChapter | `id, deck_id, name, revision, card_ids, creator, created_time, updated_time` |
| MarkjiCard | `id, status, deck_id, revision, content, content_type, files, creator, source, grammar_version, created_time, updated_time`（另有 `root_id`、`card_rids`） |
| MarkjiFile | `id, url, mime, size, info, expire_time` |
| MarkjiFolder | `id, items, name`（`items` 为 `{object_id, object_class}`） |

`content_type` 实测为 `1`（Markji 语法文本），创建时不需要传。
`card.files` 由服务端根据 `content` 中的媒体标签自动填充，创建时不需要传。

---

## 10. curl 速查

```bash
# 列牌组
curl -s -H "Authorization: Bearer $MAIMEMO_TOKEN" \
  "https://open.maimemo.com/open/api/v1/markji/decks?limit=20"

# 列章节并带上卡片
curl -s -H "Authorization: Bearer $MAIMEMO_TOKEN" \
  "https://open.maimemo.com/open/api/v1/markji/decks/$DECK/chapters?with_cards=true"

# 创建卡片
curl -s -X POST -H "Authorization: Bearer $MAIMEMO_TOKEN" \
  -H "Content-Type: application/json" \
  "https://open.maimemo.com/open/api/v1/markji/decks/$DECK/chapters/$CHAPTER/cards" \
  -d '{"card":{"content":"正面\n---\n背面\n","grammar_version":3}}'

# 上传媒体（必须 multipart，不是 JSON）
curl -s -X POST -H "Authorization: Bearer $MAIMEMO_TOKEN" \
  -F "deck_id=$DECK" -F "file=@./pic.png;type=image/png" \
  "https://open.maimemo.com/open/api/v1/markji/files'
```

优先使用 `scripts/markji.py`：它会做 URL 编码、统一错误处理，并在写入前自动校验制卡语法。
