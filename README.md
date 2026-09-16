# CFA Level II Workbench

An interactive study app built from the ten volumes of the **2026 CFA Program
Curriculum, Level II** sitting in this repository.

Published artifact: <https://claude.ai/artifact/R9Vx9cB2G9TzkKdUJbMy6K>

## What it contains

Everything is extracted from the PDFs — nothing is written from memory or
generated.

| | |
|---|---|
| Topic areas | 10 (volumes 1–10, with published exam weights) |
| Learning modules | 46 |
| Section outline entries | 1,314 (with printed page numbers, nested) |
| Learning outcome statements | 371 |
| Exam-format questions | 895 (three options, keyed answer, full solution) |
| Item-set vignettes | 159, covering 770 of the questions |
| Exhibit tables | 279 in vignettes, 71 in solutions — as real tables |
| Rendered formulas | 170 (stacked fractions cropped from the PDFs) |
| Worked problems | 143 constructed-response items with solutions |
| Glossary terms | 803, verbatim from the official glossary PDF |
| Flashcards | the same 803 terms, in Leitner boxes 1-5 |

## The four surfaces

**Curriculum** — browse topic → learning module. Each module shows its learning
outcome statements, its full section outline with the printed page numbers, and
its worked problems.

**Practice** — six session modes. *Item sets* is the default because that is how
Level II is actually sat: one vignette and every question hanging off it.
*Weak areas* draws from the five modules the dashboard ranks first; *Missed*,
*Untouched* and *Flagged* draw from your own history. Answer, then the
curriculum's own solution opens, with its tables and formulas intact.

**Flashcards** — the glossary as a spaced-repetition deck. A card moves up a box
when you know it and drops to box 1 when you don't, so the deck keeps returning
what you keep missing. Five decks (due, new, struggling, starred, everything),
filterable by topic, and runnable in either direction — term to definition, or
definition to term.

**Dashboard** — coverage and accuracy per topic against the exam's published
weight, vocabulary progress, a ranked list of what to work on next, and session
history.

## Progress tracking

Attempts, flags, flashcard boxes and session history live in the artifact's own store
(`progress/state`), so the same progress follows you across devices.
`localStorage` mirrors it, so the page still works if the store is unreachable —
the rail's footer says which is in effect.

Priority ranking is `exam weight × (0.62 × (1 − accuracy) + 0.38 × (1 − coverage))`,
so a heavy topic you are weak at outranks a light one you have merely not started.

## Rebuilding the data

```bash
pip install pymupdf
python3 tools/extract_curriculum.py   # -> curriculum2.json + mathimg2.json
python3 tools/extract_glossary.py     # -> glossary_official.json
```

`app/data.js` and `app/math.js` are the bundled outputs. Formulas whose stacked
layout does not survive text extraction are cropped from the PDF as transparent
PNGs and inverted in dark mode; `math.js` loads lazily on the first solution that
needs one.

Notes on how the extraction works, since the PDFs carry no bookmarks:

- Modules come from the contents pages, read at cell level so a page number
  that shares a visual row with its title does not get glued into it.
- Question boundaries are anchored **sequentially** against the solution
  numbering, so a stray `9 years.` in a vignette cannot hijack question 9.
- Running headers (`50 Learning Module 1 Intercorporate Investments`) are
  stripped after row assembly, where they merge into a single line.
- Exhibits are recovered with `find_tables()` and kept as cell data; formulas
  win over table detection, since they sit in a different font.
- The glossary is two-column, and the column origins shift between odd and even
  pages, so the gutter is measured per page — and placed just left of the right
  column's origin, not midway between the two, since left-column body text runs
  well past that midpoint. Columns are also split per span rather than per line,
  because PyMuPDF sometimes merges a line straight across the gutter.

An earlier version of the glossary was derived from bold defined terms in the
volume body text, before the official glossary PDF was available. Comparing the
two, all 153 terms it held that the official glossary lacks were extraction
fragments (`ates` from *interlocking directorates*, `of one price`), not real
entries, so the official glossary replaced it outright. Topic tags are assigned
by counting each term's occurrences across the ten volumes.

## Scope

The questions, vignettes, answers and solution text are reproduced from the CFA
Institute curriculum for personal study from a copy of that curriculum. The
artifact is private to its owner and is not shared publicly.
