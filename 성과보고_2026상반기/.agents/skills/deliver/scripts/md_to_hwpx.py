# -*- coding: utf-8 -*-
"""보고서 Markdown을 결재용 한글 문서(hwpx, A4, 함초롬바탕)로 변환한다.

지원: # 제목, ## / ### 소제목, 문단, **굵게**, 표(| a | b |), 그림(![설명](경로)), - 목록, 1. 목록
사용법:
    python md_to_hwpx.py <입력.md> <출력.hwpx>
필요: Python 3.10 이상, pip install python-hwpx
"""
import os
import re
import sys

from hwpx import HwpxDocument

BODY_PT = 10.5
TABLE_PT = 9.5
HEADING_PT = {1: 16, 2: 13, 3: 11.5}
PAGE_MM = {"width_mm": 210, "height_mm": 297, "margin_left_mm": 20, "margin_right_mm": 20,
           "margin_top_mm": 20, "margin_bottom_mm": 20}
CONTENT_WIDTH = round(170 * 7200 / 25.4)  # HWPUNIT (1in = 7200)


class Writer:
    def __init__(self):
        self.doc = HwpxDocument.new()
        self.doc.page.setup(**PAGE_MM)
        self._first = self.doc.paragraphs[0]  # 빈 첫 문단(구역 설정 포함)을 첫 내용에 쓴다

    def paragraph(self, text="", size=BODY_PT, bold=False, align=None, indent_mm=0):
        if self._first is not None:
            p, self._first = self._first, None
        else:
            p = self.doc.add_paragraph("", include_run=False, inherit_style=False)
        add_inline(p, text, size, bold)
        fmt = {}
        if align:
            fmt["alignment"] = align
        if indent_mm:
            fmt["indent_left_mm"] = indent_mm
        if fmt:
            self.doc.styles.apply_paragraph_format(paragraphs=[p], **fmt)
        return p

    def table(self, rows, header_bold=True):
        if self._first is not None:
            self.paragraph()
        ncol = max(len(r) for r in rows)
        t = self.doc.add_table(len(rows), ncol, width=CONTENT_WIDTH)
        for r_i, r in enumerate(rows):
            for c_i in range(ncol):
                cell = t.cell(r_i, c_i)
                p = cell.paragraphs[0]
                p.clear_text()
                add_inline(p, r[c_i] if c_i < len(r) else "", TABLE_PT, header_bold and r_i == 0)
        return t

    def picture(self, path):
        if self._first is not None:
            self.paragraph()
        ext = os.path.splitext(path)[1].lstrip(".").lower()
        with open(path, "rb") as f:
            data = f.read()
        w, h = image_size(data)
        width_mm = 160
        self.doc.add_picture(data, ext, width_mm=width_mm,
                             height_mm=width_mm * h / w if w and h else None, align="CENTER")

    def save(self, dst):
        self.doc.save_to_path(dst)


def add_inline(par, text, size, bold=False):
    parts = [p for p in re.split(r"(\*\*[^*]+\*\*)", text) if p]
    if not parts:
        par.add_run("", size=size, bold=bold)
    for part in parts:
        b = part.startswith("**") and part.endswith("**")
        par.add_run(part[2:-2] if b else part, size=size, bold=bold or b)


def image_size(data):
    """PNG·JPEG 픽셀 크기(가로, 세로). 모르면 (0, 0)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                break
            marker, seg = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2):
                return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
            i += 2 + seg
    return 0, 0


def is_table_line(line):
    return line.strip().startswith("|") and line.strip().endswith("|")


def parse_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def main(src, dst):
    base_dir = os.path.dirname(os.path.abspath(src))
    lines = open(src, encoding="utf-8").read().split("\n")
    lines = [ln for ln in lines if not re.match(r"^\s*<!--.*-->\s*$", ln)]
    w = Writer()

    missing = []
    i = 0
    while i < len(lines):
        ln = re.sub(r"<!--.*?-->", "", lines[i]).rstrip()
        if not ln.strip() or ln.strip() == "---":
            i += 1
            continue
        if is_table_line(ln):
            block = []
            while i < len(lines) and is_table_line(lines[i]):
                block.append(re.sub(r"<!--.*?-->", "", lines[i]))
                i += 1
            rows = [parse_row(b) for b in block if not re.match(r"^\|\s*:?-{2,}", b.strip())]
            w.table(rows)
            w.paragraph()
            continue
        m = re.match(r"^!\[(.*?)\]\((.*?)\)", ln.strip())
        if m:
            cands = [os.path.join(base_dir, m.group(2)),
                     os.path.join(base_dir, "..", "초안", m.group(2))]
            path = next((c for c in cands if os.path.exists(c)), None)
            if path:
                w.picture(path)
            else:
                missing.append(m.group(2))
                w.paragraph(f"[그림 없음: {m.group(2)}]")
            i += 1
            continue
        h = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if h:
            level = len(h.group(1))
            w.paragraph(h.group(2), HEADING_PT[level], bold=True,
                        align="CENTER" if level == 1 else None)
            i += 1
            continue
        lead = re.match(r"^(\s*)(.*)$", ln)
        indent = len(lead.group(1).replace("　", "  ")) // 2
        w.paragraph(lead.group(2), indent_mm=5 * indent)
        i += 1
    w.save(dst)
    print("저장:", dst)
    if missing:
        print("경고: 그림을 찾지 못함 →", ", ".join(missing))
        sys.exit(2)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
