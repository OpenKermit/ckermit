#!/usr/bin/env python3
"""Generate a full HELP/INTRO reference for C-Kermit.

This drives a built binary rather than parsing the C help text
directly, so the output matches exactly what this build's users see.

The keytab tables in the C source are still used, but only to get the
list of topic names to ask about, and to work out which names are
synonyms of which. Usage:

    make [platform-appropriate arguments]
    python3 tools/gen_help_reference.py > doc/help-reference.md
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WERMIT = REPO / "wermit"

# Each table: (source file, array name, invocation prefix, section title)
TABLES = [
    ("ckuusr.c", "cmdtab", "", "Commands"),
    ("ckuusr.c", "prmtab", "set ", "SET/SHOW Parameters"),
    ("ckuusr.c", "remcmd", "remote ", "REMOTE Subcommands"),
    ("ckuus7.c", "fctab", "file ", "FILE Subcommands"),
    ("ckuus4.c", "fnctab", "function ", "Functions"),
]

# Commands whose real content is their own output, not "help X".
# (MANUAL is deliberately excluded: it shells out to the system "man"
# command instead of printing text here.)
CONTENT_COMMANDS = ["intro", "news", "license", "support"]

ENTRY_RE = re.compile(
    r'\{\s*"((?:[^"\\]|\\.)*)"\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*'
    r'([A-Za-z0-9_|]*)\s*\}'
)

FAILURE_MARKERS = [
    "Sorry, that is not a help topic",
    "No keywords match",
    "?Ambiguous",
    "?Invalid",
    "Syntax error",
    "?Not a valid command or token",
]


def extract_table(filename, arrayname):
    """Return a list of (name, token, flags) in source order."""
    text = (REPO / filename).read_text()
    start_re = re.compile(
        r'^struct keytab %s\[\]\s*=\s*\{' % re.escape(arrayname), re.M
    )
    m = start_re.search(text)
    if not m:
        sys.exit("could not find array %s in %s" % (arrayname, filename))
    body_start = m.end()
    end = text.index("\n};", body_start)
    body = text[body_start:end]
    return ENTRY_RE.findall(body)


def group_entries(entries):
    """Group entries by token, dropping XXNOTAV placeholders.

    Every name that shares a token has identical help text, since the
    help dispatcher switches on the token, not the name. So each token
    group gets exactly one canonical name; every other name in the
    group is recorded as a synonym of the canonical.

    Returns an ordered list of (canonical, [synonyms...]).
    """
    order = []
    groups = {}
    for name, token, flags in entries:
        if token == "XXNOTAV":
            continue
        if token not in groups:
            groups[token] = []
            order.append(token)
        groups[token].append((name, flags))

    result = []
    for token in order:
        rows = groups[token]
        unique = []
        seen = {}
        for name, flags in rows:
            key = name.lower()
            visible = "CM_INV" not in flags.split("|")
            if key not in seen:
                seen[key] = len(unique)
                unique.append([name, visible])
            elif visible:
                unique[seen[key]][1] = True

        # Punctuation-only entries ("{", "!", "@", "#", ...) are
        # single-character script syntax shortcuts, not real help
        # topics, and can't be sensibly queried or cross-referenced.
        # If a token is nothing but those, drop the whole group.
        nameable = [n for n, v in unique if re.match(r'^\w', n)]
        if not nameable:
            continue

        visible_nameable = [
            n for n, v in unique if v and re.match(r'^\w', n)
        ]
        pool = visible_nameable or nameable
        canonical = min(pool, key=str.lower)

        synonyms = [n for n, _ in unique if n.lower() != canonical.lower()]
        result.append((canonical, synonyms))
    return result


def expand_group(canonical, synonyms, prefix, title):
    """Turn one (canonical, synonyms) group into render records.

    Returns one 'full' record (the real help text goes here) followed
    by one 'synonym' record per nameable synonym, each just pointing
    back at the canonical entry. Punctuation-only synonyms (e.g. "!"
    for PUSH) are kept in the full record's synonym list but don't get
    their own stub, for the same reason they can't be canonical.
    """
    records = [{
        "kind": "full",
        "name": canonical,
        "prefix": prefix,
        "title": title,
        "synonyms": synonyms,
        "marker": "%s:%s" % (title, canonical),
    }]
    for syn in synonyms:
        if re.match(r'^\w', syn):
            records.append({
                "kind": "synonym",
                "name": syn,
                "prefix": prefix,
                "title": title,
                "target": canonical,
            })
    return records


def build_script(groups_by_table):
    lines = [
        "set command more-prompting off",
        "set take error off",
    ]
    for cmd in CONTENT_COMMANDS:
        lines.append("echo ===CONTENT:%s===" % cmd)
        lines.append(cmd)
    for _, _, prefix, title, groups in groups_by_table:
        for canonical, _ in groups:
            lines.append("echo ===%s:%s===" % (title, canonical))
            lines.append("help %s%s" % (prefix, canonical))
    lines.append("quit")
    return "\n".join(lines) + "\n"


def run_script(script_text):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ksc", delete=False
    ) as f:
        f.write(script_text)
        scriptfile = f.name
    try:
        proc = subprocess.run(
            [str(WERMIT), scriptfile, "-H", "-Y", "-Q"],
            capture_output=True, text=True, timeout=120,
        )
        return proc.stdout
    finally:
        Path(scriptfile).unlink()


def split_output(output):
    """Return {marker: text} from ===marker=== delimited output."""
    parts = re.split(r'^===(.*)===\s*$', output, flags=re.M)
    # parts[0] is preamble before first marker (banner etc.), discard.
    result = {}
    for i in range(1, len(parts), 2):
        marker = parts[i]
        body = parts[i + 1].strip("\n")
        result[marker] = body
    return result


def is_failure(text):
    if not text.strip():
        return True
    return any(marker in text for marker in FAILURE_MARKERS)


def heading(prefix, name):
    return "%s%s" % (prefix.upper(), name.upper())


def slug(text):
    """Approximate the GitHub heading-anchor algorithm."""
    s = re.sub(r'[^a-z0-9\s-]', '', text.lower())
    return re.sub(r'\s+', '-', s.strip())


def assemble_records(groups_by_table, texts):
    """Expand groups into render records, now that help text is known.

    A group whose canonical topic's text failed (unavailable in this
    build) is dropped entirely, synonyms and all, rather than leaving
    behind synonym stubs that point at a heading which was never
    rendered.
    """
    records_by_table = []
    for filename, arrayname, prefix, title, groups in groups_by_table:
        records = []
        for canonical, synonyms in groups:
            marker = "%s:%s" % (title, canonical)
            text = texts.get(marker)
            if text is None or is_failure(text):
                continue
            records.extend(expand_group(canonical, synonyms, prefix, title))
        if title == "Commands":
            records.sort(key=lambda r: r["name"].lower())
        records_by_table.append((filename, arrayname, prefix, title,
                                  records))
    return records_by_table


def render_markdown(records_by_table, texts):
    out = []
    out.append("# C-Kermit Help Reference")
    out.append("")
    out.append(
        "Generated from a running kermit build by "
        "`tools/gen_help_reference.py`. Do not edit by hand. "
    )
    out.append("")

    out.append("## Introductory Material")
    out.append("")
    for cmd in CONTENT_COMMANDS:
        text = texts.get("CONTENT:%s" % cmd)
        if text is None or is_failure(text):
            continue
        out.append("### %s" % cmd.upper())
        out.append("")
        out.append("```")
        out.append(text)
        out.append("```")
        out.append("")

    for _, _, prefix, title, records in records_by_table:
        out.append("## %s" % title)
        out.append("")
        for r in records:
            head = heading(prefix, r["name"])
            if r["kind"] == "synonym":
                target = heading(prefix, r["target"])
                out.append("### %s" % head)
                out.append("")
                out.append(
                    "Synonym for [%s](#%s)." % (target, slug(target))
                )
                out.append("")
                continue

            text = texts.get(r["marker"])
            if text is None or is_failure(text):
                continue
            out.append("### %s" % head)
            out.append("")
            synonyms = r["synonyms"]
            if synonyms:
                out.append(
                    "Synonym%s: %s" % (
                        "s" if len(synonyms) > 1 else "",
                        ", ".join(s.upper() for s in synonyms),
                    )
                )
                out.append("")
            out.append("```")
            out.append(text)
            out.append("```")
            out.append("")

    return "\n".join(out)


def main():
    if not WERMIT.exists():
        sys.exit(
            "wermit binary not found at %s; run make first"
            % WERMIT
        )

    groups_by_table = []
    for filename, arrayname, prefix, title in TABLES:
        entries = extract_table(filename, arrayname)
        groups = group_entries(entries)
        groups_by_table.append((filename, arrayname, prefix, title, groups))

    script_text = build_script(groups_by_table)
    output = run_script(script_text)
    texts = split_output(output)

    records_by_table = assemble_records(groups_by_table, texts)
    print(render_markdown(records_by_table, texts))


if __name__ == "__main__":
    main()
