import io
import re

import fitz
import pytesseract
import streamlit as st
try:
    from openai import OpenAI
except Exception:
    OpenAI = None
from PIL import Image, ImageEnhance, ImageOps, ImageFilter, ImageDraw
from docx import Document

st.set_page_config(page_title="Document Reader & Completeness Checker", page_icon="📄", layout="wide")
st.title("📄 Document Reader & Completeness Checker")
st.caption("Upload a PDF, Word document, or photo. The app identifies the document, reads it, and points you to pages with missing information.")

# Optional AI checklist assistant. Keep the API key in Streamlit Secrets; never hard-code it.
with st.sidebar:
    st.header("🤖 AI Checklist Assistant")
    st.caption("Chat with the assistant to add custom fields/checks to the current document.")
    if OpenAI is None:
        st.warning("AI package is not installed. Add the OpenAI package from requirements.txt.")
    ai_key = st.secrets.get("OPENAI_API_KEY", "") if hasattr(st, "secrets") else ""
    ai_model = st.secrets.get("OPENAI_MODEL", "gpt-5.6-luna") if hasattr(st, "secrets") else "gpt-5.6-luna"
    if not ai_key:
        st.info("AI chat is optional. Add OPENAI_API_KEY in Streamlit Secrets to enable it.")
    if "custom_fields" not in st.session_state:
        st.session_state.custom_fields = {}
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []

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


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def preprocess(img):
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    if max(w, h) < 2200:
        scale = 2200 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(1.35)
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    return img


def ocr_image(img, with_data=False):
    img = preprocess(img)
    gray = ImageOps.grayscale(img)
    candidates = []
    for psm in (6, 11):
        candidates.append((pytesseract.image_to_string(gray, config=f"--oem 3 --psm {psm}"), gray, psm))
    bw = gray.point(lambda p: 255 if p > 175 else 0)
    candidates.append((pytesseract.image_to_string(bw, config="--oem 3 --psm 6"), bw, 6))
    best = max(candidates, key=lambda x: len(clean(x[0])))
    if not with_data:
        return best[0]
    data = pytesseract.image_to_data(best[1], config=f"--oem 3 --psm {best[2]}", output_type=pytesseract.Output.DICT)
    return best[0], best[1], data


def extract_pdf(data):
    doc = fitz.open(stream=data, filetype="pdf")
    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        normalized = clean(text)
        low = normalized.lower()
        needs_ocr = (len(normalized) < 300 or "docusign envelope id:" in low or len(normalized.split()) < 35)
        image = None
        if needs_ocr:
            pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr = ocr_image(image)
            if len(clean(ocr)) > len(normalized) * 1.05:
                text = ocr
        else:
            # Still render the page so the user can jump to it visually.
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pages.append({"page": i, "text": text, "image": image})
    return pages


def extract_image(data):
    img = Image.open(io.BytesIO(data))
    text = ocr_image(img)
    return [{"page": 1, "text": text, "image": preprocess(img)}]


def extract_docx(data):
    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    return [{"page": None, "text": "\n".join(parts), "image": None}]


def extract(up):
    data = up.getvalue()
    name = up.name.lower()
    if name.endswith(".pdf"):
        return extract_pdf(data)
    if name.endswith(".docx"):
        return extract_docx(data)
    return extract_image(data)


def identify_type(filename, text):
    fn = filename.lower(); t = clean(text).lower()
    filename_keys = {"Residential Lease": ["lease", "rental"], "Purchase Agreement": ["purchase agreement", "purchase contract", "sales contract"], "Seller Disclosure": ["seller disclosure", "property disclosure"], "Lead-Based Paint Disclosure": ["lead", "paint disclosure"], "Agency Disclosure": ["agency disclosure"], "Inspection/Repair Addendum": ["repair addendum", "inspection addendum"], "Inspection Report": ["inspection report", "home inspection"], "Appraisal": ["appraisal"], "Title Commitment": ["title commitment", "title report"], "HOA Documents": ["hoa", "homeowners association"], "Closing Disclosure": ["closing disclosure"], "Invoice": ["invoice"], "Authorization": ["authorization"], "Employment Document": ["employment", "offer letter"]}
    for label, keys in filename_keys.items():
        if any(k in fn for k in keys):
            return label
    scores = sorted(((sum(1 for k in keys if k in t), label) for label, keys in TYPE_RULES), reverse=True)
    return scores[0][1] if scores and scores[0][0] >= 2 else "Other"


def field_status(text, field):
    pats = FIELD_PATTERNS.get(field, []); low = text.lower()
    matches = list(re.finditer("|".join(f"(?:{p})" for p in pats), low, re.I)) if pats else []
    if not matches:
        return "NOT FOUND"
    for m in matches:
        tail = clean(text[m.end():m.end()+180]); tail = re.sub(r"^[\s:._\-–—|]+", "", tail)
        if not tail or re.match(r"^(?:_{2,}|\.{4,}|-{4,})", tail): return "MISSING"
        if re.match(r"^(?:buyer|seller|tenant|landlord|property|address|date|signature|initials|monthly rent|security deposit)\b", tail, re.I): return "MISSING"
        if len(tail) >= 2: return "FOUND"
    return "MISSING"


def signature_status(text):
    low = text.lower()
    if not re.search(r"\bsignature\b|signed\s+by|electronic\s+signature", low): return "NOT FOUND"
    if re.search(r"signature\s*[:|]?\s*_{3,}|signature\s*[:|]?\s*\.{5,}|signature\s*[:|]?\s*-{5,}", low): return "MISSING"
    return "REVIEW"


def status_for(text, field):
    return signature_status(text) if field == "Signature" else field_status(text, field)


def field_patterns_regex(field):
    return FIELD_PATTERNS.get(field, [])


def highlight_page(page_image, page_text, fields_to_highlight):
    """Highlight OCR-detected labels for missing/review fields. If labels cannot be located, return original image."""
    if page_image is None or not fields_to_highlight:
        return page_image
    img = page_image.copy().convert("RGB")
    # OCR at image resolution; rectangles are around matched label words/regions.
    try:
        data = pytesseract.image_to_data(preprocess(img), config="--oem 3 --psm 11", output_type=pytesseract.Output.DICT)
        draw = ImageDraw.Draw(img)
        words = []
        for i, word in enumerate(data.get("text", [])):
            w = clean(word)
            if not w: continue
            words.append((w, data["left"][i], data["top"][i], data["width"][i], data["height"][i]))
        for field in fields_to_highlight:
            matched = False
            for pat in field_patterns_regex(field):
                token_pat = re.compile(pat, re.I)
                for idx, (word, x, y, w, h) in enumerate(words):
                    if token_pat.search(word):
                        # Expand to the right to include the blank/value area.
                        right = min(img.width - 5, x + max(w * 5, 500))
                        bottom = min(img.height - 5, y + max(h * 2, 45))
                        draw.rectangle([max(3, x-8), max(3, y-8), right, bottom], outline=(220, 35, 35), width=8)
                        matched = True
                        break
                if matched: break
        return img
    except Exception:
        return img


def issue_locations(pages, fields):
    """Return {page_number: [fields]} for fields whose labels occur on a page and are missing/review."""
    locations = {}
    for field in fields:
        for p in pages:
            if p["page"] is None:
                continue
            status = status_for(p["text"], field)
            if status in ("MISSING", "REVIEW"):
                # Avoid generic labels being counted on every page by requiring the field pattern.
                if any(re.search(pat, p["text"], re.I) for pat in field_patterns_regex(field)):
                    locations.setdefault(p["page"], []).append(field)
    return locations


uploads = st.file_uploader("Upload document(s)", type=["pdf", "docx", "png", "jpg", "jpeg", "webp", "tif", "tiff"], accept_multiple_files=True, help="PDF, Word, and phone/photo images are supported.")

# AI chat area
if ai_key and OpenAI is not None:
    st.markdown("### 🤖 Tell the AI what you want to add")
    st.caption("Examples: “Add Broker Name and Commission to this checklist” or “For leases, also check Pet Deposit and Utilities.”")
    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    prompt = st.chat_input("What would you like the document checker to add?")
    if prompt:
        st.session_state.ai_messages.append({"role": "user", "content": prompt})
        context = {k: v for k, v in st.session_state.custom_fields.items()}
        system = (
            "You are the checklist customization assistant for a document reader. "
            "The user wants to add fields/checks. Extract concise field names from their request. "
            "Return JSON only: {\"action\":\"add_fields\",\"document_type\":\"...\",\"fields\":[\"...\"],\"reply\":\"...\"}. "
            "If the user says a document type, use it; otherwise use Other. Do not invent fields not requested. "
            f"Existing custom fields: {context}"
        )
        try:
            client = OpenAI(api_key=ai_key)
            resp = client.responses.create(model=ai_model, input=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ])
            raw = resp.output_text.strip()
            import json
            result = json.loads(raw)
            if result.get("action") == "add_fields":
                dtype_key = result.get("document_type") or "Other"
                st.session_state.custom_fields.setdefault(dtype_key, [])
                added = []
                for f in result.get("fields", []):
                    f = str(f).strip()
                    if f and f not in st.session_state.custom_fields[dtype_key]:
                        st.session_state.custom_fields[dtype_key].append(f)
                        added.append(f)
                reply = result.get("reply") or ("Added: " + ", ".join(added) if added else "No new fields were added.")
            else:
                reply = "I could not turn that request into checklist fields. Try: ‘Add Broker Name and Commission to Purchase Agreement.’"
        except Exception as e:
            reply = f"AI chat error: {e}"
        st.session_state.ai_messages.append({"role": "assistant", "content": reply})
        st.rerun()

if not uploads:
    st.info("Upload a PDF, DOCX, or photo. Results appear directly on this page.")
else:
    for up in uploads:
        with st.container(border=True):
            try:
                pages = extract(up)
                full_text = "\n".join(p["text"] for p in pages)
                dtype = identify_type(up.name, full_text)
                fields = list(DOC_FIELDS.get(dtype, DOC_FIELDS["Other"]))
                custom = st.session_state.custom_fields.get(dtype, [])
                for f in custom:
                    if f not in fields:
                        fields.append(f)
                statuses = {f: status_for(full_text, f) for f in fields}
                missing = [f for f, s in statuses.items() if s == "MISSING"]
                nf = [f for f, s in statuses.items() if s == "NOT FOUND"]
                review = [f for f, s in statuses.items() if s == "REVIEW"]

                st.markdown(f"### 📄 {up.name}")
                st.write(f"**Identified document:** {dtype}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Missing", len(missing)); c2.metric("Not detected", len(nf)); c3.metric("Needs review", len(review))

                if missing: st.error("🔴 Missing: " + ", ".join(missing))
                if nf: st.warning("🟡 Not detected: " + ", ".join(nf))
                if review: st.info("🔎 Needs review: " + ", ".join(review) + " (verify visually)")

                # Page navigator for PDFs/photos. Missing/review fields are mapped to the pages where their labels appear.
                locations = issue_locations(pages, fields)
                if locations:
                    st.markdown("#### 📍 Pages to check")
                    st.caption("Click a page below to open it. Missing/review fields are highlighted in red.")
                    page_cols = st.columns(min(5, max(1, len(locations))))
                    for idx, (page_num, page_fields) in enumerate(sorted(locations.items())):
                        label = f"Page {page_num} · {len(page_fields)} issue" + ("s" if len(page_fields) != 1 else "")
                        key = f"page_{up.name}_{page_num}"
                        if page_cols[idx % len(page_cols)].button(label, key=key, use_container_width=True):
                            st.session_state[f"open_page_{up.name}"] = page_num

                    open_page = st.session_state.get(f"open_page_{up.name}")
                    if open_page:
                        target = next((p for p in pages if p["page"] == open_page), None)
                        if target and target["image"] is not None:
                            marked = highlight_page(target["image"], target["text"], locations.get(open_page, []))
                            st.markdown(f"**Page {open_page} — highlighted issues: {', '.join(locations.get(open_page, []))}**")
                            st.image(marked, use_container_width=True)
                elif missing or review:
                    st.info("The app found an issue but could not reliably map it to a page. Review the document text below.")

                st.dataframe([{"Item": f, "Status": s} for f, s in statuses.items()], use_container_width=True, hide_index=True)
                with st.expander("Show extracted text"):
                    st.text_area("Document text", full_text[:30000], height=260, key=f"text_{up.name}")
            except Exception as e:
                st.error(f"Could not read {up.name}: {e}")

st.caption("Screening tool only. OCR and document interpretation can require human verification; signature detection is not proof of execution. AI checklist customization is optional and requires your own OpenAI API key.")
