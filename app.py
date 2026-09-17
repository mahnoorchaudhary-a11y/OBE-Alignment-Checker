import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Studio",
    page_icon="🎯",
    layout="wide"
)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>
.main-title {
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 4px;
}

.sub-title {
    color: #666;
    font-size: 16px;
    margin-bottom: 20px;
}

.good {
    padding: 12px;
    border-radius: 8px;
    background: #eaf7ee;
    border-left: 5px solid #2e8b57;
}

.warn {
    padding: 12px;
    border-radius: 8px;
    background: #fff6df;
    border-left: 5px solid #e0a000;
}

.bad {
    padding: 12px;
    border-radius: 8px;
    background: #fdecec;
    border-left: 5px solid #d9534f;
}

.info-box {
    padding: 14px;
    border-radius: 8px;
    background: #eef5ff;
    border-left: 5px solid #3b82f6;
}

.question-box {
    padding: 15px;
    border-radius: 8px;
    background: #f7f7f7;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONSTANTS
# ============================================================

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]

RANGES = {
    "Foundational": {
        "description": "Knowledge, understanding and basic application",
        "blooms": ["Remember", "Understand", "Apply"]
    },
    "Applied": {
        "description": "Application, analysis and interpretation",
        "blooms": ["Apply", "Analyze"]
    },
    "Advanced": {
        "description": "Evaluation, creation and higher-order thinking",
        "blooms": ["Evaluate", "Create"]
    }
}

QUESTION_TYPES = [
    "Short Answer",
    "Essay / Written",
    "MCQ",
    "Problem Solving",
    "Case Study",
    "Practical / Laboratory",
    "Project / Task",
    "Oral Presentation",
    "Viva",
    "Debate / Discussion",
    "Demonstration",
    "Simulation",
    "Design Task",
    "Programming Task",
    "Other"
]

EVIDENCE_TYPES = [
    "Written Response",
    "Calculation / Numerical Work",
    "Analysis / Interpretation",
    "Oral Performance",
    "Practical Performance",
    "Product / Design",
    "Code / Program",
    "Project / Portfolio",
    "Presentation",
    "Demonstration",
    "Case Analysis",
    "Other"
]

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "recall",
        "state", "mention", "recognize", "select"
    ],
    "Understand": [
        "describe", "explain", "summarize", "interpret",
        "classify", "discuss", "illustrate", "outline",
        "paraphrase"
    ],
    "Apply": [
        "apply", "calculate", "demonstrate", "use",
        "solve", "implement", "execute", "practice",
        "compute"
    ],
    "Analyze": [
        "analyze", "analyse", "compare", "contrast",
        "differentiate", "examine", "investigate",
        "categorize", "distinguish"
    ],
    "Evaluate": [
        "evaluate", "assess", "justify", "critique",
        "judge", "defend", "argue", "recommend",
        "appraise"
    ],
    "Create": [
        "create", "design", "develop", "construct",
        "formulate", "propose", "produce", "generate",
        "plan"
    ]
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this",
    "what", "which", "where", "when", "how", "why",
    "are", "was", "were", "has", "have", "had",
    "will", "would", "should", "could", "can", "may",
    "into", "about", "your", "their", "them", "than",
    "then", "also", "using", "used", "following",
    "given", "question", "questions"
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def meaningful_words(text):
    words = set(
        re.findall(
            r"[a-zA-Z]{3,}",
            clean_text(text).lower()
        )
    )
    return words - STOPWORDS


def word_overlap(text1, text2):
    a = meaningful_words(text1)
    b = meaningful_words(text2)

    if not a or not b:
        return 0

    overlap = a.intersection(b)

    return round(
        len(overlap) / max(1, min(len(a), len(b))) * 100
    )


def detect_bloom(question):
    q = clean_text(question).lower()

    found = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                q
            ):
                found.append(level)
                break

    if not found:
        return "Not detected"

    order = [
        "Remember",
        "Understand",
        "Apply",
        "Analyze",
        "Evaluate",
        "Create"
    ]

    for level in reversed(order):
        if level in found:
            return level

    return found[0]


def extract_marks(question):
    patterns = [
        r"\(\s*(\d+(?:\.\d+)?)\s*marks?\s*\)",
        r"\[\s*(\d+(?:\.\d+)?)\s*marks?\s*\]",
        r"(\d+(?:\.\d+)?)\s*marks?\b",
        r"\(\s*(\d+(?:\.\d+)?)\s*\)"
    ]

    for pattern in patterns:
        match = re.search(pattern, question, re.I)

        if match:
            try:
                return float(match.group(1))
            except Exception:
                pass

    return None


# ============================================================
# QUESTION PARSING
# ============================================================

def parse_questions(text):

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # --------------------------------------------------------
    # Numbered questions
    # Supports:
    # 1. Question
    # 1) Question
    # 1: Question
    # Q1. Question
    # Question 1. Question
    # --------------------------------------------------------

    numbered_pattern = (
        r"(?is)"
        r"(?:^|\n)"
        r"\s*"
        r"(?:Question\s*)?"
        r"(\d+)"
        r"\s*[\.\):\-]"
        r"\s*"
        r"(.*?)"
        r"(?="
        r"\n\s*(?:Question\s*)?\d+\s*[\.\):\-]\s*"
        r"|$"
        r")"
    )

    numbered = re.findall(
        numbered_pattern,
        text
    )

    questions = []

    for item in numbered:
        q = clean_text(item[1])

        if len(q) >= 10:
            questions.append(q)

    if questions:
        return questions

    # --------------------------------------------------------
    # Alternative Q1 / Q2 format
    # --------------------------------------------------------

    q_pattern = (
        r"(?is)"
        r"(?:^|\n)"
        r"\s*Q(?:uestion)?\s*(\d+)"
        r"\s*[\.\):\-]"
        r"\s*(.*?)"
        r"(?="
        r"\n\s*Q(?:uestion)?\s*\d+\s*[\.\):\-]\s*"
        r"|$"
        r")"
    )

    q_matches = re.findall(
        q_pattern,
        text
    )

    for item in q_matches:
        q = clean_text(item[1])

        if len(q) >= 10:
            questions.append(q)

    if questions:
        return questions

    # --------------------------------------------------------
    # Fall back to meaningful lines
    # --------------------------------------------------------

    lines = []

    for line in text.split("\n"):
        line = clean_text(line)

        if len(line) >= 20:
            lines.append(line)

    return lines


# ============================================================
# PDF EXTRACTION
# ============================================================

def extract_pdf(file):

    """
    Robust PDF reader.

    Tries:
    1. PyMuPDF / fitz
    2. pypdf
    3. PyPDF2
    """

    errors = []

    # --------------------------------------------------------
    # METHOD 1: PyMuPDF
    # --------------------------------------------------------

    try:

        import fitz

        file.seek(0)

        pdf_bytes = file.read()

        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        pages = []

        for page in document:
            pages.append(page.get_text("text"))

        document.close()

        text = "\n".join(pages)

        if text.strip():
            return text

        errors.append(
            "PyMuPDF opened the PDF but found no selectable text."
        )

    except Exception as e:
        errors.append(
            "PyMuPDF: " + str(e)
        )

    # --------------------------------------------------------
    # METHOD 2: pypdf
    # --------------------------------------------------------

    try:

        from pypdf import PdfReader

        file.seek(0)

        reader = PdfReader(file)

        pages = []

        for page in reader.pages:
            pages.append(
                page.extract_text() or ""
            )

        text = "\n".join(pages)

        if text.strip():
            return text

        errors.append(
            "pypdf opened the PDF but found no selectable text."
        )

    except Exception as e:
        errors.append(
            "pypdf: " + str(e)
        )

    # --------------------------------------------------------
    # METHOD 3: PyPDF2
    # --------------------------------------------------------

    try:

        from PyPDF2 import PdfReader

        file.seek(0)

        reader = PdfReader(file)

        pages = []

        for page in reader.pages:
            pages.append(
                page.extract_text() or ""
            )

        text = "\n".join(pages)

        if text.strip():
            return text

        errors.append(
            "PyPDF2 opened the PDF but found no selectable text."
        )

    except Exception as e:
        errors.append(
            "PyPDF2: " + str(e)
        )

    # --------------------------------------------------------
    # ALL METHODS FAILED
    # --------------------------------------------------------

    return (
        "ERROR: Could not read PDF.\n\n"
        "The PDF reader libraries are not available or "
        "the PDF contains scanned images.\n\n"
        + "\n".join(errors)
    )


# ============================================================
# DOCX EXTRACTION
# ============================================================

def extract_docx(file):

    try:

        from docx import Document

        file.seek(0)

        doc = Document(file)

        parts = []

        for paragraph in doc.paragraphs:

            text = paragraph.text.strip()

            if text:
                parts.append(text)

        for table in doc.tables:

            for row in table.rows:

                row_text = []

                for cell in row.cells:
                    row_text.append(cell.text)

                parts.append(
                    " ".join(row_text)
                )

        return "\n".join(parts)

    except Exception as e:

        return (
            "ERROR: Could not read DOCX. "
            + str(e)
        )


# ============================================================
# EXCEL EXTRACTION
# ============================================================

def extract_excel(file):

    try:

        file.seek(0)

        excel = pd.ExcelFile(file)

        parts = []

        for sheet in excel.sheet_names:

            df = pd.read_excel(
                file,
                sheet_name=sheet,
                header=None
            )

            parts.append(
                "Sheet: " + str(sheet)
            )

            parts.append(
                df.fillna("")
                .astype(str)
                .to_string(
                    index=False,
                    header=False
                )
            )

        return "\n".join(parts)

    except Exception as e:

        return (
            "ERROR: Could not read Excel. "
            + str(e)
        )


# ============================================================
# TXT EXTRACTION
# ============================================================

def extract_txt(file):

    try:

        file.seek(0)

        return file.read().decode(
            "utf-8",
            errors="ignore"
        )

    except Exception as e:

        return (
            "ERROR: Could not read TXT. "
            + str(e)
        )


# ============================================================
# UNIVERSAL FILE EXTRACTION
# ============================================================

def extract_uploaded_file(file):

    name = file.name.lower()

    if name.endswith(".pdf"):
        return extract_pdf(file)

    if name.endswith(".docx"):
        return extract_docx(file)

    if name.endswith((".xlsx", ".xls")):
        return extract_excel(file)

    if name.endswith(".txt"):
        return extract_txt(file)

    return (
        "ERROR: Unsupported file type."
    )


# ============================================================
# CLO / PLO ANALYSIS
# ============================================================

def check_clo(question, clo):

    overlap = word_overlap(
        question,
        clo
    )

    q_lower = question.lower()
    clo_lower = clo.lower()

    evidence_words = [
        "calculate",
        "analyze",
        "analyse",
        "compare",
        "evaluate",
        "design",
        "develop",
        "demonstrate",
        "solve",
        "interpret",
        "justify",
        "apply",
        "construct",
        "create",
        "explain"
    ]

    evidence_found = any(
        word in q_lower
        for word in evidence_words
    )

    # Give some credit for observable evidence
    if evidence_found:
        score = max(overlap, 70)
    else:
        score = overlap

    score = min(100, score)

    if score >= 80:
        reason = (
            "The question provides reasonable evidence "
            "of the selected CLO."
        )

    elif score >= 50:
        reason = (
            "The question may relate to the CLO, "
            "but the intended competency should be "
            "made more explicit."
        )

    else:
        reason = (
            "The question does not clearly demonstrate "
            "the competency described in the CLO."
        )

    return score, reason


def check_clo_plo(clo, plo):

    score = word_overlap(
        clo,
        plo
    )

    if score >= 60:
        reason = (
            "The CLO and PLO show a reasonably clear "
            "relationship."
        )

    elif score >= 30:
        score = max(score, 55)

        reason = (
            "The CLO may contribute to the PLO, "
            "but the mapping should be confirmed "
            "academically."
        )

    else:
        reason = (
            "Review whether the selected PLO genuinely "
            "represents the competency assessed by the CLO."
        )

    return min(100, score), reason


def check_plo_question(question, plo, clo_score):

    overlap = word_overlap(
        question,
        plo
    )

    # Do not rely only on exact wording.
    if clo_score >= 80:
        score = max(overlap, 80)
    elif clo_score >= 60:
        score = max(overlap, 65)
    else:
        score = overlap

    score = min(100, score)

    if score >= 80:
        reason = (
            "The assessment provides reasonable evidence "
            "toward the selected PLO through the CLO."
        )

    elif score >= 50:
        reason = (
            "The question may contribute to the PLO, "
            "but the evidence pathway should be reviewed."
        )

    else:
        reason = (
            "The question does not clearly provide "
            "evidence toward the selected PLO."
        )

    return score, reason


# ============================================================
# BLOOM CHECK
# ============================================================

def check_bloom(question, selected_bloom):

    detected = detect_bloom(question)

    if detected == "Not detected":

        return (
            60,
            detected,
            "No clear Bloom action verb was detected. "
            "Review whether the task requires the intended "
            "cognitive process."
        )

    if detected == selected_bloom:

        return (
            100,
            detected,
            "The question uses a cognitive demand consistent "
            "with the selected Bloom level."
        )

    # Adjacent levels receive partial credit
    order = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    difference = abs(
        order.get(detected, 0)
        -
        order.get(selected_bloom, 0)
    )

    if difference == 1:

        return (
            75,
            detected,
            f"The detected level is {detected}, while "
            f"{selected_bloom} was selected. Review the "
            f"actual cognitive demand of the task."
        )

    return (
        50,
        detected,
        f"The question appears to require {detected}, "
        f"while {selected_bloom} was selected."
    )


# ============================================================
# QUESTION TYPE CHECK
# ============================================================

def check_question_type(
    question_type,
    evidence_type
):

    compatibility = {

        "Short Answer": [
            "Written Response",
            "Analysis / Interpretation"
        ],

        "Essay / Written": [
            "Written Response",
            "Analysis / Interpretation",
            "Case Analysis"
        ],

        "MCQ": [
            "Written Response",
            "Calculation / Numerical Work"
        ],

        "Problem Solving": [
            "Calculation / Numerical Work",
            "Analysis / Interpretation"
        ],

        "Case Study": [
            "Case Analysis",
            "Analysis / Interpretation",
            "Written Response"
        ],

        "Practical / Laboratory": [
            "Practical Performance",
            "Calculation / Numerical Work",
            "Analysis / Interpretation"
        ],

        "Project / Task": [
            "Project / Portfolio",
            "Product / Design",
            "Presentation"
        ],

        "Oral Presentation": [
            "Oral Performance",
            "Presentation"
        ],

        "Viva": [
            "Oral Performance"
        ],

        "Debate / Discussion": [
            "Oral Performance",
            "Presentation"
        ],

        "Demonstration": [
            "Demonstration",
            "Practical Performance"
        ],

        "Simulation": [
            "Practical Performance",
            "Demonstration"
        ],

        "Design Task": [
            "Product / Design",
            "Project / Portfolio"
        ],

        "Programming Task": [
            "Code / Program"
        ]
    }

    allowed = compatibility.get(
        question_type,
        EVIDENCE_TYPES
    )

    if evidence_type in allowed:

        return (
            100,
            "The selected question type and evidence "
            "type are compatible."
        )

    return (
        60,
        "Review whether the selected question type "
        "can genuinely produce the selected evidence."
    )


# ============================================================
# SUGGESTED EDIT
# ============================================================

def suggest_edit(
    question,
    selected_bloom,
    evidence_type,
    clo
):

    suggestions = []

    detected = detect_bloom(question)

    if detected == "Not detected":

        suggestions.append(
            f"Use a clear {selected_bloom} action verb."
        )

    elif detected != selected_bloom:

        suggestions.append(
            f"Review the cognitive demand so the task "
            f"actually requires {selected_bloom}."
        )

    evidence_phrase = {
        "Written Response":
            "Provide a clear written response",
        "Calculation / Numerical Work":
            "Show the calculation steps",
        "Analysis / Interpretation":
            "Analyze and interpret the relevant information",
        "Oral Performance":
            "Present and explain your response orally",
        "Practical Performance":
            "Demonstrate the required practical procedure",
        "Product / Design":
            "Design and justify an appropriate solution",
        "Code / Program":
            "Develop and test an appropriate program",
        "Project / Portfolio":
            "Provide evidence from your project work",
        "Presentation":
            "Present and explain your work",
        "Demonstration":
            "Demonstrate the required process",
        "Case Analysis":
            "Analyze the case and justify your conclusion",
        "Other":
            "Provide observable evidence of the required skill"
    }

    phrase = evidence_phrase.get(
        evidence_type,
        "Provide observable evidence of the required skill"
    )

    improved = clean_text(question)

    # Add Bloom verb only when needed.
    if detected == "Not detected":

        verb_map = {
            "Remember": "Identify",
            "Understand": "Explain",
            "Apply": "Apply",
            "Analyze": "Analyze",
            "Evaluate": "Evaluate",
            "Create": "Design"
        }

        verb = verb_map.get(
            selected_bloom,
            "Explain"
        )

        improved = (
            verb
            + " "
            + improved[0].lower()
            + improved[1:]
        )

    # Add evidence requirement if not already obvious.
    if phrase.lower() not in improved.lower():

        improved = (
            improved.rstrip(".")
            + ". "
            + phrase
            + "."
        )

    suggestions.append(
        f"Make the evidence of the CLO more observable. "
        f"The selected CLO is: {clo}"
    )

    return improved, suggestions


# ============================================================
# COMPLETE REVIEW
# ============================================================

def review_question(
    question,
    clo,
    plo,
    bloom,
    question_type,
    evidence_type
):

    question = clean_text(question)

    clo_score, clo_reason = check_clo(
        question,
        clo
    )

    clo_plo_score, clo_plo_reason = check_clo_plo(
        clo,
        plo
    )

    plo_question_score, plo_question_reason = (
        check_plo_question(
            question,
            plo,
            clo_score
        )
    )

    bloom_score, detected_bloom, bloom_reason = (
        check_bloom(
            question,
            bloom
        )
    )

    type_score, type_reason = check_question_type(
        question_type,
        evidence_type
    )

    # Evidence review
    evidence_score = 100

    if evidence_type == "Other":
        evidence_score = 70

    evidence_reason = (
        "The selected evidence type provides a basis "
        "for observing student learning."
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Marks and difficulty DO NOT affect OBE alignment.
    # --------------------------------------------------------

    weighted_score = round(
        clo_score * 0.30
        +
        clo_plo_score * 0.15
        +
        plo_question_score * 0.20
        +
        bloom_score * 0.15
        +
        evidence_score * 0.10
        +
        type_score * 0.10
    )

    # If all major dimensions are genuinely aligned,
    # show 100%.
    if (
        clo_score >= 90
        and clo_plo_score >= 80
        and plo_question_score >= 85
        and bloom_score >= 90
        and evidence_score >= 90
        and type_score >= 90
    ):
        alignment = 100
    else:
        alignment = weighted_score

    issues = []

    if clo_score < 80:
        issues.append(
            "The question should provide clearer evidence "
            "of the selected CLO."
        )

    if clo_plo_score < 70:
        issues.append(
            "Review the CLO-PLO mapping."
        )

    if plo_question_score < 75:
        issues.append(
            "Review whether the question contributes "
            "evidence toward the selected PLO."
        )

    if bloom_score < 90:
        issues.append(
            f"Review the Bloom level. Selected: {bloom}; "
            f"Detected: {detected_bloom}."
        )

    if evidence_score < 90:
        issues.append(
            "Review the type of evidence students are "
            "expected to produce."
        )

    if type_score < 90:
        issues.append(
            "Review the relationship between question type "
            "and evidence type."
        )

    if not issues:
        issues.append(
            "The question shows strong alignment indicators. "
            "Faculty review is still required."
        )

    revised_question, edit_suggestions = suggest_edit(
        question,
        bloom,
        evidence_type,
        clo
    )

    return {
        "question": question,
        "clo_score": clo_score,
        "clo_reason": clo_reason,
        "clo_plo_score": clo_plo_score,
        "clo_plo_reason": clo_plo_reason,
        "plo_question_score": plo_question_score,
        "plo_question_reason": plo_question_reason,
        "bloom_score": bloom_score,
        "detected_bloom": detected_bloom,
        "bloom_reason": bloom_reason,
        "evidence_score": evidence_score,
        "evidence_reason": evidence_reason,
        "type_score": type_score,
        "type_reason": type_reason,
        "alignment": alignment,
        "issues": issues,
        "suggested_question": revised_question,
        "edit_suggestions": edit_suggestions
    }


# ============================================================
# SESSION STATE
# ============================================================

if "questions" not in st.session_state:
    st.session_state.questions = []

if "uploaded_text" not in st.session_state:
    st.session_state.uploaded_text = ""

if "results" not in st.session_state:
    st.session_state.results = None

if "single_review" not in st.session_state:
    st.session_state.single_review = None


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎯 OBE Assessment Studio</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'Review your own assessment question against CLO, PLO, '
    'Bloom’s Taxonomy, evidence, and question type.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Assessment Setup")

    course = st.text_input(
        "Course / Subject",
        placeholder="e.g., Chemistry, English I, Programming"
    )

    st.subheader("CLO")

    clo = st.text_area(
        "Enter the CLO",
        placeholder=(
            "e.g., Analyze experimental results "
            "to determine the concentration of an "
            "unknown solution."
        ),
        height=110
    )

    st.subheader("PLO")

    plo = st.text_area(
        "Enter the PLO",
        placeholder=(
            "e.g., Apply scientific knowledge and "
            "analytical skills to solve problems."
        ),
        height=110
    )

    st.subheader("Bloom's Level")

    bloom = st.selectbox(
        "Select intended Bloom's level",
        BLOOM_LEVELS,
        index=3
    )

    st.subheader("Assessment Range")

    selected_range = st.selectbox(
        "Select range",
        list(RANGES.keys())
    )

    st.caption(
        RANGES[selected_range]["description"]
    )

    st.subheader("Question Type")

    question_type = st.selectbox(
        "Select question type",
        QUESTION_TYPES
    )

    st.subheader("Evidence")

    evidence_type = st.selectbox(
        "What evidence will students produce?",
        EVIDENCE_TYPES
    )

    st.subheader("Marks")

    marks = st.number_input(
        "Marks",
        min_value=0.0,
        value=5.0,
        step=1.0
    )


# ============================================================
# MAIN QUESTION INPUT
# ============================================================

st.subheader("1. Enter Your Own Assessment Question")

st.info(
    "Enter the question you actually want to use. "
    "The tool will review it; it will NOT silently replace "
    "your question."
)

question = st.text_area(
    "Your assessment question",
    placeholder=(
        "Type your own assessment question here..."
    ),
    height=160
)


# ============================================================
# CHECK BUTTON
# ============================================================

if st.button(
    "🔍 CHECK OBE ALIGNMENT",
    type="primary",
    use_container_width=True
):

    if not course.strip():
        st.warning(
            "Please enter the course / subject."
        )

    elif not clo.strip():
        st.warning(
            "Please enter the CLO."
        )

    elif not plo.strip():
        st.warning(
            "Please enter the PLO."
        )

    elif not question.strip():
        st.warning(
            "Please enter your assessment question."
        )

    else:

        st.session_state.single_review = review_question(
            question,
            clo,
            plo,
            bloom,
            question_type,
            evidence_type
        )


# ============================================================
# SINGLE QUESTION REVIEW
# ============================================================

if st.session_state.single_review:

    r = st.session_state.single_review

    st.divider()

    st.subheader("2. OBE Alignment Review")

    score = r["alignment"]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Overall Alignment",
        f"{score}%"
    )

    c2.metric(
        "CLO → Question",
        f"{r['clo_score']}%"
    )

    c3.metric(
        "CLO → PLO",
        f"{r['clo_plo_score']}%"
    )

    c4.metric(
        "PLO → Question",
        f"{r['plo_question_score']}%"
    )

    st.caption(
        "Marks and difficulty are advisory only and "
        "do not reduce the OBE alignment score."
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    if score >= 90:

        st.markdown(
            '<div class="good">'
            '<b>Strong alignment indicators.</b><br>'
            'The question provides appropriate evidence '
            'of the selected learning outcome. Faculty '
            'should still make the final academic decision.'
            '</div>',
            unsafe_allow_html=True
        )

    elif score >= 70:

        st.markdown(
            '<div class="warn">'
            '<b>Reasonable alignment, but review is recommended.</b><br>'
            'Look at the feedback below and decide whether '
            'the question needs improvement.'
            '</div>',
            unsafe_allow_html=True
        )

    else:

        st.markdown(
            '<div class="bad">'
            '<b>Important alignment areas require review.</b><br>'
            'The question should be reconsidered against '
            'the intended CLO and evidence.'
            '</div>',
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # DETAILED REVIEW
    # --------------------------------------------------------

    st.subheader("3. Detailed Review")

    d1, d2 = st.columns(2)

    with d1:

        st.markdown("### CLO → Question")

        st.metric(
            "Score",
            f"{r['clo_score']}%"
        )

        st.write(
            r["clo_reason"]
        )

        st.markdown("### CLO → PLO")

        st.metric(
            "Score",
            f"{r['clo_plo_score']}%"
        )

        st.write(
            r["clo_plo_reason"]
        )

        st.markdown("### PLO → Question")

        st.metric(
            "Score",
            f"{r['plo_question_score']}%"
        )

        st.write(
            r["plo_question_reason"]
        )

    with d2:

        st.markdown("### Bloom's Taxonomy")

        st.write(
            f"**Selected:** {bloom}"
        )

        st.write(
            f"**Detected:** {r['detected_bloom']}"
        )

        st.metric(
            "Bloom Alignment",
            f"{r['bloom_score']}%"
        )

        st.write(
            r["bloom_reason"]
        )

        st.markdown("### Evidence")

        st.metric(
            "Evidence Alignment",
            f"{r['evidence_score']}%"
        )

        st.write(
            r["evidence_reason"]
        )

        st.markdown("### Question Type")

        st.metric(
            "Type Alignment",
            f"{r['type_score']}%"
        )

        st.write(
            r["type_reason"]
        )

    # --------------------------------------------------------
    # PROBLEM AREAS
    # --------------------------------------------------------

    st.subheader("4. What Needs Attention?")

    for issue in r["issues"]:
        st.write(
            "• " + issue
        )

    # --------------------------------------------------------
    # ORIGINAL QUESTION
    # --------------------------------------------------------

    st.subheader("5. Your Original Question")

    st.markdown(
        f'<div class="question-box">'
        f'{r["question"]}'
        f'</div>',
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # SUGGESTED EDIT
    # --------------------------------------------------------

    st.subheader("6. Suggested Edit")

    st.info(
        "The tool suggests a possible improvement. "
        "You decide whether to accept it."
    )

    for suggestion in r["edit_suggestions"]:

        st.write(
            "• " + suggestion
        )

    suggested = st.text_area(
        "Suggested revised question — editable",
        value=r["suggested_question"],
        height=160,
        key="suggested_revision"
    )

    a, b, c = st.columns(3)

    with a:

        if st.button(
            "✅ ACCEPT SUGGESTED EDIT",
            use_container_width=True
        ):

            st.session_state.question_to_recheck = suggested

            st.success(
                "Suggested edit accepted. "
                "Click Re-check below."
            )

    with b:

        if st.button(
            "↩️ KEEP MY QUESTION",
            use_container_width=True
        ):

            st.session_state.question_to_recheck = (
                r["question"]
            )

            st.info(
                "Your original question has been kept."
            )

    with c:

        if st.button(
            "✏️ EDIT MANUALLY",
            use_container_width=True
        ):

            st.session_state.manual_edit_mode = True

    # --------------------------------------------------------
    # MANUAL EDIT
    # --------------------------------------------------------

    if st.session_state.get(
        "manual_edit_mode",
        False
    ):

        st.markdown("### ✏️ Manual Revision")

        manual_question = st.text_area(
            "Edit the question yourself",
            value=r["question"],
            height=160,
            key="manual_question"
        )

        if st.button(
            "💾 USE MY EDIT",
            use_container_width=True
        ):

            st.session_state.question_to_recheck = (
                manual_question
            )

            st.session_state.manual_edit_mode = False

            st.success(
                "Your edited question is ready to re-check."
            )

    # --------------------------------------------------------
    # RECHECK
    # --------------------------------------------------------

    if "question_to_recheck" in st.session_state:

        st.divider()

        st.subheader("7. Re-check Revised Question")

        revised_question = st.text_area(
            "Question to re-check",
            value=st.session_state.question_to_recheck,
            height=160,
            key="final_revision"
        )

        if st.button(
            "🔄 RE-CHECK OBE ALIGNMENT",
            type="primary",
            use_container_width=True
        ):

            revised_result = review_question(
                revised_question,
                clo,
                plo,
                bloom,
                question_type,
                evidence_type
            )

            old_score = r["alignment"]
            new_score = revised_result["alignment"]

            st.subheader("Revision Result")

            q1, q2, q3 = st.columns(3)

            q1.metric(
                "Original",
                f"{old_score}%"
            )

            q2.metric(
                "Revised",
                f"{new_score}%"
            )

            q3.metric(
                "Change",
                f"{new_score - old_score:+d}%"
            )

            st.markdown(
                "### Revised Question"
            )

            st.markdown(
                f'<div class="question-box">'
                f'{revised_question}'
                f'</div>',
                unsafe_allow_html=True
            )

            st.write(
                f"**CLO → Question:** "
                f"{revised_result['clo_score']}%"
            )

            st.write(
                f"**CLO → PLO:** "
                f"{revised_result['clo_plo_score']}%"
            )

            st.write(
                f"**PLO → Question:** "
                f"{revised_result['plo_question_score']}%"
            )

            st.write(
                f"**Bloom:** "
                f"{revised_result['detected_bloom']}"
            )

            if new_score >= 90:

                st.success(
                    "The revised question now shows "
                    "strong alignment indicators."
                )

            else:

                st.warning(
                    "The question has been rechecked. "
                    "Review the remaining feedback before "
                    "finalizing it."
                )

            st.markdown("### Remaining Feedback")

            for issue in revised_result["issues"]:

                st.write(
                    "• " + issue
                )


# ============================================================
# UPLOAD EXISTING ASSESSMENT
# ============================================================

st.divider()

st.subheader(
    "8. Optional: Upload an Existing Assessment"
)

st.caption(
    "You can upload a PDF, Word document, Excel file, "
    "or TXT file. The tool will extract the questions "
    "for review."
)

uploaded = st.file_uploader(
    "Upload Quiz / Assignment / Exam",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "txt"
    ]
)

if uploaded:

    st.success(
        f"Uploaded: {uploaded.name}"
    )

    if st.button(
        "📄 READ ASSESSMENT",
        use_container_width=True
    ):

        with st.spinner(
            "Reading your assessment..."
        ):

            extracted = extract_uploaded_file(
                uploaded
            )

        if extracted.startswith("ERROR:"):

            st.error(extracted)

            if uploaded.name.lower().endswith(".pdf"):

                st.warning(
                    "If this is a scanned/image PDF, the "
                    "questions may not contain selectable text. "
                    "Use a text-based PDF or DOCX/TXT file."
                )

                st.info(
                    "For Streamlit Cloud, add PyMuPDF to "
                    "requirements.txt so PDF reading is available."
                )

        else:

            st.session_state.uploaded_text = extracted

            questions = parse_questions(
                extracted
            )

            st.session_state.questions = questions

            if questions:

                st.success(
                    f"{len(questions)} question(s) detected."
                )

                with st.expander(
                    "Preview Extracted Questions"
                ):

                    for i, q in enumerate(
                        questions,
                        1
                    ):

                        st.write(
                            f"**Q{i}.** {q}"
                        )

            else:

                st.warning(
                    "No questions were detected. "
                    "Try a numbered assessment or "
                    "enter the question manually above."
                )


# ============================================================
# MULTIPLE QUESTION ANALYSIS
# ============================================================

if st.session_state.questions:

    st.divider()

    st.subheader(
        "9. Review Extracted Questions"
    )

    st.caption(
        "This section is useful when you upload a complete "
        "quiz, assignment, or exam."
    )

    if st.button(
        "🔍 ANALYZE ALL EXTRACTED QUESTIONS",
        use_container_width=True
    ):

        if not clo.strip():

            st.warning(
                "Enter a CLO in the sidebar first."
            )

        elif not plo.strip():

            st.warning(
                "Enter a PLO in the sidebar first."
            )

        else:

            results = []

            for q in st.session_state.questions:

                result = review_question(
                    q,
                    clo,
                    plo,
                    bloom,
                    question_type,
                    evidence_type
                )

                results.append(
                    result
                )

            st.session_state.results = results


# ============================================================
# MULTIPLE RESULTS
# ============================================================

if st.session_state.results:

    results = st.session_state.results

    st.divider()

    st.subheader(
        "10. Assessment Overview"
    )

    scores = [
        r["alignment"]
        for r in results
    ]

    overall = round(
        sum(scores) / len(scores)
    )

    strong = sum(
        1 for x in scores
        if x >= 90
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Overall Alignment",
        f"{overall}%"
    )

    b.metric(
        "Questions",
        len(results)
    )

    c.metric(
        "Strong Alignment",
        strong
    )

    d.metric(
        "Needs Review",
        len(results) - strong
    )

    # --------------------------------------------------------
    # OVERVIEW TABLE
    # --------------------------------------------------------

    overview = []

    for i, r in enumerate(
        results,
        1
    ):

        overview.append({

            "Question":
                f"Q{i}",

            "CLO Alignment":
                f'{r["clo_score"]}%',

            "CLO → PLO":
                f'{r["clo_plo_score"]}%',

            "PLO → Question":
                f'{r["plo_question_score"]}%',

            "Bloom":
                r["detected_bloom"],

            "Overall":
                f'{r["alignment"]}%'
        })

    st.dataframe(
        pd.DataFrame(overview),
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # DETAILED QUESTIONS
    # --------------------------------------------------------

    st.subheader(
        "11. Detailed Question Review"
    )

    for i, r in enumerate(
        results,
        1
    ):

        with st.expander(
            f"Q{i} — Alignment: {r['alignment']}%"
        ):

            st.markdown(
                "**Question:**"
            )

            st.write(
                r["question"]
            )

            x1, x2, x3, x4 = st.columns(4)

            x1.metric(
                "CLO",
                f'{r["clo_score"]}%'
            )

            x2.metric(
                "CLO → PLO",
                f'{r["clo_plo_score"]}%'
            )

            x3.metric(
                "PLO → Question",
                f'{r["plo_question_score"]}%'
            )

            x4.metric(
                "Bloom",
                r["detected_bloom"]
            )

            st.markdown(
                "**Feedback:**"
            )

            for issue in r["issues"]:

                st.write(
                    "• " + issue
                )


# ============================================================
# FINAL FACULTY CHECKLIST
# ============================================================

st.divider()

with st.expander(
    "✅ Faculty Final Review Checklist"
):

    checks = [

        "The question measures the intended CLO.",

        "The CLO genuinely contributes to the selected PLO.",

        "The Bloom level matches the cognitive demand.",

        "The question produces observable evidence of learning.",

        "The question type is appropriate for the evidence.",

        "The question assesses taught content.",

        "Marks are appropriate for the task.",

        "The marking scheme or rubric matches the question.",

        "The faculty member has reviewed and approved the final wording."
    ]

    for i, item in enumerate(checks):

        st.checkbox(
            item,
            key=f"final_check_{i}"
        )


# ============================================================
# FOOTER
# ============================================================

st.caption(
    "OBE Assessment Studio • AI supports assessment review; "
    "faculty judgment remains central."
)
