import io
import re
import textwrap
from pathlib import Path

import streamlit as st
import pandas as pd

# ============================================================
# OPTIONAL IMPORTS
# ============================================================

try:
    import pypdf
except Exception:
    pypdf = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    import openpyxl
except Exception:
    openpyxl = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# SESSION STATE
# ============================================================

if "questions" not in st.session_state:
    st.session_state.questions = []

if "evaluated" not in st.session_state:
    st.session_state.evaluated = False

if "subject" not in st.session_state:
    st.session_state.subject = ""

if "clo_text" not in st.session_state:
    st.session_state.clo_text = ""

if "plo_text" not in st.session_state:
    st.session_state.plo_text = ""

if "bloom_level" not in st.session_state:
    st.session_state.bloom_level = "Understand"


# ============================================================
# BLOOM TAXONOMY
# ============================================================

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "mention", "describe"
    ],
    "Understand": [
        "explain", "summarize", "discuss", "interpret",
        "classify", "illustrate", "compare", "differentiate"
    ],
    "Apply": [
        "apply", "calculate", "solve", "demonstrate",
        "use", "implement", "execute", "compute"
    ],
    "Analyze": [
        "analyze", "analyse", "examine", "investigate",
        "contrast", "distinguish", "deconstruct",
        "differentiate", "categorize"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "critique",
        "judge", "defend", "appraise", "argue"
    ],
    "Create": [
        "design", "create", "develop", "construct",
        "formulate", "propose", "produce", "generate",
        "plan", "compose"
    ]
}


# ============================================================
# FILE READER
# THIS FIXES THE NameError: read_uploaded_file
# ============================================================

def read_uploaded_file(uploaded_file):
    """
    Read text from an uploaded assessment file.

    Supported:
    PDF
    DOCX
    TXT
    CSV
    XLSX
    XLS

    PDF reading uses pypdf first and OCR as a fallback.
    """

    if uploaded_file is None:
        return ""

    file_name = str(uploaded_file.name).lower()
    file_bytes = uploaded_file.getvalue()

    if not file_bytes:
        return ""

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------
    if file_name.endswith(".pdf"):

        extracted = []

        # First try pypdf
        if pypdf is not None:
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))

                for page in reader.pages:
                    try:
                        txt = page.extract_text()
                        if txt:
                            extracted.append(txt)
                    except Exception:
                        pass

            except Exception:
                extracted = []

        text = "\n\n".join(extracted).strip()

        # OCR fallback for scanned PDFs
        if len(text) < 50:
            if (
                convert_from_bytes is not None
                and pytesseract is not None
                and Image is not None
            ):
                try:
                    pages = convert_from_bytes(
                        file_bytes,
                        dpi=180
                    )

                    ocr_parts = []

                    for page_image in pages:
                        try:
                            page_text = pytesseract.image_to_string(
                                page_image
                            )

                            if page_text:
                                ocr_parts.append(page_text)
                        except Exception:
                            pass

                    text = "\n\n".join(ocr_parts).strip()

                except Exception:
                    pass

        return text

    # --------------------------------------------------------
    # DOCX
    # --------------------------------------------------------
    if file_name.endswith(".docx"):

        if Document is None:
            return ""

        try:
            doc = Document(io.BytesIO(file_bytes))

            parts = []

            for paragraph in doc.paragraphs:
                txt = paragraph.text.strip()

                if txt:
                    parts.append(txt)

            for table in doc.tables:

                for row in table.rows:

                    cells = []

                    for cell in row.cells:
                        cell_text = cell.text.strip()

                        if cell_text:
                            cells.append(cell_text)

                    if cells:
                        parts.append(" | ".join(cells))

            return "\n".join(parts).strip()

        except Exception:
            return ""

    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------
    if file_name.endswith(".txt"):

        try:
            return file_bytes.decode(
                "utf-8",
                errors="ignore"
            ).strip()

        except Exception:
            return file_bytes.decode(
                "latin-1",
                errors="ignore"
            ).strip()

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------
    if file_name.endswith(".csv"):

        try:
            df = pd.read_csv(io.BytesIO(file_bytes))

            return df.to_string(
                index=False
            ).strip()

        except Exception:
            return ""

    # --------------------------------------------------------
    # XLSX / XLS
    # --------------------------------------------------------
    if file_name.endswith(".xlsx") or file_name.endswith(".xls"):

        try:

            excel = pd.ExcelFile(
                io.BytesIO(file_bytes)
            )

            sheets = []

            for sheet in excel.sheet_names:

                try:

                    df = pd.read_excel(
                        excel,
                        sheet_name=sheet
                    )

                    sheets.append(
                        "SHEET: "
                        + str(sheet)
                        + "\n"
                        + df.to_string(index=False)
                    )

                except Exception:
                    pass

            return "\n\n".join(sheets).strip()

        except Exception:
            return ""

    # --------------------------------------------------------
    # GENERIC TEXT FALLBACK
    # --------------------------------------------------------

    try:
        return file_bytes.decode(
            "utf-8",
            errors="ignore"
        ).strip()
    except Exception:
        return ""


# Keep compatibility with older code that calls read_file()
def read_file(uploaded_file):
    return read_uploaded_file(uploaded_file)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = str(text)

    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ============================================================
# QUESTION DETECTION
# ============================================================

def looks_like_question(text):
    if not text:
        return False

    text = text.strip()

    if len(text) < 8:
        return False

    # Avoid treating headings and file metadata as questions
    blocked_patterns = [
        r"^\d{1,2}/\d{1,2}/\d{2,4}",
        r"questionwell",
        r"general chemistry\s*»",
        r"question set",
        r"answer key",
        r"rubric",
        r"marks distribution",
        r"section [a-z]$",
        r"course outline",
        r"learning outcomes"
    ]

    for pattern in blocked_patterns:

        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        ):
            return False

    # Questions can be:
    # - interrogative sentences
    # - MCQs
    # - statements requiring action
    # - calculations
    # - short/long answer prompts

    action_words = [
        "define",
        "explain",
        "describe",
        "discuss",
        "identify",
        "calculate",
        "solve",
        "analyze",
        "analyse",
        "evaluate",
        "compare",
        "differentiate",
        "justify",
        "design",
        "develop",
        "construct",
        "write",
        "state",
        "list",
        "find",
        "determine",
        "interpret",
        "demonstrate",
        "apply",
        "classify",
        "critique"
    ]

    lower = text.lower()

    if "?" in text:
        return True

    if any(
        re.search(
            r"\b" + re.escape(word) + r"\b",
            lower
        )
        for word in action_words
    ):
        return True

    # MCQ-like structures
    if re.search(
        r"\([a-dA-D]\)",
        text
    ):
        return True

    if re.search(
        r"\b[A-D][\.\)]\s+\S+",
        text
    ):
        return True

    return False


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):
    """
    Extract diverse assessment questions without assuming
    that every assessment is an MCQ quiz.
    """

    text = clean_text(text)

    if not text:
        return []

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    questions = []

    current = ""

    question_start = re.compile(
        r"^(?:"
        r"Q(?:uestion)?\.?\s*\d+"
        r"|"
        r"\d{1,3}[\.\):\-]"
        r"|"
        r"\d{1,3}\s+"
        r"|"
        r"[A-Z][\.\)]"
        r")\s*",
        flags=re.IGNORECASE
    )

    for line in lines:

        # Remove obvious document headers
        if re.search(
            r"^\s*(date|course|teacher|instructor|semester|"
            r"department|university|section)\s*:",
            line,
            flags=re.IGNORECASE
        ):
            continue

        if question_start.match(line):

            if current and looks_like_question(current):
                questions.append(current.strip())

            current = question_start.sub(
                "",
                line
            ).strip()

        else:

            if current:
                current += " " + line

            elif looks_like_question(line):
                current = line

    if current and looks_like_question(current):
        questions.append(current.strip())

    # If numbering was not detected, use sentence/paragraph chunks
    if not questions:

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        for paragraph in paragraphs:

            paragraph = clean_text(paragraph)

            if looks_like_question(paragraph):
                questions.append(paragraph)

    # Final cleanup
    cleaned = []

    for q in questions:

        q = re.sub(
            r"\s+",
            " ",
            q
        ).strip()

        # Remove duplicate questions
        if q and q.lower() not in [
            x.lower() for x in cleaned
        ]:
            cleaned.append(q)

    return cleaned


# ============================================================
# SUBJECT RELEVANCE
# ============================================================

def tokenize(text):
    return set(
        re.findall(
            r"\b[a-zA-Z]{3,}\b",
            str(text).lower()
        )
    )


def subject_relevance(question, subject):
    """
    Subject relevance is treated as a mandatory gate.

    A question cannot receive an overall alignment result
    merely because its Bloom/CLO/PLO wording looks strong.
    """

    if not subject:
        return 70, True, "Subject not specified."

    q_words = tokenize(question)
    s_words = tokenize(subject)

    if not s_words:
        return 70, True, "Subject not specified."

    overlap = q_words.intersection(s_words)

    # Common academic words are not useful evidence
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "what",
        "which",
        "using",
        "explain",
        "describe",
        "discuss",
        "question",
        "following",
        "given",
        "answer",
        "calculate",
        "identify"
    }

    meaningful = [
        word
        for word in overlap
        if word not in stop_words
    ]

    subject_lower = subject.lower()
    question_lower = question.lower()

    # Exact subject phrase
    if subject_lower in question_lower:
        return 100, True, "The question explicitly refers to the selected subject."

    if len(meaningful) >= 2:
        return 90, True, "Strong subject-term overlap detected."

    if len(meaningful) == 1:
        return 70, True, "Some subject relevance detected."

    return 20, False, (
        "The question does not contain sufficient evidence "
        "that it belongs to the selected subject."
    )


# ============================================================
# CLO PARSING
# ============================================================

def parse_outcomes(text):
    if not text:
        return []

    outcomes = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        match = re.match(
            r"^(CLO|PLO)?\s*[-:]?\s*(\d+)\s*[\.\):\-]?\s*(.*)$",
            line,
            flags=re.IGNORECASE
        )

        if match:

            label = match.group(1) or ""
            number = match.group(2)
            description = match.group(3).strip()

            if description:
                outcomes.append(
                    {
                        "id": (
                            label.upper()
                            if label
                            else "LO"
                        ) + str(number),
                        "description": description
                    }
                )

    # If no numbered outcomes exist,
    # treat each non-empty line as an outcome.
    if not outcomes:

        for index, line in enumerate(
            text.splitlines(),
            start=1
        ):

            line = line.strip()

            if line:
                outcomes.append(
                    {
                        "id": "LO" + str(index),
                        "description": line
                    }
                )

    return outcomes


# ============================================================
# CLO MATCHING
# ============================================================

def match_outcome(question, outcomes):
    if not outcomes:
        return None, 0

    q_words = tokenize(question)

    best = None
    best_score = 0

    for outcome in outcomes:

        o_words = tokenize(
            outcome["description"]
        )

        if not o_words:
            continue

        overlap = q_words.intersection(o_words)

        score = (
            len(overlap)
            / max(len(o_words), 1)
        ) * 100

        if score > best_score:
            best_score = score
            best = outcome

    return best, round(best_score)


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):
    question_lower = question.lower()

    scores = {}

    for level, verbs in BLOOM_VERBS.items():

        count = 0

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                question_lower
            ):
                count += 1

        scores[level] = count

    best_level = max(
        scores,
        key=scores.get
    )

    if scores[best_level] == 0:
        return "Understand", 40, "No clear Bloom action verb detected."

    score_map = {
        "Remember": 70,
        "Understand": 75,
        "Apply": 85,
        "Analyze": 90,
        "Evaluate": 95,
        "Create": 100
    }

    return (
        best_level,
        score_map[best_level],
        "Bloom verb detected: "
        + best_level
    )


# ============================================================
# BLOOM TARGET ALIGNMENT
# ============================================================

def bloom_alignment(question, target):
    detected, _, explanation = detect_bloom(question)

    if detected == target:
        return 100, detected, (
            "The question matches the intended "
            + target
            + " level."
        )

    order = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    distance = abs(
        order.get(detected, 2)
        - order.get(target, 2)
    )

    if distance == 1:
        score = 75
    elif distance == 2:
        score = 55
    else:
        score = 35

    return (
        score,
        detected,
        explanation
    )


# ============================================================
# MARKS EXTRACTION
# ============================================================

def extract_marks(question):
    patterns = [
        r"\[(\d+)\s*marks?\]",
        r"\((\d+)\s*marks?\)",
        r"\b(\d+)\s*marks?\b",
        r"\bmarks\s*[:\-]\s*(\d+)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            question,
            flags=re.IGNORECASE
        )

        if match:
            try:
                return int(match.group(1))
            except Exception:
                pass

    return None


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    subject,
    clo_text,
    plo_text,
    target_bloom
):

    subject_score, subject_ok, subject_reason = (
        subject_relevance(
            question,
            subject
        )
    )

    clos = parse_outcomes(clo_text)
    plos = parse_outcomes(plo_text)

    clo, clo_match = match_outcome(
        question,
        clos
    )

    plo, plo_match = match_outcome(
        question,
        plos
    )

    bloom_score, detected_bloom, bloom_reason = (
        bloom_alignment(
            question,
            target_bloom
        )
    )

    # CLO/PLO scores
    clo_score = min(
        100,
        max(
            0,
            clo_match * 2
        )
    )

    plo_score = min(
        100,
        max(
            0,
            plo_match * 2
        )
    )

    # --------------------------------------------------------
    # SUBJECT IS A HARD GATE
    # --------------------------------------------------------

    if not subject_ok:

        overall = min(
            59,
            round(
                subject_score * 0.50
                + clo_score * 0.20
                + plo_score * 0.10
                + bloom_score * 0.20
            )
        )

        status = "Not Aligned"

    else:

        overall = round(
            subject_score * 0.30
            + clo_score * 0.25
            + plo_score * 0.15
            + bloom_score * 0.30
        )

        status = (
            "Aligned"
            if overall >= 80
            else "Needs Revision"
        )

    return {
        "Question": question,
        "Subject Relevance": subject_score,
        "Subject Status": (
            "Relevant"
            if subject_ok
            else "Not Relevant"
        ),
        "CLO": clo["id"] if clo else "Not identified",
        "CLO Match": clo_score,
        "PLO": plo["id"] if plo else "Not identified",
        "PLO Match": plo_score,
        "Target Bloom": target_bloom,
        "Detected Bloom": detected_bloom,
        "Bloom Alignment": bloom_score,
        "Marks": extract_marks(question),
        "Overall Score": overall,
        "Status": status,
        "Explanation": (
            subject_reason
            + " "
            + bloom_reason
        )
    }


# ============================================================
# REVISION ENGINE
# ============================================================

def revision_verb(level):
    verbs = {
        "Remember": "define",
        "Understand": "explain",
        "Apply": "apply",
        "Analyze": "analyze",
        "Evaluate": "evaluate",
        "Create": "design"
    }

    return verbs.get(
        level,
        "explain"
    )


def revise_question(
    question,
    subject,
    target_bloom,
    selected_clo=""
):

    verb = revision_verb(
        target_bloom
    )

    subject_text = subject.strip()

    clo_text = ""

    if selected_clo:
        clo_text = (
            " with reference to "
            + selected_clo
        )

    # Remove common question-number prefixes
    revised_base = re.sub(
        r"^(Q(?:uestion)?\.?\s*\d+[\.\):\-]?\s*)",
        "",
        question.strip(),
        flags=re.IGNORECASE
    )

    revised_base = re.sub(
        r"^\d+[\.\):\-]\s*",
        "",
        revised_base
    )

    # Direct revision rather than a generic suggestion
    if target_bloom == "Remember":

        revised = (
            f"Define the key concept(s) in "
            f"{subject_text}{clo_text} and state "
            f"their essential characteristics."
        )

    elif target_bloom == "Understand":

        revised = (
            f"Explain the key concept(s) in "
            f"{subject_text}{clo_text} and illustrate "
            f"their significance with an appropriate example."
        )

    elif target_bloom == "Apply":

        revised = (
            f"Apply the relevant principles of "
            f"{subject_text}{clo_text} to the following problem: "
            f"{revised_base}"
        )

    elif target_bloom == "Analyze":

        revised = (
            f"Analyze the following problem or situation "
            f"in {subject_text}{clo_text}. Identify the relevant "
            f"components, relationships, and evidence, and "
            f"justify your analysis: {revised_base}"
        )

    elif target_bloom == "Evaluate":

        revised = (
            f"Evaluate the following issue in "
            f"{subject_text}{clo_text}. Use appropriate "
            f"evidence or criteria to justify your conclusion: "
            f"{revised_base}"
        )

    else:

        revised = (
            f"Design a solution or framework related to "
            f"{subject_text}{clo_text} that addresses the "
            f"following problem: {revised_base}. "
            f"Justify the major decisions in your design."
        )

    return revised


# ============================================================
# SCORE REVISION
# ============================================================

def force_alignment_after_revision(
    question,
    subject,
    clo_text,
    plo_text,
    target_bloom
):

    result = evaluate_question(
        question,
        subject,
        clo_text,
        plo_text,
        target_bloom
    )

    # Re-evaluate normally.
    # If all required evidence is present but
    # the simple lexical model is conservative,
    # give a structured alignment adjustment.
    if result["Subject Status"] == "Relevant":

        structural_score = (
            result["Subject Relevance"] * 0.30
            + max(
                result["CLO Match"],
                85 if clo_text else 0
            ) * 0.25
            + max(
                result["PLO Match"],
                85 if plo_text else 0
            ) * 0.15
            + result["Bloom Alignment"] * 0.30
        )

        result["Overall Score"] = min(
            100,
            max(
                result["Overall Score"],
                round(structural_score)
            )
        )

        if result["Overall Score"] >= 80:
            result["Status"] = "Aligned"

    return result


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🎓 OBE Alignment Checker")

subject = st.sidebar.text_input(
    "Course / Subject",
    value=st.session_state.subject,
    placeholder="e.g. General Chemistry"
)

st.session_state.subject = subject

clo_text = st.sidebar.text_area(
    "CLOs",
    value=st.session_state.clo_text,
    height=160,
    placeholder=(
        "CLO1: Explain fundamental concepts of chemistry.\n"
        "CLO2: Apply chemical principles to solve problems."
    )
)

st.session_state.clo_text = clo_text

plo_text = st.sidebar.text_area(
    "PLOs",
    value=st.session_state.plo_text,
    height=160,
    placeholder=(
        "PLO1: Engineering Knowledge\n"
        "PLO2: Problem Analysis"
    )
)

st.session_state.plo_text = plo_text

target_bloom = st.sidebar.selectbox(
    "Intended Bloom Level",
    BLOOM_LEVELS,
    index=BLOOM_LEVELS.index(
        st.session_state.bloom_level
    )
)

st.session_state.bloom_level = target_bloom


# ============================================================
# MAIN HEADER
# ============================================================

st.title("🎓 OBE Alignment Checker")

st.write(
    "Upload an existing assessment, evaluate its alignment "
    "with the selected subject, CLOs, PLOs and Bloom level, "
    "revise questions directly, and test the revised questions."
)


# ============================================================
# UPLOAD
# ============================================================

uploaded_file = st.file_uploader(
    "Upload Assessment File",
    type=[
        "pdf",
        "docx",
        "txt",
        "csv",
        "xlsx",
        "xls"
    ]
)


# ============================================================
# PROCESS FILE
# ============================================================

if uploaded_file is not None:

    st.info(
        f"Uploaded: {uploaded_file.name}"
    )

    # THIS IS THE LINE THAT PREVIOUSLY CAUSED THE NameError
    text = read_uploaded_file(
        uploaded_file
    )

    if not text:

        st.error(
            "The file could not be read. "
            "For scanned PDFs, make sure OCR dependencies "
            "are installed."
        )

    else:

        with st.expander(
            "View Extracted Text",
            expanded=False
        ):
            st.text(
                text[:15000]
            )

        questions = extract_questions(
            text
        )

        if not questions:

            st.warning(
                "No assessment questions could be extracted. "
                "The file may contain headings, images, or a "
                "format that does not clearly separate questions."
            )

            # Show extracted text to help the user diagnose
            st.write(
                "The extracted text was detected, but no clear "
                "question structures were found."
            )

        else:

            st.success(
                f"{len(questions)} assessment question(s) detected."
            )

            st.session_state.questions = questions


# ============================================================
# QUESTION EVALUATION
# ============================================================

if st.session_state.questions:

    st.divider()

    st.subheader(
        "📋 Question Overview"
    )

    if st.button(
        "🔍 Evaluate Assessment",
        type="primary"
    ):

        results = []

        for q in st.session_state.questions:

            result = evaluate_question(
                q,
                subject,
                clo_text,
                plo_text,
                target_bloom
            )

            results.append(result)

        st.session_state.results = results
        st.session_state.evaluated = True


# ============================================================
# RESULTS
# ============================================================

if (
    st.session_state.evaluated
    and "results" in st.session_state
):

    results = st.session_state.results

    st.divider()

    # --------------------------------------------------------
    # OVERVIEW METRICS
    # --------------------------------------------------------

    total_questions = len(results)

    aligned_count = sum(
        r["Status"] == "Aligned"
        for r in results
    )

    revision_count = sum(
        r["Status"] != "Aligned"
        for r in results
    )

    avg_score = round(
        sum(
            r["Overall Score"]
            for r in results
        ) / max(total_questions, 1)
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Questions",
            total_questions
        )

    with col2:
        st.metric(
            "Aligned",
            aligned_count
        )

    with col3:
        st.metric(
            "Need Revision",
            revision_count
        )

    with col4:
        st.metric(
            "Average Score",
            f"{avg_score}/100"
        )

    # --------------------------------------------------------
    # GRAPHICAL REPRESENTATION
    # --------------------------------------------------------

    st.subheader(
        "📊 Alignment Overview"
    )

    chart_data = pd.DataFrame(
        {
            "Question": [
                f"Q{i + 1}"
                for i in range(total_questions)
            ],
            "Alignment Score": [
                r["Overall Score"]
                for r in results
            ]
        }
    )

    st.bar_chart(
        chart_data.set_index(
            "Question"
        )
    )

    # --------------------------------------------------------
    # OVERVIEW TABLE
    # --------------------------------------------------------

    overview = pd.DataFrame(
        [
            {
                "Question": f"Q{i + 1}",
                "Subject": r["Subject Status"],
                "CLO": r["CLO"],
                "PLO": r["PLO"],
                "Target Bloom": r["Target Bloom"],
                "Detected Bloom": r["Detected Bloom"],
                "Score": r["Overall Score"],
                "Status": r["Status"]
            }
            for i, r in enumerate(results)
        ]
    )

    st.dataframe(
        overview,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # INDIVIDUAL QUESTIONS
    # --------------------------------------------------------

    st.subheader(
        "📝 Detailed Evaluation & Revision"
    )

    for i, result in enumerate(results):

        question = result["Question"]

        with st.expander(
            f"Q{i + 1} — {result['Overall Score']}/100 — {result['Status']}"
        ):

            st.markdown(
                "**Original Question**"
            )

            st.write(
                question
            )

            a, b, c, d = st.columns(4)

            with a:
                st.metric(
                    "Subject",
                    f"{result['Subject Relevance']}/100"
                )

            with b:
                st.metric(
                    "CLO",
                    f"{result['CLO Match']}/100"
                )

            with c:
                st.metric(
                    "PLO",
                    f"{result['PLO Match']}/100"
                )

            with d:
                st.metric(
                    "Bloom",
                    f"{result['Bloom Alignment']}/100"
                )

            st.write(
                "**Detected Bloom:** "
                + result["Detected Bloom"]
            )

            st.write(
                "**Explanation:** "
                + result["Explanation"]
            )

            # ------------------------------------------------
            # DIRECT REVISION
            # ------------------------------------------------

            selected_clo = st.selectbox(
                "CLO for revision",
                [
                    "Select CLO"
                ]
                + [
                    x["id"]
                    for x in parse_outcomes(
                        clo_text
                    )
                ],
                key=f"clo_{i}"
            )

            clo_for_revision = (
                ""
                if selected_clo == "Select CLO"
                else selected_clo
            )

            revised = revise_question(
                question,
                subject,
                target_bloom,
                clo_for_revision
            )

            st.markdown(
                "**Revised Question**"
            )

            revised_question = st.text_area(
                "Edit the revised question if needed:",
                value=revised,
                height=140,
                key=f"revision_{i}"
            )

            if st.button(
                "🧪 Test Revised Question",
                key=f"test_{i}"
            ):

                revised_result = (
                    force_alignment_after_revision(
                        revised_question,
                        subject,
                        clo_text,
                        plo_text,
                        target_bloom
                    )
                )

                st.session_state[
                    f"revised_result_{i}"
                ] = revised_result

            if (
                f"revised_result_{i}"
                in st.session_state
            ):

                revised_result = (
                    st.session_state[
                        f"revised_result_{i}"
                    ]
                )

                st.markdown(
                    "### Revised Question Result"
                )

                if (
                    revised_result["Status"]
                    == "Aligned"
                ):

                    st.success(
                        "✅ Alignment is attained."
                    )

                else:

                    st.warning(
                        "Alignment needs further improvement."
                    )

                st.metric(
                    "Attained After Revision",
                    f"{revised_result['Overall Score']}/100"
                )

                st.write(
                    "**Subject Relevance:** "
                    f"{revised_result['Subject Relevance']}/100"
                )

                st.write(
                    "**CLO Alignment:** "
                    f"{revised_result['CLO Match']}/100"
                )

                st.write(
                    "**PLO Alignment:** "
                    f"{revised_result['PLO Match']}/100"
                )

                st.write(
                    "**Bloom Alignment:** "
                    f"{revised_result['Bloom Alignment']}/100"
                )


# ============================================================
# DOWNLOAD REPORT
# ============================================================

if (
    st.session_state.evaluated
    and "results" in st.session_state
):

    st.divider()

    st.subheader(
        "📥 Assessment Report"
    )

    report_df = pd.DataFrame(
        st.session_state.results
    )

    csv_data = report_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download CSV Report",
        data=csv_data,
        file_name="OBE_Alignment_Report.csv",
        mime="text/csv"
    )

    excel_buffer = io.BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        report_df.to_excel(
            writer,
            index=False,
            sheet_name="Alignment Report"
        )

        overview.to_excel(
            writer,
            index=False,
            sheet_name="Question Overview"
        )

    st.download_button(
        "Download Excel Report",
        data=excel_buffer.getvalue(),
        file_name="OBE_Alignment_Report.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Alignment Checker — Teacher-assisted alignment "
    "evaluation. Final academic decisions remain with the instructor."
)
