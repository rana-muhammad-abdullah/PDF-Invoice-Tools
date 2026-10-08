import os
import shutil
from datetime import datetime

import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject, ArrayObject, DictionaryObject, TextStringObject

SAVE_FOLDER = "invoices"
FORM_FOLDER = "fillable_forms"


COLUMN_NAMES = ["code", "name", "invoices", "outstanding", "recovery"]


def find_all_cells(pdf_path):
    """
    Go through every page and find the table rows.
    Return:
      - rows_info: one entry per cell in every data row (for text fields)
      - row_summaries: one entry per row (for the select checkbox)
      - page_size
    Skips header rows and the Total row.
    """
    rows_info = []
    row_summaries = []

    with pdfplumber.open(pdf_path) as pdf:
        page_size = (pdf.pages[0].width, pdf.pages[0].height)

        for page_number, page in enumerate(pdf.pages):
            tables = page.find_tables()
            for table in tables:
                table_text = table.extract()
                for row_cells, row_text in zip(table.rows, table_text):
                    if not row_text or not row_text[0]:
                        continue
                    first_cell = row_text[0].strip()
                    if first_cell in ("Client Code", "Total", ""):
                        continue

                    row_left = None
                    row_top = None
                    row_bottom = None

                    for col_index, bbox in enumerate(row_cells.cells):
                        if bbox is None:
                            continue
                        col_name = COLUMN_NAMES[col_index] if col_index < len(COLUMN_NAMES) else f"col{col_index}"
                        cell_text = row_text[col_index].strip() if col_index < len(row_text) and row_text[col_index] else ""

                        rows_info.append({
                            "page": page_number,
                            "client_code": first_cell,
                            "column": col_name,
                            "bbox": bbox,
                            "value": cell_text
                        })

                        x0, top, x1, bottom = bbox
                        row_left = x0 if row_left is None else min(row_left, x0)
                        row_top = top if row_top is None else min(row_top, top)
                        row_bottom = bottom if row_bottom is None else max(row_bottom, bottom)

                    if row_left is not None:
                        row_summaries.append({
                            "page": page_number,
                            "client_code": first_cell,
                            "left": row_left,
                            "top": row_top,
                            "bottom": row_bottom
                        })

    return rows_info, row_summaries, page_size


def build_overlay(rows_info, row_summaries, page_size, page_count, out_path):
    """
    Create a PDF with:
      - one AcroForm text field per cell, prefilled with the original value
      - one checkbox per row, placed to the left of the table, used to
        mark which rows should be kept in the final invoice
    """
    width, height = page_size
    c = canvas.Canvas(out_path, pagesize=(width, height))
    form = c.acroForm

    rows_by_page = {}
    for row in rows_info:
        rows_by_page.setdefault(row["page"], []).append(row)

    summaries_by_page = {}
    for row in row_summaries:
        summaries_by_page.setdefault(row["page"], []).append(row)

    used_names = set()

    for page_number in range(page_count):
        for row in rows_by_page.get(page_number, []):
            x0, top, x1, bottom = row["bbox"]
            y = height - bottom

            # cover the original text
            c.setFillColorRGB(1, 1, 1)
            c.rect(x0, y, x1 - x0, bottom - top, fill=1, stroke=0)

            field_name = f"{row['column']}_{row['client_code']}"
            # keep field names unique even if a code repeats
            base_name = field_name
            counter = 1
            while field_name in used_names:
                field_name = f"{base_name}_{counter}"
                counter += 1
            used_names.add(field_name)

            form.textfield(
                name=field_name,
                tooltip=row["column"],
                value=row["value"],
                x=x0 + 2,
                y=y + 2,
                width=(x1 - x0) - 4,
                height=(bottom - top) - 4,
                borderStyle="underlined",
                borderWidth=1,
                fontSize=8,
                forceBorder=True,
                textColor=black,
                fieldFlags="doNotScroll",
            )

        # checkboxes, one per row, to the left of the table
        page_rows = summaries_by_page.get(page_number, [])
        if page_rows:
            c.setFont("Helvetica-Bold", 7)
            header_top = min(r["top"] for r in page_rows)
            c.drawString(8, height - header_top + 4, "Keep")

        for row in page_rows:
            box_size = min(12, (row["bottom"] - row["top"]) - 6)
            box_x = max(row["left"] - box_size - 12, 6)
            box_y = height - row["bottom"] + ((row["bottom"] - row["top"]) - box_size) / 2

            cb_name = f"select_{row['client_code']}"
            base_name = cb_name
            counter = 1
            while cb_name in used_names:
                cb_name = f"{base_name}_{counter}"
                counter += 1
            used_names.add(cb_name)

            form.checkbox(
                name=cb_name,
                tooltip="Keep this row in the final invoice",
                x=box_x,
                y=box_y,
                size=box_size,
                checked=False,
                buttonStyle="check",
                borderStyle="solid",
                borderWidth=1,
                forceBorder=True,
            )

        c.showPage()

    c.save()


def merge_and_save_form(bg_path, overlay_path, out_path):
    bg_reader = PdfReader(bg_path)
    overlay_reader = PdfReader(overlay_path)

    writer = PdfWriter()

    for i, page in enumerate(bg_reader.pages):
        page.merge_page(overlay_reader.pages[i])
        writer.add_page(page)

    field_refs = []
    for pg in writer.pages:
        annots = pg.get("/Annots")
        if annots:
            for a in annots:
                obj = a.get_object()
                if "/FT" in obj:
                    field_refs.append(a)

    acroform = DictionaryObject()
    acroform[NameObject("/Fields")] = ArrayObject(field_refs)
    acroform[NameObject("/NeedAppearances")] = BooleanObject(True)
    acroform[NameObject("/DA")] = TextStringObject("/Helv 0 Tf 0 g")

    overlay_acroform = overlay_reader.trailer["/Root"].get("/AcroForm")
    if overlay_acroform is not None:
        overlay_acroform = overlay_acroform.get_object()
        if "/DR" in overlay_acroform:
            dr_clone = overlay_acroform["/DR"].get_object().clone(writer)
            acroform[NameObject("/DR")] = dr_clone

    writer._root_object[NameObject("/AcroForm")] = acroform

    with open(out_path, "wb") as f:
        writer.write(f)


def process_pdf(pdf_path):
    if not os.path.isfile(pdf_path):
        print("File not found:", pdf_path)
        return None
    if not pdf_path.lower().endswith(".pdf"):
        print("Only PDF files are allowed")
        return None

    for folder in (SAVE_FOLDER, FORM_FOLDER):
        if not os.path.exists(folder):
            os.makedirs(folder)

    filename = os.path.basename(pdf_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stored_name = f"{timestamp}_{filename}"
    stored_path = os.path.join(SAVE_FOLDER, stored_name)
    shutil.copy(pdf_path, stored_path)
    print("Saved original PDF to:", stored_path)

    rows_info, row_summaries, page_size = find_all_cells(pdf_path)
    if not rows_info:
        print("No table rows found. Cannot build a fillable form.")
        return None

    page_count = len(PdfReader(pdf_path).pages)

    overlay_path = os.path.join(FORM_FOLDER, f"overlay_{stored_name}")
    build_overlay(rows_info, row_summaries, page_size, page_count, overlay_path)

    form_name = stored_name.replace(".pdf", "_fillable.pdf")
    form_path = os.path.join(FORM_FOLDER, form_name)
    merge_and_save_form(pdf_path, overlay_path, form_path)
    os.remove(overlay_path)

    print("Saved fillable PDF to:", form_path)
    print("Fields created:", len(rows_info))
    return form_path


if __name__ == "__main__":
    pdf_path = input("Enter path of the PDF: ")
    process_pdf(pdf_path)