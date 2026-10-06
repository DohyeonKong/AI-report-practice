# -*- coding: utf-8 -*-
"""설문 CSV의 개인정보를 가린 사본을 만든다. 원본은 수정하지 않고, 화면에는 처리 건수만 출력한다.

사용법:
    python mask_pii.py <원본.csv> <출력폴더 또는 출력파일.csv>
예:
    python .agents/skills/collect-data/scripts/mask_pii.py "resources/원본/06_비교과_만족도조사_원자료.csv" "resources/취합/"
"""
import csv
import os
import re
import sys

DROP_COLS = {"학번", "성명", "이름", "연락처", "전화번호", "이메일"}
TEXT_HINTS = ("의견", "서술", "기타", "코멘트")
PATTERNS = [
    ("연락처", re.compile(r"01[016789]-?\d{3,4}-?\d{4}")),
    ("이메일", re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")),
    ("학번", re.compile(r"(?<!\d)(?:19|20)\d{5,8}(?!\d)")),
]
INTRO = re.compile(r"\S+(?:학과|학부|전공) \[학번\] \S+입니다\.?\s*")


def main(src, dst):
    if os.path.isdir(dst) or dst.endswith(("/", "\\")):
        os.makedirs(dst, exist_ok=True)
        base = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(dst, f"{base}_masked.csv")
    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    header = list(rows[0].keys()) if rows else []
    keep = [c for c in header if c not in DROP_COLS]
    text_cols = [c for c in keep if any(h in c for h in TEXT_HINTS)]

    counts = {name: 0 for name, _ in PATTERNS}
    counts["자기소개 문장"] = 0
    for r in rows:
        for c in text_cols:
            t = r.get(c) or ""
            for name, pat in PATTERNS:
                t, n = pat.subn(f"[{name}]", t)
                counts[name] += n
            t, n = INTRO.subn("[자기소개 삭제] ", t)
            counts["자기소개 문장"] += n
            r[c] = t.strip()

    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keep, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    left = 0
    for r in rows:
        for c in text_cols:
            clean = re.sub(r"\[(연락처|이메일|학번)\]", "", r[c])
            left += sum(len(p.findall(clean)) for _, p in PATTERNS)

    print("저장:", dst)
    print("삭제한 열:", [c for c in header if c in DROP_COLS])
    print("검사한 자유서술 열:", text_cols)
    print("치환 건수:", counts)
    print("잔여 패턴:", left)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
