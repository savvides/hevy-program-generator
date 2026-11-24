#!/usr/bin/env python3
"""Render the active readable plan from its program definition; --check detects drift."""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

from estimate_session_time import routine_seconds, routine_time_range
from eval_recovery_interference import cardio_duration_min
from program_loader import load_program

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROGRAM = "programs/starter_full_body_2x.py"

# Fixed plan text. check_writing_standard.py checks these with the program text.
TIME_NOTE = (
    "BLUF: Session times are model estimates for planning.\n"
    "The time includes warmup sets, both sides, work sets, rest and station changes.\n"
    "It does not include the general warmup, travel or cardio.\n"
    "The ±20% planning range is an allowance, not a measured confidence interval.\n"
    "If you finish early, it is not necessary to add sets."
)
PER_SIDE_NOTE = (
    "BLUF: For “per side” sets, do both sides.\n"
    "Record the two sides as one set.\n"
    "Warmup reps are also per side.\n"
    "Do not go above the target RPE."
)
FOOTER_NOTE = (
    "BLUF: The evidence and the coaching policies are in the evidence files.\n"
    "The hours between sessions come from the session start times."
)
TOTAL_SETS_NOTE = "BLUF: The total does not include warmups. For one-side exercises, one set is both sides."
STATIC_NOTES = {"TIME_NOTE": TIME_NOTE, "PER_SIDE_NOTE": PER_SIDE_NOTE, "FOOTER_NOTE": FOOTER_NOTE,
                "TOTAL_SETS_NOTE": TOTAL_SETS_NOTE}


def paragraphs(text: str) -> str:
    """Blank lines separate sections (<p>); single newlines become <br>."""
    sections = [s for s in text.strip().split("\n\n") if s.strip()]
    return "".join("<p>" + escape(s.strip()).replace("\n", "<br>") + "</p>" for s in sections)


def details(text: str) -> str:
    return f'<div class="details"><h3>Evidence and limits</h3>{paragraphs(text)}</div>' if text else ""


def render(program: dict) -> str:
    metadata = program["PROGRAM_METADATA"]
    title = escape(metadata["title"])
    css = (ROOT / "docs/program.css").read_text()
    lines = ["<!doctype html>", '<html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             f"<title>{title}</title><style>{css}</style></head><body><main>",
             f"<h1>{title}</h1>",
             f'<p class="sub">Version {escape(metadata.get("version", "unspecified"))}. '
             f'Model time limit for each lifting session: {metadata["session_time_cap_minutes"]} minutes.</p>',
             paragraphs(metadata.get("description", "")),
             f'<div class="callout">{paragraphs(TIME_NOTE)}</div>',
             paragraphs(PER_SIDE_NOTE),
             '<h2>Week at a glance</h2><table><thead><tr><th>Day</th><th>Session</th><th>Minutes</th></tr></thead><tbody>']
    for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"):
        sessions = []
        for routine in program["ROUTINES"]:
            if routine["day_key"].lower()[:3] == day.lower()[:3]:
                sessions.append((routine["name"], f"{routine_seconds(routine)/60:.0f} nominal"))
        for cardio in program["CARDIO_SCHEDULE"]:
            if cardio["day"].lower()[:3] == day.lower()[:3]:
                sessions.append((cardio["type"], f"{cardio_duration_min(cardio):g}"))
        for name, duration in sessions or [("Rest", "—")]:
            lines.append(f"<tr><td>{day}</td><td>{escape(name)}</td><td>{duration}</td></tr>")
    lines.append("</tbody></table>")
    if metadata.get("general_notes"):
        lines += ["<h2>General rules</h2>", paragraphs(metadata["general_notes"])]
    total_sets = 0
    for routine in program["ROUTINES"]:
        work_sets = sum(ex["work_sets"] for ex in routine["exercises"])
        total_sets += work_sets
        low, high = routine_time_range(routine)
        lines += [f'<section class="day"><h2>{escape(routine["name"])}</h2>',
                  f'<p class="day-meta">{work_sets} work sets. Model time: {routine_seconds(routine)/60:.0f} minutes. '
                  f'Planning range: {low:.0f}–{high:.0f} minutes.</p>',
                  '<div style="overflow-x:auto"><table><thead><tr><th>Exercise</th><th>Warmup reps</th>'
                  '<th>Work</th><th>RPE</th><th>Rest</th></tr></thead><tbody>']
        for ex in routine["exercises"]:
            warmup = " / ".join(map(str, ex.get("warmup_reps") or [])) or "None listed"
            notes = escape(ex.get("notes", ""))
            lines.append(f'<tr><td><strong>{escape(ex["name"])}</strong><br>{notes}</td><td>{warmup}</td>'
                         f'<td>{ex["work_sets"]} × {escape(str(ex["reps"]))}</td>'
                         f'<td>{ex["rpe"]}</td><td>{ex["rest_seconds"]} s</td></tr>')
        lines += ['</tbody></table></div>',
                  paragraphs(routine.get("notes", "")), details(routine.get("details", "")), '</section>']
    lines += [f'<p>Total weekly working sets: {total_sets}.</p>', paragraphs(TOTAL_SETS_NOTE),
              '<h2>Cardio</h2>']
    for cardio in program["CARDIO_SCHEDULE"]:
        lines += [f'<h3>{escape(cardio["day"])}: {escape(cardio["type"])}</h3>',
                  f'<p>{escape(cardio["modality"])} · {cardio_duration_min(cardio):g} minutes.</p>',
                  paragraphs(cardio.get("notes", "")), details(cardio.get("details", ""))]
    lines += [paragraphs(FOOTER_NOTE),
              '<p><a href="evidence_base.md">Exercise evidence</a> · '
              '<a href="nutrition_evidence_base.md">Nutrition evidence</a></p>',
              '</main></body></html>']
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", default=DEFAULT_PROGRAM)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/program.html")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render(load_program(args.program))
    if args.check:
        if not args.output.exists() or args.output.read_text() != expected:
            print(f"FAIL: {args.output} is stale; run render_program.py with the same arguments without --check")
            return 1
        print("PASS: readable plan matches program and timing model")
    else:
        args.output.write_text(expected)
        print(f"Rendered {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
