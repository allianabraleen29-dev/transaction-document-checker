# Document Reader & Completeness Checker

A concise Streamlit web app for reading general documents and identifying missing information.

## Features
- PDF, DOCX, JPG/JPEG, PNG, WEBP, TIFF and phone photos
- OCR for scanned/image-only PDFs and photos
- Automatic document-type identification
- Missing / Not detected / Needs review statuses
- **Page navigator:** click an issue page to open it directly; detected missing/review labels are highlighted in red
- Results appear directly in the browser; no report download is required

## Run locally
```bash
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

For scanned PDFs/photos, Tesseract OCR is required. Streamlit Community Cloud installs it from `packages.txt`.

## Important
This is a screening/QA tool, not a legal or compliance determination. OCR and signature interpretation require human verification.


## Optional AI Checklist Assistant
The app includes an optional chat assistant that can add custom checklist fields such as Broker Name, Commission, Pet Deposit, or Utilities. Configure `OPENAI_API_KEY` in Streamlit Secrets. You may also set `OPENAI_MODEL` (default: `gpt-5.6-luna`). Never hard-code an API key in the repository. API usage may incur charges.
