import io
import re

import fitz
import pytesseract
import streamlit as st
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from docx import Document

st.set_page_config(page_title="Document Reader & Completeness Checker", page_icon="📄", layout="wide")
st.title("📄 Document Reader & Completeness Checker")
st.caption("Upload a PDF, Word document, or photo. The app identifies the document, reads it, and shows missing items on the page.")

DOC_FIELDS = {
    "Purchase Agreement": ["Buyer Name", "Seller Name", "Property Address", "Purchase Price", "Contract Date", "Closing Date", "Signature"],
    "Residential Lease": ["Tenant Name", "Landlord Name", "Property Address", "Lease Start Date", "Lease End Date", "Monthly Rent", "Security Deposit", "Signature"],
    "Seller Disclosure": ["Seller Name", "Property Address", "Signature"],
    "Lead-Based Paint Disclosure": ["Buyer Name", "Seller Name", "Property Address", "Signature"],
    "Agency Disclosure": ["Buyer Name", "Seller Name", "Property Address", "Signature"],
    "Inspection Report": ["Property Address", "Inspection Date"],
    "Inspection/Repair Addendum": ["Buyer Name", "Seller Name", "Property Address", "Repair Terms", "Signature"],
    "Appraisal": ["Property Address", "Appraisal Date", "Appraised Value"],
    "Title Commitment": ["Property Address", "Effective Date", "Owner Name"],
    "HOA Documents": ["Property Address", "Association Name"],
    "Closing Disclosure": ["Buyer Name", "Seller Name", "Property Address", "Closing Date", "Loan Amount"],
    "Invoice": ["Invoice Number", "Invoice Date", "Bill To", "Amount Due"],
    "Authorization": ["Authorized Person", "Purpose", "Effective Date", "Signature"],
    "Employment Document": ["Employee Name", "Employer Name", "Effective Date", "Signature"],
    "Other": ["Name", "Address", "Date", "Signature"],
}

FIELD_PATTERNS = {
    "Buyer Name": [r"\bbuyer\b", r"\bpurchaser\b"], "Seller Name": [r"\bseller\b", r"\bvendor\b"],
    "Tenant Name": [r"\btenant\b", r"\blessee\b", r"\brenter\b"], "Landlord Name": [r"\blandlord\b", r"\blessor\b"],
    "Property Address": [r"property\s+address", r"subject\s+property", r"rental\s+property", r"premises"],
    "Purchase Price": [r"purchase\s+price", r"sales?\s+price", r"purchase\s+amount"],
    "Contract Date": [r"contract\s+date", r"execution\s+date", r"effective\s+date"],
    "Closing Date": [r"closing\s+date", r"settlement\s+date"],
    "Lease Start Date": [r"lease\s+(?:start|commencement)\s+date", r"commencement\s+date", r"term\s+begins?"],
    "Lease End Date": [r"lease\s+(?:end|expiration)\s+date", r"expiration\s+date", r"term\s+ends?"],
    "Monthly Rent": [r"monthly\s+rent", r"rent\s+per\s+month", r"base\s+rent"], "Security Deposit": [r"security\s+deposit"],
    "Inspection Date": [r"inspection\s+date"], "Repair Terms": [r"repair(?:s)?", r"repair\s+terms"],
    "Appraisal Date": [r"appraisal\s+date", r"effective\s+date"], "Appraised Value": [r"appraised\s+value", r"opinion\s+of\s+value"],
    "Effective Date": [r"effective\s+date", r"effective\s+as\s+of"], "Owner Name": [r"owner(?:'s)?\s+name", r"vested\s+owner"],
    "Association Name": [r"association\s+name", r"homeowners?\s+association", r"\bhoa\b"], "Loan Amount": [r"loan\s+amount", r"principal\s+amount"],
    "Invoice Number": [r"invoice\s*(?:number|#)", r"invoice\s+no"], "Invoice Date": [r"invoice\s+date", r"date\s+of\s+invoice"],
    "Bill To": [r"bill\s+to", r"billed\s+to"], "Amount Due": [r"amount\s+due", r"balance\s+due", r"total\s+due"],
    "Authorized Person": [r"authorized\s+person", r"authorized\s+by"], "Purpose": [r"purpose", r"reason\s+for"],
    "Employee Name": [r"employee(?:'s)?\s+name", r"employee"], "Employer Name": [r"employer(?:'s)?\s+name", r"employer"],
    "Name": [r"\bname\b", r"full\s+name"], "Address": [r"\baddress\b"], "Date": [r"\bdate\b"],
    "Signature": [r"\bsignature\b", r"signed\s+by", r"authorized\s+signature", r"electronic\s+signature"],
}

TYPE_RULES = [
    ("Residential Lease", ["residential lease", "lease agreement", "rental agreement", "landlord", "tenant", "lessor", "lessee"]),
    ("Purchase Agreement", ["purchase agreement", "purchase contract", "sales contract", "real estate purchase contract", "contract for sale and purchase", "florida realtors"]),
    ("Seller Disclosure", ["seller disclosure", "property disclosure", "seller's disclosure"]),
    ("Lead-Based Paint Disclosure", ["lead-based paint", "lead based paint", "lead paint disclosure"]),
    ("Agency Disclosure", ["agency disclosure", "agency relationship", "disclosure of agency"]),
    ("Inspection/Repair Addendum", ["repair addendum", "inspection addendum", "repair amendment"]),
    ("Inspection Report", ["inspection report", "home inspection", "property inspection"]),
    ("Appraisal", ["appraisal report", "appraisal", "appraised value"]), ("Title Commitment", ["title commitment", "title report", "commitment for title"]),
    ("HOA Documents", ["homeowners association", "homeowners' association", "hoa"]), ("Closing Disclosure", ["closing disclosure", "closing disclosure statement", "loan estimate"]),
    ("Invoice", ["invoice", "amount due", "bill to"]), ("Authorization", ["authorization", "authorized by", "authorization form"]),
    ("Employment Document", ["employment agreement", "offer letter", "employment contract"]),
]

def clean(text): return re.sub(r"\s+", " ", text or "").strip()

def preprocess(img):
    img = ImageOps.exif_transpose(img).convert("RGB")
    # Upscale small phone photos/screenshots so OCR has enough character detail.
    w, h = img.size
    if max(w, h) < 2200:
        scale = 2200 / max(w, h)
        img = img.resize((int(w*scale), int(h*scale)), Image.Resampling.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(1.35)
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    return img

def ocr_image(img):
    img = preprocess(img)
    gray = ImageOps.grayscale(img)
    # Two layouts improve results for both full-page forms and sparse phone photos.
    results = []
    for psm in (6, 11):
        results.append(pytesseract.image_to_string(gray, config=f"--oem 3 --psm {psm}"))
    # A thresholded pass helps faint/gray text.
    bw = gray.point(lambda p: 255 if p > 175 else 0)
    results.append(pytesseract.image_to_string(bw, config="--oem 3 --psm 6"))
    return max(results, key=lambda x: len(clean(x))) if results else ""

def extract_pdf(data):
    doc = fitz.open(stream=data, filetype="pdf")
    pages=[]
    for page in doc:
        text = page.get_text("text") or ""
        normalized=clean(text); low=normalized.lower()
        needs_ocr=(len(normalized)<300 or "docusign envelope id:" in low or len(normalized.split())<35)
        if needs_ocr:
            pix=page.get_pixmap(matrix=fitz.Matrix(2.5,2.5), alpha=False)
            img=Image.frombytes("RGB", [pix.width,pix.height], pix.samples)
            ocr=ocr_image(img)
            if len(clean(ocr)) > len(normalized)*1.25:
                text=ocr
        pages.append(text)
    return "\n".join(pages)

def extract_image(data):
    return ocr_image(Image.open(io.BytesIO(data)))

def extract_docx(data):
    doc=Document(io.BytesIO(data)); parts=[p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows: parts.append(" | ".join(c.text for c in row.cells))
    return "\n".join(parts)

def extract(up):
    data=up.getvalue(); name=up.name.lower()
    if name.endswith('.pdf'): return extract_pdf(data)
    if name.endswith('.docx'): return extract_docx(data)
    return extract_image(data)

def identify_type(filename,text):
    fn=filename.lower(); t=clean(text).lower()
    filename_keys={"Residential Lease":["lease","rental"],"Purchase Agreement":["purchase agreement","purchase contract","sales contract"],"Seller Disclosure":["seller disclosure","property disclosure"],"Lead-Based Paint Disclosure":["lead","paint disclosure"],"Agency Disclosure":["agency disclosure"],"Inspection/Repair Addendum":["repair addendum","inspection addendum"],"Inspection Report":["inspection report","home inspection"],"Appraisal":["appraisal"],"Title Commitment":["title commitment","title report"],"HOA Documents":["hoa","homeowners association"],"Closing Disclosure":["closing disclosure"],"Invoice":["invoice"],"Authorization":["authorization"],"Employment Document":["employment","offer letter"]}
    for label,keys in filename_keys.items():
        if any(k in fn for k in keys): return label
    scores=sorted(((sum(1 for k in keys if k in t),label) for label,keys in TYPE_RULES), reverse=True)
    return scores[0][1] if scores and scores[0][0]>=2 else "Other"

def field_status(text,field):
    pats=FIELD_PATTERNS.get(field,[]); low=text.lower()
    matches=list(re.finditer("|".join(f"(?:{p})" for p in pats),low,re.I)) if pats else []
    if not matches: return "NOT FOUND"
    for m in matches:
        tail=clean(text[m.end():m.end()+180]); tail=re.sub(r"^[\s:._\-–—|]+","",tail)
        if not tail or re.match(r"^(?:_{2,}|\.{4,}|-{4,})",tail): return "MISSING"
        if re.match(r"^(?:buyer|seller|tenant|landlord|property|address|date|signature|initials|monthly rent|security deposit)\b",tail,re.I): return "MISSING"
        if len(tail)>=2: return "FOUND"
    return "MISSING"

def signature_status(text):
    low=text.lower()
    if not re.search(r"\bsignature\b|signed\s+by|electronic\s+signature",low): return "NOT FOUND"
    if re.search(r"signature\s*[:|]?\s*_{3,}|signature\s*[:|]?\s*\.{5,}|signature\s*[:|]?\s*-{5,}",low): return "MISSING"
    return "REVIEW"

def status_for(text,field): return signature_status(text) if field=="Signature" else field_status(text,field)

uploads=st.file_uploader("Upload document(s)",type=["pdf","docx","png","jpg","jpeg","webp","tif","tiff"],accept_multiple_files=True,help="PDF, Word, and phone/photo images are supported.")
if not uploads:
    st.info("Upload a PDF, DOCX, or photo. Results appear directly on this page.")
else:
    for up in uploads:
        with st.container(border=True):
            try:
                text=extract(up); dtype=identify_type(up.name,text); fields=DOC_FIELDS.get(dtype,DOC_FIELDS["Other"])
                statuses={f:status_for(text,f) for f in fields}; missing=[f for f,s in statuses.items() if s=="MISSING"]; nf=[f for f,s in statuses.items() if s=="NOT FOUND"]; review=[f for f,s in statuses.items() if s=="REVIEW"]
                st.markdown(f"### 📄 {up.name}"); st.write(f"**Identified document:** {dtype}")
                c1,c2,c3=st.columns(3); c1.metric("Missing",len(missing)); c2.metric("Not detected",len(nf)); c3.metric("Needs review",len(review))
                if missing: st.error("🔴 Missing: "+", ".join(missing))
                if nf: st.warning("🟡 Not detected: "+", ".join(nf))
                if review: st.info("🔎 Needs review: "+", ".join(review)+" (verify visually)")
                if not missing and not nf and not review: st.success("🟢 All applicable items were detected.")
                st.dataframe([{"Item":f,"Status":s} for f,s in statuses.items()],use_container_width=True,hide_index=True)
                with st.expander("Show extracted text"):
                    st.text_area("Document text",text[:30000],height=260,key=f"text_{up.name}")
            except Exception as e:
                st.error(f"Could not read {up.name}: {e}")

st.caption("Screening tool only. OCR and document interpretation can require human verification; signature detection is not proof of execution.")
