"""Step 3 of the evaluation: write eval/results.md from the answers and the RAGAS scores.

Besides RAGAS, it computes checks that need no judge LLM:
    retrieval hit@k   one of the k retrieved chunks comes from an expected source page
    citation hit      one of the cited sources is an expected source page
    answered          in-corpus question answered with citations (not "I don't know")
    refused           out-of-corpus question answered with "I don't know"
    language match    answer written in the language of the question

Usage:
    python -X utf8 -m src.evaluation.report
"""
from __future__ import annotations

import csv
import statistics
from collections import Counter
from datetime import date

from ..generation.prompt import detect_lang
from ..ingest.common import ROOT
from .ragas_eval import METRICS, SCORES
from .run_answers import ANSWERS, RUNS, load_answers, load_questions

RESULTS = ROOT / "eval" / "results.md"
BASELINE = RUNS / "phase4_vector"  # frozen copy of the phase 4 run (dense retrieval only)


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "-"


def mean(xs: list[float]) -> str:
    xs = [x for x in xs if x == x]  # drop NaN (judge failed)
    return f"{statistics.mean(xs):.2f}" if xs else "-"


def load_scores(path=SCORES) -> dict[int, dict[str, float]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {int(r["id"]): {m: float(r[m]) if r.get(m) not in (None, "") else float("nan")
                               for m in METRICS} for r in csv.DictReader(f)}


def build_rows(qs: dict, ans: dict, scores: dict) -> list[dict]:
    rows = []
    for i, q in sorted(qs.items()):
        a = ans.get(i)
        if a is None:
            continue
        expected = set(q["source_urls"])
        rows.append({
            **q,
            "a": a,
            "hit": bool(expected & set(a["context_urls"])),
            "cite_hit": bool(expected & set(a["cited_urls"])),
            "lang_ok": (not a["answer"]) or detect_lang(a["answer"]) == q["lang"],
            "s": scores.get(i, {}),
        })
    return rows


def headline(rows: list[dict]) -> dict[str, str]:
    """The numbers compared between runs."""
    inc = [r for r in rows if r["in_corpus"]]
    ooc = [r for r in rows if not r["in_corpus"]]
    scored = [r for r in inc if r["s"]]
    out = {
        "Trả lời được (trong tài liệu)": pct(sum(r["a"]["found"] for r in inc), len(inc)),
        "Nói \"không biết\" đúng (ngoài tài liệu)": pct(sum(not r["a"]["found"] for r in ooc), len(ooc)),
        "Retrieval hit@5": pct(sum(r["hit"] for r in inc), len(inc)),
        "Trích dẫn đúng trang nguồn": pct(sum(r["cite_hit"] for r in inc), len(inc)),
        "Đúng ngôn ngữ": pct(sum(r["lang_ok"] for r in rows), len(rows)),
    }
    for m in METRICS:
        xs = [r["s"][m] for r in scored if r["s"][m] == r["s"][m]]
        out[m] = mean(xs) + (f" (chấm {len(xs)}/{len(inc)})" if len(xs) < len(inc) else "")
    out["Thời gian trung vị"] = f"{statistics.median(r['a']['seconds'] for r in rows):.1f}s"
    return out


def main() -> None:
    qs = {q["id"]: q for q in load_questions()}
    scores = load_scores()
    rows = build_rows(qs, load_answers(), scores)
    inc = [r for r in rows if r["in_corpus"]]
    ooc = [r for r in rows if not r["in_corpus"]]
    secs = [r["a"]["seconds"] for r in rows]

    out = [f"# Kết quả đánh giá / Evaluation results", "",
           f"Chạy ngày {date.today()} trên {len(rows)} câu hỏi ({len(inc)} có trong tài liệu, "
           f"{len(ooc)} ngoài tài liệu; {sum(r['lang'] == 'vi' for r in rows)} tiếng Việt, "
           f"{sum(r['lang'] == 'en' for r in rows)} tiếng Anh). Câu hỏi và đáp án chuẩn: "
           f"[questions.csv](questions.csv). Câu trả lời và đoạn tài liệu lấy về: "
           f"[runs/answers.jsonl](runs/answers.jsonl). Điểm RAGAS từng câu: "
           f"[runs/ragas_scores.csv](runs/ragas_scores.csv).", "",
           "## Tổng quan", "", "| Chỉ số | Kết quả |", "|---|---|"]
    out += [
        f"| Trả lời được (câu có trong tài liệu) | {pct(sum(r['a']['found'] for r in inc), len(inc))} |",
        f"| Nói \"không biết\" đúng (câu ngoài tài liệu) | {pct(sum(not r['a']['found'] for r in ooc), len(ooc))} |",
        f"| Retrieval hit@5 (có trang nguồn đúng trong 5 đoạn lấy về) | {pct(sum(r['hit'] for r in inc), len(inc))} |",
        f"| Trích dẫn đúng trang nguồn | {pct(sum(r['cite_hit'] for r in inc), len(inc))} |",
        f"| Trả lời đúng ngôn ngữ câu hỏi | {pct(sum(r['lang_ok'] for r in rows), len(rows))} |",
        f"| Lỗi (mọi LLM đều thất bại) | {sum(bool(r['a']['error']) for r in rows)} |",
        f"| Thời gian trả lời (trung vị / lâu nhất) | {statistics.median(secs):.1f}s / {max(secs):.1f}s |",
    ]
    if scores:
        scored = [r for r in inc if r["s"]]
        out += ["", f"## RAGAS ({len(scored)} câu có trong tài liệu và đã được trả lời)", "",
                "| Nhóm | n | faithfulness | answer_relevancy | context_precision | context_recall |",
                "|---|---|---|---|---|---|"]
        groups = [("Tất cả", scored),
                  ("Tiếng Việt", [r for r in scored if r["lang"] == "vi"]),
                  ("Tiếng Anh", [r for r in scored if r["lang"] == "en"])]
        groups += [(f"Độ khó: {d}", [r for r in scored if r["difficulty"] == d]) for d in ("easy", "medium", "hard")]
        for name, g in groups:
            if g:
                out.append(f"| {name} | {len(g)} | " + " | ".join(mean([r["s"][m] for r in g]) for m in METRICS) + " |")
        missing = {m: sum(1 for r in scored if r["s"][m] != r["s"][m]) for m in METRICS}
        if any(missing.values()):
            out += ["", "Điểm trống (LLM chấm bị giới hạn lượt, không tính vào trung bình): "
                    + ", ".join(f"{m} {n}/{len(scored)}" for m, n in missing.items()) + "."]
        out += ["", "- **faithfulness**: tỷ lệ ý trong câu trả lời có căn cứ trong đoạn tài liệu lấy về (thấp = bịa).",
                "- **answer_relevancy**: câu trả lời có đúng trọng tâm câu hỏi không.",
                "- **context_precision**: đoạn liên quan có được xếp lên đầu không (so với đáp án chuẩn).",
                "- **context_recall**: tỷ lệ ý của đáp án chuẩn tìm thấy trong các đoạn lấy về."]

    base_answers = BASELINE / ANSWERS.name
    if base_answers.exists():
        base = headline(build_rows(qs, load_answers(base_answers), load_scores(BASELINE / SCORES.name)))
        now = headline(rows)
        out += ["", "## So với Giai đoạn 4 (chỉ tìm theo vector)", "",
                f"Lần chạy Giai đoạn 4 được giữ nguyên ở [runs/{BASELINE.name}/](runs/{BASELINE.name}/results.md). "
                "Model trả lời và model chấm có thể khác giữa hai lần chạy (xem bảng model bên dưới), "
                "nên chênh lệch nhỏ ở điểm RAGAS chưa chắc do retrieval.", "",
                "| Chỉ số | Giai đoạn 4 | Lần này |", "|---|---|---|"]
        out += [f"| {k} | {base.get(k, '-')} | {v} |" for k, v in now.items()]

    models = Counter(r["a"]["model"] or "(none)" for r in rows)
    out += ["", "## Model đã trả lời", "", "| Model | Số câu |", "|---|---|"]
    out += [f"| `{m}` | {n} |" for m, n in models.most_common()]

    bad = [r for r in inc if not r["a"]["found"] or not r["hit"]
           or (r["s"] and min(r["s"].values()) < 0.5)]
    bad += [r for r in ooc if r["a"]["found"]]
    bad += [r for r in rows if not r["lang_ok"] and r not in bad]
    out += ["", "## Câu cần xem lại", ""]
    if not bad:
        out.append("Không có.")
    for r in bad:
        why = []
        if r["in_corpus"] and not r["a"]["found"]:
            why.append("không trả lời được")
        if r["in_corpus"] and not r["hit"]:
            why.append("không lấy được trang nguồn đúng")
        if not r["in_corpus"] and r["a"]["found"]:
            why.append("câu ngoài tài liệu nhưng vẫn trả lời")
        if not r["lang_ok"]:
            why.append("sai ngôn ngữ")
        low = [f"{m} {r['s'][m]:.2f}" for m in METRICS if r["s"] and r["s"][m] == r["s"][m] and r["s"][m] < 0.5]
        if low:
            why.append("điểm thấp: " + ", ".join(low))
        out.append(f"- **#{r['id']}** {r['question']}: {'; '.join(why)}")

    out += ["", "## Từng câu", "",
            "| # | lang | độ khó | trả lời | hit@5 | trích đúng | faith | relev | ctx P | ctx R | giây |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    yn = lambda b: "✅" if b else "❌"
    for r in rows:
        s = r["s"]
        cells = [f"{s[m]:.2f}" if s and s[m] == s[m] else "-" for m in METRICS]
        if r["in_corpus"]:
            first = [yn(r["a"]["found"]), yn(r["hit"]), yn(r["cite_hit"])]
        else:
            first = ["không biết ✅" if not r["a"]["found"] else "trả lời ❌", "-", "-"]
        out.append(f"| {r['id']} | {r['lang']} | {r['difficulty']} | " + " | ".join(first + cells)
                   + f" | {r['a']['seconds']} |")

    RESULTS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out[:20]))
    print("saved", RESULTS)


if __name__ == "__main__":
    main()
