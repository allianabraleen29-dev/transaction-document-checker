
import io
import re
from pathlib import Path

import streamlit as st
import fitz
import pytesseract
from PIL import Image, ImageEnhance

st.set_page_config(page_title="Transaction Document Checker", page_icon="📋", layout="wide")

FIELD_PATTERNS = {
    "Buyer Name": [r"\bbuyer\s+name\b", r"\bbuyer\b", r"\bpurchaser\b"],
    "Seller Name": [r"\bseller\s+name\b", r"\bseller\b", r"\bvendor\b"],
    "Property Address": [r"\bproperty\s+address\b", r"\bsubject\s+property\b", r"\bproperty\b", r"\bpremises\b"],
    "Purchase Price": [r"\bpurchase\s+price\b", r"\bsales?\s+price\b", r"\bprice\b"],
    "Contract Date": [r"\bcontract\s+date\b", r"\bexecution\s+date\b", r"\beffective\s+date\b"],
    "Closing Date": [r"\bclosing\s+date\b", r"\bsettlement\s+date\b"],
    "Signature": [r"\bsignature\b", r"\bsigned\s+by\b", r"\bauthorized\s+signature\b"],
    "Initials": [r"\binitials?\b"],
}

DEFAULT_DOCS = [
    "Purchase Agreement",
    "Seller Disclosure",
    "Lead-Based Paint Disclosure",
    "Agency Disclosure",
    "Inspection Report",
    "Inspection/Repair Addendum",
    "Appraisal",
    "Title Commitment",
    "HOA Documents",
    "Closing Disclosure",
]

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def pdf_text(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        if len(clean(text)) < 25:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img = ImageEnhance.Contrast(img).enhance(1.35)
            text = pytesseract.image_to_string(img)
        pages.append((i + 1, text))
    return pages

def image_text(file_bytes):
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.35)
    return [(1, pytesseract.image_to_string(img))]

def extract(uploaded):
    b = uploaded.getvalue()
    if uploaded.name.lower().endswith(".pdf"):
        return pdf_text(b)
    return image_text(b)

def field_status(text, label):
    t = clean(text).lower()
    patterns = FIELD_PATTERNS[label]
    for p in patterns:
        for m in re.finditer(p, t, flags=re.I):
            tail = clean(t[m.end():m.end()+180])
            tail = re.sub(r"^[\s:._\-–—|]+", "", tail)
            if not tail:
                return "MISSING"
            if re.search(r"_{3,}", tail[:100]):
                return "MISSING"
            if label in ("Signature", "Initials"):
                if len(tail) < 8 or re.match(r"^(date|name|print|initials?)\b", tail):
                    return "REVIEW"
                return "FOUND"
            if len(tail) >= 2:
                return "FOUND"
    return "NOT FOUND"

def doc_type(filename):
    n = filename.lower()
    rules = [
        ("Purchase Agreement", ["purchase agreement", "sales contract", "contract"]),
        ("Seller Disclosure", ["seller disclosure", "property disclosure"]),
        ("Lead-Based Paint Disclosure", ["lead", "paint disclosure"]),
        ("Agency Disclosure", ["agency disclosure", "agency"]),
        ("Inspection Report", ["inspection report", "home inspection"]),
        ("Inspection/Repair Addendum", ["repair addendum", "inspection addendum", "repair"]),
        ("Appraisal", ["appraisal"]),
        ("Title Commitment", ["title commitment", "title report"]),
        ("HOA Documents", ["hoa", "homeowners association"]),
        ("Closing Disclosure", ["closing disclosure", "cd"]),
    ]
    for label, keys in rules:
        if any(k in n for k in keys):
            return label
    return "Other"

st.title("📋 Transaction Document Checker")
st.caption("Real-estate transaction QA screening tool — upload documents, review required fields, and identify items that need attention.")

with st.sidebar:
    st.header("Transaction")
    address = st.text_input("Property Address", placeholder="123 Main St, City, State ZIP")
    buyer = st.text_input("Buyer Name", placeholder="Buyer full name")
    seller = st.text_input("Seller Name", placeholder="Seller full name")
    st.divider()
    st.header("Required Documents")
    required = []
    for d in DEFAULT_DOCS:
        if st.checkbox(d, value=d in ["Purchase Agreement", "Seller Disclosure", "Agency Disclosure"], key="req_"+d):
            required.append(d)
    st.divider()
    st.info("For privacy, this demo processes uploaded files in the running app session and does not intentionally save them to a database. Do not upload real client documents to an unapproved deployment.")

uploads = st.file_uploader(
    "Upload transaction documents",
    type=["pdf", "png", "jpg", "jpeg", "tif", "tiff"],
    accept_multiple_files=True
)

if uploads:
    st.success(f"{len(uploads)} document(s) loaded.")
    results = []
    all_text = ""
    found_types = set()

    for up in uploads:
        try:
            pages = extract(up)
            text = "\n".join(t for _, t in pages)
            all_text += "\n" + text
            found_types.add(doc_type(up.name))
            row = {"Document": up.name, "Type": doc_type(up.name)}
            for field in FIELD_PATTERNS:
                states = [field_status(t, field) for _, t in pages]
                if "FOUND" in states:
                    row[field] = "FOUND"
                elif "REVIEW" in states:
                    row[field] = "REVIEW"
                elif "MISSING" in states:
                    row[field] = "MISSING"
                else:
                    row[field] = "NOT FOUND"
            results.append(row)
        except Exception as e:
            st.error(f"Could not process {up.name}: {e}")

    st.subheader("📊 Transaction Summary")
    missing_docs = [d for d in required if d not in found_types]
    c1, c2, c3 = st.columns(3)
    c1.metric("Documents Uploaded", len(uploads))
    c2.metric("Required Documents Missing", len(missing_docs))
    c3.metric("Fields Requiring Review", sum(
        1 for r in results for k, v in r.items() if v in ("MISSING", "REVIEW")
    ))

    if missing_docs:
        st.error("🔴 Missing required documents: " + ", ".join(missing_docs))
    else:
        st.success("🟢 All selected required document types were detected by filename.")

    # Basic cross-document consistency checks
    st.subheader("🔎 Cross-Document Checks")
    checks = []
    if buyer:
        checks.append(("Buyer name", buyer, buyer.lower() in all_text.lower()))
    if seller:
        checks.append(("Seller name", seller, seller.lower() in all_text.lower()))
    if address:
        checks.append(("Property address", address, address.lower() in all_text.lower()))

    if checks:
        for label, value, ok in checks:
            if ok:
                st.success(f"🟢 {label}: found in extracted text")
            else:
                st.warning(f"🟡 {label}: not found exactly — manually review for formatting/OCR differences")
    else:
        st.info("Enter buyer, seller, and/or property address in the sidebar to run exact cross-document checks.")

    st.subheader("📋 Document-Level Results")
    if results:
        # Display a compact table without pandas dependency.
        import pandas as pd
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download QA Report (CSV)", csv, "transaction_qa_report.csv", "text/csv")

    st.warning("Signature detection is heuristic. Always visually verify signatures, initials, dates, and contractual requirements before marking a transaction complete.")
else:
    st.info("Upload one or more PDFs/images to begin.")
