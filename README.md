# Document Reader & Completeness Checker

General document reader for PDF, DOCX, and photo/image uploads.

## Supports
- PDF (including scanned/image-only PDFs)
- Word DOCX
- JPG/JPEG/PNG/WEBP/TIF/TIFF photos and scans

## What it does
- Automatically identifies common document types
- OCRs scanned PDFs and photos
- Shows detected, missing, and review items directly in the browser
- Does not require a report download

## Streamlit deployment
The app requires Tesseract OCR. `packages.txt` installs it on Streamlit Community Cloud.

## Important
This is a screening/QA tool, not a legal or compliance determination. Review results manually, especially signatures and OCR text.
