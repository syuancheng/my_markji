#!/usr/bin/env python3
"""墨墨记忆卡 (Markji) 开放 API 客户端 + 制卡语法校验器。

仅使用 Python 标准库。凭证从环境变量 MAIMEMO_TOKEN 读取，
或从仓库根目录 / 当前目录向上查找的 .env 文件读取。凭证绝不写入代码或日志。
"""
import argparse
import json
import mimetypes
import os
import re
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://open.maimemo.com/open/api/v1/markji"
GRAMMAR_VERSION = 3  # 由真实卡片数据确认

# ---------------------------------------------------------------- 凭证


def _read_env_file(path):
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("MAIMEMO_TOKEN="):
                v = line.split("=", 1)[1].strip().strip("\"'")
                if v and v != "your_token_here":
                    return v
    except OSError:
        pass
    return None


def _walk_up(start):
    d = os.path.abspath(start)
    while True:
        yield os.path.join(d, ".env")
        parent = os.path.dirname(d)
        if parent == d:
            return
        d = parent


def load_token():
    tok = os.environ.get("MAIMEMO_TOKEN", "").strip()
    if tok:
        return tok
    # 依次尝试：当前目录向上 → 脚本真实位置向上（软链到 ~/.claude/skills 后仍能找到仓库里的 .env）
    seen = set()
    for start in (os.getcwd(), os.path.dirname(os.path.realpath(__file__))):
        for candidate in _walk_up(start):
            if candidate in seen:
                continue
            seen.add(candidate)
            v = _read_env_file(candidate)
            if v:
                return v
    sys.exit(
        "错误：未找到凭证。请设置环境变量 MAIMEMO_TOKEN，或在仓库根目录创建 .env\n"
        "（参考 .env.example；.env 已被 .gitignore 忽略）"
    )


# ---------------------------------------------------------------- HTTP


def api(method, path, query=None, body=None):
    url = BASE + path
    if query:
        q = {k: v for k, v in query.items() if v is not None}
        if q:
            url += "?" + urllib.parse.urlencode(q)
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + load_token())
        req.add_header("Accept", "application/json")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            # 429 触发频控、5xx 服务端抖动 —— 退避后重试；4xx 是请求本身有问题，重试无意义
            if e.code == 429 or 500 <= e.code < 600:
                if attempt < 2:
                    wait = 5 * (attempt + 1)
                    print(f"HTTP {e.code}，{wait}s 后重试（第 {attempt + 2}/3 次）", file=sys.stderr)
                    time.sleep(wait)
                    continue
            try:
                errs = json.loads(raw).get("errors", [])
                msg = "; ".join(f"{x.get('code')}: {x.get('msg') or x.get('message')}" for x in errs) or raw
            except Exception:
                msg = raw
            sys.exit(f"API 错误 HTTP {e.code} — {msg}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(5)
                continue
            sys.exit(f"网络错误：{e.reason}")
    if not payload.get("success", True) and payload.get("errors"):
        sys.exit("API 错误：" + json.dumps(payload["errors"], ensure_ascii=False))
    return payload.get("data", payload)


def api_multipart(path, fields, filename, blob, mime):
    """/files 端点实际要求 multipart/form-data，OpenAPI 中的 application/json 声明与实现不符。"""
    boundary = "----mkj" + uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        if v is None:
            continue
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + blob + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + load_token())
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            errs = json.loads(raw).get("errors", [])
            msg = "; ".join(f"{x.get('code')}: {x.get('msg') or x.get('message')} {x.get('info', '')}".strip() for x in errs) or raw
        except Exception:
            msg = raw
        sys.exit(f"API 错误 HTTP {e.code} — {msg}")
    except urllib.error.URLError as e:
        sys.exit(f"网络错误：{e.reason}")
    return payload.get("data", payload)


# ---------------------------------------------------------------- 语法校验

TAGS = {"T", "P", "F", "Choice", "Pic", "Audio", "Card", "E"}
TAG_OPEN = re.compile(r"\[(T|P|F|Choice|Pic|Audio|Card|E)#")
T_PARAMS = {"B", "U", "I", "D", "up", "down"}
P_PARAMS = {"H1", "L", "left", "center", "right"}
BLOCK_PREFIX = ("[P#", "[Choice#", "[Pic#")


def _escaped(s, i):
    """位置 i 的字符是否被反斜杠转义（考虑连续反斜杠）。"""
    n = 0
    j = i - 1
    while j >= 0 and s[j] == "\\":
        n += 1
        j -= 1
    return n % 2 == 1


def find_tags(s):
    """返回 [(name, params, content, start, end)]，end 为闭合 ] 的下标。"""
    out = []
    for m in TAG_OPEN.finditer(s):
        start = m.start()
        if _escaped(s, start):
            continue
        name = m.group(1)
        p = m.end()  # 参数区起点
        # 参数区在下一个未转义 # 处结束
        h = p
        while h < len(s) and not (s[h] == "#" and not _escaped(s, h)):
            h += 1
        if h >= len(s):
            out.append((name, None, None, start, -1))
            continue
        params = s[p:h]
        # 从内容起点扫描到配对的 ]
        depth = 1
        k = h + 1
        while k < len(s):
            c = s[k]
            if not _escaped(s, k):
                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        break
            k += 1
        if k >= len(s):
            out.append((name, params, None, start, -1))
        else:
            out.append((name, params, s[h + 1:k], start, k))
    return out


def lint(content, path="<content>"):
    """返回 [(level, line_no, message)]。level: ERROR / WARN。"""
    issues = []
    lines = content.split("\n")

    def err(ln, msg):
        issues.append(("ERROR", ln, msg))

    def warn(ln, msg):
        issues.append(("WARN", ln, msg))

    def line_of(idx):
        return content.count("\n", 0, idx) + 1

    # 1. 字面 \n —— 换行被写成了两个普通字符
    if re.search(r"(?<!\\)\\n", content) and "\n" not in content:
        err(1, r"整段内容没有真实换行，却出现字面 \n —— 换行必须是真实换行符")
    elif re.search(r"(?<!\\)\\n(?![a-zA-Z])", content):
        for i, l in enumerate(lines, 1):
            if re.search(r"(?<!\\)\\n(?![a-zA-Z])", l):
                warn(i, r"出现字面 \n，确认是否本应是真实换行")

    # 2. 残留 HTML
    for i, l in enumerate(lines, 1):
        m = re.search(r"</?(b|i|u|s|em|strong|span|div|p|br|li|ul|ol|sub|sup|del|ins|font)\b[^>]*>", l, re.I)
        if m:
            err(i, f"残留 HTML 标签 {m.group(0)!r} —— 必须先转换成 Markji 语法")

    # 3. 未替换的占位符
    for i, l in enumerate(lines, 1):
        for m in re.finditer(r"<[^<>\n]{1,40}>", l):
            if not re.match(r"</?(b|i|u|s|em|strong|span|div|p|br|li|ul|ol|sub|sup|del|ins|font)\b", m.group(0), re.I):
                warn(i, f"疑似未替换的占位符 {m.group(0)!r}")

    # 4. 答案线
    sep_lines = [i for i, l in enumerate(lines, 1) if l.strip() == "---"]
    bad_sep = [i for i, l in enumerate(lines, 1) if l.strip() == "---" and l != "---"]
    for i in bad_sep:
        err(i, "答案线 --- 前后有空格，必须独占一行且无多余空白")
    for i, l in enumerate(lines, 1):
        if l.strip() != "---" and re.match(r"^\s*-{3,}\s*\S", l):
            warn(i, "该行以三个以上连字符开头但同行还有其它内容，确认是否想写答案线")
    if not sep_lines:
        warn(1, "没有答案线 ---，卡片将只有一面（如果是刻意为之可忽略）")
    if sep_lines and sep_lines[-1] == len(lines) and not content.endswith("\n"):
        warn(sep_lines[-1], "末尾的答案线后应保留一个真实换行")

    # 5. 块级语法必须从行首开始
    for i, l in enumerate(lines, 1):
        for pref in BLOCK_PREFIX:
            idx = l.find(pref)
            if idx > 0:
                # [Pic# 相邻组成画廊是合法的：允许前面紧跟另一个 ] 结尾
                if pref == "[Pic#" and l[:idx].endswith("#]"):
                    continue
                err(i, f"块级语法 {pref} 必须从行首第一个字符开始（当前在第 {idx + 1} 列）")

    # 6. 逐标签检查
    tags = find_tags(content)
    for name, params, cont, start, end in tags:
        ln = line_of(start)
        if end == -1:
            err(ln, f"[{name}# 标签没有闭合的 ]")
            continue
        if name == "T":
            parts = split_params(params)
            for p in parts:
                if p in T_PARAMS:
                    continue
                if re.fullmatch(r"!{1,2}[0-9a-f]{6}", p):
                    continue
                if re.fullmatch(r'link/"[^"]*"', p):
                    if re.search(r'link/"[^"]*[#,]', p):
                        err(ln, f"链接 URL 含未编码的 # 或逗号（应写成 %23 / %2C）：{p}")
                    continue
                if re.fullmatch(r"!{1,2}#?[0-9a-fA-F]{3,8}", p):
                    err(ln, f"颜色值 {p!r} 非法：必须是不带 # 的 6 位小写十六进制，如 !e53935")
                elif p.startswith("link/"):
                    err(ln, f"链接参数 {p!r} 非法：URL 必须放在英文双引号中，如 link/\"https://...\"")
                else:
                    err(ln, f"[T#...] 未知参数 {p!r}")
            if "up" in parts and "down" in parts:
                err(ln, "[T#...] 不能同时使用 up 和 down")
            if len(parts) != len(set(parts)):
                err(ln, "[T#...] 参数重复")
            if TAG_OPEN.search(cont or ""):
                err(ln, "[T#...] 的内容中不能嵌套其它标签（多种样式请合并到同一个 T 的参数里）")
        elif name == "P":
            parts = split_params(params)
            for p in parts:
                if p in P_PARAMS or re.fullmatch(r"I[1-9]\d*", p):
                    continue
                err(ln, f"[P#...] 未知参数 {p!r}（可用：H1, L, I<n>, left, center, right）")
            aligns = [p for p in parts if p in ("left", "center", "right")]
            if len(aligns) > 1:
                err(ln, "[P#...] 一段只能有一种对齐方式")
            for inner, _, _, _, _ in find_tags(cont or ""):
                if inner not in ("T", "F", "Audio", "Card"):
                    err(ln, f"[P#...] 中不能放 [{inner}#...]（只允许 T / F / Audio / Card）")
        elif name == "F":
            if not re.fullmatch(r"[1-9]\d*", params or ""):
                err(ln, f"挖空编号 {params!r} 非法：必须是从 1 开始的正整数")
            for inner, _, _, _, _ in find_tags(cont or ""):
                if inner == "E":
                    err(ln, "公式挖空嵌套方向写反了：应写成 [E##前段[F#1#被挖空的LaTeX]后段]，而不是 [F#1#[E##...]]")
                else:
                    err(ln, f"[F#...] 的内容中不能嵌套 [{inner}#...]")
        elif name == "Pic":
            if cont:
                err(ln, "[Pic#...#] 的内容区必须为空，结尾应是 #]")
            ids = dict(re.findall(r"(ID|MID)/([^,]*)", params or ""))
            if "ID" not in ids or not ids.get("ID"):
                err(ln, "[Pic#...] 缺少原图 ID/<file.id>")
            if "MID" in ids and not ids["MID"]:
                err(ln, "[Pic#...] 的 MID 为空：没有遮罩时应整个删掉 MID 参数")
            if params and re.match(r"^\s*MID/", params):
                err(ln, "[Pic#...] 参数顺序错误：必须 ID 在前、MID 在后")
            for v in ids.values():
                if re.search(r"[/\\.]|^https?:", v or ""):
                    err(ln, f"{v!r} 看起来是文件名或 URL，不是 Markji file.id")
        elif name == "Audio":
            parts = split_params(params)
            if "M" in parts and "A" in parts:
                err(ln, "[Audio#...] 不能同时使用 M 和 A")
            if not any(p.startswith("ID/") for p in parts):
                err(ln, "[Audio#...] 缺少 ID/<file.id>")
            if TAG_OPEN.search(cont or ""):
                err(ln, "[Audio#...] 的显示文字中不能嵌套其它语法")
        elif name == "Card":
            m = re.fullmatch(r"ID/(.+)", params or "")
            if not m:
                err(ln, "[Card#...] 参数必须是 ID/<root_id>")
            else:
                rids = m.group(1).split("-")
                if len(rids) > 5:
                    err(ln, f"卡片引用最多关联 5 张卡片，当前 {len(rids)} 个")
                if any(not r for r in rids):
                    err(ln, "卡片引用中有空的 root_id")
            if TAG_OPEN.search(cont or ""):
                err(ln, "[Card#...] 的显示文字中不能嵌套其它语法")
        elif name == "E":
            if params:
                err(ln, f"[E#...] 不接受参数，必须写成 [E##公式内容]（当前参数 {params!r}）")
            body = cont or ""
            for bad in ("$$", "$", "\\(", "\\)"):
                if bad in body:
                    err(ln, f"公式中残留定界符 {bad!r} —— [E##...] 本身已经是公式边界")
                    break
            for inner, _, _, _, _ in find_tags(body):
                if inner != "F":
                    err(ln, f"[E##...] 中只能嵌 F（公式挖空），不能放 [{inner}#...]")

    # 7. 选择题块
    i = 0
    while i < len(lines):
        m = re.match(r"^\[Choice#([^#]*)#\s*$", lines[i])
        if not m:
            if lines[i].startswith("[Choice#") and not re.match(r"^\[Choice#[^#]*#\s*$", lines[i]):
                err(i + 1, "[Choice#...# 之后必须换行，选项不能写在同一行")
            i += 1
            continue
        params = split_params(m.group(1))
        for p in params:
            if p not in ("fixed", "multi"):
                err(i + 1, f"[Choice#...] 未知参数 {p!r}（可用：fixed, multi）")
        j = i + 1
        opts = []
        while j < len(lines) and lines[j].strip() != "]":
            opts.append((j + 1, lines[j]))
            j += 1
        if j >= len(lines):
            err(i + 1, "选择题块没有以独占一行的 ] 结束")
        for ln_no, l in opts:
            if not re.match(r"^[*-] ", l):
                err(ln_no, f"选项必须以 '* '（正确）或 '- '（错误）开头，符号后有一个空格：{l[:30]!r}")
            for inner, _, _, _, _ in find_tags(l):
                if inner not in ("T", "E"):
                    err(ln_no, f"选择题选项中不能放 [{inner}#...]（只允许 T 文字样式，公式 E 已在真实卡片验证可用）")
        n_correct = sum(1 for _, l in opts if l.startswith("* "))
        if n_correct == 0:
            err(i + 1, "选择题没有任何以 '* ' 开头的正确选项")
        elif n_correct == 1 and "multi" in params:
            err(i + 1, "只有一个正确选项，不应使用 multi")
        elif n_correct > 1 and "multi" not in params:
            err(i + 1, f"有 {n_correct} 个正确选项，必须使用 [Choice#multi# 或 [Choice#fixed,multi#")
        i = j + 1

    # 8. 未转义的普通中括号（不是任何已知标签的开头）
    known = re.compile(r"\[(T|P|F|Choice|Pic|Audio|Card|E)#")
    for idx, ch in enumerate(content):
        if ch != "[" or _escaped(content, idx):
            continue
        if not known.match(content, idx):
            # 成对时 Markji 靠括号配平通常仍能渲染，故只警告；真正失配由第 9 项报错
            warn(line_of(idx), "普通文字中的 [ 建议转义成 \\[（右括号同理写成 \\]），否则容易提前闭合外层标签")

    # 9. 括号平衡
    depth = 0
    for idx, ch in enumerate(content):
        if _escaped(content, idx):
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth < 0:
                err(line_of(idx), "多余的 ] —— 普通文字中的中括号必须写成 \\[ 和 \\]")
                depth = 0
    if depth > 0:
        err(len(lines), f"有 {depth} 个 [ 没有闭合 —— 普通文字中的中括号必须写成 \\[ 和 \\]")

    issues.sort(key=lambda x: (x[1], x[0]))
    return issues


def split_params(params):
    """按顶层逗号切分参数，保留 link/"a,b" 中的逗号。"""
    if not params:
        return []
    out, buf, in_q = [], "", False
    for c in params:
        if c == '"':
            in_q = not in_q
            buf += c
        elif c == "," and not in_q:
            out.append(buf.strip())
            buf = ""
        else:
            buf += c
    if buf.strip():
        out.append(buf.strip())
    return [p for p in out if p]


# ---------------------------------------------------------------- 命令


def read_content(args):
    if args.file == "-":
        return sys.stdin.read()
    with open(args.file, encoding="utf-8") as f:
        return f.read()


def cmd_folders(a):
    d = api("GET", "/decks/folders")
    for f in d.get("folders", []):
        print(f"{f['id']}  {f.get('name', '')}  ({len(f.get('items', []))} 项)")


def cmd_decks(a):
    d = api("GET", "/decks", {"offset": a.offset, "limit": a.limit, "folder_id": a.folder})
    print(f"共 {d.get('total')} 个牌组")
    for x in d.get("decks", []):
        print(f"{x['id']}\n    {x['name']}  卡片 {x['card_count']}  章节 {x['chapter_count']}  更新 {x['updated_time'][:10]}")


def cmd_chapters(a):
    d = api("GET", f"/decks/{urllib.parse.quote(a.deck, safe='')}/chapters", {"with_cards": "false"})
    for c in d.get("chapters", []):
        print(f"{c['id']}\n    {c['name']}  卡片 {len(c.get('card_ids', []))}")


def cmd_cards(a):
    d = api("GET", f"/decks/{urllib.parse.quote(a.deck, safe='')}/chapters", {"with_cards": "true"})
    for c in d.get("cards", []):
        if a.chapter and c["id"] not in _chapter_card_ids(d, a.chapter):
            continue
        if a.json:
            print(json.dumps(c, ensure_ascii=False))
        else:
            first = c["content"].split("\n")[0][:70]
            print(f"{c['id']}  root={c.get('root_id')}\n    {first}")


def _chapter_card_ids(d, chapter):
    for c in d.get("chapters", []):
        if c["id"] == chapter:
            return set(c.get("card_ids", []))
    return set()


def cmd_card(a):
    d = api("GET", f"/decks/{urllib.parse.quote(a.deck, safe='')}/cards/{urllib.parse.quote(a.card, safe='')}")
    c = d["card"]
    if a.json:
        print(json.dumps(c, ensure_ascii=False, indent=2))
    else:
        print(c["content"])


def cmd_create(a):
    content = read_content(a)
    issues = lint(content, a.file)
    errors = [x for x in issues if x[0] == "ERROR"]
    if issues:
        print_issues(issues, a.file)
    if errors and not a.force:
        sys.exit("\n发现语法错误，已中止。修正后重试，或加 --force 强行提交。")
    # 注意：OpenAPI 把 deck/chapter 标为 body 必填，但服务端会把它们当作 24 位 ObjectId 校验，
    # 传开放 ID 会报 "deck not a valid ObjectId"。实测必须省略，牌组和章节由路径参数决定。
    body = {"card": {"content": content, "grammar_version": GRAMMAR_VERSION}}
    if a.order is not None:
        body["order"] = a.order
    path = f"/decks/{urllib.parse.quote(a.deck, safe='')}/chapters/{urllib.parse.quote(a.chapter, safe='')}/cards"
    if a.dry_run:
        print("POST " + BASE + path)
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return
    d = api("POST", path, body=body)
    c = d["card"]
    print(f"已创建卡片 {c['id']}\n  root_id: {c.get('root_id')}")


def cmd_update(a):
    content = read_content(a)
    issues = lint(content, a.file)
    errors = [x for x in issues if x[0] == "ERROR"]
    if issues:
        print_issues(issues, a.file)
    if errors and not a.force:
        sys.exit("\n发现语法错误，已中止。修正后重试，或加 --force 强行提交。")
    body = {
        "deck_id": a.deck,
        "card_id": a.card,
        "card": {"content": content, "grammar_version": GRAMMAR_VERSION},
    }
    d = api("POST", f"/decks/{urllib.parse.quote(a.deck, safe='')}/cards/{urllib.parse.quote(a.card, safe='')}", body=body)
    print(f"已更新卡片 {d['card']['id']}  revision={d['card'].get('revision')}")


def cmd_upload(a):
    with open(a.path, "rb") as f:
        blob = f.read()
    mime = a.mime or mimetypes.guess_type(a.path)[0] or "application/octet-stream"
    if a.path.endswith(".msk1"):
        mime = "markji/mask"
    d = api_multipart("/files", {"deck_id": a.deck}, os.path.basename(a.path), blob, mime)
    f = d["file"]
    print(f"file.id: {f['id']}")
    print(f"  mime: {f.get('mime')}  info: {json.dumps(f.get('info', {}), ensure_ascii=False)}")
    print(f"  url（临时，{f.get('expire_time')} 过期，不要写进卡片）: {f.get('url')}")


def cmd_query_files(a):
    d = api("POST", "/files/query", body={"ids": a.ids, "expires": a.expires})
    print(json.dumps(d.get("files", []), ensure_ascii=False, indent=2))


def cmd_verify(a):
    """批量校验一个章节：卡片数、顺序、媒体引用、逐张语法。"""
    d = api("GET", f"/decks/{urllib.parse.quote(a.deck, safe='')}/chapters/{urllib.parse.quote(a.chapter, safe='')}",
            {"with_cards": "true"})
    ch = d.get("chapter") or {}
    cards = {c["id"]: c for c in d.get("cards", [])}
    order = ch.get("card_ids", [])

    print(f"章节：{ch.get('name')}  卡片 {len(order)} 张  revision={ch.get('revision')}")
    missing = [cid for cid in order if cid not in cards]
    if missing:
        print(f"✗ 章节引用了 {len(missing)} 张取不到的卡片：{missing[:3]}")
    extra = [cid for cid in cards if cid not in order]
    if extra:
        print(f"! 有 {len(extra)} 张卡不在章节顺序表中：{extra[:3]}")

    bad = 0
    for i, cid in enumerate(order):
        c = cards.get(cid)
        if not c:
            continue
        issues = lint(c["content"])
        errs = [x for x in issues if x[0] == "ERROR"]
        # 卡片语法里引用的媒体 ID 应当都出现在服务端解析出的 files 数组中
        refs = set(re.findall(r"\[(?:Pic|Audio)#[^#\]]*?(?:ID|MID)/([^,#\]]+)", c["content"]))
        got = {f["id"] for f in c.get("files", [])}
        unresolved = refs - got
        head = c["content"].split("\n")[0][:52]
        flags = []
        if errs:
            flags.append(f"{len(errs)} 个语法错误")
        if unresolved:
            flags.append(f"未解析媒体 {sorted(unresolved)}")
        mark = "✗" if flags else "✓"
        if flags:
            bad += 1
        print(f"{mark} [{i}] {head}" + (f"   ← {'；'.join(flags)}" if flags else ""))
        if a.verbose and errs:
            for _, ln, msg in errs[:5]:
                print(f"      L{ln}: {msg}")
        if refs:
            print(f"      媒体 {len(got)}/{len(refs)} 已关联: {sorted(got) or '无'}")

    print(f"\n{len(order) - bad}/{len(order)} 张通过")
    sys.exit(1 if bad or missing else 0)


def print_issues(issues, path):
    for level, ln, msg in issues:
        mark = "✗" if level == "ERROR" else "!"
        print(f"{mark} {path}:{ln}: {msg}", file=sys.stderr)
    n_err = sum(1 for x in issues if x[0] == "ERROR")
    n_warn = len(issues) - n_err
    print(f"— {n_err} 个错误，{n_warn} 个警告", file=sys.stderr)


def cmd_lint(a):
    ok = True
    for path in a.files:
        content = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        issues = lint(content, path)
        if issues:
            print_issues(issues, path)
            if any(x[0] == "ERROR" for x in issues):
                ok = False
        else:
            print(f"✓ {path}: 语法检查通过")
    sys.exit(0 if ok else 1)


def cmd_whoami(a):
    d = api("GET", "/decks", {"limit": 1})
    print(f"凭证有效 ✓  可访问 {d.get('total')} 个墨墨记忆卡牌组")


def main():
    p = argparse.ArgumentParser(description="墨墨记忆卡 (Markji) 开放 API 客户端")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami", help="验证凭证").set_defaults(fn=cmd_whoami)
    sub.add_parser("folders", help="列出文件夹").set_defaults(fn=cmd_folders)

    s = sub.add_parser("decks", help="列出牌组")
    s.add_argument("--offset", type=int)
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--folder")
    s.set_defaults(fn=cmd_decks)

    s = sub.add_parser("chapters", help="列出某牌组的章节")
    s.add_argument("deck")
    s.set_defaults(fn=cmd_chapters)

    s = sub.add_parser("cards", help="列出某牌组的卡片")
    s.add_argument("deck")
    s.add_argument("--chapter")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_cards)

    s = sub.add_parser("card", help="读取单张卡片内容")
    s.add_argument("deck")
    s.add_argument("card")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_card)

    s = sub.add_parser("create", help="在章节中创建卡片（提交前自动校验语法）")
    s.add_argument("deck")
    s.add_argument("chapter")
    s.add_argument("--file", required=True, help="卡片内容文件，- 表示标准输入")
    s.add_argument("--order", type=int)
    s.add_argument("--force", action="store_true", help="即使有语法错误也提交")
    s.add_argument("--dry-run", action="store_true", help="只校验并打印将要发送的请求，不写入")
    s.set_defaults(fn=cmd_create)

    s = sub.add_parser("update", help="更新卡片内容（提交前自动校验语法）")
    s.add_argument("deck")
    s.add_argument("card")
    s.add_argument("--file", required=True)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_update)

    s = sub.add_parser("upload", help="上传图片 / 音频 / .msk1 遮罩，返回 file.id")
    s.add_argument("path")
    s.add_argument("--deck")
    s.add_argument("--mime")
    s.set_defaults(fn=cmd_upload)

    s = sub.add_parser("query-files", help="按 file.id 查询媒体")
    s.add_argument("ids", nargs="+")
    s.add_argument("--expires", type=int)
    s.set_defaults(fn=cmd_query_files)

    s = sub.add_parser("verify", help="批量校验一个章节：卡片数、顺序、媒体关联、逐张语法")
    s.add_argument("deck")
    s.add_argument("chapter")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("lint", help="离线校验制卡语法")
    s.add_argument("files", nargs="+", help="内容文件，- 表示标准输入")
    s.set_defaults(fn=cmd_lint)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
