import streamlit as st
import pandas as pd
import io
import re

# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# SESSION STATE
# ============================================================

if "results" not in st.session_state:
    st.session_state.results = []

if "revisions" not in st.session_state:
    st.session_state.revisions = {}

# ============================================================
# TEXT FUNCTIONS
# ============================================================

def clean(text):
    if text is None:
        return ""

    text = str(text)

    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\xa0", " ")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize(text):
    text = clean(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def word_list(text):
    return [
        x
        for x in normalize(text).split()
        if len(x) > 2
    ]


def stem(word):
    word = word.lower()

    for ending in [
        "ization",
        "ation",
        "ments",
        "ment",
        "ingly",
        "edly",
        "ing",
        "ies",
        "ed",
        "es",
        "ly",
        "s"
    ]:
        if len(word) > len(ending) + 3 and word.endswith(ending):
            return word[:-len(ending)]

    return word


def stems(text):
    return {
        stem(x)
        for x in word_list(text)
    }


def final_question(text):
    text = clean(text)

    text = re.sub(
        r"[.!?]+$",
        "",
        text
    )

    return text.strip() + "?"


# ============================================================
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):

    data = uploaded_file.getvalue()

    # --------------------------------------------------------
    # PyMuPDF
    # --------------------------------------------------------

    try:
        import fitz

        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for page in document:
            txt = page.get_text("text")

            if txt:
                pages.append(txt)

        result = "\n".join(pages)

        if result.strip():
            return result, "PyMuPDF"

    except Exception:
        pass

    # --------------------------------------------------------
    # pypdf
    # --------------------------------------------------------

    try:
        import pypdf

        reader = pypdf.PdfReader(
            io.BytesIO(data)
        )

        pages = []

        for page in reader.pages:

            txt = page.extract_text()

            if txt:
                pages.append(txt)

        result = "\n".join(pages)

        if result.strip():
            return result, "pypdf"

    except Exception:
        pass

    # --------------------------------------------------------
    # pdfplumber
    # --------------------------------------------------------

    try:
        import pdfplumber

        pages = []

        with pdfplumber.open(
            io.BytesIO(data)
        ) as pdf:

            for page in pdf.pages:

                txt = page.extract_text()

                if txt:
                    pages.append(txt)

        result = "\n".join(pages)

        if result.strip():
            return result, "pdfplumber"

    except Exception:
        pass

    return "", "No PDF text extractor available"


def read_docx(uploaded_file):

    try:

        from docx import Document

        document = Document(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        content = []

        # Paragraphs
        for paragraph in document.paragraphs:

            text = clean(
                paragraph.text
            )

            if text:
                content.append(text)

        # Tables
        for table in document.tables:

            for row in table.rows:

                cells = []

                for cell in row.cells:

                    value = clean(
                        cell.text
                    )

                    if value:
                        cells.append(value)

                if cells:
                    content.append(
                        " ".join(cells)
                    )

        return "\n".join(content), "python-docx"

    except Exception as e:

        return "", f"DOCX error: {e}"


def read_excel(uploaded_file):

    try:

        data = uploaded_file.getvalue()

        workbook = pd.ExcelFile(
            io.BytesIO(data)
        )

        content = []

        for sheet in workbook.sheet_names:

            content.append(
                f"--- Sheet: {sheet} ---"
            )

            df = pd.read_excel(
                io.BytesIO(data),
                sheet_name=sheet,
                header=None
            )

            for row in df.fillna("").values:

                values = []

                for cell in row:

                    value = clean(cell)

                    if value:
                        values.append(value)

                if values:

                    content.append(
                        " ".join(values)
                    )

        return "\n".join(content), "pandas Excel"


    except Exception as e:

        return "", f"Excel error: {e}"


def read_csv(uploaded_file):

    try:

        data = uploaded_file.getvalue()

        df = pd.read_csv(
            io.BytesIO(data),
            header=None
        )

        content = []

        for row in df.fillna("").values:

            values = []

            for cell in row:

                value = clean(cell)

                if value:
                    values.append(value)

            if values:
                content.append(
                    " ".join(values)
                )

        return "\n".join(content), "pandas CSV"

    except Exception:

        try:

            return (
                uploaded_file
                .getvalue()
                .decode(
                    "utf-8",
                    errors="ignore"
                ),
                "UTF-8 text"
            )

        except Exception as e:

            return "", f"CSV error: {e}"


def read_txt(uploaded_file):

    try:

        return (
            uploaded_file
            .getvalue()
            .decode(
                "utf-8",
                errors="ignore"
            ),
            "UTF-8 text"
        )

    except Exception as e:

        return "", f"TXT error: {e}"


def read_file(uploaded_file):

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if filename.endswith(".docx"):
        return read_docx(uploaded_file)

    if filename.endswith(".xlsx"):
        return read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return read_csv(uploaded_file)

    if filename.endswith(".txt"):
        return read_txt(uploaded_file)

    return "", "Unsupported format"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

QUESTION_START = re.compile(
    r"""
    ^
    (?:
        Q(?:uestion)?\s*
    )?
    (?:
        \d{1,3}
        |
        [A-Z]
    )
    \s*
    [\.\):\-]?
    \s*
    """,
    re.IGNORECASE | re.VERBOSE
)


def remove_question_number(text):

    return QUESTION_START.sub(
        "",
        clean(text)
    ).strip()


def remove_options(text):

    text = clean(text)

    # If A., B., C., D. appear after the question,
    # keep the question and remove options.
    patterns = [
        r"\s+\(?A\)?[\.\):]\s+",
        r"\s+Option\s+A\s*[:\-]\s+"
    ]

    positions = []

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:
            positions.append(
                match.start()
            )

    if positions:

        text = text[
            :min(positions)
        ]

    return clean(text)


def is_header(text):

    n = normalize(text)

    headers = [
        "student name",
        "student id",
        "roll number",
        "registration number",
        "date",
        "time",
        "course code",
        "course title",
        "semester",
        "section",
        "instructor",
        "teacher",
        "total marks",
        "maximum marks",
        "marks obtained",
        "instructions",
        "answer key"
    ]

    for h in headers:

        if n.startswith(h):
            return True

    return False


def is_question_like(text):

    text = clean(text)

    if not text:
        return False

    if is_header(text):
        return False

    if len(word_list(text)) < 4:
        return False

    n = normalize(text)

    question_words = [
        "define",
        "identify",
        "explain",
        "describe",
        "discuss",
        "compare",
        "contrast",
        "differentiate",
        "analyze",
        "analyse",
        "evaluate",
        "assess",
        "justify",
        "calculate",
        "solve",
        "apply",
        "determine",
        "state",
        "list",
        "design",
        "develop",
        "construct",
        "formulate",
        "interpret",
        "classify",
        "what",
        "why",
        "how",
        "which",
        "when",
        "where",
        "write",
        "find",
        "show",
        "derive",
        "prove"
    ]

    if "?" in text:
        return True

    for word in question_words:

        if re.search(
            r"\b" + re.escape(word) + r"\b",
            n
        ):
            return True

    # Long assessment statements are accepted.
    if len(word_list(text)) >= 8:
        return True

    return False


def extract_numbered_questions(text):

    text = clean(text)

    # Preserve line breaks.
    lines = [
        clean(x)
        for x in text.split("\n")
        if clean(x)
    ]

    questions = []

    current = ""

    for line in lines:

        # New numbered question
        if re.match(
            r"^(?:Q(?:uestion)?\s*)?\d{1,3}\s*[\.\):\-]",
            line,
            re.IGNORECASE
        ):

            if current:

                questions.append(
                    current
                )

            current = remove_question_number(
                line
            )

        # Number alone on its own line
        elif re.match(
            r"^(?:Q(?:uestion)?\s*)?\d{1,3}\s*$",
            line,
            re.IGNORECASE
        ):

            if current:

                questions.append(
                    current
                )

            current = ""

        else:

            if current:

                current += " " + line

            else:

                current = line

    if current:
        questions.append(
            current
        )

    final = []

    for q in questions:

        q = remove_options(q)

        q = re.sub(
            r"\s+\(?\d+\s*marks?\)?$",
            "",
            q,
            flags=re.IGNORECASE
        )

        if is_question_like(q):
            final.append(q)

    return final


def extract_question_marks(text):

    chunks = re.split(
        r"(?<=\?)",
        clean(text)
    )

    questions = []

    for chunk in chunks:

        chunk = clean(chunk)

        if is_question_like(chunk):

            questions.append(
                remove_options(chunk)
            )

    return questions


def extract_bullets(text):

    lines = clean(text).split("\n")

    questions = []

    for line in lines:

        line = clean(line)

        line = re.sub(
            r"^[\-\*\•]+\s*",
            "",
            line
        )

        if is_question_like(line):

            questions.append(
                remove_options(line)
            )

    return questions


def extract_fallback_questions(text):

    """
    Very important fallback.

    If the assessment does not use recognizable
    question numbering, every substantial assessment
    line/paragraph is considered as a possible question.

    This prevents the app from returning zero questions
    simply because the document uses an unusual format.
    """

    text = clean(text)

    paragraphs = re.split(
        r"\n\s*\n",
        text
    )

    candidates = []

    for paragraph in paragraphs:

        paragraph = clean(paragraph)

        if not paragraph:
            continue

        if is_header(paragraph):
            continue

        # Split long blocks into sentences where possible.
        sentences = re.split(
            r"(?<=[.!?])\s+",
            paragraph
        )

        if len(sentences) > 1:

            for sentence in sentences:

                sentence = clean(
                    sentence
                )

                if is_question_like(
                    sentence
                ):
                    candidates.append(
                        sentence
                    )

        elif is_question_like(
            paragraph
        ):

            candidates.append(
                paragraph
            )

    # Final line-level fallback
    if not candidates:

        for line in text.split("\n"):

            line = clean(line)

            if (
                len(word_list(line)) >= 5
                and not is_header(line)
            ):
                candidates.append(
                    line
                )

    return candidates


def extract_questions(text):

    text = clean(text)

    if not text:
        return []

    all_questions = []

    # 1. Numbered
    all_questions.extend(
        extract_numbered_questions(
            text
        )
    )

    # 2. Question marks
    all_questions.extend(
        extract_question_marks(
            text
        )
    )

    # 3. Bullets
    all_questions.extend(
        extract_bullets(
            text
        )
    )

    # 4. Fallback
    if not all_questions:

        all_questions.extend(
            extract_fallback_questions(
                text
            )
        )

    # --------------------------------------------------------
    # Clean + deduplicate
    # --------------------------------------------------------

    final = []

    seen = set()

    for q in all_questions:

        q = clean(q)

        q = remove_question_number(q)

        q = remove_options(q)

        if not q:
            continue

        key = normalize(q)

        if key in seen:
            continue

        seen.add(key)

        final.append(q)

    return final


# ============================================================
# OUTCOMES
# ============================================================

def parse_outcomes(text):

    if not text:
        return []

    lines = re.split(
        r"[\n;]+",
        clean(text)
    )

    results = []

    for line in lines:

        line = clean(line)

        line = re.sub(
            r"^(?:CLO|PLO)?\s*\d+\s*[\.\):\-–]*\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        if len(word_list(line)) >= 4:
            results.append(line)

    return results


# ============================================================
# BLOOM
# ============================================================

BLOOM = {
    "Remember": [
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall"
    ],
    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "classify",
        "discuss"
    ],
    "Apply": [
        "apply",
        "calculate",
        "solve",
        "use",
        "implement",
        "demonstrate"
    ],
    "Analyze": [
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "differentiate",
        "examine"
    ],
    "Evaluate": [
        "evaluate",
        "assess",
        "justify",
        "critique",
        "defend",
        "judge"
    ],
    "Create": [
        "design",
        "develop",
        "construct",
        "formulate",
        "create",
        "propose"
    ]
}

BLOOM_ORDER = list(
    BLOOM.keys()
)


def detect_bloom(question):

    n = normalize(question)

    found = []

    for level, verbs in BLOOM.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                n
            ):
                found.append(level)
                break

    if not found:
        return "Understand"

    return max(
        found,
        key=lambda x:
        BLOOM_ORDER.index(x)
    )


def bloom_score(
    question,
    target
):

    detected = detect_bloom(
        question
    )

    if detected == target:
        return 100

    difference = abs(
        BLOOM_ORDER.index(
            detected
        )
        -
        BLOOM_ORDER.index(
            target
        )
    )

    if difference == 1:
        return 80

    if difference == 2:
        return 65

    return 45


# ============================================================
# CLO / PLO
# ============================================================

GENERIC = {
    "understand",
    "knowledge",
    "learning",
    "learn",
    "ability",
    "demonstrate",
    "student",
    "students",
    "skills",
    "skill",
    "course",
    "concept",
    "concepts",
    "principles",
    "principle"
}


def clo_concepts(clo):

    return [
        w
        for w in word_list(clo)
        if stem(w) not in GENERIC
    ]


PLO_ACTIONS = {
    "communication": [
        "communicate",
        "write",
        "present",
        "explain",
        "report"
    ],
    "problem solving": [
        "solve",
        "problem",
        "analyze",
        "analyse",
        "evaluate"
    ],
    "critical thinking": [
        "analyze",
        "analyse",
        "evaluate",
        "compare",
        "justify"
    ],
    "research": [
        "research",
        "investigate",
        "evidence",
        "analyze",
        "analyse"
    ],
    "technology": [
        "technology",
        "software",
        "tool",
        "digital"
    ],
    "ethics": [
        "ethical",
        "ethics",
        "professional",
        "responsible"
    ]
}


def plo_action(plo):

    n = normalize(plo)

    for action, verbs in PLO_ACTIONS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                n
            ):
                return action

    return "problem solving"


def score_clo(question, clo):

    if not clo:
        return 0

    q = stems(question)

    concepts = {
        stem(x)
        for x in clo_concepts(clo)
    }

    overlap = q.intersection(
        concepts
    )

    if not concepts:
        return 70

    ratio = (
        len(overlap)
        /
        len(concepts)
    )

    if len(overlap) >= 3:
        return 100

    if len(overlap) == 2:
        return 90

    if len(overlap) == 1:
        return 82

    if ratio >= 0.3:
        return 80

    return 50


def score_plo(question, plo):

    if not plo:
        return 0

    n = normalize(question)

    action = plo_action(
        plo
    )

    verbs = PLO_ACTIONS.get(
        action,
        []
    )

    if any(
        re.search(
            r"\b" + re.escape(v) + r"\b",
            n
        )
        for v in verbs
    ):
        return 95

    bloom = detect_bloom(
        question
    )

    if action in [
        "problem solving",
        "critical thinking",
        "research"
    ]:

        if bloom in [
            "Analyze",
            "Evaluate",
            "Create"
        ]:
            return 85

    if action == "communication":

        if any(
            x in n
            for x in [
                "explain",
                "describe",
                "write",
                "present",
                "discuss"
            ]
        ):
            return 85

    return 60


# ============================================================
# SUBJECT
# ============================================================

ALIASES = {

    "chemistry": [
        "atom",
        "molecule",
        "chemical",
        "reaction",
        "acid",
        "base",
        "bond",
        "compound",
        "ph"
    ],

    "physics": [
        "force",
        "energy",
        "motion",
        "velocity",
        "momentum",
        "electric",
        "magnetic",
        "wave",
        "mass"
    ],

    "mathematics": [
        "equation",
        "function",
        "matrix",
        "derivative",
        "integral",
        "probability",
        "algebra",
        "calculus"
    ],

    "biology": [
        "cell",
        "gene",
        "protein",
        "enzyme",
        "organism",
        "dna",
        "ecosystem"
    ],

    "english": [
        "writing",
        "reading",
        "grammar",
        "essay",
        "language",
        "paragraph",
        "tone",
        "purpose",
        "main idea"
    ],

    "programming": [
        "code",
        "program",
        "algorithm",
        "variable",
        "function",
        "loop",
        "array",
        "class",
        "object"
    ],

    "computer science": [
        "algorithm",
        "software",
        "computer",
        "database",
        "network",
        "programming"
    ]
}


def score_subject(
    question,
    subject
):

    if not subject:
        return 85

    q = normalize(
        question
    )

    s = normalize(
        subject
    )

    # Direct subject terms
    if s in q:
        return 100

    for subject_name, terms in ALIASES.items():

        if subject_name in s:

            matches = sum(
                1
                for term in terms
                if term in q
            )

            if matches >= 3:
                return 100

            if matches == 2:
                return 95

            if matches == 1:
                return 88

    return 60


# ============================================================
# OTHER SCORES
# ============================================================

def score_specificity(question):

    count = len(
        word_list(question)
    )

    score = 45

    if count >= 8:
        score += 15

    if count >= 12:
        score += 10

    if count >= 16:
        score += 10

    useful_terms = [
        "calculate",
        "compare",
        "differentiate",
        "analyze",
        "analyse",
        "evaluate",
        "justify",
        "given",
        "scenario",
        "evidence",
        "criteria",
        "steps"
    ]

    matches = sum(
        1
        for x in useful_terms
        if x in normalize(question)
    )

    score += min(
        20,
        matches * 5
    )

    return min(
        100,
        score
    )


def score_quality(question):

    score = 50

    if len(question) >= 30:
        score += 10

    if len(question) >= 60:
        score += 10

    if len(word_list(question)) >= 8:
        score += 10

    if question.endswith("?"):
        score += 10

    return min(
        100,
        score
    )


# ============================================================
# EVALUATION
# ============================================================

def evaluate(
    question,
    subject,
    clos,
    plos,
    target_bloom
):

    question = final_question(
        question
    )

    # Best CLO
    best_clo = None
    best_clo_score = 0

    for clo in clos:

        score = score_clo(
            question,
            clo
        )

        if score > best_clo_score:

            best_clo_score = score
            best_clo = clo

    # Best PLO
    best_plo = None
    best_plo_score = 0

    for plo in plos:

        score = score_plo(
            question,
            plo
        )

        if score > best_plo_score:

            best_plo_score = score
            best_plo = plo

    subject_score = score_subject(
        question,
        subject
    )

    bloom = bloom_score(
        question,
        target_bloom
    )

    specificity = score_specificity(
        question
    )

    quality = score_quality(
        question
    )

    overall = (
        subject_score * 0.20
        +
        best_clo_score * 0.25
        +
        best_plo_score * 0.25
        +
        bloom * 0.15
        +
        specificity * 0.10
        +
        quality * 0.05
    )

    overall = round(
        min(100, overall),
        1
    )

    attained = (
        overall >= 80
        and subject_score >= 80
        and best_clo_score >= 80
        and best_plo_score >= 80
        and bloom >= 80
    )

    return {
        "question": question,
        "overall": overall,
        "subject": subject_score,
        "clo": best_clo_score,
        "plo": best_plo_score,
        "bloom": bloom,
        "specificity": specificity,
        "quality": quality,
        "best_clo": best_clo,
        "best_plo": best_plo,
        "attained": attained
    }


# ============================================================
# REVISION
# ============================================================

def make_revisions(
    question,
    subject,
    clos,
    plos,
    target_bloom
):

    best_clo = None
    best_score = -1

    for clo in clos:

        score = score_clo(
            question,
            clo
        )

        if score > best_score:

            best_score = score
            best_clo = clo

    if not best_clo and clos:
        best_clo = clos[0]

    if best_clo:

        concepts = clo_concepts(
            best_clo
        )

        concept = " ".join(
            concepts[:8]
        )

    else:

        concept = subject

    if not concept:
        concept = "the relevant concept"

    best_plo = None

    if plos:

        best_plo = max(
            plos,
            key=lambda x:
            score_plo(
                question,
                x
            )
        )

    action = (
        plo_action(best_plo)
        if best_plo
        else "problem solving"
    )

    candidates = []

    if target_bloom == "Remember":

        candidates = [
            f"Define {concept} and identify its main characteristics",
            f"Identify the main elements of {concept} and state their functions",
            f"List the key features of {concept} and state their significance"
        ]

    elif target_bloom == "Understand":

        candidates = [
            f"Explain {concept} and describe how its main elements are related",
            f"Describe {concept} and explain its main characteristics",
            f"Explain the main principles of {concept} and give a relevant example"
        ]

    elif target_bloom == "Apply":

        candidates = [
            f"Apply {concept} to a relevant problem and explain the result",
            f"Given a relevant scenario involving {concept}, apply the appropriate method and show the result",
            f"Use {concept} to solve a relevant problem and explain the steps"
        ]

    elif target_bloom == "Analyze":

        candidates = [
            f"Analyze {concept} by examining its main components and their relationships",
            f"Analyze {concept} in a relevant scenario and justify your conclusion",
            f"Differentiate the major components of {concept} and explain their relationships",
            f"Analyze a relevant problem involving {concept} and identify the factors affecting the outcome"
        ]

    elif target_bloom == "Evaluate":

        candidates = [
            f"Evaluate {concept} using appropriate criteria and justify your conclusion",
            f"Assess {concept} in a relevant scenario and justify your decision",
            f"Evaluate the effectiveness of {concept} using relevant evidence and justify your conclusion"
        ]

    else:

        candidates = [
            f"Design a solution using {concept} and justify the major decisions",
            f"Develop an appropriate solution based on {concept} and explain the reasoning",
            f"Construct a solution involving {concept} and justify the proposed approach"
        ]

    # PLO-oriented additions
    if action == "communication":

        candidates.append(
            f"Explain {concept} clearly and support your explanation with a relevant example"
        )

    elif action == "research":

        candidates.append(
            f"Analyze {concept} using relevant evidence and justify the conclusion"
        )

    elif action == "critical thinking":

        candidates.append(
            f"Analyze {concept}, compare the relevant factors, and justify the conclusion"
        )

    elif action == "problem solving":

        candidates.append(
            f"Apply {concept} to a relevant problem and justify the solution"
        )

    # --------------------------------------------------------
    # Evaluate all revisions
    # --------------------------------------------------------

    evaluated = []

    seen = set()

    for candidate in candidates:

        candidate = final_question(
            candidate
        )

        key = normalize(
            candidate
        )

        if key in seen:
            continue

        seen.add(key)

        result = evaluate(
            candidate,
            subject,
            clos,
            plos,
            target_bloom
        )

        evaluated.append(
            result
        )

    # Highest real score first
    evaluated.sort(
        key=lambda x: (
            x["attained"],
            x["overall"],
            x["clo"],
            x["plo"]
        ),
        reverse=True
    )

    return evaluated[:3]


# ============================================================
# UI
# ============================================================

st.title(
    "🎓 OBE Assessment Alignment Checker"
)

st.write(
    "Evaluate assessment questions and revise them "
    "for stronger CLO, PLO, Bloom's Taxonomy and "
    "subject alignment."
)

# ------------------------------------------------------------
# COURSE
# ------------------------------------------------------------

col1, col2 = st.columns(2)

with col1:

    subject = st.text_input(
        "Subject / Course",
        placeholder="Example: Chemistry"
    )

with col2:

    target_bloom = st.selectbox(
        "Target Bloom's Level",
        BLOOM_ORDER,
        index=2
    )

# ------------------------------------------------------------
# CLO
# ------------------------------------------------------------

clo_text = st.text_area(
    "CLOs",
    height=140,
    placeholder=(
        "CLO 1: Explain the principles of chemical bonding\n"
        "CLO 2: Apply chemical concepts to solve problems"
    )
)

# ------------------------------------------------------------
# PLO
# ------------------------------------------------------------

plo_text = st.text_area(
    "PLOs",
    height=140,
    placeholder=(
        "PLO 1: Apply knowledge to solve problems\n"
        "PLO 2: Communicate effectively"
    )
)

# ------------------------------------------------------------
# FILE
# ------------------------------------------------------------

uploaded = st.file_uploader(
    "Upload Assessment",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "csv",
        "txt"
    ]
)

# ============================================================
# PROCESS
# ============================================================

if uploaded:

    if st.button(
        "🔍 Evaluate Assessment",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Reading assessment..."
        ):

            raw_text, reader_used = read_file(
                uploaded
            )

        # ----------------------------------------------------
        # ALWAYS SHOW READING RESULT
        # ----------------------------------------------------

        st.subheader(
            "File Reading"
        )

        st.write(
            f"**File:** {uploaded.name}"
        )

        st.write(
            f"**Reader used:** {reader_used}"
        )

        st.write(
            f"**Characters extracted:** {len(raw_text):,}"
        )

        if raw_text:

            with st.expander(
                "👁 View Extracted Text"
            ):

                st.text_area(
                    "Extracted content",
                    raw_text[:15000],
                    height=350
                )

        else:

            st.error(
                "No readable text was extracted from this file."
            )

        # ----------------------------------------------------
        # QUESTION EXTRACTION
        # ----------------------------------------------------

        questions = extract_questions(
            raw_text
        )

        st.write(
            f"**Questions detected:** {len(questions)}"
        )

        # ----------------------------------------------------
        # IMPORTANT: DEBUG FALLBACK
        # ----------------------------------------------------

        if not questions and raw_text:

            st.warning(
                "The document contains readable text, "
                "but the automatic question detector did not "
                "recognize the structure. The system will now "
                "treat substantial text blocks as assessment items."
            )

            lines = [
                clean(x)
                for x in raw_text.split("\n")
                if clean(x)
            ]

            fallback = []

            for line in lines:

                line = remove_question_number(
                    line
                )

                if (
                    len(word_list(line)) >= 5
                    and not is_header(line)
                ):

                    fallback.append(
                        line
                    )

            questions = []

            seen = set()

            for q in fallback:

                key = normalize(q)

                if key not in seen:

                    seen.add(key)

                    questions.append(q)

        # ----------------------------------------------------
        # FINAL RESULT
        # ----------------------------------------------------

        if not questions:

            st.error(
                "No assessment questions could be extracted."
            )

            st.info(
                "The extracted text is shown above. "
                "If the PDF is scanned/image-based, it requires OCR."
            )

        else:

            clos = parse_outcomes(
                clo_text
            )

            plos = parse_outcomes(
                plo_text
            )

            results = []

            for number, question in enumerate(
                questions,
                start=1
            ):

                result = evaluate(
                    question,
                    subject,
                    clos,
                    plos,
                    target_bloom
                )

                result["number"] = number

                results.append(
                    result
                )

            st.session_state.results = results
            st.session_state.revisions = {}

            st.success(
                f"✓ {len(results)} assessment question(s) "
                f"detected successfully."
            )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.results:

    results = st.session_state.results

    st.divider()

    st.header(
        "Assessment Evaluation"
    )

    average = sum(
        x["overall"]
        for x in results
    ) / len(results)

    attained = sum(
        1
        for x in results
        if x["attained"]
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Questions",
            len(results)
        )

    with c2:
        st.metric(
            "Average Score",
            f"{average:.1f}/100"
        )

    with c3:
        st.metric(
            "Initially Attained",
            f"{attained}/{len(results)}"
        )

    # --------------------------------------------------------
    # QUESTIONS
    # --------------------------------------------------------

    for item in results:

        number = item["number"]

        st.divider()

        st.subheader(
            f"Question {number}"
        )

        st.write(
            f"**Original:** {item['question']}"
        )

        if item["attained"]:

            st.success(
                "✓ Alignment is Attained"
            )

        else:

            st.warning(
                "Alignment Needs Revision"
            )

        st.metric(
            "Original Alignment Score",
            f"{item['overall']:.1f}/100"
        )

        score_table = pd.DataFrame(
            {
                "Metric": [
                    "Subject Relevance",
                    "CLO Alignment",
                    "PLO Alignment",
                    "Bloom's Alignment",
                    "Specificity",
                    "Question Quality"
                ],
                "Score": [
                    item["subject"],
                    item["clo"],
                    item["plo"],
                    item["bloom"],
                    item["specificity"],
                    item["quality"]
                ]
            }
        )

        st.dataframe(
            score_table,
            use_container_width=True,
            hide_index=True
        )

        if item["best_clo"]:

            st.caption(
                f"Best CLO: {item['best_clo']}"
            )

        if item["best_plo"]:

            st.caption(
                f"Best PLO: {item['best_plo']}"
            )

        # ----------------------------------------------------
        # REVISIONS
        # ----------------------------------------------------

        if not item["attained"]:

            if number not in st.session_state.revisions:

                st.session_state.revisions[
                    number
                ] = make_revisions(
                    item["question"],
                    subject,
                    parse_outcomes(
                        clo_text
                    ),
                    parse_outcomes(
                        plo_text
                    ),
                    target_bloom
                )

            revisions = (
                st.session_state.revisions[
                    number
                ]
            )

            st.markdown(
                "### 🔧 Suggested Revisions"
            )

            for idx, revision in enumerate(
                revisions,
                start=1
            ):

                st.markdown(
                    f"#### Revision {idx}"
                )

                st.write(
                    revision["question"]
                )

                r1, r2, r3 = st.columns(3)

                with r1:

                    st.metric(
                        "Revised Score",
                        f"{revision['overall']:.1f}/100"
                    )

                with r2:

                    st.metric(
                        "CLO",
                        f"{revision['clo']:.1f}%"
                    )

                with r3:

                    st.metric(
                        "PLO",
                        f"{revision['plo']:.1f}%"
                    )

                if revision["attained"]:

                    st.success(
                        "✓ Alignment is Attained After Revision"
                    )

                else:

                    st.warning(
                        "This revision is below 80/100."
                    )

                comparison = pd.DataFrame(
                    {
                        "Metric": [
                            "Overall",
                            "Subject",
                            "CLO",
                            "PLO",
                            "Bloom's",
                            "Specificity",
                            "Quality"
                        ],
                        "Before": [
                            item["overall"],
                            item["subject"],
                            item["clo"],
                            item["plo"],
                            item["bloom"],
                            item["specificity"],
                            item["quality"]
                        ],
                        "After": [
                            revision["overall"],
                            revision["subject"],
                            revision["clo"],
                            revision["plo"],
                            revision["bloom"],
                            revision["specificity"],
                            revision["quality"]
                        ]
                    }
                )

                st.dataframe(
                    comparison,
                    use_container_width=True,
                    hide_index=True
                )

                if st.button(
                    "✓ Select This Revision",
                    key=f"revision_{number}_{idx}",
                    use_container_width=True
                ):

                    st.session_state.revisions[
                        f"selected_{number}"
                    ] = revision

                    st.rerun()

        # ----------------------------------------------------
        # SELECTED REVISION
        # ----------------------------------------------------

        selected_key = (
            f"selected_{number}"
        )

        if selected_key in st.session_state.revisions:

            selected = (
                st.session_state.revisions[
                    selected_key
                ]
            )

            st.markdown(
                "### ✅ Selected Revised Question"
            )

            st.write(
                f"**{selected['question']}**"
            )

            if selected["overall"] >= 80:

                st.success(
                    "✓ Alignment is Attained After Revision"
                )

                st.metric(
                    "Final Alignment Score",
                    f"{selected['overall']:.1f}/100"
                )

            else:

                st.error(
                    "This revision has not reached 80/100."
                )

                st.metric(
                    "Final Alignment Score",
                    f"{selected['overall']:.1f}/100"
                )


# ============================================================
# EXPORT
# ============================================================

if st.session_state.results:

    st.divider()

    st.header(
        "📥 Export"
    )

    export_rows = []

    for item in st.session_state.results:

        number = item["number"]

        selected_key = (
            f"selected_{number}"
        )

        if selected_key in st.session_state.revisions:

            selected = (
                st.session_state.revisions[
                    selected_key
                ]
            )

            final_question_text = (
                selected["question"]
            )

            final_score = (
                selected["overall"]
            )

            final_status = (
                "Alignment is Attained After Revision"
                if final_score >= 80
                else "Needs Further Revision"
            )

        else:

            final_question_text = (
                item["question"]
            )

            final_score = (
                item["overall"]
            )

            final_status = (
                "Alignment is Attained"
                if item["attained"]
                else "Needs Revision"
            )

        export_rows.append(
            {
                "Question": number,
                "Original Question": item["question"],
                "Original Score": item["overall"],
                "Final Question": final_question_text,
                "Final Score": final_score,
                "Status": final_status
            }
        )

    export_df = pd.DataFrame(
        export_rows
    )

    csv = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Evaluation",
        data=csv,
        file_name="OBE_Alignment_Evaluation.csv",
        mime="text/csv",
        use_container_width=True
    )
