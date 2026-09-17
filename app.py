import streamlit as st
import pandas as pd
import re
import io
import os
import math
from collections import Counter

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎓",
    layout="wide"
)

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

BLOOM_VERBS = {
    "Remember": [
        "define", "list", "name", "identify", "state", "recall",
        "recognize", "mention", "label", "select", "describe"
    ],
    "Understand": [
        "explain", "summarize", "interpret", "discuss", "classify",
        "compare", "paraphrase", "illustrate", "describe", "outline"
    ],
    "Apply": [
        "apply", "use", "demonstrate", "solve", "calculate", "execute",
        "implement", "show", "construct", "perform"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "examine", "compare",
        "contrast", "categorize", "distinguish", "investigate",
        "deconstruct", "relate", "break down"
    ],
    "Evaluate": [
        "evaluate", "justify", "critique", "assess", "judge", "defend",
        "appraise", "recommend", "argue", "validate", "critically assess"
    ],
    "Create": [
        "create", "design", "develop", "formulate", "produce", "construct",
        "compose", "plan", "propose", "generate", "write", "develop a"
    ]
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for",
    "with", "by", "from", "at", "as", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "their", "they", "them", "you", "your", "we",
    "our", "which", "what", "how", "why", "when", "where", "who",
    "can", "could", "should", "would", "will", "may", "might",
    "do", "does", "did", "into", "than", "then", "also"
}

# ============================================================
# BASIC TEXT UTILITIES
# ============================================================

def clean_text(text):
    text = str(text or "")
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")

    # Normalize common OCR characters
    replacements = {
        "–": "-",
        "—": "-",
        "−": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_code(code):
    code = str(code).upper().strip()
    code = re.sub(r"[\s_\-]+", "", code)

    # CLO 1 -> CLO1
    if re.fullmatch(r"CLO\d+", code):
        return code

    if re.fullmatch(r"PLO\d+", code):
        return code

    return code


def tokenize(text):
    text = str(text or "").lower()
    words = re.findall(r"[a-zA-Z]{3,}", text)

    return [
        w for w in words
        if w not in STOPWORDS
    ]


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text, outcome_type):
    """
    Parses many formats such as:

    CLO1: Analyze academic texts.
    CLO 1 - Analyze academic texts.
    CLO-1: Analyze academic texts.
    1. Analyze academic texts.

    Same for PLOs.
    """

    text = clean_text(text)

    if not text:
        return []

    pattern = rf"""
        (?P<code>
            {outcome_type}\s*[-_]?\s*\d+
        )
        \s*
        (?:
            [:.\-–—]\s*
        )?
        (?P<desc>
            .*?
        )
        (?=
            {outcome_type}\s*[-_]?\s*\d+
            \s*(?:[:.\-–—])?
            |
            \n\s*{outcome_type}\s*[-_]?\s*\d+
            |
            $
        )
    """

    matches = re.finditer(
        pattern,
        text,
        flags=re.IGNORECASE | re.VERBOSE | re.DOTALL
    )

    results = []

    for match in matches:
        code = normalize_code(match.group("code"))
        desc = clean_text(match.group("desc"))

        desc = re.sub(r"^[\s:.\-–—]+", "", desc)
        desc = re.sub(r"\s+", " ", desc).strip()

        if desc:
            results.append({
                "Code": code,
                "Description": desc
            })

    # --------------------------------------------------------
    # Alternative line-by-line parser
    # --------------------------------------------------------

    if not results:

        lines = [x.strip() for x in text.splitlines() if x.strip()]

        current_code = None
        current_description = []

        for line in lines:

            match = re.match(
                rf"^({outcome_type}\s*[-_]?\s*\d+)\s*(?:[:.\-–—])?\s*(.*)$",
                line,
                flags=re.IGNORECASE
            )

            if match:

                if current_code and current_description:
                    results.append({
                        "Code": normalize_code(current_code),
                        "Description": clean_text(
                            " ".join(current_description)
                        )
                    })

                current_code = match.group(1)
                current_description = [match.group(2)]

            elif current_code:
                current_description.append(line)

        if current_code and current_description:
            results.append({
                "Code": normalize_code(current_code),
                "Description": clean_text(
                    " ".join(current_description)
                )
            })

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique = []

    seen = set()

    for item in results:

        key = (
            item["Code"],
            item["Description"].lower()
        )

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):
    q = question.lower()

    scores = {
        level: 0
        for level in BLOOM_LEVELS
    }

    matched_verbs = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            pattern = r"\b" + re.escape(verb) + r"\b"

            if re.search(pattern, q):

                scores[level] += 1
                matched_verbs.append((verb, level))

    # --------------------------------------------------------
    # Cognitive clues beyond explicit verbs
    # --------------------------------------------------------

    if re.search(r"\bwhy\b", q):
        scores["Analyze"] += 1

    if re.search(r"\bhow\b", q):
        scores["Understand"] += 1

    if re.search(
        r"\bcompare\b|\bcontrast\b|\bdifference between\b",
        q
    ):
        scores["Analyze"] += 2

    if re.search(
        r"\bjustify\b|\bdefend\b|\bcritically assess\b",
        q
    ):
        scores["Evaluate"] += 2

    if re.search(
        r"\bdesign\b|\bdevelop\b|\bcreate\b|\bpropose\b|\bformulate\b",
        q
    ):
        scores["Create"] += 2

    if re.search(
        r"\bcalculate\b|\bsolve\b|\bapply\b|\buse\b",
        q
    ):
        scores["Apply"] += 2

    max_score = max(scores.values())

    if max_score == 0:
        return {
            "level": "Needs Review",
            "verbs": [],
            "scores": scores
        }

    candidates = [
        level for level, score in scores.items()
        if score == max_score
    ]

    # Prefer higher cognitive demand when tied
    priority = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    detected = sorted(
        candidates,
        key=lambda x: priority[x],
        reverse=True
    )[0]

    return {
        "level": detected,
        "verbs": [x[0] for x in matched_verbs],
        "scores": scores
    }


# ============================================================
# BLOOM COMPARISON
# ============================================================

def compare_bloom(intended, detected):
    if detected == "Needs Review":
        return "Needs Review"

    if intended == detected:
        return "Aligned"

    intended_rank = BLOOM_LEVELS.index(intended)
    detected_rank = BLOOM_LEVELS.index(detected)

    difference = abs(intended_rank - detected_rank)

    if difference == 1:
        return "Partially Aligned"

    return "Not Aligned"


def bloom_feedback(intended, detected, question):
    if detected == "Needs Review":
        return (
            "The tool could not identify a clear Bloom-level action "
            "from the question. Review the wording manually and make "
            "the intended cognitive action explicit."
        )

    if intended == detected:
        return (
            f"The question appears consistent with the intended "
            f"Bloom level of {intended}. The wording contains "
            f"cognitive demand associated with {detected}."
        )

    intended_rank = BLOOM_LEVELS.index(intended)
    detected_rank = BLOOM_LEVELS.index(detected)

    if detected_rank < intended_rank:
        return (
            f"The intended level is {intended}, but the question "
            f"appears to operate at the lower level of {detected}. "
            f"Increase the cognitive demand by requiring students "
            f"to analyze, evaluate, apply, or create rather than "
            f"only recall or explain information."
        )

    return (
        f"The intended level is {intended}, while the question "
        f"appears to require {detected}. Check whether the question "
        f"is demanding more cognitive processing than intended."
    )


# ============================================================
# SEMANTIC-LIKE TEXT SIMILARITY
# ============================================================

def similarity_score(question, outcome):
    """
    Lightweight semantic-like matching without external AI APIs.

    Uses:
    - meaningful word overlap
    - word frequency
    - phrase overlap
    """

    q_words = tokenize(question)
    o_words = tokenize(outcome)

    if not q_words or not o_words:
        return 0.0

    q_counter = Counter(q_words)
    o_counter = Counter(o_words)

    common = set(q_words) & set(o_words)

    if not common:
        return 0.0

    overlap = sum(
        min(q_counter[w], o_counter[w])
        for w in common
    )

    # Dice-style similarity
    score = (
        2 * overlap /
        (len(q_words) + len(o_words))
    )

    return round(score * 100, 1)


# ============================================================
# CLO / PLO MATCHING
# ============================================================

def find_best_outcome(question, outcomes):
    if not outcomes:
        return None, 0.0

    scored = []

    for outcome in outcomes:

        score = similarity_score(
            question,
            outcome["Description"]
        )

        scored.append(
            (
                outcome,
                score
            )
        )

    scored.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return scored[0]


def outcome_status(score):
    if score >= 30:
        return "Strong Alignment"

    if score >= 15:
        return "Partial Alignment"

    return "Needs Review"


def outcome_feedback(
    question,
    outcome,
    score,
    outcome_type
):

    if outcome is None:
        return (
            f"No {outcome_type} was provided for comparison."
        )

    status = outcome_status(score)

    if status == "Strong Alignment":
        return (
            f"The question has substantial conceptual overlap "
            f"with {outcome['Code']}. The tool found meaningful "
            f"connections between the question and the outcome."
        )

    if status == "Partial Alignment":
        return (
            f"The question has some connection with "
            f"{outcome['Code']}, but the alignment is not strong "
            f"enough to be accepted automatically. Faculty review "
            f"is recommended."
        )

    return (
        f"The question has limited textual/conceptual overlap "
        f"with {outcome['Code']}. Consider whether another CLO/PLO "
        f"is more appropriate or revise the question to make the "
        f"intended learning outcome clearer."
    )


# ============================================================
# MARKS EXTRACTION
# ============================================================

def extract_marks(text):
    patterns = [
        r"\((\d+)\s*marks?\)",
        r"\[(\d+)\s*marks?\]",
        r"(\d+)\s*marks?",
        r"(\d+)\s*points?"
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
# FILE EXTRACTION
# ============================================================

def extract_pdf(uploaded_file):

    try:

        from pypdf import PdfReader

        reader = PdfReader(uploaded_file)

        pages = []

        for page in reader.pages:

            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            if text.strip():
                pages.append(text)

        extracted = "\n\n".join(pages)

        if extracted.strip():
            return clean_text(extracted), "PDF text extraction"

    except Exception as e:

        st.warning(
            f"PDF text extraction issue: {e}"
        )

    # --------------------------------------------------------
    # OCR fallback
    # --------------------------------------------------------

    try:

        import pytesseract
        from pdf2image import convert_from_bytes

        uploaded_file.seek(0)

        pdf_bytes = uploaded_file.read()

        st.info(
            "No selectable PDF text was found. "
            "The tool is attempting OCR."
        )

        images = convert_from_bytes(
            pdf_bytes,
            dpi=250
        )

        ocr_pages = []

        progress = st.progress(0)

        total = len(images)

        for i, image in enumerate(images):

            text = pytesseract.image_to_string(
                image,
                config="--oem 3 --psm 6"
            )

            if text.strip():
                ocr_pages.append(text)

            progress.progress(
                (i + 1) / total
            )

        progress.empty()

        result = "\n\n".join(ocr_pages)

        if result.strip():
            return clean_text(result), "PDF OCR"

        return "", "No text could be extracted from PDF"

    except Exception as e:

        return "", (
            "PDF OCR failed. Make sure requirements.txt contains "
            "pypdf, pytesseract, pdf2image, Pillow and packages.txt "
            "contains tesseract-ocr and poppler-utils. "
            f"Technical detail: {e}"
        )


def extract_docx(uploaded_file):

    try:

        from docx import Document

        document = Document(uploaded_file)

        paragraphs = []

        for paragraph in document.paragraphs:

            if paragraph.text.strip():
                paragraphs.append(
                    paragraph.text
                )

        return (
            clean_text("\n".join(paragraphs)),
            "DOCX extraction"
        )

    except Exception as e:

        return "", f"DOCX extraction failed: {e}"


def extract_excel(uploaded_file):

    try:

        excel = pd.ExcelFile(uploaded_file)

        all_text = []

        for sheet in excel.sheet_names:

            df = pd.read_excel(
                uploaded_file,
                sheet_name=sheet,
                header=None
            )

            all_text.append(
                f"Sheet: {sheet}"
            )

            for row in df.astype(str).values:

                row_text = " ".join(
                    [
                        str(x)
                        for x in row
                        if str(x).lower() != "nan"
                    ]
                )

                if row_text.strip():
                    all_text.append(row_text)

            uploaded_file.seek(0)

        return (
            clean_text("\n".join(all_text)),
            "Excel extraction"
        )

    except Exception as e:

        return "", f"Excel extraction failed: {e}"


def extract_txt(uploaded_file):

    try:

        raw = uploaded_file.read()

        for encoding in [
            "utf-8",
            "utf-16",
            "latin-1"
        ]:

            try:

                text = raw.decode(encoding)

                return (
                    clean_text(text),
                    "TXT extraction"
                )

            except Exception:
                continue

        return "", "TXT encoding could not be detected"

    except Exception as e:

        return "", f"TXT extraction failed: {e}"


def extract_file(uploaded_file):

    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return extract_pdf(uploaded_file)

    if name.endswith(".docx"):
        return extract_docx(uploaded_file)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return extract_excel(uploaded_file)

    if name.endswith(".txt"):
        return extract_txt(uploaded_file)

    return "", "Unsupported file type"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def parse_questions(text):

    text = clean_text(text)

    if not text:
        return []

    # Normalize question labels
    text = re.sub(
        r"\bQUESTION\s*(\d+)\b",
        r"Q\1",
        text,
        flags=re.IGNORECASE
    )

    # --------------------------------------------------------
    # Try numbered questions
    # --------------------------------------------------------

    pattern = r"(?:^|\n)\s*(?:Q(?:uestion)?\s*)?(\d+)\s*[\.\):\-]\s*(.*?)(?=(?:\n\s*(?:Q(?:uestion)?\s*)?\d+\s*[\.\):\-])|$)"

    matches = re.finditer(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    questions = []

    for match in matches:

        number = match.group(1)

        content = clean_text(
            match.group(2)
        )

        if len(content) >= 8:

            questions.append({
                "Question": f"Q{number}",
                "Text": content
            })

    # --------------------------------------------------------
    # If numbered parsing failed, split by question marks
    # --------------------------------------------------------

    if not questions:

        chunks = re.split(
            r"(?<=[?])\s+",
            text
        )

        counter = 1

        for chunk in chunks:

            chunk = clean_text(chunk)

            if len(chunk) >= 15:

                questions.append({
                    "Question": f"Q{counter}",
                    "Text": chunk
                })

                counter += 1

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique = []

    seen = set()

    for q in questions:

        key = q["Text"].lower()

        if key not in seen:

            seen.add(key)
            unique.append(q)

    return unique


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question_number,
    question_text,
    intended_bloom,
    clos,
    plos,
    total_questions
):

    bloom_result = detect_bloom(
        question_text
    )

    detected_bloom = bloom_result["level"]

    bloom_alignment = compare_bloom(
        intended_bloom,
        detected_bloom
    )

    best_clo, clo_score = find_best_outcome(
        question_text,
        clos
    )

    best_plo, plo_score = find_best_outcome(
        question_text,
        plos
    )

    marks = extract_marks(
        question_text
    )

    # --------------------------------------------------------
    # Overall status
    # --------------------------------------------------------

    issues = []

    if bloom_alignment != "Aligned":
        issues.append("Bloom mismatch")

    if clo_score < 15:
        issues.append("Weak CLO alignment")

    if plo_score < 15:
        issues.append("Weak PLO alignment")

    if detected_bloom == "Needs Review":
        issues.append("Bloom needs review")

    if issues:
        overall = "Needs Review"
    else:
        overall = "Aligned"

    # --------------------------------------------------------
    # Detailed feedback
    # --------------------------------------------------------

    bloom_comment = bloom_feedback(
        intended_bloom,
        detected_bloom,
        question_text
    )

    clo_comment = outcome_feedback(
        question_text,
        best_clo,
        clo_score,
        "CLO"
    )

    plo_comment = outcome_feedback(
        question_text,
        best_plo,
        plo_score,
        "PLO"
    )

    # --------------------------------------------------------
    # Improvement suggestion
    # --------------------------------------------------------

    suggestions = []

    if bloom_alignment != "Aligned":

        suggestions.append(
            f"Revise the question so its cognitive demand "
            f"clearly reflects the intended Bloom level "
            f"({intended_bloom})."
        )

    if clo_score < 15:

        suggestions.append(
            "Check whether the question directly assesses "
            "the selected learning outcome."
        )

    if plo_score < 15:

        suggestions.append(
            "Check whether the question provides sufficient "
            "evidence for the selected program outcome."
        )

    if not suggestions:

        suggestions.append(
            "The question appears reasonably aligned. "
            "Faculty should still review the content and "
            "academic appropriateness."
        )

    return {
        "Question": question_number,
        "Question Text": question_text,
        "Marks": marks if marks is not None else "",
        "Intended Bloom": intended_bloom,
        "Detected Bloom": detected_bloom,
        "Bloom Alignment": bloom_alignment,
        "Bloom Evidence": ", ".join(
            bloom_result["verbs"]
        ),
        "CLO": (
            best_clo["Code"]
            if best_clo
            else "None detected"
        ),
        "CLO Score": clo_score,
        "CLO Alignment": outcome_status(
            clo_score
        ),
        "PLO": (
            best_plo["Code"]
            if best_plo
            else "None detected"
        ),
        "PLO Score": plo_score,
        "PLO Alignment": outcome_status(
            plo_score
        ),
        "Overall Status": overall,
        "Bloom Feedback": bloom_comment,
        "CLO Feedback": clo_comment,
        "PLO Feedback": plo_comment,
        "Suggested Improvement": " ".join(
            suggestions
        )
    }


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""

if "questions" not in st.session_state:
    st.session_state.questions = []


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Alignment Checker")

st.write(
    "Enter your intended CLO, PLO and Bloom information, "
    "upload a quiz, and check whether the actual questions "
    "match your intended OBE design."
)

st.info(
    "The tool provides an automated review. Final academic "
    "judgment should always be made by the faculty member."
)

# ============================================================
# STEP 1: COURSE
# ============================================================

st.header("1. Course Information")

course_name = st.text_input(
    "Course Name",
    placeholder="e.g., English I"
)

# ============================================================
# STEP 2: CLO
# ============================================================

st.header("2. Enter Course Learning Outcomes (CLOs)")

st.caption(
    "Enter one CLO per line. Example: CLO1: Identify the main idea."
)

clo_text = st.text_area(
    "CLOs",
    height=160,
    placeholder=(
        "CLO1: Identify the main idea of a passage.\n"
        "CLO2: Analyze patterns of organization in academic texts.\n"
        "CLO3: Apply critical reading strategies."
    )
)

clos = parse_outcomes(
    clo_text,
    "CLO"
)

if clos:

    st.success(
        f"{len(clos)} CLO(s) detected."
    )

    st.dataframe(
        pd.DataFrame(clos),
        use_container_width=True,
        hide_index=True
    )

else:

    if clo_text.strip():
        st.warning(
            "CLO text was entered, but the tool could not "
            "identify the CLO codes. Use formats such as "
            "'CLO1: ...' or 'CLO 1: ...'."
        )

# ============================================================
# STEP 3: PLO
# ============================================================

st.header("3. Enter Program Learning Outcomes (PLOs)")

st.caption(
    "Enter one PLO per line. Example: PLO1: Communication Skills."
)

plo_text = st.text_area(
    "PLOs",
    height=160,
    placeholder=(
        "PLO1: Communication Skills.\n"
        "PLO2: Critical Thinking.\n"
        "PLO3: Problem Solving."
    )
)

plos = parse_outcomes(
    plo_text,
    "PLO"
)

if plos:

    st.success(
        f"{len(plos)} PLO(s) detected."
    )

    st.dataframe(
        pd.DataFrame(plos),
        use_container_width=True,
        hide_index=True
    )

else:

    if plo_text.strip():
        st.warning(
            "PLO text was entered, but the tool could not "
            "identify the PLO codes. Use formats such as "
            "'PLO1: ...' or 'PLO 1: ...'."
        )

# ============================================================
# STEP 4: INTENDED BLOOM
# ============================================================

st.header("4. Intended Bloom's Taxonomy Level")

intended_bloom = st.selectbox(
    "What Bloom level was intended for this quiz?",
    BLOOM_LEVELS,
    index=3
)

st.info(
    f"The quiz is intended to assess students at the "
    f"**{intended_bloom}** level."
)

# ============================================================
# STEP 5: UPLOAD QUIZ
# ============================================================

st.header("5. Upload Quiz")

uploaded_file = st.file_uploader(
    "Upload your quiz",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "txt"
    ],
    help=(
        "PDF, DOCX, XLSX, XLS and TXT are supported."
    )
)

# ============================================================
# ANALYZE BUTTON
# ============================================================

if uploaded_file:

    st.write(
        f"Uploaded file: **{uploaded_file.name}**"
    )

    if st.button(
        "🔍 Read and Analyze Quiz",
        type="primary",
        use_container_width=True
    ):

        if not course_name.strip():

            st.error(
                "Please enter the course name."
            )
            st.stop()

        if not clos:

            st.error(
                "Please enter at least one CLO."
            )
            st.stop()

        if not plos:

            st.error(
                "Please enter at least one PLO."
            )
            st.stop()

        # ----------------------------------------------------
        # Extract
        # ----------------------------------------------------

        with st.spinner(
            "Reading the uploaded quiz..."
        ):

            text, method = extract_file(
                uploaded_file
            )

        if not text.strip():

            st.error(
                f"The quiz could not be read. {method}"
            )
            st.stop()

        st.session_state.extracted_text = text

        # ----------------------------------------------------
        # Parse questions
        # ----------------------------------------------------

        questions = parse_questions(
            text
        )

        st.session_state.questions = questions

        if not questions:

            st.error(
                "The file was read, but no questions could "
                "be identified. Please make sure questions "
                "are numbered, for example Q1, Q2, Q3."
            )
            st.stop()

        # ----------------------------------------------------
        # Evaluate
        # ----------------------------------------------------

        results = []

        total_questions = len(
            questions
        )

        progress = st.progress(0)

        for i, question in enumerate(
            questions
        ):

            result = evaluate_question(
                question["Question"],
                question["Text"],
                intended_bloom,
                clos,
                plos,
                total_questions
            )

            results.append(
                result
            )

            progress.progress(
                (i + 1) / total_questions
            )

        progress.empty()

        df_results = pd.DataFrame(
            results
        )

        st.session_state.analysis_results = df_results

        st.success(
            f"Analysis completed for {len(results)} question(s)."
        )

# ============================================================
# DISPLAY RESULTS
# ============================================================

if st.session_state.analysis_results is not None:

    df = st.session_state.analysis_results

    st.divider()

    st.header("6. Overall OBE Analysis")

    # --------------------------------------------------------
    # Summary metrics
    # --------------------------------------------------------

    total = len(df)

    bloom_aligned = int(
        (df["Bloom Alignment"] == "Aligned").sum()
    )

    clo_aligned = int(
        (df["CLO Alignment"] == "Strong Alignment").sum()
    )

    plo_aligned = int(
        (df["PLO Alignment"] == "Strong Alignment").sum()
    )

    overall_aligned = int(
        (df["Overall Status"] == "Aligned").sum()
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Questions",
        total
    )

    col2.metric(
        "Bloom Aligned",
        f"{bloom_aligned}/{total}"
    )

    col3.metric(
        "CLO Strongly Aligned",
        f"{clo_aligned}/{total}"
    )

    col4.metric(
        "PLO Strongly Aligned",
        f"{plo_aligned}/{total}"
    )

    # --------------------------------------------------------
    # Overall interpretation
    # --------------------------------------------------------

    st.subheader(
        "Overall Interpretation"
    )

    overall_percentage = (
        overall_aligned / total * 100
        if total
        else 0
    )

    if overall_percentage >= 80:

        st.success(
            f"{overall_percentage:.0f}% of questions passed "
            "the automated alignment checks."
        )

    elif overall_percentage >= 50:

        st.warning(
            f"{overall_percentage:.0f}% of questions passed "
            "the automated alignment checks. Several questions "
            "should be reviewed."
        )

    else:

        st.error(
            f"{overall_percentage:.0f}% of questions passed "
            "the automated alignment checks. The quiz requires "
            "substantial review."
        )

    # --------------------------------------------------------
    # Bloom distribution
    # --------------------------------------------------------

    st.subheader(
        "Bloom Level Distribution"
    )

    bloom_counts = (
        df["Detected Bloom"]
        .value_counts()
        .reindex(
            BLOOM_LEVELS,
            fill_value=0
        )
    )

    bloom_table = pd.DataFrame({
        "Bloom Level": bloom_counts.index,
        "Questions": bloom_counts.values
    })

    st.dataframe(
        bloom_table,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # CLO coverage
    # --------------------------------------------------------

    st.subheader(
        "CLO Coverage"
    )

    clo_counts = (
        df["CLO"]
        .value_counts()
        .reset_index()
    )

    clo_counts.columns = [
        "CLO",
        "Questions"
    ]

    st.dataframe(
        clo_counts,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # PLO coverage
    # --------------------------------------------------------

    st.subheader(
        "PLO Coverage"
    )

    plo_counts = (
        df["PLO"]
        .value_counts()
        .reset_index()
    )

    plo_counts.columns = [
        "PLO",
        "Questions"
    ]

    st.dataframe(
        plo_counts,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # QUESTION-BY-QUESTION REVIEW
    # ========================================================

    st.divider()

    st.header(
        "7. Detailed Question-by-Question Feedback"
    )

    for _, row in df.iterrows():

        question_title = (
            f"{row['Question']} — "
            f"{row['Overall Status']}"
        )

        with st.expander(
            question_title,
            expanded=True
        ):

            st.markdown(
                f"**Question:** {row['Question Text']}"
            )

            st.markdown("---")

            col1, col2, col3 = st.columns(3)

            with col1:

                st.markdown(
                    "**Bloom Analysis**"
                )

                st.write(
                    f"Intended: **{row['Intended Bloom']}**"
                )

                st.write(
                    f"Detected: **{row['Detected Bloom']}**"
                )

                st.write(
                    f"Result: **{row['Bloom Alignment']}**"
                )

                if row["Bloom Evidence"]:

                    st.write(
                        "Detected wording: "
                        + row["Bloom Evidence"]
                    )

            with col2:

                st.markdown(
                    "**CLO Analysis**"
                )

                st.write(
                    f"Best match: **{row['CLO']}**"
                )

                st.write(
                    f"Similarity evidence: "
                    f"**{row['CLO Score']}%**"
                )

                st.write(
                    f"Result: **{row['CLO Alignment']}**"
                )

            with col3:

                st.markdown(
                    "**PLO Analysis**"
                )

                st.write(
                    f"Best match: **{row['PLO']}**"
                )

                st.write(
                    f"Similarity evidence: "
                    f"**{row['PLO Score']}%**"
                )

                st.write(
                    f"Result: **{row['PLO Alignment']}**"
                )

            st.markdown("---")

            st.markdown(
                "**Bloom Feedback**"
            )

            st.write(
                row["Bloom Feedback"]
            )

            st.markdown(
                "**CLO Feedback**"
            )

            st.write(
                row["CLO Feedback"]
            )

            st.markdown(
                "**PLO Feedback**"
            )

            st.write(
                row["PLO Feedback"]
            )

            st.markdown(
                "**Suggested Improvement**"
            )

            st.info(
                row["Suggested Improvement"]
            )

    # ========================================================
    # QUESTIONS NEEDING REVIEW
    # ========================================================

    st.divider()

    st.header(
        "8. Questions Needing Faculty Review"
    )

    review_df = df[
        df["Overall Status"] == "Needs Review"
    ]

    if review_df.empty:

        st.success(
            "No questions were flagged by the automated checks."
        )

    else:

        st.warning(
            f"{len(review_df)} question(s) require review."
        )

        display_columns = [
            "Question",
            "Detected Bloom",
            "Bloom Alignment",
            "CLO",
            "CLO Alignment",
            "PLO",
            "PLO Alignment",
            "Suggested Improvement"
        ]

        st.dataframe(
            review_df[display_columns],
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # FULL RESULTS TABLE
    # ========================================================

    st.divider()

    st.header(
        "9. Complete Analysis Table"
    )

    display_columns = [
        "Question",
        "Marks",
        "Intended Bloom",
        "Detected Bloom",
        "Bloom Alignment",
        "CLO",
        "CLO Score",
        "CLO Alignment",
        "PLO",
        "PLO Score",
        "PLO Alignment",
        "Overall Status"
    ]

    st.dataframe(
        df[display_columns],
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # DOWNLOAD REPORT
    # ========================================================

    st.divider()

    st.header(
        "10. Download Report"
    )

    csv_data = df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download CSV Report",
        data=csv_data,
        file_name="OBE_Alignment_Report.csv",
        mime="text/csv",
        use_container_width=True
    )

    excel_buffer = io.BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Question Analysis"
        )

        pd.DataFrame(
            clos
        ).to_excel(
            writer,
            index=False,
            sheet_name="CLOs"
        )

        pd.DataFrame(
            plos
        ).to_excel(
            writer,
            index=False,
            sheet_name="PLOs"
        )

        bloom_table.to_excel(
            writer,
            index=False,
            sheet_name="Bloom Distribution"
        )

    st.download_button(
        "Download Excel Report",
        data=excel_buffer.getvalue(),
        file_name="OBE_Alignment_Report.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        use_container_width=True
    )

    # ========================================================
    # FACULTY FINAL CHECK
    # ========================================================

    st.divider()

    st.header(
        "11. Faculty Final Verification"
    )

    st.checkbox(
        "I have reviewed the detected Bloom levels."
    )

    st.checkbox(
        "I have reviewed the CLO alignment."
    )

    st.checkbox(
        "I have reviewed the PLO alignment."
    )

    st.checkbox(
        "I have checked whether the questions actually measure the intended learning outcomes."
    )

    st.checkbox(
        "I understand that automated feedback should be verified by the faculty member."
    )

    st.success(
        "The automated analysis is complete. "
        "Use the detailed feedback to identify what needs "
        "to be corrected in the quiz."
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "Workshop Workflow"
    )

    st.write(
        "1. Enter CLOs"
    )

    st.write(
        "2. Enter PLOs"
    )

    st.write(
        "3. Select intended Bloom level"
    )

    st.write(
        "4. Upload quiz"
    )

    st.write(
        "5. Analyze"
    )

    st.write(
        "6. Review question-level feedback"
    )

    st.write(
        "7. Download report"
    )

    st.divider()

    st.caption(
        "OBE Alignment Checker"
    )

    st.caption(
        "Automated academic alignment support"
    )
