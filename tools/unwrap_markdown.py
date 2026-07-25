#!/usr/bin/env python3
"""Unwrap wrapped Markdown lines into long-line format.

This converts line-wrapped Markdown paragraphs, blockquotes, and list items
into single long lines for pasting into rendering environments (such as
GitHub release descriptions) that treat soft line breaks as hard breaks.
"""

import re
import sys

HEADER_RE = re.compile(r"^\s*#+\s")
LIST_MARKER_RE = re.compile(r"^(\s*)([-*+]|\d+[\.\)])\s+(.*)$")
BLOCKQUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
HR_RE = re.compile(r"^\s*([-*_]\s*){3,}\s*$")
CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def unwrap_markdown(text):
    """Return text with line-wrapped Markdown blocks joined into long lines."""
    lines = text.splitlines()
    output = []

    in_code_block = False
    fence_str = ""

    buf_type = None
    buf_indent = ""
    buf_prefix = ""
    buf_parts = []

    def flush_buffer():
        nonlocal buf_type, buf_indent, buf_prefix, buf_parts
        if not buf_type or not buf_parts:
            buf_type = None
            buf_parts = []
            return

        joined = " ".join(buf_parts)
        if buf_type == "PARAGRAPH":
            output.append(joined)
        elif buf_type == "BLOCKQUOTE":
            output.append(f"{buf_prefix}{joined}")
        elif buf_type == "LIST_ITEM":
            output.append(f"{buf_indent}{buf_prefix}{joined}")

        buf_type = None
        buf_indent = ""
        buf_prefix = ""
        buf_parts = []

    for line in lines:
        fence_match = CODE_FENCE_RE.match(line)
        if fence_match:
            if in_code_block:
                marker = fence_match.group(1)
                if marker == fence_str:
                    in_code_block = False
                    fence_str = ""
                    output.append(line)
                    continue
            else:
                flush_buffer()
                in_code_block = True
                fence_str = fence_match.group(1)
                output.append(line)
                continue

        if in_code_block:
            output.append(line)
            continue

        stripped = line.strip()

        if not stripped:
            flush_buffer()
            output.append("")
            continue

        if HEADER_RE.match(line):
            flush_buffer()
            output.append(line)
            continue

        if HR_RE.match(line):
            flush_buffer()
            output.append(line)
            continue

        if "|" in line:
            flush_buffer()
            output.append(line)
            continue

        bq_match = BLOCKQUOTE_RE.match(line)
        if bq_match:
            content = bq_match.group(1).strip()
            if not content:
                flush_buffer()
                output.append(">")
                continue

            if buf_type == "BLOCKQUOTE":
                buf_parts.append(content)
            else:
                flush_buffer()
                buf_type = "BLOCKQUOTE"
                buf_prefix = "> "
                buf_parts = [content]
            continue

        list_match = LIST_MARKER_RE.match(line)
        if list_match:
            flush_buffer()
            indent, marker, content = list_match.groups()
            buf_type = "LIST_ITEM"
            buf_indent = indent
            buf_prefix = f"{marker} "
            buf_parts = [content.strip()]
            continue

        if buf_type in ("PARAGRAPH", "LIST_ITEM"):
            buf_parts.append(stripped)
        else:
            flush_buffer()
            buf_type = "PARAGRAPH"
            buf_parts = [stripped]

    flush_buffer()
    return "\n".join(output)


def main():
    if len(sys.argv) > 1 and sys.argv[1] not in ("-", "--help", "-h"):
        filepath = sys.argv[1]
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    elif len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        print("Usage: unwrap_markdown.py [FILE]")
        print("Unwrap line-wrapped Markdown text into long lines format.")
        sys.exit(0)
    else:
        content = sys.stdin.read()

    result = unwrap_markdown(content)
    print(result)


if __name__ == "__main__":
    main()
