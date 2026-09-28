"""Create controlled filled PDFs by overlaying explicit sample values on Annexe 05."""
from __future__ import annotations

import fitz
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "datasets/boq/male_municipal_maintenance_v1"
REFERENCE = BASE / "reference/MM_Cahier-des-charges-type-Entretien.pdf"
OUT = BASE / "synthetic"

# Each item is (article, designation, quantity, HT unit, HT total, TTC unit, TTC total).
SCENARIOS = {
    "fixture_a_clean": {
        "rows": [("01", "Entretien voirie", "2", "125,000", "250,000", "148,750", "297,500"),
                 ("02", "Refection reseau", "1", "100,000", "100,000", "119,000", "119,000")],
        "totals": ("350,000", "66,500", "416,500"), "shift": 0,
    },
    "fixture_b_french_numbers": {
        "rows": [("01", "Entretien voirie", "1 250,500", "0,200", "250,100", "0,238", "297,619"),
                 ("02", "Refection reseau", "1", "100,000", "100,000", "119,000", "119,000")],
        "totals": ("350,100", "66,519", "416,619"), "shift": 0,
    },
    "fixture_d_missing_quantity": {
        "rows": [("01", "Entretien voirie", "", "125,000", "250,000", "148,750", "297,500"),
                 ("02", "Refection reseau", "1", "100,000", "100,000", "119,000", "119,000")],
        "totals": ("350,000", "66,500", "416,500"), "shift": 0,
    },
    "fixture_e_arithmetic_error": {
        "rows": [("01", "Entretien voirie", "2", "125,000", "250,100", "148,750", "297,500"),
                 ("02", "Refection reseau", "1", "100,000", "100,000", "119,000", "119,000")],
        "totals": ("350,100", "66,519", "416,619"), "shift": 0,
    },
    "fixture_f_shifted_geometry": {
        "rows": [("01", "Entretien voirie", "2", "125,000", "250,000", "148,750", "297,500"),
                 ("02", "Refection reseau", "1", "100,000", "100,000", "119,000", "119,000")],
        "totals": ("350,000", "66,500", "416,500"), "shift": 2,
    },
}

X = [70.82, 115.01, 297.96, 333.48, 375.98, 418.49, 460.97, 503.47]
Y = [243.91, 303.22, 362.26, 421.32, 480.38, 554.33]
BASELINES = [269, 328, 387, 446, 520]


def put_cell(page, rect, text, *, font=8, align=fitz.TEXT_ALIGN_CENTER):
    if not text:
        return
    page.insert_textbox(rect, text, fontname="helv", fontsize=font, color=(0, 0, 0), align=align,
                        overlay=True, lineheight=1.0)


def create(name, scenario):
    source = fitz.open(REFERENCE)
    output = fitz.open()
    page = output.new_page(width=source[24].rect.width, height=source[24].rect.height)
    # Raster base prevents invisible blank-template text from contaminating the filled fixture layer.
    base = source[24].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    page.insert_image(page.rect, stream=base.tobytes("png"))
    # The visible reference labels are already in the raster. An invisible, explicit text layer
    # makes these controlled fixtures usable by native-text test adapters as well as OCR.
    for point, text in [((267, 87), "Annexe 05"), ((180, 181), "BORDERAU DES PRIX - DEVIS ESTIMATIF"),
                        ((338, 228), "Prix HTVA"), ((424, 228), "Prix TTC"),
                        ((357, 565), "Total HTVA"), ((350, 580), "TVA (19%)"), ((366, 595), "Total TTC")]:
        page.insert_text(point, text, fontname="hebo", fontsize=10, render_mode=3, overlay=True)
    shift = scenario["shift"]
    for ri, y0 in enumerate(Y[:-1]):
        y1 = Y[ri + 1]
        baseline = BASELINES[ri]
        # White-fill the interior of all seven cells, retaining original rule lines.
        for ci in range(7):
            page.draw_rect(fitz.Rect(X[ci]+.8, y0+.8, X[ci+1]-.8, y1-.8), color=None, fill=(1,1,1), overlay=True)
        values = scenario["rows"][ri] if ri < len(scenario["rows"]) else (f"{ri+1:02d}", "", "", "", "", "", "")
        for ci, value in enumerate(values):
            left, right = X[ci]+1.5+shift, X[ci+1]-1.5+shift
            if ci == 0:
                rect = fitz.Rect(left, y0+5+shift, right, y0+21+shift)
                put_cell(page, rect, value, font=9)
            elif ci == 1:
                put_cell(page, fitz.Rect(left+4, y0+8+shift, right-4, y0+23+shift), value, font=8, align=fitz.TEXT_ALIGN_LEFT)
                if value:
                    words = "deux cent cinquante dinars" if ri == 0 else "cent dinars"
                    put_cell(page, fitz.Rect(left+4, y1-20+shift, right-4, y1-4+shift), f"L'unite : {words}", font=7, align=fitz.TEXT_ALIGN_LEFT)
            elif value:
                put_cell(page, fitz.Rect(left, y0+7+shift, right, y0+24+shift), value, font=6 if ci == 2 else 8)
    # Blank the three total value cells, preserving their rules, then insert the explicit scenario totals.
    total_rows = ((554.81, 569.45), (569.93, 584.57), (585.05, 599.69))
    for row_i, (top, bottom) in enumerate(total_rows):
        page.draw_rect(fitz.Rect(419.2, top+.7, 502.1, bottom-.7), color=None, fill=(1,1,1), overlay=True)
        put_cell(page, fitz.Rect(420, top+2, 502, bottom-2), scenario["totals"][row_i], font=8, align=fitz.TEXT_ALIGN_RIGHT)
    output.save(OUT / f"{name}.pdf", garbage=4, deflate=True)
    output.close(); source.close()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, scenario in SCENARIOS.items():
        create(name, scenario)


if __name__ == "__main__":
    main()
