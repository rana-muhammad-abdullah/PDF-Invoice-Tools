import os
import re
from datetime import datetime

import pdfplumber
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm

OUTPUT_FOLDER = "final_invoices"

COLUMN_NAMES = ["code", "name", "invoices", "outstanding", "recovery"]
COLUMN_LABELS = {
    "code": "Client Code",
    "name": "Client Name",
    "invoices": "No. of invoices",
    "outstanding": "Outstanding Amount",
    "recovery": "Recovery Amount"
}


def read_header_info(pdf_path):
    info = {}
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text() or ""

    route_match = re.search(r"Route:\s*(.+?)\s*\|\s*Day:\s*(.+)", text)
    if route_match:
        info["route"] = route_match.group(1).strip()
        info["day"] = route_match.group(2).strip()

    return info


def read_selected_rows(pdf_path):
    reader = PdfReader(pdf_path)
    fields = reader.get_fields() or {}

    rows_by_code = {}

    for field_name, field in fields.items():
        value = field.get("/V") or ""

        if field_name.startswith("select_"):
            code = field_name[len("select_"):]
            rows_by_code.setdefault(code, {})["selected"] = (value == "/Yes")
            continue

        for col in COLUMN_NAMES:
            prefix = col + "_"
            if field_name.startswith(prefix):
                code = field_name[len(prefix):]
                rows_by_code.setdefault(code, {})[col] = str(value).strip()
                break

    selected_rows = []
    for code, row in rows_by_code.items():
        if row.get("selected"):
            row.setdefault("code", code)
            selected_rows.append(row)

    return selected_rows


def parse_amount(text):
    if not text:
        return 0.0
    match = re.search(r"[\d,]+\.?\d*", text)
    if not match:
        return 0.0
    digits = match.group(0).replace(",", "")
    try:
        return float(digits) if digits else 0.0
    except ValueError:
        return 0.0


def build_invoice_pdf(header_info, selected_rows, out_path):
    doc = SimpleDocTemplate(out_path, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Invoice", styles["Title"]))
    if header_info.get("route"):
        story.append(Paragraph(f"Route: {header_info['route']}", styles["Normal"]))
    if header_info.get("day"):
        story.append(Paragraph(f"Day: {header_info['day']}", styles["Normal"]))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    table_data = [["Client Code", "Client Name", "No. of invoices", "Outstanding Amount", "Recovery Amount"]]
    total_invoices = 0
    total_outstanding = 0.0
    total_recovery = 0.0

    for row in selected_rows:
        table_data.append([
            row.get("code", ""),
            row.get("name", ""),
            row.get("invoices", ""),
            row.get("outstanding", ""),
            row.get("recovery", "")
        ])
        try:
            total_invoices += int(re.sub(r"[^\d]", "", row.get("invoices", "0")) or 0)
        except ValueError:
            pass
        total_outstanding += parse_amount(row.get("outstanding", ""))
        total_recovery += parse_amount(row.get("recovery", ""))

    table_data.append([
        "Total",
        "",
        str(total_invoices),
        f"Rs. {total_outstanding:,.2f}",
        f"Rs. {total_recovery:,.2f}"
    ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eeeeee")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (2, 0), (4, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(table)
    doc.build(story)


def process_filled_form(filled_pdf_path):
    if not os.path.isfile(filled_pdf_path):
        print("File not found:", filled_pdf_path)
        return None

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    header_info = read_header_info(filled_pdf_path)
    selected_rows = read_selected_rows(filled_pdf_path)

    if not selected_rows:
        print("No rows were checked. Nothing to put in the final invoice.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_FOLDER, f"invoice_{timestamp}.pdf")
    build_invoice_pdf(header_info, selected_rows, out_path)

    print("Selected rows:", len(selected_rows))
    print("Saved final invoice to:", out_path)
    return out_path


if __name__ == "__main__":
    filled_pdf_path = input("Enter path of the filled PDF: ")
    process_filled_form(filled_pdf_path)