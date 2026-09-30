# Document Reader & Completeness Checker

A concise Streamlit web app for reading general documents and identifying the document type, detected information, missing items, and fields that need human review.

## Supported files
- PDF
- Word DOCX
- PNG/JPG/JPEG/TIF/TIFF

## Features
- Automatically identifies common document types
- Reads Word documents directly; no conversion/download required
- OCR for scanned PDFs and images
- Shows missing/not-detected/review items directly on the webpage
- Conservative signature handling: a printed "Signature" label does not count as a completed signature
- No report download is required

## Run locally
```bash
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## Streamlit deployment
Deploy `app.py` from the `main` branch of the GitHub repository.

## Privacy
Files are processed in the running Streamlit session and are not intentionally saved to a database by this prototype. Do not upload confidential client documents to an unapproved deployment.

This tool is a document-screening aid, not a legal or compliance determination.
