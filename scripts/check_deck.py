r"""check_deck.py -- programmatic proof that a generated deck obeys the rules.

    python scripts\check_deck.py <deck.pptx> [--fig-dir DIR] [--max-title 70]

Checks (the first two kill the historical defects for good):
  1. NO-OVERFLOW: every picture lies fully inside the slide.
  2. ASPECT: every picture's placed aspect matches its source PNG's aspect
     within 1% -- catches any regression to width-only add_picture.
  3. STYLE: every text run is Arial; title-band runs (top < 1.0") are bold,
     >= 20 pt, and BLACK (never blue); body runs outside the title band are
     <= 12.5 pt unless bold (display numbers / section titles are bold).
  4. TABLES: every table uses the plain grid style (no PowerPoint banding).
  5. FILL (warn): a picture occupying < 85% of the content box in BOTH
     dimensions signals a wrong figsize preset (letterboxing), not an error.
  6. TITLES (warn): a title-band run longer than --max-title characters.
  7. DENSITY (info): slides with no picture and no table (text-only count).
Exit 1 on any FAIL; warnings do not fail the build.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

EMU_PER_IN = 914400
TITLE_BAND_IN = 1.0
CONTENT_W_IN = 12.4
CONTENT_H_IN = 6.05  # max content box (no subtitle, no caption)
BODY_MAX_PT = 12.5
TABLE_STYLE_NONE = "{5940675A-B579-460E-94D1-54222C63F5DA}"


def png_size_bytes(blob: bytes):
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", blob[16:24])
    return int(w), int(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--fig-dir", default=None,
                    help="unused (aspect read from embedded image parts)")
    ap.add_argument("--max-title", type=int, default=70)
    args = ap.parse_args()

    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.oxml.ns import qn

    prs = Presentation(args.deck)
    sw, sh = prs.slide_width, prs.slide_height
    fails, warns = [], []
    n_pics = n_runs = n_tables = 0
    text_only = []

    for i, slide in enumerate(prs.slides, start=1):
        pics_on_slide = sum(1 for s in slide.shapes
                            if s.shape_type == MSO_SHAPE_TYPE.PICTURE)
        tables_on_slide = sum(1 for s in slide.shapes if s.has_table)
        if pics_on_slide == 0 and tables_on_slide == 0:
            text_only.append(i)
        # a two_fig slide's per-picture box is half the content width
        w_ref = CONTENT_W_IN / max(pics_on_slide, 1)
        # title/section slides have no title band: display text there is free-form
        has_band = any(s.has_text_frame and s.top is not None and s.top < TITLE_BAND_IN * EMU_PER_IN
                       and any(r.font.size is not None and r.font.size.pt >= 20
                               for p in s.text_frame.paragraphs for r in p.runs)
                       for s in slide.shapes)
        for shp in slide.shapes:
            if shp.shape_type == MSO_SHAPE_TYPE.PICTURE:
                n_pics += 1
                L, T, W, H = shp.left, shp.top, shp.width, shp.height
                if L < 0 or T < 0 or L + W > sw + 1000 or T + H > sh + 1000:
                    fails.append(
                        f"slide {i}: picture overflows slide "
                        f"(L={L/EMU_PER_IN:.2f} T={T/EMU_PER_IN:.2f} "
                        f"W={W/EMU_PER_IN:.2f} H={H/EMU_PER_IN:.2f} in)")
                src = png_size_bytes(shp.image.blob)
                if src:
                    ar_src = src[0] / src[1]
                    ar_placed = W / H
                    if abs(ar_placed - ar_src) / ar_src > 0.01:
                        fails.append(
                            f"slide {i}: aspect distorted (src {ar_src:.3f} "
                            f"vs placed {ar_placed:.3f}) -- width-only insert?")
                w_in, h_in = W / EMU_PER_IN, H / EMU_PER_IN
                if w_in < 0.85 * w_ref and h_in < 0.85 * CONTENT_H_IN:
                    warns.append(
                        f"slide {i}: picture fills only "
                        f"{w_in/w_ref:.0%} x {h_in/CONTENT_H_IN:.0%} "
                        f"of its box -- wrong figsize preset?")
            if shp.has_table:
                n_tables += 1
                sid = shp.table._tbl.tblPr.find(qn("a:tableStyleId"))
                if sid is None or (sid.text or "").upper() != TABLE_STYLE_NONE:
                    fails.append(f"slide {i}: table uses style {sid.text if sid is not None else 'default'} "
                                 f"(must be the plain grid {TABLE_STYLE_NONE})")
                for row in shp.table.rows:
                    for cell in row.cells:
                        for para in cell.text_frame.paragraphs:
                            for run in para.runs:
                                n_runs += 1
                                if run.font.name is not None and run.font.name != "Arial":
                                    fails.append(f"slide {i}: non-Arial table run '{run.font.name}'")
            if shp.has_text_frame:
                in_title_band = shp.top is not None and shp.top < TITLE_BAND_IN * EMU_PER_IN
                for para in shp.text_frame.paragraphs:
                    for run in para.runs:
                        n_runs += 1
                        f = run.font
                        if f.name is not None and f.name != "Arial":
                            fails.append(f"slide {i}: non-Arial run '{f.name}' "
                                         f"({run.text[:30]!r})")
                        if in_title_band and f.size is not None and f.size.pt >= 20:
                            rgb = getattr(f.color, "rgb", None)
                            if f.bold is not True:
                                fails.append(f"slide {i}: title run not bold "
                                             f"({run.text[:30]!r})")
                            if rgb is not None and str(rgb) != "0B0B0B" and \
                                    str(rgb) != "000000":
                                fails.append(f"slide {i}: title color #{rgb} "
                                             f"is not black ({run.text[:30]!r})")
                            if len(run.text) > args.max_title:
                                warns.append(f"slide {i}: title is {len(run.text)} chars "
                                             f"(> {args.max_title}): {run.text[:50]!r}...")
                        elif has_band and not in_title_band and f.size is not None and \
                                f.size.pt > BODY_MAX_PT and f.bold is not True:
                            fails.append(f"slide {i}: body run {f.size.pt:.0f} pt > {BODY_MAX_PT} "
                                         f"and not bold ({run.text[:30]!r})")

    n_slides = len(prs.slides._sldIdLst)
    print(f"check_deck: {n_slides} slides, {n_pics} pictures, {n_tables} tables, {n_runs} text runs")
    if text_only:
        print(f"  info: {len(text_only)} text-only slide(s): {text_only}")
    for w in warns:
        print(f"  warn: {w}")
    for f_ in fails:
        print(f"  FAIL: {f_}")
    if fails:
        print(f"VERDICT: FAIL ({len(fails)} failure(s), {len(warns)} warning(s))")
        sys.exit(1)
    print(f"VERDICT: PASS ({len(warns)} warning(s))")


if __name__ == "__main__":
    main()
