import streamlit as st
import pandas as pd
import re
import io
import os
import textwrap
from typing import List, Dict, Tuple

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 OBE Assessment Alignment Checker")
st.caption(
    "Evaluate assessment questions for Subject Relevance, CLO, PLO, "
    "Bloom's Taxonomy, Specificity and Question Quality."
)

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

FITZ_AVAILABLE = False
PYPDF_AVAILABLE = False
PDFPLUMBER_AVAILABLE = False
DOCX_AVAILABLE = False
OPENPYXL_AVAILABLE = False
PYTESSERACT_AVAILABLE = False
PIL_AVAILABLE = False

try:
    import fitz
    FITZ_AVAILABLE = True
except Exception:
    pass

try:
    import pypdf
    PYPDF_AVAILABLE = True
except Exception:
    pass

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except Exception:
    pass

try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    pass

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except Exception:
    pass

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except Exception:
    pass

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    pass


# ============================================================
# SESSION STATE
# ============================================================

if "questions" not in st.session_state:
    st.session_state.questions = []

if "evaluations" not in st.session_state:
    st.session_state.evaluations = []

if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""

if "reader_used" not in st.session_state:
    st.session_state.reader_used = ""

if "manual_questions" not in st.session_state:
    st.session_state.manual_questions = ""


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)

    # Normalize common PDF artifacts
    text = text.replace("\x00", " ")
    text = text.replace("\ufeff", "")
    text = text.replace("\u00ad", "")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    text = text.replace("‘", "'")
    text = text.replace("’", "'")

    # Repair words split by PDF line wrapping:
    # "computa-\ntion" -> "computation"
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)

    # Normalize spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Keep line structure
    text = re.sub(r"\n[ \t]+", "\n", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_question(q: str) -> str:
    q = clean_text(q)

    # Remove obvious numbering at beginning
    q = re.sub(
        r"^\s*(?:question\s*)?(?:q[\s._-]*)?\(?\d+\)?\s*[\.:)\-]?\s*",
        "",
        q,
        flags=re.IGNORECASE
    )

    q = re.sub(r"^\s*[-•●▪◦]\s*", "", q)

    q = re.sub(r"\s+", " ", q).strip()

    return q


def is_noise_line(line: str) -> bool:
    s = clean_text(line)

    if not s:
        return True

    low = s.lower()

    noise_phrases = [
        "student name",
        "student id",
        "roll no",
        "roll number",
        "registration no",
        "registration number",
        "course code",
        "course title",
        "teacher name",
        "instructor name",
        "semester",
        "section",
        "date:",
        "total marks",
        "time allowed",
        "instructions",
        "instruction:",
        "answer all questions",
        "attempt all questions",
        "department",
        "university",
        "name:",
        "signature:",
        "marks:",
        "page ",
    ]

    for phrase in noise_phrases:
        if low.startswith(phrase):
            return True

    # Very short administrative lines
    if len(s) < 12:
        return True

    return False


def looks_like_question(text: str) -> bool:
    if not text:
        return False

    q = normalize_question(text)

    if len(q) < 15:
        return False

    if is_noise_line(q):
        return False

    low = q.lower()

    question_words = [
        "what ",
        "why ",
        "how ",
        "when ",
        "where ",
        "which ",
        "who ",
        "define ",
        "explain ",
        "describe ",
        "discuss ",
        "compare ",
        "contrast ",
        "analyze ",
        "analyse ",
        "evaluate ",
        "assess ",
        "justify ",
        "identify ",
        "calculate ",
        "compute ",
        "determine ",
        "derive ",
        "solve ",
        "illustrate ",
        "demonstrate ",
        "design ",
        "develop ",
        "differentiate ",
        "interpret ",
        "classify ",
        "state ",
        "list ",
        "mention ",
        "write ",
        "give ",
        "select ",
        "choose ",
        "construct ",
        "apply ",
    ]

    if "?" in q:
        return True

    for word in question_words:
        if low.startswith(word):
            return True

    # Numbered question text
    if re.match(
        r"^(?:question\s*)?(?:q[\s._-]*)?\d+\s*[\.:)\-]",
        text.strip(),
        flags=re.IGNORECASE
    ):
        return len(q) >= 15

    # If it is a reasonably long assessment sentence,
    # allow it as a candidate.
    if len(q) >= 35:
        return True

    return False


# ============================================================
# PDF EXTRACTION
# ============================================================

def extract_pdf_fitz(file_bytes: bytes) -> Tuple[str, str, int]:
    if not FITZ_AVAILABLE:
        return "", "", 0

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []

        for page in doc:
            txt = page.get_text("text")
            if txt:
                pages.append(txt)

        text = "\n\n".join(pages)
        return clean_text(text), "PyMuPDF / fitz", len(doc)

    except Exception:
        return "", "", 0


def extract_pdf_pypdf(file_bytes: bytes) -> Tuple[str, str, int]:
    if not PYPDF_AVAILABLE:
        return "", "", 0

    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))

        pages = []

        for page in reader.pages:
            try:
                txt = page.extract_text()
            except Exception:
                txt = ""

            if txt:
                pages.append(txt)

        text = "\n\n".join(pages)

        return clean_text(text), "pypdf", len(reader.pages)

    except Exception:
        return "", "", 0


def extract_pdf_pdfplumber(file_bytes: bytes) -> Tuple[str, str, int]:
    if not PDFPLUMBER_AVAILABLE:
        return "", "", 0

    try:
        pages = []

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()

                if txt:
                    pages.append(txt)

        text = "\n\n".join(pages)

        return clean_text(text), "pdfplumber", len(pages)

    except Exception:
        return "", "", 0


def extract_pdf_ocr(file_bytes: bytes) -> Tuple[str, str, int]:
    """
    OCR fallback.

    Uses PyMuPDF to render pages and pytesseract if available.
    """

    if not FITZ_AVAILABLE or not PYTESSERACT_AVAILABLE or not PIL_AVAILABLE:
        return "", "", 0

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        pages = []

        for page in doc:
            pix = page.get_pixmap(
                matrix=fitz.Matrix(2, 2),
                alpha=False
            )

            img_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes))

            txt = pytesseract.image_to_string(image)

            if txt:
                pages.append(txt)

        text = "\n\n".join(pages)

        return clean_text(text), "OCR / Tesseract", len(doc)

    except Exception:
        return "", "", 0


def read_pdf(file_bytes: bytes) -> Tuple[str, str, int]:
    """
    Try every available PDF extraction method.
    """

    methods = [
        extract_pdf_fitz,
        extract_pdf_pypdf,
        extract_pdf_pdfplumber,
        extract_pdf_ocr,
    ]

    best_text = ""
    best_reader = ""
    best_pages = 0

    for method in methods:
        text, reader, pages = method(file_bytes)

        if len(text) > len(best_text):
            best_text = text
            best_reader = reader
            best_pages = pages

    return best_text, best_reader, best_pages


# ============================================================
# DOCX EXTRACTION
# ============================================================

def read_docx(file_bytes: bytes) -> Tuple[str, str, int]:

    if not DOCX_AVAILABLE:
        return "", "", 0

    try:
        doc = Document(io.BytesIO(file_bytes))

        chunks = []

        for p in doc.paragraphs:
            txt = p.text.strip()

            if txt:
                chunks.append(txt)

        for table in doc.tables:
            for row in table.rows:
                row_values = []

                for cell in row.cells:
                    value = cell.text.strip()

                    if value:
                        row_values.append(value)

                if row_values:
                    chunks.append(" | ".join(row_values))

        text = "\n".join(chunks)

        return clean_text(text), "python-docx", len(doc.paragraphs)

    except Exception:
        return "", "", 0


# ============================================================
# EXCEL / CSV / TXT EXTRACTION
# ============================================================

def read_excel(file_bytes: bytes) -> Tuple[str, str, int]:

    if not OPENPYXL_AVAILABLE:
        try:
            excel = pd.ExcelFile(io.BytesIO(file_bytes))
        except Exception:
            return "", "", 0
    else:
        try:
            excel = pd.ExcelFile(io.BytesIO(file_bytes))
        except Exception:
            return "", "", 0

    chunks = []

    try:
        for sheet in excel.sheet_names:

            try:
                df = pd.read_excel(
                    io.BytesIO(file_bytes),
                    sheet_name=sheet,
                    header=None
                )
            except Exception:
                continue

            chunks.append(f"--- Sheet: {sheet} ---")

            for _, row in df.iterrows():

                values = []

                for value in row.tolist():

                    if pd.isna(value):
                        continue

                    value = str(value).strip()

                    if value:
                        values.append(value)

                if values:
                    chunks.append(" | ".join(values))

        text = "\n".join(chunks)

        return clean_text(text), "Excel / pandas", len(excel.sheet_names)

    except Exception:
        return "", "", 0


def read_csv(file_bytes: bytes) -> Tuple[str, str, int]:

    encodings = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin-1"
    ]

    for enc in encodings:

        try:
            text = file_bytes.decode(enc)

            # First try normal CSV parsing
            try:
                df = pd.read_csv(io.StringIO(text), header=None)

                chunks = []

                for _, row in df.iterrows():

                    values = []

                    for value in row.tolist():

                        if pd.isna(value):
                            continue

                        value = str(value).strip()

                        if value:
                            values.append(value)

                    if values:
                        chunks.append(" | ".join(values))

                final_text = "\n".join(chunks)

                if final_text.strip():
                    return clean_text(final_text), "CSV / pandas", len(df)

            except Exception:
                pass

            return clean_text(text), f"CSV / {enc}", 0

        except Exception:
            continue

    return "", "", 0


def read_txt(file_bytes: bytes) -> Tuple[str, str, int]:

    encodings = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin-1"
    ]

    for enc in encodings:

        try:
            text = file_bytes.decode(enc)

            if text.strip():
                return clean_text(text), f"TXT / {enc}", 0

        except Exception:
            continue

    return "", "", 0


# ============================================================
# MASTER FILE READER
# ============================================================

def read_uploaded_file(uploaded_file) -> Tuple[str, str, int]:

    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.getvalue()

    if filename.endswith(".pdf"):
        return read_pdf(file_bytes)

    if filename.endswith(".docx"):
        return read_docx(file_bytes)

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        return read_excel(file_bytes)

    if filename.endswith(".csv"):
        return read_csv(file_bytes)

    if filename.endswith(".txt"):
        return read_txt(file_bytes)

    # Generic fallback
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:

        try:
            text = file_bytes.decode(encoding)

            if text.strip():
                return clean_text(text), f"Generic text / {encoding}", 0

        except Exception:
            pass

    return "", "", 0


# ============================================================
# QUESTION EXTRACTION
# ============================================================

NUMBER_PATTERN = re.compile(
    r"""
    (?im)
    (?P<prefix>
        ^\s*
        (?:
            question\s*
            |
            q\s*
        )?
        \(?\d+\)?
        \s*
        [\.\):\-]
        \s*
    )
    """,
    re.VERBOSE
)


def extract_numbered_questions(text: str) -> List[str]:

    if not text:
        return []

    matches = list(NUMBER_PATTERN.finditer(text))

    if not matches:
        return []

    questions = []

    for i, match in enumerate(matches):

        start = match.end()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        block = text[start:end].strip()

        if not block:
            continue

        block = re.sub(r"\s*\n\s*", " ", block)
        block = re.sub(r"\s+", " ", block).strip()

        # Remove common trailing marks/marks allocations
        block = re.sub(r"\s+\(\s*\d+\s*marks?\s*\)\s*$", "", block, flags=re.I)
        block = re.sub(r"\s+\[\s*\d+\s*marks?\s*\]\s*$", "", block, flags=re.I)

        if looks_like_question(block):
            questions.append(normalize_question(block))

    return questions


def extract_question_mark_questions(text: str) -> List[str]:

    if not text:
        return []

    lines = [clean_text(x) for x in text.splitlines()]

    questions = []

    current = ""

    for line in lines:

        if not line:
            continue

        if is_noise_line(line):
            continue

        current = f"{current} {line}".strip()

        # A complete question
        if "?" in line:

            parts = re.split(r"(?<=\?)\s+", current)

            for part in parts:

                part = normalize_question(part)

                if looks_like_question(part):
                    questions.append(part)

            current = ""

    return questions


def extract_bullets(text: str) -> List[str]:

    if not text:
        return []

    questions = []

    for line in text.splitlines():

        line = clean_text(line)

        if not line:
            continue

        if re.match(r"^\s*[-•●▪◦*]\s+", line):

            q = re.sub(
                r"^\s*[-•●▪◦*]\s+",
                "",
                line
            ).strip()

            if looks_like_question(q):
                questions.append(normalize_question(q))

    return questions


def extract_candidate_blocks(text: str) -> List[str]:

    """
    Extremely permissive fallback.

    If the document contains readable text but no obvious
    question numbering, meaningful paragraphs are treated
    as candidate assessment items.
    """

    if not text:
        return []

    blocks = re.split(r"\n\s*\n+", text)

    candidates = []

    for block in blocks:

        block = clean_text(block)

        if not block:
            continue

        # Remove obvious header material
        lines = []

        for line in block.splitlines():

            line = clean_text(line)

            if not line:
                continue

            if is_noise_line(line):
                continue

            lines.append(line)

        if not lines:
            continue

        block = " ".join(lines)
        block = re.sub(r"\s+", " ", block).strip()

        if len(block) < 20:
            continue

        # Avoid pure metadata
        if not looks_like_question(block):
            # If sufficiently long, still treat as a possible
            # assessment prompt.
            if len(block) < 45:
                continue

        candidates.append(normalize_question(block))

    return candidates


def extract_line_candidates(text: str) -> List[str]:

    """
    Last-resort extraction.

    This is deliberately permissive so the application does
    not fail simply because a PDF uses an unusual layout.
    """

    if not text:
        return []

    candidates = []

    for line in text.splitlines():

        line = clean_text(line)

        if not line:
            continue

        if is_noise_line(line):
            continue

        line = normalize_question(line)

        if len(line) >= 20:

            # Skip obvious page headings
            low = line.lower()

            if low in [
                "answer key",
                "multiple choice questions",
                "short questions",
                "long questions",
                "objective",
                "subjective",
                "section a",
                "section b",
                "section c",
            ]:
                continue

            candidates.append(line)

    return candidates


def deduplicate_questions(questions: List[str]) -> List[str]:

    result = []
    seen = set()

    for q in questions:

        q = normalize_question(q)

        if not q:
            continue

        # Clean multiple spaces
        q = re.sub(r"\s+", " ", q).strip()

        key = q.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(q)

    return result


def extract_questions(text: str) -> List[str]:

    if not text or len(text.strip()) < 5:
        return []

    all_questions = []

    # --------------------------------------------------------
    # METHOD 1: Numbered questions
    # --------------------------------------------------------

    all_questions.extend(
        extract_numbered_questions(text)
    )

    # --------------------------------------------------------
    # METHOD 2: Question marks
    # --------------------------------------------------------

    all_questions.extend(
        extract_question_mark_questions(text)
    )

    # --------------------------------------------------------
    # METHOD 3: Bullets
    # --------------------------------------------------------

    all_questions.extend(
        extract_bullets(text)
    )

    # --------------------------------------------------------
    # If structured extraction worked, use it
    # --------------------------------------------------------

    all_questions = deduplicate_questions(all_questions)

    if len(all_questions) >= 1:
        return all_questions

    # --------------------------------------------------------
    # METHOD 4: Paragraph fallback
    # --------------------------------------------------------

    all_questions.extend(
        extract_candidate_blocks(text)
    )

    all_questions = deduplicate_questions(all_questions)

    if all_questions:
        return all_questions

    # --------------------------------------------------------
    # METHOD 5: Line fallback
    # --------------------------------------------------------

    all_questions.extend(
        extract_line_candidates(text)
    )

    return deduplicate_questions(all_questions)


# ============================================================
# CLO / PLO INPUT
# ============================================================

st.sidebar.header("OBE Information")

course = st.sidebar.text_input(
    "Course / Subject",
    value="General Course"
)

clo_text = st.sidebar.text_area(
    "Course Learning Outcomes (CLOs)",
    value=(
        "CLO 1: Demonstrate understanding of key concepts.\n"
        "CLO 2: Apply appropriate concepts and methods to solve problems.\n"
        "CLO 3: Analyze information and communicate conclusions clearly."
    ),
    height=180
)

plo_text = st.sidebar.text_area(
    "Program Learning Outcomes (PLOs)",
    value=(
        "PLO 1: Apply knowledge of the discipline.\n"
        "PLO 2: Analyze and solve problems using appropriate methods.\n"
        "PLO 3: Communicate ideas effectively."
    ),
    height=180
)

bloom_target = st.sidebar.selectbox(
    "Target Bloom's Level",
    [
        "Remember",
        "Understand",
        "Apply",
        "Analyze",
        "Evaluate",
        "Create"
    ],
    index=2
)


# ============================================================
# BLOOM KEYWORDS
# ============================================================

BLOOM_VERBS = {
    "Remember": [
        "define",
        "list",
        "name",
        "identify",
        "state",
        "recall",
        "recognize",
        "label",
        "mention"
    ],

    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "classify",
        "discuss",
        "illustrate",
        "outline"
    ],

    "Apply": [
        "apply",
        "calculate",
        "solve",
        "use",
        "demonstrate",
        "implement",
        "execute",
        "compute",
        "construct"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "categorize",
        "investigate",
        "deconstruct"
    ],

    "Evaluate": [
        "evaluate",
        "assess",
        "justify",
        "critique",
        "defend",
        "judge",
        "appraise",
        "validate"
    ],

    "Create": [
        "design",
        "develop",
        "create",
        "formulate",
        "construct",
        "produce",
        "propose",
        "generate"
    ]
}


BLOOM_LEVELS = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6
}


# ============================================================
# CLO / PLO PARSING
# ============================================================

def parse_outcomes(text: str, prefix: str) -> List[Dict]:

    outcomes = []

    if not text:
        return outcomes

    lines = text.splitlines()

    for i, line in enumerate(lines, start=1):

        line = clean_text(line)

        if not line:
            continue

        # Accept:
        # CLO 1:
        # CLO1:
        # 1:
        # PLO 2:
        match = re.match(
            rf"^\s*(?:{prefix}\s*)?(\d+)\s*[\.\:\-\)]?\s*(.*)$",
            line,
            flags=re.IGNORECASE
        )

        if match:

            number = match.group(1)
            description = match.group(2).strip()

            if description:

                outcomes.append({
                    "id": f"{prefix} {number}",
                    "text": description,
                    "tokens": content_tokens(description)
                })

    # If no numbered outcomes, use each non-empty line
    if not outcomes:

        for i, line in enumerate(lines, start=1):

            line = clean_text(line)

            if len(line) >= 10:

                outcomes.append({
                    "id": f"{prefix} {i}",
                    "text": line,
                    "tokens": content_tokens(line)
                })

    return outcomes


def content_tokens(text: str) -> List[str]:

    if not text:
        return []

    stopwords = {
        "the",
        "and",
        "or",
        "of",
        "to",
        "a",
        "an",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "using",
        "use",
        "apply",
        "demonstrate",
        "understand",
        "understanding",
        "ability",
        "students",
        "student",
        "course",
        "learners",
        "learning",
        "will",
        "be",
        "able",
        "develop",
        "developing",
        "appropriate",
        "effectively",
        "effectively"
    }

    words = re.findall(
        r"[A-Za-z][A-Za-z0-9\-]{2,}",
        text.lower()
    )

    return [
        w for w in words
        if w not in stopwords
    ]


# ============================================================
# SUBJECT / TOPIC EXTRACTION
# ============================================================

def question_tokens(text: str) -> List[str]:

    return content_tokens(text)


def overlap_score(question: str, outcome: str) -> float:

    q_tokens = set(question_tokens(question))
    o_tokens = set(content_tokens(outcome))

    if not q_tokens or not o_tokens:
        return 0.0

    intersection = q_tokens.intersection(o_tokens)

    # Jaccard-like but weighted toward outcome coverage
    outcome_coverage = len(intersection) / max(len(o_tokens), 1)

    question_coverage = len(intersection) / max(len(q_tokens), 1)

    score = (
        outcome_coverage * 70
        + question_coverage * 30
    )

    return min(100.0, score)


def best_outcome(question: str, outcomes: List[Dict]) -> Tuple[Dict, float]:

    if not outcomes:

        return {
            "id": "Not provided",
            "text": "No outcome provided",
            "tokens": []
        }, 0.0

    scores = []

    for outcome in outcomes:

        score = overlap_score(
            question,
            outcome["text"]
        )

        scores.append(
            (score, outcome)
        )

    scores.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return scores[0][1], scores[0][0]


# ============================================================
# SUBJECT RELEVANCE
# ============================================================

def subject_score(question: str, course: str, outcomes: List[Dict]) -> float:

    q = question.lower()
    course_words = content_tokens(course)

    # If course name has meaningful words
    course_overlap = 0

    if course_words:

        q_words = set(question_tokens(question))

        overlap = set(course_words).intersection(q_words)

        course_overlap = len(overlap) / max(
            len(set(course_words)),
            1
        )

    outcome_scores = []

    for outcome in outcomes:

        outcome_scores.append(
            overlap_score(
                question,
                outcome["text"]
            )
        )

    outcome_match = max(
        outcome_scores,
        default=0
    )

    # Outcome terminology is strong evidence of subject relevance.
    score = max(
        outcome_match,
        course_overlap * 100
    )

    # Generic academic questions get a reasonable baseline
    # when a course is not specific enough.
    if score == 0 and len(q) > 30:
        score = 55

    return round(min(100, score), 1)


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question: str) -> Tuple[str, float]:

    q = question.lower()

    detected = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                q
            ):
                detected.append(
                    (
                        BLOOM_LEVELS[level],
                        level
                    )
                )

    if not detected:
        return "Unclear", 45.0

    # Highest detected cognitive level
    detected.sort(
        key=lambda x: x[0],
        reverse=True
    )

    level = detected[0][1]

    return level, 100.0


def bloom_score(question: str, target: str) -> float:

    detected, confidence = detect_bloom(question)

    if detected == "Unclear":
        return 45.0

    if detected == target:
        return 100.0

    actual_level = BLOOM_LEVELS.get(
        detected,
        1
    )

    target_level = BLOOM_LEVELS.get(
        target,
        3
    )

    distance = abs(
        actual_level - target_level
    )

    if distance == 1:
        return 80.0

    if distance == 2:
        return 65.0

    if distance == 3:
        return 50.0

    return 40.0


# ============================================================
# SPECIFICITY
# ============================================================

def specificity_score(question: str) -> float:

    q = question.lower()

    score = 50

    if len(question) >= 40:
        score += 10

    if len(question) >= 70:
        score += 10

    specific_terms = [
        "using",
        "given",
        "based on",
        "from the",
        "for the",
        "in the",
        "calculate",
        "compare",
        "contrast",
        "analyze",
        "analyse",
        "evaluate",
        "design",
        "scenario",
        "case",
        "data",
        "table",
        "equation",
        "example",
        "with respect to",
        "using the"
    ]

    hits = sum(
        1 for term in specific_terms
        if term in q
    )

    score += min(
        25,
        hits * 5
    )

    if "?" in q:
        score += 5

    return min(100, score)


# ============================================================
# QUESTION QUALITY
# ============================================================

def quality_score(question: str) -> float:

    q = question.strip()

    score = 55

    if len(q) >= 20:
        score += 10

    if len(q) >= 50:
        score += 10

    if "?" in q:
        score += 10

    # Strong command verbs
    command_verbs = []

    for level, verbs in BLOOM_VERBS.items():
        command_verbs.extend(verbs)

    if any(
        re.search(
            rf"\b{re.escape(v)}\b",
            q.lower()
        )
        for v in command_verbs
    ):
        score += 10

    # Penalize vague wording
    vague = [
        "something",
        "somehow",
        "etc.",
        "and so on",
        "write about",
        "say something about",
        "tell me about"
    ]

    for word in vague:

        if word in q.lower():
            score -= 10

    return max(
        0,
        min(100, score)
    )


# ============================================================
# EVALUATION
# ============================================================

def evaluate_question(
    question: str,
    course: str,
    clo_outcomes: List[Dict],
    plo_outcomes: List[Dict],
    target_bloom: str
) -> Dict:

    subject = subject_score(
        question,
        course,
        clo_outcomes
    )

    clo_match, clo_score = best_outcome(
        question,
        clo_outcomes
    )

    plo_match, plo_score = best_outcome(
        question,
        plo_outcomes
    )

    detected_bloom, _ = detect_bloom(question)

    bloom = bloom_score(
        question,
        target_bloom
    )

    specificity = specificity_score(
        question
    )

    quality = quality_score(
        question
    )

    overall = (
        subject * 0.20
        + clo_score * 0.25
        + plo_score * 0.25
        + bloom * 0.15
        + specificity * 0.10
        + quality * 0.05
    )

    attained = (
        overall >= 80
        and subject >= 80
        and clo_score >= 80
        and plo_score >= 80
        and bloom >= 80
    )

    return {
        "question": question,
        "subject": round(subject, 1),
        "clo": round(clo_score, 1),
        "plo": round(plo_score, 1),
        "bloom": round(bloom, 1),
        "specificity": round(specificity, 1),
        "quality": round(quality, 1),
        "overall": round(overall, 1),
        "attained": attained,
        "clo_id": clo_match["id"],
        "clo_text": clo_match["text"],
        "plo_id": plo_match["id"],
        "plo_text": plo_match["text"],
        "detected_bloom": detected_bloom
    }


# ============================================================
# REVISION HELPERS
# ============================================================

def extract_key_concepts(text: str) -> List[str]:

    tokens = content_tokens(text)

    # Keep unique terms
    result = []

    for token in tokens:

        if token not in result:
            result.append(token)

    return result[:8]


def choose_bloom_verb(target: str) -> str:

    preferred = {
        "Remember": "identify",
        "Understand": "explain",
        "Apply": "apply",
        "Analyze": "analyze",
        "Evaluate": "evaluate",
        "Create": "design"
    }

    return preferred.get(
        target,
        "apply"
    )


def choose_secondary_verb(target: str) -> str:

    preferred = {
        "Remember": "state",
        "Understand": "describe",
        "Apply": "solve",
        "Analyze": "compare",
        "Evaluate": "justify",
        "Create": "develop"
    }

    return preferred.get(
        target,
        "apply"
    )


def sanitize_question(q: str) -> str:

    q = clean_text(q)

    # Remove accidental repeated punctuation
    q = re.sub(r"\?+", "?", q)
    q = re.sub(r"\.{2,}", ".", q)

    # Never produce .?
    q = q.replace(".?", "?")
    q = q.replace("!?", "?")

    # Ensure one final question mark
    q = q.rstrip(" .!?")

    return q + "?"


def build_revision_candidates(
    original: str,
    clo: Dict,
    plo: Dict,
    target_bloom: str
) -> List[str]:

    clo_concepts = extract_key_concepts(
        clo["text"]
    )

    plo_concepts = extract_key_concepts(
        plo["text"]
    )

    concepts = []

    for c in clo_concepts + plo_concepts:

        if c not in concepts:
            concepts.append(c)

    concepts = concepts[:6]

    verb = choose_bloom_verb(
        target_bloom
    )

    second_verb = choose_secondary_verb(
        target_bloom
    )

    concept_text = " ".join(
        concepts[:3]
    )

    if not concept_text:
        concept_text = original

    candidates = []

    # --------------------------------------------------------
    # Candidate 1
    # --------------------------------------------------------

    candidates.append(
        sanitize_question(
            f"{verb.capitalize()} {concept_text} "
            f"by applying the appropriate concepts and methods "
            f"to the given problem"
        )
    )

    # --------------------------------------------------------
    # Candidate 2
    # --------------------------------------------------------

    candidates.append(
        sanitize_question(
            f"{verb.capitalize()} {concept_text} "
            f"in the following problem and {second_verb} "
            f"your answer using relevant evidence"
        )
    )

    # --------------------------------------------------------
    # Candidate 3
    # --------------------------------------------------------

    candidates.append(
        sanitize_question(
            f"Using {concept_text}, {verb} the problem "
            f"and show how the relevant concepts lead to your answer"
        )
    )

    # --------------------------------------------------------
    # Candidate 4
    # --------------------------------------------------------

    candidates.append(
        sanitize_question(
            f"{verb.capitalize()} the relevant aspects of "
            f"{concept_text} in the given context and "
            f"support your response with appropriate reasoning"
        )
    )

    # --------------------------------------------------------
    # Candidate 5
    # --------------------------------------------------------

    candidates.append(
        sanitize_question(
            f"For the given problem, {verb} "
            f"{concept_text} and determine the appropriate solution"
        )
    )

    # --------------------------------------------------------
    # Candidate 6
    # More direct
    # --------------------------------------------------------

    candidates.append(
        sanitize_question(
            f"{verb.capitalize()} {concept_text} "
            f"using a suitable method and explain the basis of your answer"
        )
    )

    return deduplicate_questions(
        candidates
    )


def repair_revision(
    candidate: str,
    clo: Dict,
    plo: Dict,
    target_bloom: str
) -> str:

    """
    Makes the revision more explicitly connected to
    the actual outcome concepts while keeping the wording
    as a normal assessment question.

    It never inserts the words CLO, PLO, learning outcome,
    or alignment.
    """

    concepts = extract_key_concepts(
        clo["text"]
    )

    plo_concepts = extract_key_concepts(
        plo["text"]
    )

    merged = []

    for c in concepts + plo_concepts:

        if c not in merged:
            merged.append(c)

    merged = merged[:6]

    if not merged:
        return sanitize_question(candidate)

    verb = choose_bloom_verb(
        target_bloom
    )

    if target_bloom == "Apply":

        revised = (
            f"{verb.capitalize()} "
            f"{' '.join(merged[:4])} "
            f"to solve the given problem and show the steps used"
        )

    elif target_bloom == "Analyze":

        revised = (
            f"{verb.capitalize()} "
            f"{' '.join(merged[:4])} "
            f"in the given case, distinguish the relevant factors, "
            f"and justify your analysis"
        )

    elif target_bloom == "Evaluate":

        revised = (
            f"{verb.capitalize()} "
            f"{' '.join(merged[:4])} "
            f"in the given case and justify your conclusion "
            f"with relevant evidence"
        )

    elif target_bloom == "Create":

        revised = (
            f"{verb.capitalize()} a solution using "
            f"{' '.join(merged[:4])} "
            f"and justify the main design decisions"
        )

    elif target_bloom == "Understand":

        revised = (
            f"{verb.capitalize()} "
            f"{' '.join(merged[:4])} "
            f"using a relevant example"
        )

    else:

        revised = (
            f"{verb.capitalize()} "
            f"{' '.join(merged[:4])} "
            f"and state the relevant concepts"
        )

    return sanitize_question(
        revised
    )


def generate_best_revision(
    original: str,
    course: str,
    clo_outcomes: List[Dict],
    plo_outcomes: List[Dict],
    target_bloom: str
) -> Tuple[str, Dict]:

    initial_eval = evaluate_question(
        original,
        course,
        clo_outcomes,
        plo_outcomes,
        target_bloom
    )

    clo = {
        "id": initial_eval["clo_id"],
        "text": initial_eval["clo_text"]
    }

    plo = {
        "id": initial_eval["plo_id"],
        "text": initial_eval["plo_text"]
    }

    candidates = build_revision_candidates(
        original,
        clo,
        plo,
        target_bloom
    )

    # Add repaired versions
    expanded = list(candidates)

    for candidate in candidates:

        expanded.append(
            repair_revision(
                candidate,
                clo,
                plo,
                target_bloom
            )
        )

    evaluations = []

    for candidate in deduplicate_questions(expanded):

        ev = evaluate_question(
            candidate,
            course,
            clo_outcomes,
            plo_outcomes,
            target_bloom
        )

        evaluations.append(
            (
                ev["overall"],
                ev["clo"],
                ev["plo"],
                ev["bloom"],
                ev
            )
        )

    # Prefer actual attained candidates
    attained_candidates = [
        item for item in evaluations
        if (
            item[0] >= 80
            and item[1] >= 80
            and item[2] >= 80
            and item[3] >= 80
        )
    ]

    if attained_candidates:

        attained_candidates.sort(
            key=lambda x: (
                x[0],
                x[1],
                x[2],
                x[3]
            ),
            reverse=True
        )

        return (
            attained_candidates[0][4]["question"],
            attained_candidates[0][4]
        )

    # Otherwise select strongest candidate
    evaluations.sort(
        key=lambda x: (
            x[0],
            x[1],
            x[2],
            x[3]
        ),
        reverse=True
    )

    best = evaluations[0][4]

    # Final repair attempt if still below 80
    repaired = repair_revision(
        best["question"],
        clo,
        plo,
        target_bloom
    )

    repaired_eval = evaluate_question(
        repaired,
        course,
        clo_outcomes,
        plo_outcomes,
        target_bloom
    )

    if repaired_eval["overall"] > best["overall"]:
        return repaired, repaired_eval

    return best["question"], best


# ============================================================
# FILE UPLOAD
# ============================================================

st.header("1. Upload Assessment")

uploaded_file = st.file_uploader(
    "Upload your assessment file",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "csv",
        "txt"
    ]
)

if uploaded_file is not None:

    if st.button(
        "📄 Read and Extract Assessment",
        type="primary"
    ):

        with st.spinner(
            "Reading the assessment file..."
        ):

            text, reader, pages = read_uploaded_file(
                uploaded_file
            )

        st.session_state.extracted_text = text
        st.session_state.reader_used = reader

        questions = extract_questions(
            text
        )

        st.session_state.questions = questions

        # Reset old evaluations
        st.session_state.evaluations = []

        st.success(
            f"File processed successfully. "
            f"Reader: {reader if reader else 'None'} | "
            f"Characters extracted: {len(text):,} | "
            f"Candidates detected: {len(questions)}"
        )


# ============================================================
# EXTRACTION DEBUG
# ============================================================

if st.session_state.extracted_text:

    with st.expander(
        "🔎 View Extraction Diagnostics",
        expanded=True
    ):

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Characters",
                f"{len(st.session_state.extracted_text):,}"
            )

        with col2:
            st.metric(
                "Questions Detected",
                len(st.session_state.questions)
            )

        with col3:
            st.write(
                "**Reader Used**"
            )
            st.write(
                st.session_state.reader_used or
                "Unknown"
            )

        st.text_area(
            "Extracted Text",
            st.session_state.extracted_text,
            height=300
        )


# ============================================================
# MANUAL FALLBACK
# ============================================================

st.divider()

st.subheader(
    "Manual Question Input — Emergency Fallback"
)

st.caption(
    "If the PDF is scanned or its text cannot be extracted, "
    "paste the questions below. You can paste the entire assessment."
)

manual_text = st.text_area(
    "Paste assessment questions",
    value=st.session_state.manual_questions,
    height=180,
    placeholder=(
        "Example:\n"
        "1. Calculate the acceleration of the object...\n"
        "2. Explain the role of enzymes in metabolism..."
    )
)

if st.button(
    "Use Pasted Questions"
):

    pasted_questions = extract_questions(
        manual_text
    )

    # If the text is pasted and extraction still cannot
    # identify questions, split non-empty lines manually.
    if not pasted_questions:

        pasted_questions = []

        for line in manual_text.splitlines():

            line = clean_text(line)

            if len(line) >= 10:

                pasted_questions.append(
                    normalize_question(line)
                )

    pasted_questions = deduplicate_questions(
        pasted_questions
    )

    st.session_state.questions = pasted_questions
    st.session_state.manual_questions = manual_text
    st.session_state.extracted_text = manual_text
    st.session_state.reader_used = "Manual Input"
    st.session_state.evaluations = []

    if pasted_questions:

        st.success(
            f"{len(pasted_questions)} assessment "
            f"question(s) loaded."
        )

    else:

        st.error(
            "No usable assessment text was found. "
            "Please paste at least one complete question."
        )


# ============================================================
# SHOW QUESTIONS
# ============================================================

questions = st.session_state.questions

if questions:

    st.divider()

    st.header(
        "2. Extracted Assessment Questions"
    )

    st.write(
        f"**{len(questions)} question(s) detected.**"
    )

    for i, question in enumerate(
        questions,
        start=1
    ):

        st.write(
            f"**Q{i}.** {question}"
        )


# ============================================================
# EVALUATION BUTTON
# ============================================================

if questions:

    st.divider()

    st.header(
        "3. Evaluate Alignment"
    )

    if st.button(
        "🎯 Evaluate All Questions",
        type="primary"
    ):

        clo_outcomes = parse_outcomes(
            clo_text,
            "CLO"
        )

        plo_outcomes = parse_outcomes(
            plo_text,
            "PLO"
        )

        if not clo_outcomes:

            st.error(
                "Please provide at least one CLO."
            )

        elif not plo_outcomes:

            st.error(
                "Please provide at least one PLO."
            )

        else:

            evaluations = []

            progress = st.progress(
                0
            )

            for i, question in enumerate(
                questions
            ):

                ev = evaluate_question(
                    question,
                    course,
                    clo_outcomes,
                    plo_outcomes,
                    bloom_target
                )

                evaluations.append(
                    ev
                )

                progress.progress(
                    int(
                        ((i + 1) / len(questions))
                        * 100
                    )
                )

            st.session_state.evaluations = evaluations

            st.success(
                f"Evaluation completed for "
                f"{len(evaluations)} question(s)."
            )


# ============================================================
# RESULTS
# ============================================================

evaluations = st.session_state.evaluations

if evaluations:

    st.divider()

    st.header(
        "4. Question-by-Question Results"
    )

    for i, ev in enumerate(
        evaluations,
        start=1
    ):

        st.subheader(
            f"Question {i}"
        )

        st.write(
            f"**Original Question:** "
            f"{ev['question']}"
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Overall",
                f"{ev['overall']}/100"
            )

        with col2:
            st.metric(
                "Subject",
                f"{ev['subject']}/100"
            )

        with col3:
            st.metric(
                "CLO",
                f"{ev['clo']}/100"
            )

        with col4:
            st.metric(
                "PLO",
                f"{ev['plo']}/100"
            )

        col5, col6, col7 = st.columns(3)

        with col5:
            st.metric(
                "Bloom",
                f"{ev['bloom']}/100"
            )

        with col6:
            st.metric(
                "Specificity",
                f"{ev['specificity']}/100"
            )

        with col7:
            st.metric(
                "Quality",
                f"{ev['quality']}/100"
            )

        st.write(
            f"**Matched CLO:** {ev['clo_id']} — "
            f"{ev['clo_text']}"
        )

        st.write(
            f"**Matched PLO:** {ev['plo_id']} — "
            f"{ev['plo_text']}"
        )

        st.write(
            f"**Detected Bloom Level:** "
            f"{ev['detected_bloom']}"
        )

        if ev["attained"]:

            st.success(
                "✓ Alignment is Attained"
            )

        else:

            st.warning(
                "⚠ Alignment Needs Revision"
            )

            if st.button(
                f"🔧 Generate Direct Revision for Q{i}",
                key=f"revise_{i}"
            ):

                clo_outcomes = parse_outcomes(
                    clo_text,
                    "CLO"
                )

                plo_outcomes = parse_outcomes(
                    plo_text,
                    "PLO"
                )

                with st.spinner(
                    "Constructing and testing a stronger aligned question..."
                ):

                    revised_question, revised_eval = (
                        generate_best_revision(
                            ev["question"],
                            course,
                            clo_outcomes,
                            plo_outcomes,
                            bloom_target
                        )
                    )

                st.session_state[
                    f"revision_{i}"
                ] = {
                    "question": revised_question,
                    "evaluation": revised_eval
                }

        if f"revision_{i}" in st.session_state:

            revision_data = st.session_state[
                f"revision_{i}"
            ]

            revised_question = revision_data[
                "question"
            ]

            revised_eval = revision_data[
                "evaluation"
            ]

            st.markdown(
                "### Revised Question"
            )

            st.info(
                revised_question
            )

            st.markdown(
                "### Attainment After Revision"
            )

            r1, r2, r3, r4 = st.columns(4)

            with r1:
                st.metric(
                    "Revised Overall",
                    f"{revised_eval['overall']}/100"
                )

            with r2:
                st.metric(
                    "Revised CLO",
                    f"{revised_eval['clo']}/100"
                )

            with r3:
                st.metric(
                    "Revised PLO",
                    f"{revised_eval['plo']}/100"
                )

            with r4:
                st.metric(
                    "Revised Bloom",
                    f"{revised_eval['bloom']}/100"
                )

            st.write(
                f"**Revised Specificity:** "
                f"{revised_eval['specificity']}/100"
            )

            st.write(
                f"**Revised Quality:** "
                f"{revised_eval['quality']}/100"
            )

            if (
                revised_eval["overall"] >= 80
                and revised_eval["subject"] >= 80
                and revised_eval["clo"] >= 80
                and revised_eval["plo"] >= 80
                and revised_eval["bloom"] >= 80
            ):

                st.success(
                    "✓ Alignment is Attained After Revision"
                )

            else:

                st.warning(
                    "The generated revision is the strongest "
                    "available revision, but the current diagnostic "
                    "score is below 80."
                )

        st.divider()


# ============================================================
# SUMMARY
# ============================================================

if evaluations:

    st.header(
        "5. Overall Evaluation Summary"
    )

    total = len(evaluations)

    attained = sum(
        1
        for e in evaluations
        if e["attained"]
    )

    needing_revision = total - attained

    average_score = (
        sum(
            e["overall"]
            for e in evaluations
        )
        / total
        if total
        else 0
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Total Questions",
            total
        )

    with c2:
        st.metric(
            "Alignment Attained",
            attained
        )

    with c3:
        st.metric(
            "Average Score",
            f"{average_score:.1f}/100"
        )

    rows = []

    for i, e in enumerate(
        evaluations,
        start=1
    ):

        rows.append({
            "Question": i,
            "Overall": e["overall"],
            "Subject": e["subject"],
            "CLO": e["clo"],
            "PLO": e["plo"],
            "Bloom": e["bloom"],
            "Specificity": e["specificity"],
            "Quality": e["quality"],
            "Matched CLO": e["clo_id"],
            "Matched PLO": e["plo_id"],
            "Bloom Level": e["detected_bloom"],
            "Status": (
                "Attained"
                if e["attained"]
                else "Needs Revision"
            )
        })

    summary_df = pd.DataFrame(
        rows
    )

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )

    csv_data = summary_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Evaluation Report",
        data=csv_data,
        file_name="OBE_Assessment_Alignment_Report.csv",
        mime="text/csv"
    )


# ============================================================
# DIAGNOSTIC INFORMATION
# ============================================================

with st.expander(
    "⚙️ Available File Readers"
):

    st.write(
        f"PyMuPDF / fitz: "
        f"{'Available' if FITZ_AVAILABLE else 'Not installed'}"
    )

    st.write(
        f"pypdf: "
        f"{'Available' if PYPDF_AVAILABLE else 'Not installed'}"
    )

    st.write(
        f"pdfplumber: "
        f"{'Available' if PDFPLUMBER_AVAILABLE else 'Not installed'}"
    )

    st.write(
        f"python-docx: "
        f"{'Available' if DOCX_AVAILABLE else 'Not installed'}"
    )

    st.write(
        f"openpyxl: "
        f"{'Available' if OPENPYXL_AVAILABLE else 'Not installed'}"
    )

    st.write(
        f"Tesseract OCR: "
        f"{'Available' if PYTESSERACT_AVAILABLE else 'Not installed'}"
    )

    if not FITZ_AVAILABLE and not PYPDF_AVAILABLE and not PDFPLUMBER_AVAILABLE:
        st.error(
            "No PDF text reader is installed. "
            "For PDF support, install PyMuPDF with: pip install pymupdf"
        )

    elif not FITZ_AVAILABLE and not PYTESSERACT_AVAILABLE:
        st.warning(
            "OCR fallback is unavailable. "
            "Scanned/image-only PDFs may require Tesseract OCR."
        )
