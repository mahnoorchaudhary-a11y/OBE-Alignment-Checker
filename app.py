import streamlit as st
import pandas as pd
import io
import re
from difflib import SequenceMatcher


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# CONSTANTS
# ============================================================

ATTAINMENT_THRESHOLD = 80

METRICS = [
    "CLO Alignment",
    "PLO Alignment",
    "Bloom Alignment",
    "Subject Relevance",
    "Clarity",
    "Measurability"
]

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name",
        "state", "recall", "recognize", "label"
    ],
    "Understand": [
        "explain", "describe", "summarize",
        "interpret", "classify", "discuss",
        "illustrate", "paraphrase"
    ],
    "Apply": [
        "apply", "calculate", "solve",
        "demonstrate", "use", "implement",
        "execute", "perform"
    ],
    "Analyze": [
        "analyze", "analyse", "compare",
        "contrast", "differentiate",
        "examine", "investigate",
        "categorize", "deconstruct"
    ],
    "Evaluate": [
        "evaluate", "assess", "justify",
        "critique", "judge", "defend",
        "appraise", "recommend"
    ],
    "Create": [
        "design", "create", "develop",
        "construct", "formulate",
        "produce", "plan", "propose"
    ]
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to",
    "in", "on", "for", "with", "by", "is",
    "are", "was", "were", "be", "as", "at",
    "from", "that", "this", "these", "those",
    "into", "using", "use", "used", "can",
    "may", "will", "student", "students",
    "question", "questions", "following",
    "answer", "answers"
}


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

if "questions" not in st.session_state:
    st.session_state.questions = []

if "results" not in st.session_state:
    st.session_state.results = []

if "file_name" not in st.session_state:
    st.session_state.file_name = ""

if "subject" not in st.session_state:
    st.session_state.subject = ""

if "course" not in st.session_state:
    st.session_state.course = ""

if "clo_text" not in st.session_state:
    st.session_state.clo_text = ""

if "plo_text" not in st.session_state:
    st.session_state.plo_text = ""


# ============================================================
# SIMPLE CSS
# ============================================================

st.markdown(
    """
    <style>
    .title {
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .subtitle {
        color: #666;
        margin-bottom: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")

    # Normalize common PDF / Word symbols
    text = text.replace("»", " » ")
    text = text.replace("•", " ")
    text = text.replace("–", "-")
    text = text.replace("—", "-")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def normalize(text):

    text = clean_text(text).lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def keyword_tokens(text):

    words = re.findall(
        r"[A-Za-z]{3,}",
        normalize(text)
    )

    return [
        word
        for word in words
        if word not in STOPWORDS
    ]


def keyword_overlap(a, b):

    first = set(
        keyword_tokens(a)
    )

    second = set(
        keyword_tokens(b)
    )

    if not first or not second:
        return 0

    return len(
        first.intersection(second)
    ) / max(
        1,
        min(
            len(first),
            len(second)
        )
    )


def similarity(a, b):

    return SequenceMatcher(
        None,
        normalize(a),
        normalize(b)
    ).ratio()


# ============================================================
# DOCUMENT HEADER / METADATA DETECTION
# ============================================================

def is_document_header_or_metadata(text):

    """
    IMPORTANT:
    This function prevents titles, timestamps, platform names,
    document metadata and QuestionWell headers from becoming
    assessment questions.
    """

    text = clean_text(text)

    if not text:
        return True

    normalized = normalize(text)

    # --------------------------------------------------------
    # Exact / common platform names
    # --------------------------------------------------------

    platform_terms = [
        "questionwell",
        "question well",
        "kahoot",
        "quizizz",
        "google forms",
        "microsoft forms",
        "canvas",
        "moodle",
        "blackboard",
        "turnitin",
        "quizlet",
        "chatgpt",
        "openai"
    ]

    for term in platform_terms:

        if term in normalized:
            return True

    # --------------------------------------------------------
    # Timestamp / date headers
    #
    # Examples:
    # 9/19/26, 5:27 AM General Chemistry » QuestionWell
    # 09/19/2026 5:27 AM
    # September 19, 2026, 5:27 AM
    # 19 Sep 2026 05:27
    # --------------------------------------------------------

    date_pattern_1 = re.compile(
        r"^\s*\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}"
        r"(?:\s*[,|-]?\s*"
        r"\d{1,2}:\d{2}"
        r"(?:\s*[APap][Mm])?)?"
    )

    date_pattern_2 = re.compile(
        r"^\s*(?:"
        r"jan(?:uary)?|"
        r"feb(?:ruary)?|"
        r"mar(?:ch)?|"
        r"apr(?:il)?|"
        r"may|"
        r"jun(?:e)?|"
        r"jul(?:y)?|"
        r"aug(?:ust)?|"
        r"sep(?:tember)?|"
        r"oct(?:ober)?|"
        r"nov(?:ember)?|"
        r"dec(?:ember)?"
        r")\s+"
        r"\d{1,2}"
        r"(?:st|nd|rd|th)?"
        r"(?:,|\s+)"
        r"\d{4}"
    )

    date_pattern_3 = re.compile(
        r"^\s*\d{1,2}\s+"
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"[a-z]*\s+\d{4}",
        flags=re.I
    )

    if date_pattern_1.search(text):
        return True

    if date_pattern_2.search(text):
        return True

    if date_pattern_3.search(text):
        return True

    # --------------------------------------------------------
    # Time-only headers
    # --------------------------------------------------------

    if re.match(
        r"^\s*\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b",
        text
    ):
        return True

    # --------------------------------------------------------
    # Browser / export style metadata
    # --------------------------------------------------------

    metadata_terms = [
        "question set",
        "question bank",
        "assessment set",
        "quiz set",
        "generated questions",
        "generated question set",
        "exported from",
        "created with",
        "created by",
        "generated by",
        "downloaded from",
        "document title",
        "untitled document",
        "page ",
        "page 1",
        "page 2",
        "page 3",
        "page 4",
        "page 5"
    ]

    for term in metadata_terms:

        if term in normalized:
            return True

    # --------------------------------------------------------
    # Arrow / breadcrumb title
    #
    # Example:
    # General Chemistry » QuestionWell
    # --------------------------------------------------------

    if "»" in text:

        pieces = [
            p.strip()
            for p in text.split("»")
            if p.strip()
        ]

        if len(pieces) >= 2:

            # If the last item is a known platform,
            # this is definitely a document header.
            last_piece = normalize(
                pieces[-1]
            )

            if last_piece in [
                "questionwell",
                "question well",
                "kahoot",
                "quizizz",
                "quizlet",
                "canvas",
                "moodle"
            ]:
                return True

            # Breadcrumb-like short labels
            if all(
                len(p.split()) <= 8
                for p in pieces
            ):
                return True

    # --------------------------------------------------------
    # Common title forms
    # --------------------------------------------------------

    title_patterns = [

        r"^general\s+chemistry\s+question\s+set$",
        r"^chemistry\s+question\s+set$",
        r"^general\s+chemistry$",
        r"^chemistry\s+question\s+bank$",
        r"^question\s+set$",
        r"^question\s+bank$",
        r"^assessment\s+question\s+set$",
        r"^quiz\s+question\s+set$",
        r"^test\s+question\s+set$",
        r"^exam\s+question\s+set$",
        r"^generated\s+question\s+set$",
        r"^generated\s+questions?$"
    ]

    for pattern in title_patterns:

        if re.fullmatch(
            pattern,
            normalized,
            flags=re.I
        ):
            return True

    # --------------------------------------------------------
    # Very short title-like lines
    # --------------------------------------------------------

    words = normalized.split()

    if len(words) <= 6:

        title_words = [
            "chemistry",
            "physics",
            "biology",
            "mathematics",
            "math",
            "computer",
            "science",
            "programming",
            "english",
            "economics",
            "accounting",
            "management",
            "question",
            "questions",
            "set",
            "bank",
            "assessment",
            "quiz",
            "test",
            "exam"
        ]

        title_hits = sum(
            1
            for word in words
            if word in title_words
        )

        if title_hits >= 2:
            return True

    return False


# ============================================================
# HEADINGS / LABELS
# ============================================================

def is_heading_or_label(text):

    text = clean_text(text)

    if not text:
        return True

    # First remove document metadata
    if is_document_header_or_metadata(
        text
    ):
        return True

    normalized = normalize(text)

    patterns = [

        # Sections
        r"^section\s*[a-z0-9ivx\-]+$",
        r"^part\s*[a-z0-9ivx\-]+$",
        r"^unit\s*[a-z0-9ivx\-]+$",
        r"^chapter\s*[a-z0-9ivx\-]+$",
        r"^module\s*[a-z0-9ivx\-]+$",

        # Instructions
        r"^instructions?\s*:?",
        r"^general\s+instructions?",
        r"^specific\s+instructions?",

        # Question categories
        r"^mcqs?$",
        r"^mcq\s+section$",
        r"^multiple\s+choice\s+questions?$",
        r"^true\s*(/|or)\s*false$",
        r"^short\s+questions?$",
        r"^short\s+answers?$",
        r"^long\s+questions?$",
        r"^long\s+answers?$",
        r"^essay\s+questions?$",
        r"^descriptive\s+questions?$",
        r"^subjective\s+questions?$",
        r"^objective\s+questions?$",
        r"^case\s+studies?$",
        r"^numerical\s+questions?$",
        r"^practical\s+questions?$",

        # Instructions
        r"^answer\s+the\s+following$",
        r"^answer\s+all\s+questions?$",
        r"^attempt\s+all\s+questions?$",
        r"^attempt\s+any\s+questions?$",

        # Assessment labels
        r"^assessment$",
        r"^quiz$",
        r"^test$",
        r"^exam$",
        r"^midterm$",
        r"^final\s+exam$",

        # OBE labels
        r"^course\s+learning\s+outcomes?$",
        r"^programme\s+learning\s+outcomes?$",
        r"^program\s+learning\s+outcomes?$",
        r"^clo[s]?$",
        r"^plo[s]?$",

        # Answer material
        r"^rubric$",
        r"^marking\s+scheme$",
        r"^answer\s+key$",
        r"^answers?$",

        # Metadata
        r"^name\s*:?",
        r"^roll\s*(no|number)\s*:?",
        r"^registration\s*(no|number)\s*:?",
        r"^date\s*:?",
        r"^time\s*:?",
        r"^total\s+marks?\s*:?",
        r"^marks?\s*:?",
        r"^points?\s*:?"
    ]

    for pattern in patterns:

        if re.search(
            pattern,
            normalized,
            flags=re.I
        ):
            return True

    # Label followed by colon/equal
    if re.match(
        r"^(clo|plo|bloom|marks?|points?|"
        r"topic|section|part|course|subject|"
        r"date|time|name|roll\s*(no|number))"
        r"\s*[:=\-]",
        normalized,
        flags=re.I
    ):
        return True

    return False


# ============================================================
# QUESTION VALIDATION
# ============================================================

def looks_like_actual_question(text):

    text = clean_text(text)

    if not text:
        return False

    # NEVER accept document headers
    if is_document_header_or_metadata(
        text
    ):
        return False

    if is_heading_or_label(
        text
    ):
        return False

    # Very short lines are almost always labels/headings
    if len(text.split()) < 4:
        return False

    # Pure metadata patterns
    if re.fullmatch(
        r"[\d\s/:,\-]+",
        text
    ):
        return False

    # A real question can have a question mark
    if "?" in text:
        return True

    command_words = [
        "define",
        "identify",
        "state",
        "list",
        "name",
        "explain",
        "describe",
        "discuss",
        "compare",
        "contrast",
        "analyze",
        "analyse",
        "evaluate",
        "assess",
        "justify",
        "calculate",
        "compute",
        "solve",
        "determine",
        "derive",
        "demonstrate",
        "apply",
        "design",
        "develop",
        "construct",
        "write",
        "interpret",
        "classify",
        "differentiate",
        "examine",
        "critique",
        "recommend",
        "predict",
        "identify",
        "illustrate"
    ]

    normalized = normalize(text)

    for word in command_words:

        if re.search(
            r"\b" + re.escape(word) + r"\b",
            normalized
        ):
            return True

    return False


# ============================================================
# CLEAN QUESTION
# ============================================================

def clean_question_candidate(
    block
):

    block = clean_text(
        block
    )

    if not block:
        return ""

    # Remove answer key / rubric material
    block = re.split(
        r"\n\s*(Answer\s*Key|Answers?|"
        r"Marking\s*Scheme|Rubric)\s*:?",
        block,
        maxsplit=1,
        flags=re.I
    )[0]

    # Remove trailing marks
    block = re.sub(
        r"\s*\(\s*\d+\s*(marks?|points?)\s*\)\s*$",
        "",
        block,
        flags=re.I
    )

    block = re.sub(
        r"\s*\[\s*\d+\s*(marks?|points?)\s*\]\s*$",
        "",
        block,
        flags=re.I
    )

    return block.strip()


# ============================================================
# REMOVE DOCUMENT HEADER LINES BEFORE EXTRACTION
# ============================================================

def remove_header_lines(
    text
):

    lines = text.splitlines()

    cleaned_lines = []

    for line in lines:

        line = clean_text(line)

        if not line:
            continue

        # Remove known document headers
        if is_document_header_or_metadata(
            line
        ):
            continue

        cleaned_lines.append(
            line
        )

    return "\n".join(
        cleaned_lines
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(
    text
):

    text = clean_text(
        text
    )

    if not text:
        return []

    # Remove obvious page/document headers first
    text = remove_header_lines(
        text
    )

    questions = []

    # --------------------------------------------------------
    # Numbered questions
    # --------------------------------------------------------

    numbered_pattern = re.compile(
        r"(?im)^\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s+"
    )

    matches = list(
        numbered_pattern.finditer(
            text
        )
    )

    if matches:

        for i, match in enumerate(
            matches
        ):

            start = match.end()

            if i + 1 < len(matches):

                end = matches[
                    i + 1
                ].start()

            else:

                end = len(text)

            block = text[
                start:end
            ]

            lines = []

            for line in block.splitlines():

                line = clean_text(
                    line
                )

                if not line:
                    continue

                # Do not include header/label lines
                if is_heading_or_label(
                    line
                ):
                    continue

                if is_document_header_or_metadata(
                    line
                ):
                    continue

                lines.append(
                    line
                )

            block = clean_text(
                "\n".join(lines)
            )

            block = clean_question_candidate(
                block
            )

            if not block:
                continue

            if len(
                block.split()
            ) < 4:
                continue

            if is_document_header_or_metadata(
                block
            ):
                continue

            if is_heading_or_label(
                block
            ):
                continue

            if not looks_like_actual_question(
                block
            ):
                continue

            # Remove duplicate questions
            duplicate = False

            for old in questions:

                if similarity(
                    block,
                    old
                ) >= 0.92:

                    duplicate = True
                    break

            if not duplicate:

                questions.append(
                    block
                )

        return questions


    # --------------------------------------------------------
    # Fallback for unnumbered questions
    # --------------------------------------------------------

    blocks = re.split(
        r"\n\s*\n+",
        text
    )

    for block in blocks:

        block = clean_question_candidate(
            block
        )

        if not block:
            continue

        if len(
            block.split()
        ) < 4:
            continue

        if is_document_header_or_metadata(
            block
        ):
            continue

        if is_heading_or_label(
            block
        ):
            continue

        if not looks_like_actual_question(
            block
        ):
            continue

        duplicate = False

        for old in questions:

            if similarity(
                block,
                old
            ) >= 0.90:

                duplicate = True
                break

        if not duplicate:

            questions.append(
                block
            )

    return questions


# ============================================================
# QUESTION TYPE
# ============================================================

def detect_question_type(
    question
):

    q = normalize(
        question
    )

    if re.search(
        r"\b(true or false|true false|t/f)\b",
        q
    ):
        return "True / False"

    if re.search(
        r"\b(fill in the blank|"
        r"fill the blank|"
        r"complete the sentence)\b",
        q
    ):
        return "Fill in the Blank"

    if re.search(
        r"\b(match|matching|"
        r"column a|column b)\b",
        q
    ):
        return "Matching"

    if re.search(
        r"\b(case study|scenario|"
        r"situation|given case)\b",
        q
    ):
        return "Case / Scenario"

    if re.search(
        r"\b(write code|programming|"
        r"program|code|algorithm)\b",
        q
    ):
        return "Coding / Practical"

    if re.search(
        r"\b(calculate|compute|"
        r"solve|numerical|"
        r"find the value)\b",
        q
    ):
        return "Numerical"

    if re.search(
        r"\b(design|implement|"
        r"perform|demonstrate|"
        r"develop|construct)\b",
        q
    ):
        return "Practical / Application"

    if len(
        question.split()
    ) > 45:
        return "Essay / Long Answer"

    return "Short Answer"


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(
    question
):

    q = normalize(
        question
    )

    detected = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                q
            ):

                detected.append(
                    level
                )

                break

    if not detected:
        return "Understand"

    priority = [
        "Create",
        "Evaluate",
        "Analyze",
        "Apply",
        "Understand",
        "Remember"
    ]

    for level in priority:

        if level in detected:
            return level

    return detected[0]


# ============================================================
# SCORING
# ============================================================

def score_clo(
    question,
    clo
):

    if not clo.strip():
        return None

    overlap = keyword_overlap(
        question,
        clo
    )

    if overlap >= 0.60:
        return 96

    if overlap >= 0.45:
        return 90

    if overlap >= 0.32:
        return 84

    if overlap >= 0.22:
        return 76

    if overlap >= 0.12:
        return 64

    return 45


def score_plo(
    question,
    plo
):

    if not plo.strip():
        return None

    overlap = keyword_overlap(
        question,
        plo
    )

    if overlap >= 0.55:
        return 96

    if overlap >= 0.42:
        return 90

    if overlap >= 0.30:
        return 84

    if overlap >= 0.20:
        return 76

    if overlap >= 0.10:
        return 64

    return 45


def score_bloom(
    question
):

    bloom = detect_bloom(
        question
    )

    q = normalize(
        question
    )

    explicit = False

    for verb in BLOOM_VERBS.get(
        bloom,
        []
    ):

        if re.search(
            r"\b" + re.escape(verb) + r"\b",
            q
        ):

            explicit = True
            break

    if explicit:
        return 96

    return 76


def score_subject(
    question,
    subject,
    course
):

    reference = " ".join(
        [
            value
            for value in [
                subject,
                course
            ]
            if value.strip()
        ]
    )

    if not reference:
        return 75

    overlap = keyword_overlap(
        question,
        reference
    )

    if overlap >= 0.60:
        return 98

    if overlap >= 0.45:
        return 92

    if overlap >= 0.30:
        return 85

    if overlap >= 0.20:
        return 78

    if overlap >= 0.10:
        return 65

    return 48


def score_clarity(
    question
):

    question = clean_text(
        question
    )

    if not question:
        return 0

    score = 100

    word_count = len(
        question.split()
    )

    if word_count < 5:
        score -= 20

    if word_count > 120:
        score -= 10

    if question.count("?") > 2:
        score -= 8

    if re.search(
        r"\b(etc|and so on)\b",
        question,
        flags=re.I
    ):
        score -= 8

    return max(
        0,
        min(
            100,
            score
        )
    )


def score_measurability(
    question
):

    q = normalize(
        question
    )

    measurable_verbs = [
        "define",
        "identify",
        "list",
        "explain",
        "describe",
        "calculate",
        "solve",
        "apply",
        "compare",
        "contrast",
        "analyze",
        "analyse",
        "evaluate",
        "justify",
        "design",
        "develop",
        "construct",
        "implement",
        "write",
        "determine",
        "classify",
        "demonstrate",
        "interpret",
        "recommend"
    ]

    hits = 0

    for verb in measurable_verbs:

        if re.search(
            r"\b" + re.escape(verb) + r"\b",
            q
        ):
            hits += 1

    if hits >= 2:
        return 96

    if hits == 1:
        return 88

    if len(q.split()) >= 8:
        return 74

    return 58


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    clo,
    plo,
    subject,
    course
):

    metrics = {

        "CLO Alignment":
            score_clo(
                question,
                clo
            ),

        "PLO Alignment":
            score_plo(
                question,
                plo
            ),

        "Bloom Alignment":
            score_bloom(
                question
            ),

        "Subject Relevance":
            score_subject(
                question,
                subject,
                course
            ),

        "Clarity":
            score_clarity(
                question
            ),

        "Measurability":
            score_measurability(
                question
            )
    }

    available = [
        score
        for score in metrics.values()
        if score is not None
    ]

    if available:

        overall = round(
            sum(available)
            /
            len(available)
        )

    else:

        overall = 0

    return {
        "question": question,
        "metrics": metrics,
        "overall": overall,
        "bloom": detect_bloom(
            question
        ),
        "type": detect_question_type(
            question
        )
    }


# ============================================================
# STATUS
# ============================================================

def get_status(
    score
):

    if score is None:
        return "Not Available"

    if score >= 85:
        return "Strong"

    if score >= 80:
        return "Attained"

    if score >= 60:
        return "Needs Attention"

    if score >= 40:
        return "Weak"

    return "Poor"


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🎓 OBE Quiz Checker"
    )

    st.caption(
        "Assessment Alignment Analysis"
    )

    st.divider()

    st.markdown(
        "### Course Information"
    )

    subject = st.text_input(
        "Subject",
        value=st.session_state.subject,
        placeholder="e.g. General Chemistry"
    )

    course = st.text_input(
        "Course",
        value=st.session_state.course,
        placeholder="e.g. General Chemistry"
    )

    st.markdown(
        "### Learning Outcomes"
    )

    clo = st.text_area(
        "CLO",
        value=st.session_state.clo_text,
        height=120,
        placeholder="Enter the Course Learning Outcome"
    )

    plo = st.text_area(
        "PLO",
        value=st.session_state.plo_text,
        height=120,
        placeholder="Enter the Programme Learning Outcome"
    )

    st.markdown(
        "### Assessment File"
    )

    uploaded_file = st.file_uploader(
        "Upload complete assessment",
        type=[
            "pdf",
            "docx",
            "pptx",
            "xlsx",
            "xls",
            "xlsm",
            "csv",
            "txt",
            "md",
            "rtf",
            "png",
            "jpg",
            "jpeg",
            "webp",
            "bmp"
        ]
    )

    analyze = st.button(
        "🔍 Analyze Assessment",
        type="primary",
        use_container_width=True
    )

    reset = st.button(
        "🗑️ Reset",
        use_container_width=True
    )

    if reset:

        st.session_state.analysis_done = False
        st.session_state.questions = []
        st.session_state.results = []
        st.session_state.file_name = ""
        st.session_state.subject = ""
        st.session_state.course = ""
        st.session_state.clo_text = ""
        st.session_state.plo_text = ""

        st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="title">🎓 OBE Quiz Checker</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Collective assessment alignment overview and graphical analysis'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# ANALYZE
# ============================================================

if analyze:

    if not subject.strip():

        st.error(
            "Please enter the subject."
        )
        st.stop()

    if not clo.strip():

        st.error(
            "Please enter the CLO."
        )
        st.stop()

    if not plo.strip():

        st.error(
            "Please enter the PLO."
        )
        st.stop()

    if not uploaded_file:

        st.error(
            "Please upload an assessment file."
        )
        st.stop()

    with st.spinner(
        "Reading and analyzing the assessment..."
    ):

        text = read_uploaded_file(
            uploaded_file
        )

        if not text:

            st.error(
                "The uploaded file could not be read. "
                "Please check the file format or OCR requirements."
            )
            st.stop()

        questions = extract_questions(
            text
        )

        if not questions:

            st.error(
                "No assessment questions could be extracted. "
                "Please check the file format and content."
            )
            st.stop()

        results = []

        for question in questions:

            results.append(
                evaluate_question(
                    question,
                    clo,
                    plo,
                    subject,
                    course
                )
            )

        st.session_state.questions = questions
        st.session_state.results = results
        st.session_state.file_name = uploaded_file.name
        st.session_state.subject = subject
        st.session_state.course = course
        st.session_state.clo_text = clo
        st.session_state.plo_text = plo
        st.session_state.analysis_done = True

    st.success(
        f"Analysis complete — "
        f"{len(questions)} actual assessment question(s) detected. "
        f"Document headings, timestamps, platform names and labels "
        f"were excluded."
    )


# ============================================================
# WAIT FOR ANALYSIS
# ============================================================

if not st.session_state.analysis_done:

    st.info(
        "Enter the course information, CLO and PLO, "
        "upload the assessment, and click **Analyze Assessment**."
    )

    st.stop()


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.results


# ============================================================
# METRIC AVERAGES
# ============================================================

metric_averages = {}

for metric in METRICS:

    values = []

    for result in results:

        value = result[
            "metrics"
        ].get(metric)

        if value is not None:
            values.append(value)

    if values:

        metric_averages[
            metric
        ] = round(
            sum(values)
            /
            len(values)
        )


# ============================================================
# OVERALL SCORE
# ============================================================

all_scores = [
    result["overall"]
    for result in results
]

if all_scores:

    overall_score = round(
        sum(all_scores)
        /
        len(all_scores)
    )

else:

    overall_score = 0


# ============================================================
# OVERALL ALIGNMENT
# ============================================================

st.markdown(
    "## 📊 Overall Alignment Dashboard"
)

if overall_score >= ATTAINMENT_THRESHOLD:

    st.success(
        f"🟢 **Alignment Attained** — "
        f"Overall Alignment Score: **{overall_score}/100**"
    )

else:

    st.warning(
        f"🟠 **Revision Required** — "
        f"Overall Alignment Score: **{overall_score}/100**"
    )


# ============================================================
# OVERALL METRICS
# ============================================================

st.markdown(
    "### Overall Metrics"
)

metric_columns = st.columns(3)

for i, metric in enumerate(
    METRICS
):

    score = metric_averages.get(
        metric
    )

    with metric_columns[
        i % 3
    ]:

        if score is None:

            st.metric(
                metric,
                "N/A"
            )

        else:

            st.metric(
                metric,
                f"{score}/100",
                get_status(score)
            )


# ============================================================
# QUESTION OVERVIEW
# ============================================================

st.markdown(
    "## 📋 Question Overview"
)

st.caption(
    f"{len(results)} actual assessment question(s) detected. "
    "Document titles, timestamps, platform headings, section "
    "headings, instructions and labels are excluded."
)


overview_rows = []

for number, result in enumerate(
    results,
    start=1
):

    overview_rows.append(
        {
            "Question":
                f"Q{number}",

            "Question Type":
                result["type"],

            "Bloom Level":
                result["bloom"],

            "CLO":
                result["metrics"][
                    "CLO Alignment"
                ],

            "PLO":
                result["metrics"][
                    "PLO Alignment"
                ],

            "Bloom":
                result["metrics"][
                    "Bloom Alignment"
                ],

            "Subject":
                result["metrics"][
                    "Subject Relevance"
                ],

            "Clarity":
                result["metrics"][
                    "Clarity"
                ],

            "Measurability":
                result["metrics"][
                    "Measurability"
                ],

            "Overall":
                result["overall"],

            "Status":
                get_status(
                    result["overall"]
                )
        }
    )


overview_df = pd.DataFrame(
    overview_rows
)

st.dataframe(
    overview_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# SINGLE GRAPHICAL REPRESENTATION
# ============================================================

st.markdown(
    "## 📈 Alignment Graph"
)

chart_df = pd.DataFrame(
    {
        "Metric": METRICS,

        "Score": [
            metric_averages.get(
                metric,
                0
            )
            for metric in METRICS
        ]
    }
)

st.bar_chart(
    chart_df.set_index(
        "Metric"
    ),
    y="Score",
    height=400
)


# ============================================================
# FINAL SUMMARY
# ============================================================

st.markdown(
    "### Assessment Summary"
)

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Total Questions",
        len(results)
    )

with col2:

    attained = sum(
        1
        for result in results
        if result["overall"] >= ATTAINMENT_THRESHOLD
    )

    st.metric(
        "Questions Attained",
        attained
    )

with col3:

    revision = sum(
        1
        for result in results
        if result["overall"] < ATTAINMENT_THRESHOLD
    )

    st.metric(
        "Questions Requiring Revision",
        revision
    )


if overall_score >= ATTAINMENT_THRESHOLD:

    st.success(
        "🟢 Overall assessment alignment has been attained."
    )

else:

    st.warning(
        "🟠 The overall assessment requires revision "
        "in one or more alignment areas."
    )


# ============================================================
# FOOTER
# ============================================================

st.caption(
    "OBE Quiz Checker • Collective Assessment Alignment Analysis"
)
