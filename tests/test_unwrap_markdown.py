"""Unit tests for tools/unwrap_markdown.py."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.unwrap_markdown import unwrap_markdown


def test_unwrap_paragraph():
    text = (
        "First line of paragraph.\n"
        "Second line of paragraph.\n"
        "Third line.\n"
    )
    expected = (
        "First line of paragraph. Second line of paragraph. Third line."
    )
    assert unwrap_markdown(text) == expected


def test_unwrap_blockquote():
    text = (
        "> First line of quote.\n"
        "> Second line of quote.\n"
        ">\n"
        "> Next blockquote paragraph.\n"
    )
    expected = (
        "> First line of quote. Second line of quote.\n"
        ">\n"
        "> Next blockquote paragraph."
    )
    assert unwrap_markdown(text) == expected


def test_unwrap_list_items():
    text = (
        "- First item header.\n"
        "  Continuation line 1.\n"
        "  Continuation line 2.\n"
        "\n"
        "- Second item.\n"
    )
    expected = (
        "- First item header. Continuation line 1. Continuation line 2.\n"
        "\n"
        "- Second item."
    )
    assert unwrap_markdown(text) == expected


def test_preserve_code_blocks():
    text = (
        "Paragraph before code.\n"
        "\n"
        "```python\n"
        "def foo():\n"
        "    line1 = 1\n"
        "    line2 = 2\n"
        "```\n"
        "\n"
        "Paragraph after code.\n"
    )
    expected = (
        "Paragraph before code.\n"
        "\n"
        "```python\n"
        "def foo():\n"
        "    line1 = 1\n"
        "    line2 = 2\n"
        "```\n"
        "\n"
        "Paragraph after code."
    )
    assert unwrap_markdown(text) == expected
