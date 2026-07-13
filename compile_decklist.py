#!/usr/bin/env python3
"""
compile_decklist.py

Reads a cube checklist markdown file (as produced by cube_checklist.py),
validates that every section's actual line-item count matches the count
declared in its heading (e.g. "### 3 (x5)" must have exactly 5 "- " lines
beneath it, summed all the way up to "# White (x68)"), and compiles every
card name into an MTGO-style decklist (one "1 <Card Name>" line per card
slot).

Every slot must be filled in before compiling. A blank "- " line (outside
of a Keywords section) is treated as an error, reported with its exact
line number, so nothing gets silently skipped.

"## Keywords" subsections are informational-only (a vertical slice over
cards already counted elsewhere) and are excluded from both count
validation and card-name extraction, to avoid double-counting.

Usage:
    python3 compile_decklist.py <input.md> [output.txt]

If output.txt is omitted, the output is written next to the input file
with the same base name and a .txt extension.
"""

import argparse
import re
import sys
from pathlib import Path

HEADING_RE = re.compile(r"^(#+)\s*(.+?)\s*$")
ITEM_RE = re.compile(r"^-\s?(.*)$")
COUNT_RE = re.compile(r"\(x(\d+)\)\s*$")


class Node:
    def __init__(self, level, title, count, path):
        self.level = level
        self.title = title
        self.count = count          # declared count from "(xN)", or None
        self.path = path            # human-readable path for error messages
        self.children = []
        self.items = []             # (line_number, raw_text) for direct items
        self.is_keywords = title.strip() == "Keywords"

    def effective_actual(self):
        """
        Actual slot count for this node -- Python does the counting, never
        estimated. Keywords subtrees are informational only and contribute
        nothing to any parent's total.
        """
        if self.is_keywords:
            return 0
        if self.children:
            return sum(c.effective_actual() for c in self.children)
        return len(self.items)

    def collect_card_lines(self, out):
        """Collect '1 <Card Name>' lines from every leaf item, skipping
        Keywords subtrees entirely. Assumes collect_blank_lines already
        confirmed there are no blank slots."""
        if self.is_keywords:
            return
        if self.children:
            for c in self.children:
                c.collect_card_lines(out)
            return
        for _line_no, raw in self.items:
            out.append(f"1 {raw.strip()}")

    def collect_mismatches(self, out):
        if self.is_keywords:
            return
        if self.count is not None:
            actual = self.effective_actual()
            if actual != self.count:
                out.append((self.path, self.count, actual))
        for c in self.children:
            c.collect_mismatches(out)

    def collect_blank_lines(self, out):
        """Collect (line_number, path) for every blank '- ' slot, skipping
        Keywords subtrees entirely."""
        if self.is_keywords:
            return
        if self.children:
            for c in self.children:
                c.collect_blank_lines(out)
            return
        for line_no, raw in self.items:
            if not raw.strip():
                out.append((line_no, self.path))


def parse_markdown(text):
    root = Node(0, "ROOT", None, "ROOT")
    stack = [root]

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        heading_match = HEADING_RE.match(raw_line)
        if heading_match:
            level = len(heading_match.group(1))
            title_full = heading_match.group(2)
            count_match = COUNT_RE.search(title_full)
            count = int(count_match.group(1)) if count_match else None

            while stack[-1].level >= level:
                stack.pop()

            parent = stack[-1]
            path = title_full if parent is root else f"{parent.path} > {title_full}"
            node = Node(level, title_full, count, path)
            parent.children.append(node)
            stack.append(node)
            continue

        item_match = ITEM_RE.match(raw_line)
        if item_match:
            stack[-1].items.append((line_no, item_match.group(1)))

    return root


def resolve_output_path(input_path, output_arg):
    if output_arg:
        return Path(output_arg)
    return Path(input_path).with_suffix(".txt")


def main():
    parser = argparse.ArgumentParser(
        description="Compile a cube checklist markdown file into an MTGO-style decklist."
    )
    parser.add_argument("input_path", help="Path to the cube checklist markdown file.")
    parser.add_argument(
        "output_path",
        nargs="?",
        default=None,
        help="Path to write the .txt decklist to. Defaults to the input filename with a .txt extension.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_path)
    if not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding="utf-8")
    root = parse_markdown(text)

    mismatches = []
    root.collect_mismatches(mismatches)

    if mismatches:
        print("Section count validation failed:", file=sys.stderr)
        for path, expected, actual in mismatches:
            print(f"  {path} -- Expected: {expected}, Actual: {actual}", file=sys.stderr)
        sys.exit(1)

    blanks = []
    root.collect_blank_lines(blanks)

    if blanks:
        print("Found blank (unfilled) slots:", file=sys.stderr)
        for line_no, path in blanks:
            print(f"  Line {line_no}: {path}", file=sys.stderr)
        sys.exit(1)

    card_lines = []
    root.collect_card_lines(card_lines)

    output_path = resolve_output_path(input_path, args.output_path)
    output_path.write_text("\n".join(card_lines) + ("\n" if card_lines else ""), encoding="utf-8")

    print(f"Validated OK. Wrote {len(card_lines)} card lines to {output_path}")


if __name__ == "__main__":
    main()
