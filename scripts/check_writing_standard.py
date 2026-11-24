#!/usr/bin/env python3
"""Check user-facing program text against the declared writing standard.

A program opts in with PROGRAM_METADATA["writing_standard"] = "ASD-STE100". The check covers
every text the lifter reads: the description, general notes, session notes and details,
exercise notes, cardio notes and details, the exported Hevy notes, and the fixed plan text.

Mechanical rules (a subset of ASD-STE100, plus BLUF):
  - Each section (blank-line separated) of a block starts with "BLUF:" or "WARNING:".
  - BLUF line: at most 20 words. After it: at most 6 sentences (STE paragraph limit).
  - Every sentence: at most 20 words (the STE limit for procedural sentences).
  - No -ing words, except technical names and non-verb words in ING_ALLOWED.
  - No words from BANNED_WORDS (common words that STE does not approve).
  - Active voice: no "be" + past participle ("is lifted", "are not exported"), except state
    words in PARTICIPLE_ALLOWED ("you are tired"). Misses forms such as "gets lifted".
  - One instruction per sentence: in an instruction (a main clause that starts with a listed
    verb), no second listed verb after "and", "then" or ";" ("Lift the bar and rack it.").
    A leading condition ("If ..., ") and a label ("Per side: ") are skipped. The check
    stops at the first that/which/who/when/if/while/because. Verbs that are also nouns (NOUN_LIKE_VERBS) count only
    when an object, a particle or the sentence end follows. This also rejects simultaneous
    actions, which STE permits. Verbs outside the lists are not seen.
  - Exercise notes: at most 2 sentences. Hevy notes: at most HEVY_NOTE_MAX_CHARS.

Not checked: imperative mood. STE requires it for instructions only, and descriptive text is
valid, so a reviewer checks it. Neither does this check words against the STE dictionary.
A pass is not STE certification.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from program_loader import load_program  # noqa: E402

MAX_SENTENCE_WORDS = 20
MAX_BLUF_WORDS = 20
MAX_SECTION_SENTENCES = 6
MAX_EXERCISE_NOTE_SENTENCES = 2
HEVY_NOTE_MAX_CHARS = 250
SECTION_LABELS = ("BLUF:", "WARNING:")

# Technical names used in this domain, and common words that only look like -ing verbs.
ING_ALLOWED = {
    "lifting", "cycling", "coaching", "training", "planning", "working",
    "during", "thing", "things", "nothing", "something", "anything", "everything",
    "morning", "evening", "ceiling", "string", "bring", "ring", "spring", "king", "wing",
}
# Word -> approved replacement.
BANNED_WORDS = {
    "ensure": "make sure", "perform": "do", "utilize": "use", "utilise": "use",
    "commence": "start", "terminate": "stop", "facilitate": "help", "prior": "before",
    "via": "through", "regarding": "about", "numerous": "many",
}
# Verbs that start an instruction. Lowercase only: a capital after "and" is an exercise name
# ("Bench Press and Pull-Up"), not a second instruction. Left out because this domain uses
# them as nouns after "and": push, pull, lower, rest, set, drop ("push and pull", "work and rest").
IMPERATIVE_VERBS = {
    "add", "brace", "breathe", "choose", "do", "examine", "go", "keep", "make", "measure", "move",
    "put", "rack", "reduce", "return", "sit", "squeeze", "stand", "take", "use", "write",
}
# Verbs that are also nouns here ("start and stop times", "ride and walk days"). After "and" or
# "then", they are a second instruction only when the sentence end or an _OBJECT_START word follows.
NOUN_LIKE_VERBS = {
    "carry", "change", "check", "decrease", "finish", "hold", "increase", "lift", "pause", "raise",
    "record", "repeat", "ride", "start", "stop", "walk", "warm",
}
_OBJECT_START = {
    "the", "a", "an", "it", "them", "your", "one", "both", "each", "all", "this", "these",
    "up", "down", "out", "for", "at", "to", "with", "on",
}
# Words after "be" that look like participles but name a state, or are not participles.
PARTICIPLE_ALLOWED = {
    "indeed", "speed", "tired", "fatigued", "rested", "recovered", "trained", "untrained",
    "detrained", "experienced", "advanced", "injured", "seated",
}
_IRREGULAR_PARTICIPLES = ("done|given|made|taken|kept|held|put|set|shown|known|seen|written|built|chosen|"
                          "driven|ridden|brought|found|told|left|lost|sent|spent|worn|run|split|led|cut|begun")
# "be" + optional adverbs + lowercase past participle ("is Seated Cable Row" is a name, not passive).
# "[a-z]{2,}ed" skips short words such as "red".
_PASSIVE = re.compile(r"\b(?i:am|is|are|was|were|be|been|being)(?:n['’]t)?\s+"
                      r"(?:(?:not|never|also|always|then|still|now|often|[a-z]+ly)\s+)*"
                      rf"([a-z]{{2,}}ed|{_IRREGULAR_PARTICIPLES})\b")
_LABEL = re.compile(r"^[^:]{1,40}:\s+")
_LEAD_CLAUSE = re.compile(r"^(?:if|when|before|after|until|while|once|for|between|with)\b[^,]*,\s*", re.I)
# Not before/after/until: here they are mostly prepositions ("Stop before failure").
_SUBORDINATE = re.compile(r"\b(?:that|which|who|when|if|while|because)\b")
_CHAINED = re.compile(r"(\band then|;\s*then|,?\s*\bthen|\band|;)\s+(?:[a-z]+ly\s+)?([a-z]+)\b(?!-)")

_ABBREVIATIONS = ("et al.", "e.g.", "i.e.", "vs.", "approx.", "etc.")
_ABBREVIATION_RE = re.compile("|".join(re.escape(a) for a in _ABBREVIATIONS), re.IGNORECASE)


def sentences(text: str) -> list[str]:
    """Split on line breaks and on sentence-final punctuation; keeps list items as sentences."""
    protected = _ABBREVIATION_RE.sub(lambda m: m.group(0).replace(".", "\x00"), text)
    out = []
    for line in protected.split("\n"):
        line = re.sub(r"^\s*(?:-|\d+\.)\s+", "", line)
        for part in re.split(r"(?<=[.!?])\s+", line):
            part = part.replace("\x00", ".").strip()
            if words(part):
                out.append(part)
    return out


def words(sentence: str) -> list[str]:
    return [w for w in sentence.split() if re.search(r"[A-Za-z0-9]", w)]


def instruction_clause(sentence: str) -> str:
    """The main clause if it starts with a listed verb; "" for a descriptive sentence."""
    clause = _LEAD_CLAUSE.sub("", _LABEL.sub("", sentence))
    clause = _SUBORDINATE.split(re.sub(r"^then\s+", "", clause, flags=re.I))[0]
    first = clause.split()[0].lower() if clause.split() else ""
    return clause if first in IMPERATIVE_VERBS | NOUN_LIKE_VERBS else ""


def second_instruction(sentence: str) -> tuple[str, str] | None:
    """(joiner, verb) for a second instruction in the main clause, else None."""
    clause = instruction_clause(sentence)
    for m in _CHAINED.finditer(clause):
        verb = m.group(2)
        after = re.findall(r"[A-Za-z0-9]+", clause[m.end():])
        nxt = after[0].lower() if after else ""
        if verb in IMPERATIVE_VERBS or (verb in NOUN_LIKE_VERBS and (not nxt or nxt.isdigit() or nxt in _OBJECT_START)):
            return m.group(1).strip(", "), verb
    return None


def word_problems(sentence: str, where: str) -> list[str]:
    problems = []
    count = len(words(sentence))
    if count > MAX_SENTENCE_WORDS:
        problems.append(f"{where}: {count} words (max {MAX_SENTENCE_WORDS}): {sentence!r}")
    for raw in re.findall(r"[A-Za-z]+", sentence):
        low = raw.lower()
        if low.endswith("ing") and len(low) > 4 and low not in ING_ALLOWED:
            problems.append(f"{where}: -ing word {raw!r}; use a simple verb form, or add a technical name "
                            f"to ING_ALLOWED: {sentence!r}")
        if low in BANNED_WORDS:
            problems.append(f"{where}: {raw!r} is not approved; use {BANNED_WORDS[low]!r}: {sentence!r}")
    passive = next((m for m in _PASSIVE.finditer(sentence) if m.group(1) not in PARTICIPLE_ALLOWED), None)
    if passive:
        problems.append(f"{where}: passive voice {passive.group(0)!r}; use the active voice: {sentence!r}")
    chained = second_instruction(sentence)
    if chained:
        problems.append(f"{where}: second instruction {chained[1]!r} after {chained[0]!r}; "
                        f"write one instruction per sentence: {sentence!r}")
    return problems


def check_block(text: str, where: str) -> list[str]:
    """A block of BLUF sections separated by blank lines."""
    problems: list[str] = []
    sections = [s.strip() for s in text.strip().split("\n\n") if s.strip()]
    if not sections:
        return [f"{where}: empty"]
    for i, section in enumerate(sections, 1):
        loc = f"{where} §{i}"
        first, _, rest = section.partition("\n")
        label = next((lab for lab in SECTION_LABELS if first.startswith(lab)), None)
        if label is None:
            problems.append(f"{loc}: section must start with 'BLUF:' or 'WARNING:': {first!r}")
            body = section
        else:
            head = first[len(label):].strip()
            if len(words(head)) > MAX_BLUF_WORDS:
                problems.append(f"{loc}: {label} line has {len(words(head))} words (max {MAX_BLUF_WORDS})")
            for s in sentences(head):
                problems += [p for p in word_problems(s, loc) if "words (max" not in p]
            body = rest
        body_sentences = sentences(body)
        if len(body_sentences) > MAX_SECTION_SENTENCES:
            problems.append(f"{loc}: {len(body_sentences)} sentences after the first line "
                            f"(max {MAX_SECTION_SENTENCES}); split the section or cut text")
        for s in body_sentences:
            problems += word_problems(s, loc)
    return problems


def check_plain(text: str, where: str, max_sentences: int | None = None) -> list[str]:
    problems: list[str] = []
    found = sentences(text)
    if max_sentences is not None and len(found) > max_sentences:
        problems.append(f"{where}: {len(found)} sentences (max {max_sentences})")
    for s in found:
        problems += word_problems(s, where)
    return problems


def check_program(program: dict) -> list[str]:
    import build_routines as br
    import render_program

    meta = program.get("PROGRAM_METADATA", {})
    problems: list[str] = []
    problems += check_block(meta.get("description", ""), "description")
    if meta.get("general_notes"):
        problems += check_block(meta["general_notes"], "general_notes")
    for routine in program.get("ROUTINES", []):
        name = routine.get("name", "?")
        problems += check_block(routine.get("notes", ""), f"{name} notes")
        if routine.get("details"):
            problems += check_block(routine["details"], f"{name} details")
        for ex in routine.get("exercises", []):
            if ex.get("notes"):
                problems += check_plain(ex["notes"], f"{name} / {ex['name']} notes", MAX_EXERCISE_NOTE_SENTENCES)
        # What Hevy shows: exercise cues, generated sentences and the session notes.
        payload = br.build_routine_payload(routine, {e["name"]: 0 for e in routine.get("exercises", [])},
                                           compact=True)
        for ex_payload, ex in zip(payload["routine"]["exercises"], routine.get("exercises", [])):
            note = ex_payload["notes"]
            if len(note) > HEVY_NOTE_MAX_CHARS:
                problems.append(f"{name} / {ex['name']} Hevy note: {len(note)} characters "
                                f"(max {HEVY_NOTE_MAX_CHARS})")
            problems += check_block(note, f"{name} / {ex['name']} Hevy note")
    for cardio in program.get("CARDIO_SCHEDULE", []):
        where = f"cardio {cardio.get('day', '?')} {cardio.get('type', '')}".strip()
        problems += check_block(cardio.get("notes", ""), f"{where} notes")
        if cardio.get("details"):
            problems += check_block(cardio["details"], f"{where} details")
    for const, text in render_program.STATIC_NOTES.items():
        problems += check_block(text, f"render_program.{const}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--program", default=None)
    args = parser.parse_args(argv)
    program = load_program(args.program)
    standard = program.get("PROGRAM_METADATA", {}).get("writing_standard")
    if not standard:
        print("SKIP: program does not declare PROGRAM_METADATA['writing_standard'].")
        return 0
    if standard != "ASD-STE100":
        print(f"FAIL: unknown writing_standard {standard!r}; supported: 'ASD-STE100'.")
        return 1
    problems = check_program(program)
    if problems:
        print(f"FAIL: {len(problems)} writing-standard problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PASS: user-facing text meets the mechanical ASD-STE100 and BLUF rules "
          "(no dictionary check; not STE certification).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
