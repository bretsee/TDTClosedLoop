"""Render a runbook / helper card (Markdown) to PDF for the bench, via Edge headless.

    python scripts/md_to_pdf.py RIG_DAY_2026-10-14.md HELPER_CARD_2026-10-14.md [--out-dir day_2026-10-14]

Arial 10 pt, black headings, code blocks wrap (long command lines stay on the page), tables
with thin borders. No pandoc / LaTeX needed: python-markdown -> HTML -> msedge --print-to-pdf.
"""
import argparse, io, os, subprocess, sys, tempfile

import markdown

EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
CSS = """
@page { size: A4; margin: 12mm 12mm 14mm 12mm; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 10pt; color: #000; line-height: 1.3; }
h1 { font-size: 15pt; margin: 0 0 6pt 0; } h2 { font-size: 12.5pt; margin: 12pt 0 4pt 0; border-bottom: 1px solid #000; }
h3 { font-size: 11pt; margin: 9pt 0 3pt 0; }
h1, h2, h3 { color: #000; page-break-after: avoid; }
p { margin: 4pt 0; } ul, ol { margin: 3pt 0 3pt 16pt; padding: 0; } li { margin: 1pt 0; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 8.6pt; background: #f2f2f2; padding: 0 2px; }
pre { font-family: Consolas, 'Courier New', monospace; font-size: 8.2pt; background: #f2f2f2; border: 1px solid #bbb;
      padding: 5px 6px; margin: 4pt 0; white-space: pre-wrap; word-break: break-all; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; margin: 5pt 0; font-size: 9pt; page-break-inside: auto; }
th, td { border: 1px solid #888; padding: 2px 5px; vertical-align: top; text-align: left; }
th { background: #e6e6e6; } tr { page-break-inside: avoid; }
blockquote { margin: 4pt 0; padding: 3pt 8pt; border-left: 3px solid #888; background: #f7f7f7; }
hr { border: 0; border-top: 1px solid #000; margin: 8pt 0; }
"""


def render(md_path, out_dir):
    text = io.open(md_path, encoding="utf-8").read()
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    html = ("<!doctype html><html><head><meta charset='utf-8'><title>%s</title><style>%s</style></head>"
            "<body>%s</body></html>" % (os.path.basename(md_path), CSS, body))
    base = os.path.splitext(os.path.basename(md_path))[0]
    html_path = os.path.join(tempfile.gettempdir(), base + ".html")
    io.open(html_path, "w", encoding="utf-8").write(html)
    pdf_path = os.path.abspath(os.path.join(out_dir, base + ".pdf"))
    edge = next((e for e in EDGE if os.path.exists(e)), None)
    if edge is None:
        print("FAIL: msedge.exe not found"); return 1
    cmd = [edge, "--headless=new", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer",
           "--print-to-pdf=" + pdf_path, "file:///" + html_path.replace("\\", "/")]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not os.path.exists(pdf_path):
        print("FAIL: no pdf written (rc=%s)\n%s" % (r.returncode, r.stderr[-800:])); return 1
    print("wrote %s (%.0f kB)" % (pdf_path, os.path.getsize(pdf_path) / 1024.0))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out-dir", default=".")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    return max(render(f, a.out_dir) for f in a.files)


if __name__ == "__main__":
    sys.exit(main())
