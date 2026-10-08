# PDF Invoice Tools

Python tools that turn a printed PDF into something you can edit. The main tool takes a recovery sheet (a table of clients and amounts), makes every cell editable, lets you tick the rows you want, and builds a clean final invoice from them.

## How it works

**Step 1. Make the PDF fillable** with `fillable_form.py`

* Finds every table row in the PDF with pdfplumber.
* Puts an editable text field over each cell, filled with the original value.
* Adds a "Keep" checkbox next to each row.
* Skips the header row and the Total row.

**Step 2. Fill it in.** Open the fillable PDF in any PDF reader. Change any values and tick the rows you want to keep.

**Step 3. Build the final invoice** with `final_invoice.py`

* Reads the ticked rows and their values from the filled PDF.
* Reads the route and day from the top of the page.
* Builds a new invoice PDF with a table and totals for invoices, outstanding amount and recovery amount.

### Input format

The PDF should have a line like `Route: Model Town | Day: Monday` at the top, and a table with these columns:

| Client Code | Client Name | No. of invoices | Outstanding Amount | Recovery Amount |
| --- | --- | --- | --- | --- |

## Notebooks

Two extra tools made in Google Colab:

* `notebooks/editable_pdf.ipynb` turns every line of text on a PDF page into an editable field, using PyMuPDF.
* `notebooks/pdf_to_word.ipynb` converts a PDF to a Word file, keeping the text and tables.

## Project structure

```
fillable_form.py   Turns a table PDF into a fillable form
final_invoice.py   Builds the final invoice from the filled form
notebooks/         Editable PDF and PDF to Word notebooks
```

## How to run

1. Install the packages:
   ```
   pip install -r requirements.txt
   ```
2. Make the fillable form. Enter the path of your PDF when asked. The result is saved in `fillable_forms/`.
   ```
   python fillable_form.py
   ```
3. Fill it in and save it, then build the final invoice. The result is saved in `final_invoices/`.
   ```
   python final_invoice.py
   ```

## Tools

Python, pdfplumber, pypdf, ReportLab, PyMuPDF, python-docx.
