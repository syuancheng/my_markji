# -*- coding: utf-8 -*-
"""
批量制卡生成脚本骨架。复制后按需增删 add(...) 调用。

设计目的：结构性避开两个反复出现的坑——
1. 用 list + "".join(parts) 拼内容，不用 "+" 链式拼接，
   不会因为漏写一个 "+" 导致下游 SyntaxError。
2. note() 和 ex() 分开：note() 是纯文字灰色注释，ex() 是可能包含
   hl() 高亮的例句/说明——因为 [T#...] 不能嵌套 [T#...]，
   灰色包高亮会踩 Markji 语法的嵌套白名单。
"""

cards = []


def add(title_zh, parts):
    """title_zh: 卡片标题（正面）；parts: 组成背面内容的字符串片段列表。"""
    cards.append((title_zh, "".join(parts)))


def F(n, text):
    """挖空。同一组挖空用同一个 n。"""
    return "[F#" + str(n) + "#" + text + "]"


def hl(text):
    """行内高亮（加粗+蓝），标可迁移的目标表达/结构。"""
    return "[T#B,!1a73e8#" + text + "]"


def note(text):
    """纯文字灰色补充说明，内容里不能再包 hl() 等标签。"""
    return "[P#L#[T#!888888#" + text + "]]"


def ex(text):
    """例句/说明行，内容可以包含 hl()（不套灰色外层，避免 T 嵌 T）。"""
    return "[P#L#" + text + "]"


def title(zh):
    return "[P#H1,center#[T#B#" + zh + "]]\n---\n"


# 示例：一张规则/概念卡（挖空回忆），一张操练卡（中英对照）
add("示例·规则卡", [
    title("这是规则卡的标题"),
    "正文里可以用 " + F(1, "挖空") + " 来考察关键概念。",
])

add("示例·操练卡", [
    title("中文提示句"),
    "This is the English answer with a " + hl("highlighted structure") + ".",
    "\n\n",
    "[T#B,!78909c#📌 重点]\n",
    ex("[T#B#highlighted structure] — [T#!888888#中文释义]"),
])

if __name__ == "__main__":
    print(len(cards), "cards")
    out_lines = [content for _, content in cards]
    with open("/tmp/batch_output.txt", "w", encoding="utf-8") as f:
        f.write("\n@@@\n".join(out_lines))
    with open("/tmp/batch_titles.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(t for t, _ in cards))
    print("written to /tmp/batch_output.txt")
