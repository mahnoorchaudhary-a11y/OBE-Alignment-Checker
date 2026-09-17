import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎯",
    layout="wide"
)

# ============================================================
# BLOOM'S TAXONOMY
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
        "define", "list", "name", "identify", "state",
        "recall", "recognize", "label", "select",
        "mention", "give", "tell", "repeat"
    ],

    "Understand": [
        "explain", "summarize", "interpret", "describe",
        "classify", "discuss", "illustrate", "paraphrase",
        "compare", "translate", "outline", "clarify"
    ],

    "Apply": [
        "apply", "use", "calculate", "solve",
        "demonstrate", "implement", "execute",
        "operate", "practice", "show", "utilize"
    ],

    "Analyze": [
        "analyze", "analyse", "differentiate", "examine",
        "compare", "contrast", "investigate",
        "categorize", "distinguish", "break",
        "deconstruct", "identify relationships",
        "infer", "separate"
    ],

    "Evaluate": [
        "evaluate", "judge", "justify", "critique",
        "assess", "defend", "argue", "recommend",
        "appraise", "validate", "verify", "rate"
    ],

    "Create": [
        "create", "design", "develop", "construct",
        "formulate", "produce", "generate", "compose",
        "plan", "propose", "write", "invent",
        "develop a", "design a"
    ]
}

# Stronger verbs are given more weight.
# This prevents weak words such as "identify" from overpowering
# a clear higher-level action such as "evaluate".

BLOOM_WEIGHTS = {
    "Remember": 1.0,
    "Understand": 1.0,
    "Apply": 1.2,
    "Analyze": 1.5,
    "Evaluate": 1.6,
    "Create": 1.7
}

# ============================================================
# BLOOM COGNITIVE ORDER
# ============================================================

BLOOM_INDEX = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6
}

# ============================================================
# COMMON LOW-VALUE WORDS
# ============================================================

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in",
    "on", "for", "with", "by", "is", "are", "was",
    "were", "be", "been", "being", "this", "that",
    "these", "those", "from", "as", "at", "it",
    "its", "into", "your", "you", "their", "them",
    "they", "we", "our", "can", "could", "should",
    "would", "will", "may", "might", "do", "does",
    "did", "how", "what", "why", "when", "where",
    "which", "who", "using", "use", "following"
}


# ============================================================
# TEXT UTILITIES
# ============================================================

def clean_text(text):
    text = str(text or "")
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def words(text):
    found = re.findall(
        r"[A-Za-z]{3,}",
        str(text).lower()
    )

    return [
        word
        for word in found
        if word not in STOPWORDS
    ]


def word_set(text):
    return set(words(text))


def similarity(question, outcome):
    """
    Simple semantic proxy based on meaningful word overlap.
    This is deliberately treated as supporting evidence,
    not proof of OBE alignment.
    """

    q_words = word_set(question)
    o_words = word_set(outcome)

    if not q_words or not o_words:
        return 0.0

    common = q_words.intersection(o_words)

    # Jaccard similarity
    score = (
        len(common)
        /
        len(q_words.union(o_words))
    ) * 100

    return round(score, 1)


# ============================================================
# BLOOM VERB DETECTION
# ============================================================

def detect_bloom(question):

    text = question.lower()

    detected = []

    for level in BLOOM_LEVELS:

        for verb in BLOOM_VERBS[level]:

            pattern = r"\b" + re.escape(verb) + r"\b"

            if re.search(pattern, text):

                detected.append(
                    (
                        level,
                        verb,
                        BLOOM_WEIGHTS[level]
                    )
                )

                break

    if not detected:

        return {
            "level": "Not Detected",
            "verb": "",
            "all_levels": []
        }

    # The primary cognitive action is generally the strongest
    # explicit action verb in the question.
    detected.sort(
        key=lambda x: x[2],
        reverse=True
    )

    primary = detected[0]

    return {
        "level": primary[0],
        "verb": primary[1],
        "all_levels": detected
    }


# ============================================================
# BLOOM ALIGNMENT
# ============================================================

def compare_bloom(detected, expected):

    if not expected:
        return {
            "status": "Not Specified",
            "score": 0,
            "reason": "No expected Bloom level was provided."
        }

    expected = expected.strip()

    if expected not in BLOOM_LEVELS:
        return {
            "status": "Invalid Expected Level",
            "score": 0,
            "reason": (
                "Expected Bloom level '"
                + expected
                + "' is not recognized."
            )
        }

    if detected == "Not Detected":

        return {
            "status": "Needs Review",
            "score": 0,
            "reason": (
                "No clear Bloom action verb was detected. "
                "The faculty member should review the actual "
                "cognitive demand of the question."
            )
        }

    if detected == expected:

        return {
            "status": "Aligned",
            "score": 100,
            "reason": (
                "The detected action verb is consistent with "
                "the specified Bloom level."
            )
        }

    d = BLOOM_INDEX[detected]
    e = BLOOM_INDEX[expected]

    difference = d - e

    if difference < 0:

        return {
            "status": "Needs Review",
            "score": max(
                0,
                100 - abs(difference) * 30
            ),
            "reason": (
                "The detected cognitive level ("
                + detected
                + ") is lower than the intended level ("
                + expected
                + "). The question may not demand the "
                "intended level of thinking."
            )
        }

    return {
        "status": "Needs Review",
        "score": max(
            0,
            100 - difference * 20
        ),
        "reason": (
            "The detected cognitive level ("
            + detected
            + ") is higher than the specified level ("
            + expected
            + "). Faculty review is recommended to confirm "
            "the actual cognitive demand."
        )
    }


# ============================================================
# EXTRACT MARKS
# ============================================================

def extract_marks(text):

    patterns = [
        r"\((\d+)\s*marks?\)",
        r"\[(\d+)\s*marks?\]",
        r"(\d+)\s*marks?",
        r"marks?\s*[:\-]\s*(\d+)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            try:
                return int(match.group(1))
            except Exception:
                pass

    return None


# ============================================================
# PDF READER + OCR
# ============================================================

def extract_pdf(file):

    try:
        from pypdf import PdfReader
    except Exception as e:
        return (
            "",
            "pypdf is not installed: " + str(e)
        )

    file.seek(0)
    pdf_bytes = file.read()

    if not pdf_bytes:
        return "", "The PDF is empty."

    # --------------------------------------------------------
    # First attempt: normal PDF text
    # --------------------------------------------------------

    try:

        reader = PdfReader(
            BytesIO(pdf_bytes)
        )

        normal_pages = []

        for number, page in enumerate(
            reader.pages,
            start=1
        ):

            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            if page_text.strip():

                normal_pages.append(
                    "\n--- Page "
                    + str(number)
                    + " ---\n"
                    + page_text
                )

        normal_text = clean_text(
            "\n".join(normal_pages)
        )

        if len(normal_text) >= 30:
            return normal_text, "PDF text extraction"

    except Exception:
        pass

    # --------------------------------------------------------
    # OCR fallback
    # --------------------------------------------------------

    st.info(
        "📷 This appears to be a scanned/image PDF. "
        "OCR is being used automatically."
    )

    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except Exception as e:

        return (
            "",
            "OCR libraries are unavailable: " + str(e)
        )

    # Check Tesseract

    try:

        version = pytesseract.get_tesseract_version()

        st.success(
            "OCR engine detected: Tesseract "
            + str(version)
        )

    except Exception as e:

        return (
            "",
            "Tesseract is not available. "
            "Check packages.txt."
            "\n\nError: "
            + str(e)
        )

    # Convert PDF pages

    try:

        images = convert_from_bytes(
            pdf_bytes,
            dpi=300,
            fmt="png"
        )

    except Exception as e:

        return (
            "",
            "The PDF could not be converted into images. "
            "Poppler may not be installed."
            "\n\nError: "
            + str(e)
        )

    if not images:
        return "", "No pages were found."

    # OCR

    all_pages = []

    progress = st.progress(
        0,
        text="Starting OCR..."
    )

    for number, image in enumerate(
        images,
        start=1
    ):

        try:

            image = image.convert("RGB")

            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--oem 3 --psm 6"
            )

        except Exception:

            text = ""

        text = clean_text(text)

        if text:

            all_pages.append(
                "\n--- OCR Page "
                + str(number)
                + " ---\n"
                + text
            )

        progress.progress(
            int(
                number
                / len(images)
                * 100
            ),
            text=(
                "OCR page "
                + str(number)
                + " of "
                + str(len(images))
            )
        )

    progress.empty()

    final_text = clean_text(
        "\n".join(all_pages)
    )

    if len(final_text) < 20:

        return (
            "",
            "OCR completed, but readable text was not found."
        )

    return final_text, "OCR"


# ============================================================
# DOCX READER
# ============================================================

def extract_docx(file):

    try:

        from docx import Document

        file.seek(0)

        document = Document(file)

        parts = []

        for paragraph in document.paragraphs:

            if paragraph.text.strip():

                parts.append(
                    paragraph.text.strip()
                )

        for table in document.tables:

            for row in table.rows:

                values = []

                for cell in row.cells:

                    if cell.text.strip():

                        values.append(
                            cell.text.strip()
                        )

                if values:

                    parts.append(
                        " | ".join(values)
                    )

        return clean_text(
            "\n".join(parts)
        ), "DOCX"

    except Exception as e:

        return (
            "",
            "Could not read DOCX: " + str(e)
        )


# ============================================================
# EXCEL READER
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
                "\n--- Sheet "
                + sheet
                + " ---\n"
                + df.fillna("")
                .astype(str)
                .to_string(index=False)
            )

        return clean_text(
            "\n".join(parts)
        ), "Excel"

    except Exception as e:

        return (
            "",
            "Could not read Excel: " + str(e)
        )


# ============================================================
# TEXT READER
# ============================================================

def extract_txt(file):

    try:

        file.seek(0)

        data = file.read()

        if isinstance(data, bytes):

            text = data.decode(
                "utf-8",
                errors="ignore"
            )

        else:

            text = str(data)

        return clean_text(text), "TXT"

    except Exception as e:

        return (
            "",
            "Could not read TXT: " + str(e)
        )


# ============================================================
# UNIVERSAL FILE READER
# ============================================================

def extract_file(file):

    name = file.name.lower()

    if name.endswith(".pdf"):
        return extract_pdf(file)

    if name.endswith(".docx"):
        return extract_docx(file)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return extract_excel(file)

    if name.endswith(".txt"):
        return extract_txt(file)

    return (
        "",
        "Unsupported file type."
    )


# ============================================================
# PARSE CLO/PLO LIST
# ============================================================

def parse_outcomes(text, prefix):

    outcomes = []

    if not text:
        return outcomes

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        pattern = (
            r"^\s*("
            + prefix
            + r"\s*[-]?\s*\d+"
            r")\s*[:\-]\s*(.+)$"
        )

        match = re.match(
            pattern,
            line,
            flags=re.IGNORECASE
        )

        if match:

            code = (
                match.group(1)
                .upper()
                .replace(" ", "")
                .replace("-", "")
            )

            description = match.group(2).strip()

            outcomes.append(
                {
                    "code": code,
                    "description": description
                }
            )

    return outcomes


# ============================================================
# PARSE QUESTIONS
# ============================================================

def parse_questions(text):

    if not text:
        return []

    # Normalize common OCR mistakes.

    text = text.replace(
        "\u2013",
        "-"
    )

    text = text.replace(
        "\u2014",
        "-"
    )

    lines = [
        clean_text(line)
        for line in text.splitlines()
        if clean_text(line)
    ]

    questions = []

    current = ""

    # Supports:
    # Q1.
    # Q1:
    # Q1)
    # Question 1
    # 1.
    # 1)
    # 1:

    pattern = re.compile(
        r"^(?:"
        r"Q(?:uestion)?\s*"
        r")?\d+\s*[\.\):\-]\s+",
        flags=re.IGNORECASE
    )

    for line in lines:

        if pattern.match(line):

            if current:

                questions.append(
                    current.strip()
                )

            current = line

        else:

            if current:

                current += " " + line

    if current:
        questions.append(
            current.strip()
        )

    # If OCR did not preserve numbering,
    # use paragraphs.

    if len(questions) == 0:

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        questions = [
            clean_text(p)
            for p in paragraphs
            if len(clean_text(p)) >= 15
        ]

    return questions


# ============================================================
# REMOVE QUESTION NUMBER
# ============================================================

def remove_question_number(text):

    return re.sub(
        r"^(?:Q(?:uestion)?\s*)?\d+\s*[\.\):\-]\s*",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()


# ============================================================
# FIND BEST CLO
# ============================================================

def best_outcome(question, outcomes):

    if not outcomes:

        return {
            "code": "Not Provided",
            "score": 0,
            "description": ""
        }

    results = []

    q_words = word_set(
        remove_question_number(question)
    )

    for outcome in outcomes:

        o_words = word_set(
            outcome["description"]
        )

        if not q_words or not o_words:

            score = 0

        else:

            common = q_words.intersection(
                o_words
            )

            # Combination of overlap and coverage.
            overlap = (
                len(common)
                /
                max(len(q_words), 1)
            ) * 100

            coverage = (
                len(common)
                /
                max(len(o_words), 1)
            ) * 100

            score = (
                overlap * 0.4
                +
                coverage * 0.6
            )

        results.append(
            {
                "code": outcome["code"],
                "score": round(
                    min(score, 100),
                    1
                ),
                "description": outcome["description"]
            }
        )

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[0]


# ============================================================
# EVALUATE CLO
# ============================================================

def evaluate_clo(
    question,
    expected_clo,
    clo_description,
    available_clos
):

    if not expected_clo:

        return {
            "status": "Not Specified",
            "score": 0,
            "reason": "No expected CLO was specified."
        }

    expected_description = clo_description

    if not expected_description:

        for item in available_clos:

            if item["code"] == expected_clo:

                expected_description = (
                    item["description"]
                )

    score = similarity(
        question,
        expected_description
    )

    if score >= 25:

        return {
            "status": "Aligned",
            "score": score,
            "reason": (
                "The question shows meaningful connection "
                "with the specified CLO: "
                + expected_description
            )
        }

    if score >= 10:

        return {
            "status": "Partial",
            "score": score,
            "reason": (
                "The question has some connection with the "
                "specified CLO, but the relationship should "
                "be reviewed by the faculty member."
            )
        }

    return {
        "status": "Needs Review",
        "score": score,
        "reason": (
            "The question has weak textual evidence of "
            "alignment with the specified CLO. "
            "Faculty review is recommended."
        )
    }


# ============================================================
# EVALUATE PLO
# ============================================================

def evaluate_plo(
    question,
    expected_plo,
    plo_description
):

    if not expected_plo:

        return {
            "status": "Not Specified",
            "score": 0,
            "reason": "No expected PLO was specified."
        }

    score = similarity(
        question,
        plo_description
    )

    if score >= 20:

        return {
            "status": "Aligned",
            "score": score,
            "reason": (
                "The question provides reasonable evidence "
                "of connection with the specified PLO."
            )
        }

    if score >= 8:

        return {
            "status": "Partial",
            "score": score,
            "reason": (
                "There is some evidence of PLO connection, "
                "but faculty review is recommended."
            )
        }

    return {
        "status": "Needs Review",
        "score": score,
        "reason": (
            "The question provides weak evidence of the "
            "specified PLO."
        )
    }


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    number,
    question,
    expected_clo,
    expected_plo,
    expected_bloom,
    clo_description,
    plo_description,
    clos,
    plos
):

    clean_question = remove_question_number(
        question
    )

    # Bloom
    bloom = detect_bloom(
        clean_question
    )

    bloom_result = compare_bloom(
        bloom["level"],
        expected_bloom
    )

    # CLO
    clo_result = evaluate_clo(
        clean_question,
        expected_clo,
        clo_description,
        clos
    )

    # PLO
    plo_result = evaluate_plo(
        clean_question,
        expected_plo,
        plo_description
    )

    # Best automatic CLO/PLO suggestions
    best_clo = best_outcome(
        clean_question,
        clos
    )

    best_plo = best_outcome(
        clean_question,
        plos
    )

    marks = extract_marks(
        clean_question
    )

    # --------------------------------------------------------
    # Overall decision
    # --------------------------------------------------------

    statuses = [
        bloom_result["status"],
        clo_result["status"],
        plo_result["status"]
    ]

    if "Needs Review" in statuses:

        overall = "⚠️ Needs Review"

    elif "Partial" in statuses:

        overall = "🟡 Partially Aligned"

    elif "Not Specified" in statuses:

        overall = "ℹ️ Incomplete Mapping"

    else:

        overall = "✅ Aligned"

    # --------------------------------------------------------
    # Build explanation
    # --------------------------------------------------------

    reasons = []

    reasons.append(
        "Bloom: "
        + bloom_result["reason"]
    )

    reasons.append(
        "CLO: "
        + clo_result["reason"]
    )

    reasons.append(
        "PLO: "
        + plo_result["reason"]
    )

    return {
        "Question No.": number,
        "Question": clean_question,
        "Marks": marks,
        "Expected Bloom": expected_bloom,
        "Detected Bloom": bloom["level"],
        "Detected Verb": bloom["verb"],
        "Bloom Status": bloom_result["status"],
        "Expected CLO": expected_clo,
        "CLO Status": clo_result["status"],
        "CLO Evidence %": clo_result["score"],
        "Expected PLO": expected_plo,
        "PLO Status": plo_result["status"],
        "PLO Evidence %": plo_result["score"],
        "Suggested CLO": best_clo["code"],
        "Suggested PLO": best_plo["code"],
        "Overall Decision": overall,
        "Explanation": " ".join(reasons)
    }


# ============================================================
# SESSION STATE
# ============================================================

if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""

if "questions" not in st.session_state:
    st.session_state.questions = []

if "results" not in st.session_state:
    st.session_state.results = pd.DataFrame()


# ============================================================
# HEADER
# ============================================================

st.title("🎯 OBE Alignment Checker")

st.write(
    "Enter the intended CLO, PLO, and Bloom level, "
    "then upload an assessment. The tool evaluates "
    "each question against the intended mapping."
)

st.info(
    "⚠️ This is an AI-assisted screening tool. "
    "Final academic judgment remains with the faculty member."
)

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("1️⃣ Course Information")

    course_name = st.text_input(
        "Course Name",
        placeholder="English I"
    )

    st.divider()

    st.header("2️⃣ CLOs")

    clo_text = st.text_area(
        "Enter CLOs",
        height=200,
        placeholder=(
            "CLO1: Identify main ideas in academic texts\n"
            "CLO2: Analyze patterns of organization\n"
            "CLO3: Apply critical reading strategies"
        )
    )

    st.divider()

    st.header("3️⃣ PLOs")

    plo_text = st.text_area(
        "Enter PLOs",
        height=200,
        placeholder=(
            "PLO1: Communication Skills\n"
            "PLO2: Critical Thinking\n"
            "PLO3: Problem Solving"
        )
    )


# ============================================================
# PARSE OUTCOMES
# ============================================================

clos = parse_outcomes(
    clo_text,
    "CLO"
)

plos = parse_outcomes(
    plo_text,
    "PLO"
)


# ============================================================
# DISPLAY ENTERED OUTCOMES
# ============================================================

col1, col2 = st.columns(2)

with col1:

    st.subheader("📘 Provided CLOs")

    if clos:

        clo_df = pd.DataFrame(
            clos
        )

        clo_df.columns = [
            "CLO",
            "Description"
        ]

        st.dataframe(
            clo_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "No CLOs detected. Use format: CLO1: description"
        )


with col2:

    st.subheader("📗 Provided PLOs")

    if plos:

        plo_df = pd.DataFrame(
            plos
        )

        plo_df.columns = [
            "PLO",
            "Description"
        ]

        st.dataframe(
            plo_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "No PLOs detected. Use format: PLO1: description"
        )


st.divider()


# ============================================================
# QUESTION MAPPING TABLE
# ============================================================

st.header("3️⃣ Specify Intended Alignment")

st.write(
    "For accurate evaluation, specify what each question "
    "is intended to assess."
)

if "mapping_rows" not in st.session_state:

    st.session_state.mapping_rows = 5


mapping_count = st.number_input(
    "Number of questions to map",
    min_value=1,
    max_value=100,
    value=st.session_state.mapping_rows
)

st.session_state.mapping_rows = mapping_count


mapping_data = []

for i in range(
    int(mapping_count)
):

    col1, col2, col3, col4 = st.columns(
        [1.2, 2, 2, 2]
    )

    with col1:

        st.write(
            "**Q"
            + str(i + 1)
            + "**"
        )

    with col2:

        clo_options = [
            ""
        ] + [
            item["code"]
            for item in clos
        ]

        expected_clo = st.selectbox(
            "CLO",
            clo_options,
            key="clo_" + str(i),
            label_visibility="collapsed"
        )

    with col3:

        plo_options = [
            ""
        ] + [
            item["code"]
            for item in plos
        ]

        expected_plo = st.selectbox(
            "PLO",
            plo_options,
            key="plo_" + str(i),
            label_visibility="collapsed"
        )

    with col4:

        expected_bloom = st.selectbox(
            "Bloom",
            [
                ""
            ] + BLOOM_LEVELS,
            key="bloom_" + str(i),
            label_visibility="collapsed"
        )

    mapping_data.append(
        {
            "Question": i + 1,
            "CLO": expected_clo,
            "PLO": expected_plo,
            "Bloom": expected_bloom
        }
    )


mapping_df = pd.DataFrame(
    mapping_data
)


# ============================================================
# UPLOAD ASSESSMENT
# ============================================================

st.divider()

st.header("4️⃣ Upload Assessment")

uploaded_file = st.file_uploader(
    "Upload assignment/question paper",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "txt"
    ]
)


# ============================================================
# READ ASSESSMENT
# ============================================================

if uploaded_file:

    st.write(
        "**File:**",
        uploaded_file.name
    )

    if st.button(
        "📖 Read Assessment",
        type="primary"
    ):

        with st.spinner(
            "Reading assessment..."
        ):

            text, method = extract_file(
                uploaded_file
            )

        if text:

            st.session_state.extracted_text = text

            st.session_state.questions = (
                parse_questions(text)
            )

            st.session_state.results = (
                pd.DataFrame()
            )

            st.success(
                "Assessment successfully read using "
                + method
                + "."
            )

        else:

            st.error(
                "Assessment could not be read."
            )

            st.error(
                method
            )


# ============================================================
# SHOW EXTRACTED TEXT
# ============================================================

if st.session_state.extracted_text:

    st.header("5️⃣ Extracted Assessment")

    with st.expander(
        "Show extracted text"
    ):

        st.text_area(
            "Extracted text",
            st.session_state.extracted_text,
            height=400
        )


# ============================================================
# SHOW QUESTIONS
# ============================================================

questions = st.session_state.questions

if questions:

    st.header("6️⃣ Questions Detected")

    st.success(
        str(len(questions))
        + " question(s) detected."
    )

    for i, question in enumerate(
        questions,
        start=1
    ):

        st.write(
            "**Q"
            + str(i)
            + ":** "
            + question
        )


# ============================================================
# RUN EVALUATION
# ============================================================

if questions:

    st.divider()

    if st.button(
        "🎯 Evaluate OBE Alignment",
        type="primary"
    ):

        results = []

        for i, question in enumerate(
            questions,
            start=1
        ):

            # Find mapping for this question.
            row = mapping_df[
                mapping_df["Question"] == i
            ]

            if row.empty:

                expected_clo = ""
                expected_plo = ""
                expected_bloom = ""

            else:

                expected_clo = (
                    row.iloc[0]["CLO"]
                )

                expected_plo = (
                    row.iloc[0]["PLO"]
                )

                expected_bloom = (
                    row.iloc[0]["Bloom"]
                )

            # Find CLO description

            clo_description = ""

            for item in clos:

                if item["code"] == expected_clo:

                    clo_description = (
                        item["description"]
                    )

            # Find PLO description

            plo_description = ""

            for item in plos:

                if item["code"] == expected_plo:

                    plo_description = (
                        item["description"]
                    )

            result = evaluate_question(
                i,
                question,
                expected_clo,
                expected_plo,
                expected_bloom,
                clo_description,
                plo_description,
                clos,
                plos
            )

            results.append(
                result
            )

        st.session_state.results = (
            pd.DataFrame(results)
        )

        st.success(
            "Evaluation completed."
        )


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.results

if not results.empty:

    st.header("7️⃣ OBE Evaluation Results")

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    aligned = len(
        results[
            results["Overall Decision"]
            == "✅ Aligned"
        ]
    )

    partial = len(
        results[
            results["Overall Decision"]
            == "🟡 Partially Aligned"
        ]
    )

    review = len(
        results[
            results["Overall Decision"]
            == "⚠️ Needs Review"
        ]
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Questions",
            len(results)
        )

    with col2:

        st.metric(
            "Aligned",
            aligned
        )

    with col3:

        st.metric(
            "Partial",
            partial
        )

    with col4:

        st.metric(
            "Needs Review",
            review
        )

    st.divider()

    # --------------------------------------------------------
    # Main table
    # --------------------------------------------------------

    display_columns = [
        "Question No.",
        "Question",
        "Marks",
        "Expected Bloom",
        "Detected Bloom",
        "Detected Verb",
        "Bloom Status",
        "Expected CLO",
        "CLO Status",
        "Expected PLO",
        "PLO Status",
        "Overall Decision"
    ]

    st.dataframe(
        results[display_columns],
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # Detailed question review
    # --------------------------------------------------------

    st.header(
        "🔎 Detailed Question-by-Question Review"
    )

    for _, row in results.iterrows():

        with st.expander(
            "Q"
            + str(row["Question No."])
            + " — "
            + row["Overall Decision"]
        ):

            st.write(
                "**Question:** "
                + row["Question"]
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.write(
                    "**Bloom**"
                )

                st.write(
                    "Expected: "
                    + str(row["Expected Bloom"])
                )

                st.write(
                    "Detected: "
                    + str(row["Detected Bloom"])
                )

                st.write(
                    "Verb: "
                    + str(row["Detected Verb"])
                )

                st.write(
                    "Status: "
                    + str(row["Bloom Status"])
                )

            with c2:

                st.write(
                    "**CLO**"
                )

                st.write(
                    "Expected: "
                    + str(row["Expected CLO"])
                )

                st.write(
                    "Suggested: "
                    + str(row["Suggested CLO"])
                )

                st.write(
                    "Status: "
                    + str(row["CLO Status"])
                )

                st.write(
                    "Evidence: "
                    + str(row["CLO Evidence %"])
                    + "%"
                )

            with c3:

                st.write(
                    "**PLO**"
                )

                st.write(
                    "Expected: "
                    + str(row["Expected PLO"])
                )

                st.write(
                    "Suggested: "
                    + str(row["Suggested PLO"])
                )

                st.write(
                    "Status: "
                    + str(row["PLO Status"])
                )

                st.write(
                    "Evidence: "
                    + str(row["PLO Evidence %"])
                    + "%"
                )

            st.info(
                "💡 "
                + row["Explanation"]
            )


# ============================================================
# BLOOM DISTRIBUTION
# ============================================================

if not results.empty:

    st.divider()

    st.header(
        "🧠 Bloom's Taxonomy Distribution"
    )

    bloom_counts = (
        results["Detected Bloom"]
        .value_counts()
        .reindex(
            BLOOM_LEVELS,
            fill_value=0
        )
    )

    st.bar_chart(
        bloom_counts
    )


# ============================================================
# ALIGNMENT SUMMARY
# ============================================================

if not results.empty:

    st.header(
        "📊 Alignment Summary"
    )

    summary_data = pd.DataFrame(
        {
            "Category": [
                "Bloom",
                "CLO",
                "PLO"
            ],
            "Aligned": [
                len(
                    results[
                        results["Bloom Status"]
                        == "Aligned"
                    ]
                ),
                len(
                    results[
                        results["CLO Status"]
                        == "Aligned"
                    ]
                ),
                len(
                    results[
                        results["PLO Status"]
                        == "Aligned"
                    ]
                )
            ],
            "Needs Review": [
                len(
                    results[
                        results["Bloom Status"]
                        == "Needs Review"
                    ]
                ),
                len(
                    results[
                        results["CLO Status"]
                        == "Needs Review"
                    ]
                ),
                len(
                    results[
                        results["PLO Status"]
                        == "Needs Review"
                    ]
                )
            ]
        }
    )

    st.dataframe(
        summary_data,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# QUESTIONS NEEDING FACULTY REVIEW
# ============================================================

if not results.empty:

    st.header(
        "⚠️ Questions Requiring Faculty Review"
    )

    review_df = results[
        results["Overall Decision"]
        == "⚠️ Needs Review"
    ]

    if review_df.empty:

        st.success(
            "No questions were automatically flagged."
        )

    else:

        for _, row in review_df.iterrows():

            st.warning(
                "Q"
                + str(row["Question No."])
                + ": "
                + row["Explanation"]
            )


# ============================================================
# DOWNLOAD REPORT
# ============================================================

if not results.empty:

    st.divider()

    st.header(
        "📥 Download Evaluation Report"
    )

    csv_data = results.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download CSV Report",
        data=csv_data,
        file_name="OBE_Alignment_Report.csv",
        mime="text/csv"
    )

    excel_buffer = BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        results.to_excel(
            writer,
            index=False,
            sheet_name="OBE Evaluation"
        )

        mapping_df.to_excel(
            writer,
            index=False,
            sheet_name="Intended Mapping"
        )

        if clos:

            pd.DataFrame(
                clos
            ).to_excel(
                writer,
                index=False,
                sheet_name="CLOs"
            )

        if plos:

            pd.DataFrame(
                plos
            ).to_excel(
                writer,
                index=False,
                sheet_name="PLOs"
            )

    st.download_button(
        "⬇️ Download Excel Report",
        data=excel_buffer.getvalue(),
        file_name="OBE_Alignment_Report.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


# ============================================================
# FACULTY REVIEW CHECKLIST
# ============================================================

st.divider()

st.header(
    "✅ Faculty Final Review"
)

check1 = st.checkbox(
    "The detected Bloom level represents the actual cognitive demand."
)

check2 = st.checkbox(
    "The question genuinely assesses the selected CLO."
)

check3 = st.checkbox(
    "The question provides evidence for the selected PLO."
)

check4 = st.checkbox(
    "The marks are appropriate for the cognitive demand."
)

check5 = st.checkbox(
    "The final mapping has been reviewed by the faculty member."
)

if all(
    [
        check1,
        check2,
        check3,
        check4,
        check5
    ]
):

    st.success(
        "✅ Faculty review completed."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Alignment Checker | AI-assisted screening tool | "
    "Faculty judgment remains the final authority."
)
