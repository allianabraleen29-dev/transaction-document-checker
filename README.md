
# Transaction Document Checker — Web App

This is a Streamlit web version of the desktop prototype.

## Run locally

1. Install Python 3.10+.
2. Install Tesseract OCR and keep it at:
   `C:\Program Files\Tesseract-OCR`
3. Open Command Prompt in this folder.
4. Run:

   `py -m pip install -r requirements.txt`

5. Run:

   `py -m streamlit run app.py`

The app opens in your browser.

## Put it online

A simple option is Streamlit Community Cloud. Create a GitHub repository, upload:
- `app.py`
- `requirements.txt`

Then deploy the repository as a Streamlit app.

For real client documents, use only a deployment/storage environment approved by your brokerage/company. This prototype is intended for QA/testing and does not provide legal/compliance determinations.

## Current features

- Multiple PDF/image upload
- OCR for scanned PDFs/images
- Real-estate transaction document checklist
- Buyer/seller/property-address exact text checks
- Required document detection based on filename
- Name/address/date/signature/initials field screening
- CSV QA report
- Missing/review status

## Recommended production upgrades

- Secure login and role-based access
- Encrypted temporary storage
- Automatic deletion/retention controls
- Document-type classification using document content, not just filenames
- Better signature/initial detection
- Cross-document entity matching with OCR-tolerant normalization
- Contract-specific deadline extraction
- Audit trail
- Brokerage-specific checklists
- Secure cloud storage integration
