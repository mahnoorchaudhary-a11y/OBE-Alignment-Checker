import streamlit as st
import pandas as pd
import re
import io
import random
import time

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import fitz
except Exception:
    fitz = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    from pptx import Presentation
except Exception:
    Presentation = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
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
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "select", "mention"
    ],
    "Understand": [
        "describe", "explain", "summarize", "interpret",
        "classify", "discuss", "illustrate", "outline"
    ],
    "Apply": [
        "calculate", "apply", "demonstrate", "use",
        "solve", "implement", "execute", "show"
    ],
    "Analyze": [
        "analyze", "analyse", "compare", "differentiate",
        "examine", "contrast", "investigate", "categorize"
    ],
    "Evaluate": [
        "evaluate", "assess", "justify", "critique",
        "defend", "judge", "appraise", "argue"
    ],
    "Create": [
        "create", "design", "develop", "construct",
        "formulate", "propose", "produce"
    ]
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then",
    "than", "that", "this", "these", "those", "with",
    "from", "into", "onto", "for", "of", "to", "in",
    "on", "at", "by", "as", "is", "are", "was", "were",
    "be", "been", "being", "do", "does", "did", "can",
    "could", "should", "would", "will", "may", "might",
    "what", "which", "who", "whom", "when", "where",
    "why", "how", "your", "their", "his", "her", "its",
    "our", "you", "we", "they", "it", "student", "students"
}


# ============================================================
# SESSION STATE
# ============================================================

if "questions" not in st.session_state:
    st.session_state.questions = []

if "analysis" not in st.session_state:
    st.session_state.analysis = []

if "uploaded_text" not in st.session_state:
    st.session_state.uploaded_text = ""

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

if "selected_question" not in st.session_state:
    st.session_state.selected_question = 0

if "wheel_score" not in st.session_state:
    st.session_state.wheel_score = None

if "wheel_spun" not in st.session_state:
    st.session_state.wheel_spun = False


# ============================================================
# TEXT UTILITIES
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text)

    text = text.replace("\x00", " ")
    text = text.replace("\u2018", "'")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = text.replace("\u00a0", " ")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def normalize_text(text):

    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def content_words(text):

    words = normalize_text(text).split()

    result = []

    for word in words:

        if word in STOP_WORDS:
            continue

        if len(word) < 3:
            continue

        result.append(word)

    return result


def stem_like(word):

    word = word.lower().strip()

    endings = [
        "ization",
        "ations",
        "ation",
        "ments",
        "ment",
        "ingly",
        "edly",
        "ing",
        "ers",
        "ies",
        "es",
        "ed",
        "s"
    ]

    for ending in endings:

        if word.endswith(ending) and len(word) > len(ending) + 3:
            return word[:-len(ending)]

    return word


def normalized_content_words(text):

    return [
        stem_like(w)
        for w in content_words(text)
    ]


# ============================================================
# OUTCOMES
# ============================================================

def parse_outcomes(text):

    if not text:
        return []

    outcomes = []

    for line in text.splitlines():

        line = clean_text(line)

        if not line:
            continue

        line = re.sub(
            r"^(CLO|PLO)\s*[-:]?\s*\d+\s*[:.)-]?\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        line = re.sub(
            r"^\d+\s*[\).:-]\s*",
            "",
            line
        )

        line = re.sub(
            r"^[-•*]\s*",
            "",
            line
        )

        if len(line.split()) >= 3:
            outcomes.append(line)

    return outcomes


# ============================================================
# BLOOM
# ============================================================

def find_bloom_verb(question):

    q = normalize_text(question)

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                q
            ):
                return level, verb

    return "Unknown", ""


def bloom_distance(current, target):

    if current == "Unknown" or target == "Unknown":
        return 0

    try:
        return abs(
            BLOOM_LEVELS.index(current)
            - BLOOM_LEVELS.index(target)
        )
    except Exception:
        return 0


def bloom_score(question, target_bloom=""):

    current, _ = find_bloom_verb(question)

    if not target_bloom:

        if current == "Unknown":
            return 82.0

        return 92.0

    if current == "Unknown":
        return 78.0

    distance = bloom_distance(
        current,
        target_bloom
    )

    if distance == 0:
        return 100.0

    if distance == 1:
        return 91.0

    if distance == 2:
        return 83.0

    if distance == 3:
        return 76.0

    return 70.0


# ============================================================
# QUESTION TYPE
# ============================================================

def detect_question_type(question):

    q = question.lower()

    if re.search(r"\btrue\s*(or|/)?\s*false\b", q):
        return "True / False"

    if re.search(r"\b(a\)|b\)|c\)|d\))", q):
        return "MCQ"

    if "choose the correct" in q:
        return "MCQ"

    if "select the correct" in q:
        return "MCQ"

    if "match the following" in q:
        return "Matching"

    if "fill in the blank" in q:
        return "Fill in the Blank"

    if any(
        x in q
        for x in [
            "calculate",
            "compute",
            "find the value",
            "solve for",
            "determine the value"
        ]
    ):
        return "Numerical / Calculation"

    if any(
        x in q
        for x in [
            "case study",
            "read the case",
            "scenario",
            "case"
        ]
    ):
        return "Case Study"

    if any(
        x in q
        for x in [
            "design",
            "develop",
            "construct",
            "implement",
            "perform",
            "demonstrate"
        ]
    ):
        return "Practical / Application"

    if any(
        x in q
        for x in [
            "essay",
            "discuss in detail",
            "write an essay",
            "critically discuss"
        ]
    ):
        return "Essay / Long Answer"

    if len(q.split()) > 35:
        return "Essay / Long Answer"

    return "Short Answer"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    lines = [
        clean_text(x)
        for x in text.splitlines()
        if clean_text(x)
    ]

    questions = []
    current = ""

    for line in lines:

        is_start = bool(
            re.match(
                r"^(?:Q(?:uestion)?\s*)?\d+\s*[\).:-]\s+",
                line,
                flags=re.IGNORECASE
            )
        )

        if is_start:

            if current:
                questions.append(current.strip())

            current = re.sub(
                r"^(?:Q(?:uestion)?\s*)?\d+\s*[\).:-]\s*",
                "",
                line,
                flags=re.IGNORECASE
            ).strip()

        else:

            if current:
                current += " " + line

    if current:
        questions.append(current.strip())

    # Fallback to paragraphs
    if len(questions) < 2:

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        candidates = []

        for paragraph in paragraphs:

            paragraph = clean_text(paragraph)

            if len(paragraph.split()) >= 5:
                candidates.append(paragraph)

        if len(candidates) >= 2:
            questions = candidates

    # Fallback to question-looking lines
    if not questions:

        for line in lines:

            if (
                "?" in line
                or re.match(
                    r"^(explain|describe|define|identify|calculate|"
                    r"compare|analyze|analyse|evaluate|discuss|"
                    r"state|list|design|develop|what|why|how|which)\b",
                    line,
                    flags=re.IGNORECASE
                )
            ):

                if len(line.split()) >= 4:
                    questions.append(line)

    final_questions = []
    seen = set()

    for question in questions:

        question = clean_text(question)

        if len(question.split()) < 3:
            continue

        key = normalize_text(question)

        if key in seen:
            continue

        seen.add(key)
        final_questions.append(question)

    return final_questions


# ============================================================
# PDF READER
# ============================================================

def read_pdf(uploaded_file):

    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is not installed. Add PyMuPDF to requirements.txt."
        )

    data = uploaded_file.read()

    document = fitz.open(
        stream=data,
        filetype="pdf"
    )

    pages = []

    for page in document:

        page_text = page.get_text("text")

        if page_text and page_text.strip():

            pages.append(page_text)

        else:

            # OCR fallback
            if pytesseract is not None and Image is not None:

                try:

                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(2, 2),
                        alpha=False
                    )

                    image = Image.open(
                        io.BytesIO(
                            pix.tobytes("png")
                        )
                    )

                    ocr_text = pytesseract.image_to_string(
                        image
                    )

                    if ocr_text.strip():
                        pages.append(ocr_text)

                except Exception:
                    pass

    document.close()

    return clean_text("\n\n".join(pages))


# ============================================================
# DOCX READER
# ============================================================

def read_docx(uploaded_file):

    if Document is None:
        raise RuntimeError(
            "python-docx is not installed."
        )

    document = Document(
        io.BytesIO(uploaded_file.read())
    )

    parts = []

    for paragraph in document.paragraphs:

        text = clean_text(
            paragraph.text
        )

        if text:
            parts.append(text)

    for table in document.tables:

        for row in table.rows:

            values = []

            for cell in row.cells:

                value = clean_text(
                    cell.text
                )

                if value:
                    values.append(value)

            if values:
                parts.append(" | ".join(values))

    return clean_text("\n".join(parts))


# ============================================================
# PPTX READER
# ============================================================

def read_pptx(uploaded_file):

    if Presentation is None:
        raise RuntimeError(
            "python-pptx is not installed."
        )

    presentation = Presentation(
        io.BytesIO(uploaded_file.read())
    )

    slides = []

    for slide in presentation.slides:

        texts = []

        for shape in slide.shapes:

            if hasattr(shape, "text"):

                text = clean_text(
                    shape.text
                )

                if text:
                    texts.append(text)

        if texts:
            slides.append("\n".join(texts))

    return clean_text("\n\n".join(slides))


# ============================================================
# EXCEL READER
# ============================================================

def read_excel(uploaded_file):

    data = uploaded_file.read()

    sheets = pd.read_excel(
        io.BytesIO(data),
        sheet_name=None
    )

    parts = []

    for sheet_name, dataframe in sheets.items():

        parts.append(
            "Sheet: " + str(sheet_name)
        )

        dataframe = dataframe.fillna("")

        for _, row in dataframe.iterrows():

            values = [
                str(value).strip()
                for value in row.tolist()
                if str(value).strip()
            ]

            if values:
                parts.append(
                    " | ".join(values)
                )

    return clean_text(
        "\n".join(parts)
    )


# ============================================================
# CSV READER
# ============================================================

def read_csv(uploaded_file):

    data = uploaded_file.read()

    dataframe = pd.read_csv(
        io.BytesIO(data)
    )

    dataframe = dataframe.fillna("")

    lines = []

    for _, row in dataframe.iterrows():

        values = [
            str(value).strip()
            for value in row.tolist()
            if str(value).strip()
        ]

        if values:
            lines.append(
                " | ".join(values)
            )

    return clean_text(
        "\n".join(lines)
    )


# ============================================================
# TEXT READER
# ============================================================

def read_text(uploaded_file):

    data = uploaded_file.read()

    return clean_text(
        data.decode(
            "utf-8",
            errors="ignore"
        )
    )


# ============================================================
# IMAGE READER
# ============================================================

def read_image(uploaded_file):

    if Image is None:
        raise RuntimeError(
            "Pillow is not installed."
        )

    if pytesseract is None:
        raise RuntimeError(
            "OCR support is unavailable. "
            "Add pytesseract to requirements.txt."
        )

    image = Image.open(
        uploaded_file
    )

    return clean_text(
        pytesseract.image_to_string(
            image
        )
    )


# ============================================================
# FILE ROUTER
# ============================================================

def read_uploaded_file(uploaded_file):

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if filename.endswith(".docx"):
        return read_docx(uploaded_file)

    if filename.endswith(".pptx"):
        return read_pptx(uploaded_file)

    if filename.endswith(".xlsx"):
        return read_excel(uploaded_file)

    if filename.endswith(".xls"):
        return read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return read_csv(uploaded_file)

    if filename.endswith(
        (".txt", ".md")
    ):
        return read_text(uploaded_file)

    if filename.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp",
            ".tiff"
        )
    ):
        return read_image(uploaded_file)

    if filename.endswith(".svg"):
        return read_text(uploaded_file)

    raise ValueError(
        "Unsupported file type."
    )


# ============================================================
# OUTCOME MATCHING
# ============================================================

def outcome_similarity(question, outcome):

    q_words = set(
        normalized_content_words(question)
    )

    o_words = set(
        normalized_content_words(outcome)
    )

    if not q_words or not o_words:
        return 0.0

    overlap = len(
        q_words.intersection(o_words)
    )

    return overlap / max(
        1,
        min(len(q_words), len(o_words))
    )


def best_outcome_match(question, outcomes):

    if not outcomes:
        return 80.0, ""

    scores = []

    for outcome in outcomes:

        similarity = outcome_similarity(
            question,
            outcome
        )

        scores.append(
            (similarity, outcome)
        )

    scores.sort(
        key=lambda x: x[0],
        reverse=True
    )

    best_similarity, best_outcome = scores[0]

    # Lenient but meaningful scale
    score = 62 + (
        min(best_similarity, 1.0) * 38
    )

    return round(score, 1), best_outcome


# ============================================================
# CLARITY
# ============================================================

def clarity_score(question):

    words = question.split()

    score = 98.0

    if len(words) > 60:
        score -= 8

    elif len(words) > 45:
        score -= 4

    vague_phrases = [
        "discuss something",
        "explain everything",
        "write about",
        "tell me about",
        "what do you think",
        "give your opinion"
    ]

    q = question.lower()

    for phrase in vague_phrases:

        if phrase in q:
            score -= 8

    if question.count("?") > 2:
        score -= 3

    return round(
        max(60, min(100, score)),
        1
    )


# ============================================================
# MEASURABILITY
# ============================================================

def measurability_score(
    question,
    qtype
):

    q = question.lower()

    clear_verbs = []

    for verbs in BLOOM_VERBS.values():
        clear_verbs.extend(verbs)

    has_action = any(
        re.search(
            r"\b" + re.escape(v) + r"\b",
            q
        )
        for v in clear_verbs
    )

    score = 94.0

    if has_action:
        score += 4

    if qtype in [
        "MCQ",
        "True / False",
        "Numerical / Calculation"
    ]:
        score += 1

    vague = [
        "discuss something",
        "say something",
        "write anything",
        "what do you think"
    ]

    for phrase in vague:

        if phrase in q:
            score -= 10

    return round(
        max(65, min(100, score)),
        1
    )


# ============================================================
# RELEVANCE
# ============================================================

def relevance_score(
    clo_score,
    plo_score
):

    return round(
        (clo_score * 0.60)
        + (plo_score * 0.40),
        1
    )


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos,
    target_bloom
):

    qtype = detect_question_type(
        question
    )

    bloom, bloom_verb = find_bloom_verb(
        question
    )

    clo_score, clo_match = best_outcome_match(
        question,
        clos
    )

    plo_score, plo_match = best_outcome_match(
        question,
        plos
    )

    bloom_value = bloom_score(
        question,
        target_bloom
    )

    relevance = relevance_score(
        clo_score,
        plo_score
    )

    clarity = clarity_score(
        question
    )

    measurability = measurability_score(
        question,
        qtype
    )

    overall = (
        clo_score * 0.20
        + plo_score * 0.15
        + bloom_value * 0.20
        + relevance * 0.15
        + clarity * 0.15
        + measurability * 0.15
    )

    overall = round(
        max(0, min(100, overall)),
        1
    )

    if overall >= 85:
        status = "🟢 Strong"

    elif overall >= 75:
        status = "🏆 Attained"

    elif overall >= 65:
        status = "🟡 Minor Revision"

    elif overall >= 50:
        status = "🟠 Review"

    else:
        status = "🔴 Needs Revision"

    return {
        "question": question,
        "type": qtype,
        "bloom": bloom,
        "bloom_verb": bloom_verb,
        "clo": clo_score,
        "plo": plo_score,
        "bloom_score": bloom_value,
        "relevance": relevance,
        "clarity": clarity,
        "measurability": measurability,
        "overall": overall,
        "status": status,
        "clo_match": clo_match,
        "plo_match": plo_match,
        "target_bloom": target_bloom
    }


# ============================================================
# ANALYZE ALL QUESTIONS
# ============================================================

def analyze_questions(
    questions,
    clos,
    plos,
    target_bloom
):

    results = []

    for question in questions:

        result = evaluate_question(
            question,
            clos,
            plos,
            target_bloom
        )

        results.append(result)

    return results


# ============================================================
# OVERALL SCORE
# ============================================================

def calculate_overall_score(results):

    if not results:
        return 0.0

    values = [
        r["overall"]
        for r in results
    ]

    return round(
        sum(values) / len(values),
        1
    )


# ============================================================
# PRACTICAL REVISION ENGINE
# ============================================================

def revise_clarity(
    question,
    qtype
):

    q = question.strip()

    replacements = [
        (
            "Please answer the following question:",
            ""
        ),
        (
            "Answer the following question:",
            ""
        ),
        (
            "Kindly answer the following question:",
            ""
        ),
        (
            "Can you explain",
            "Explain"
        ),
        (
            "Can you describe",
            "Describe"
        )
    ]

    for old, new in replacements:

        pattern = re.compile(
            re.escape(old),
            re.IGNORECASE
        )

        q = pattern.sub(
            new,
            q,
            count=1
        )

    q = re.sub(
        r"\s+",
        " ",
        q
    ).strip()

    return q


def revise_measurability(
    question,
    qtype
):

    q = question.strip()

    lower = q.lower()

    if qtype == "Numerical / Calculation":

        if (
            "show the steps" not in lower
            and "show your calculation" not in lower
        ):

            q = q.rstrip(" .?")

            q += (
                " Show the calculation steps and "
                "state the final answer with units."
            )

    elif qtype == "Case Study":

        if (
            "evidence from the case"
            not in lower
        ):

            q = q.rstrip(" .?")

            q += (
                " Support your answer with "
                "evidence from the case."
            )

    elif qtype == "Short Answer":

        if (
            "example" not in lower
            and "evidence" not in lower
            and len(q.split()) < 30
        ):

            q = q.rstrip(" .?")

            q += (
                " Give one relevant example "
                "to support your answer."
            )

    elif qtype == "Essay / Long Answer":

        if (
            "evidence" not in lower
            and "example" not in lower
        ):

            q = q.rstrip(" .?")

            q += (
                " Support your response with "
                "relevant examples or evidence."
            )

    elif qtype == "True / False":

        q = q.replace(
            "not not",
            "not"
        )

    return q


def revise_bloom(
    question,
    current_bloom,
    target_bloom
):

    if not target_bloom:
        return question

    verb_map = {
        "Remember": "Identify",
        "Understand": "Explain",
        "Apply": "Apply",
        "Analyze": "Analyze",
        "Evaluate": "Evaluate",
        "Create": "Develop"
    }

    target_verb = verb_map.get(
        target_bloom
    )

    if not target_verb:
        return question

    pattern = re.compile(
        r"^\s*(define|state|list|name|identify|"
        r"describe|explain|discuss|outline|"
        r"calculate|apply|compare|analyze|analyse|"
        r"evaluate|assess|develop|design|create|"
        r"justify)\b",
        re.IGNORECASE
    )

    match = pattern.match(
        question
    )

    if match:

        return (
            question[:match.start()]
            + target_verb
            + question[match.end():]
        )

    return question


def revise_for_clo(
    question,
    clo_text
):

    if not clo_text:
        return question

    q = question.strip()
    clo = clo_text.lower()

    if (
        "compare" in clo
        and "compare" not in q.lower()
    ):

        q = q.rstrip(" .?")
        q += (
            " Compare the relevant aspects "
            "clearly."
        )

    elif (
        ("analyze" in clo or "analyse" in clo)
        and "analyze" not in q.lower()
        and "analyse" not in q.lower()
    ):

        q = q.rstrip(" .?")
        q += (
            " Analyze the relevant factors "
            "in your answer."
        )

    elif (
        "evaluate" in clo
        and "evaluate" not in q.lower()
        and "justify" not in q.lower()
    ):

        q = q.rstrip(" .?")
        q += (
            " Justify your answer using "
            "relevant evidence."
        )

    elif (
        "explain" in clo
        and "explain" not in q.lower()
    ):

        q = q.rstrip(" .?")
        q += (
            " Explain your answer clearly."
        )

    return q


def generate_revisions(
    question,
    analysis,
    clos,
    plos
):

    qtype = analysis["type"]
    problem_scores = {
        "CLO Alignment": analysis["clo"],
        "PLO Alignment": analysis["plo"],
        "Bloom's Taxonomy": analysis["bloom_score"],
        "Relevance": analysis["relevance"],
        "Clarity": analysis["clarity"],
        "Measurability": analysis["measurability"]
    }

    weakest = min(
        problem_scores,
        key=problem_scores.get
    )

    revisions = []

    # Revision 1: target weakest area

    if weakest == "Clarity":

        candidate = revise_clarity(
            question,
            qtype
        )

        focus = "Clarity"

        why = (
            "The wording has been made more direct "
            "without changing the original topic."
        )

    elif weakest == "Measurability":

        candidate = revise_measurability(
            question,
            qtype
        )

        focus = "Measurability"

        why = (
            "The revision makes the expected student "
            "response easier to observe and assess."
        )

    elif weakest == "Bloom's Taxonomy":

        candidate = revise_bloom(
            question,
            analysis["bloom"],
            analysis["target_bloom"]
        )

        focus = "Bloom's Taxonomy"

        why = (
            "The action verb has been adjusted to "
            "better reflect the intended cognitive level."
        )

    elif weakest == "CLO Alignment":

        clo = analysis.get(
            "clo_match",
            ""
        )

        candidate = revise_for_clo(
            question,
            clo
        )

        focus = "CLO Alignment"

        why = (
            "The revision makes the intended learning "
            "skill more visible while preserving the topic."
        )

    else:

        candidate = revise_measurability(
            question,
            qtype
        )

        focus = weakest

        why = (
            "The revision strengthens the assessment "
            "requirement while preserving the question."
        )

    candidate = clean_text(candidate)

    if candidate != question:

        revisions.append({
            "revision": candidate,
            "focus": focus,
            "why": why
        })

    # Revision 2

    candidate2 = revise_measurability(
        question,
        qtype
    )

    candidate2 = clean_text(
        candidate2
    )

    if (
        candidate2 != question
        and not any(
            r["revision"] == candidate2
            for r in revisions
        )
    ):

        revisions.append({
            "revision": candidate2,
            "focus": "Measurability",
            "why": (
                "The question now gives students a "
                "clearer and more assessable response requirement."
            )
        })

    # Revision 3

    target_bloom = analysis.get(
        "target_bloom",
        ""
    )

    candidate3 = revise_bloom(
        question,
        analysis["bloom"],
        target_bloom
    )

    candidate3 = clean_text(
        candidate3
    )

    if (
        candidate3 != question
        and not any(
            r["revision"] == candidate3
            for r in revisions
        )
    ):

        revisions.append({
            "revision": candidate3,
            "focus": "Bloom's Taxonomy",
            "why": (
                "The question uses an action verb that "
                "better reflects the intended cognitive skill."
            )
        })

    # Never show an error.
    if not revisions:

        revisions.append({
            "revision": question,
            "focus": "Keep Current Question",
            "why": (
                "The question is already reasonably usable. "
                "No unnecessary wording change was made."
            )
        })

    return revisions[:3]


# ============================================================
# SCORE WHEEL
# ============================================================

def score_band(score):

    if score >= 90:
        return "Excellent Alignment"

    if score >= 80:
        return "Strong Alignment"

    if score >= 70:
        return "Good Alignment – Minor Improvement"

    if score >= 60:
        return "Developing Alignment"

    return "Needs Improvement"


def score_analysis(score):

    if score >= 90:

        return (
            "The assessment demonstrates very strong alignment. "
            "The questions generally connect well with the intended "
            "learning outcomes, cognitive levels, relevance, clarity, "
            "and measurability."
        )

    if score >= 80:

        return (
            "The assessment demonstrates strong alignment. "
            "Most questions appear appropriate for the intended "
            "learning outcomes and cognitive levels. A few targeted "
            "improvements may further strengthen the assessment."
        )

    if score >= 70:

        return (
            "The assessment shows reasonable alignment. Some questions "
            "can be strengthened by making the CLO connection clearer, "
            "using a more suitable action verb, or making the expected "
            "student response more measurable."
        )

    if score >= 60:

        return (
            "The assessment has several areas that can be improved. "
            "Focus first on the questions identified by the tool and "
            "use the automatic revision feature to strengthen them."
        )

    return (
        "The assessment requires substantial improvement in several "
        "areas. Start with the weakest questions and revise their "
        "learning-outcome connection, cognitive level, clarity, and "
        "measurability."
    )


def spin_score(
    calculated_score
):

    # The wheel stays close to the real analysis.
    # It creates a workshop-style reveal without making
    # the score completely random.

    variation = random.choice([
        -3,
        -2,
        -1,
        0,
        0,
        0,
        1,
        2,
        3
    ])

    result = calculated_score + variation

    return round(
        max(0, min(100, result)),
        1
    )


def show_score_wheel(
    calculated_score
):

    st.subheader(
        "🎡 Assessment Score Wheel"
    )

    st.write(
        "Spin the wheel to reveal the workshop score."
    )

    if st.button(
        "🎡 SPIN THE WHEEL",
        type="primary",
        use_container_width=True
    ):

        placeholder = st.empty()

        for _ in range(15):

            temporary = random.randint(
                max(45, int(calculated_score) - 12),
                min(100, int(calculated_score) + 12)
            )

            placeholder.markdown(
                f"""
                <div style="
                    width:240px;
                    height:240px;
                    border-radius:50%;
                    border:10px solid #555;
                    margin:20px auto;
                    display:flex;
                    flex-direction:column;
                    justify-content:center;
                    align-items:center;
                    background:#f5f7fa;
                ">
                    <div style="
                        font-size:20px;
                        font-weight:700;
                    ">
                        🎡 OBE SCORE
                    </div>

                    <div style="
                        font-size:52px;
                        font-weight:900;
                    ">
                        {temporary}%
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            time.sleep(0.07)

        final_score = spin_score(
            calculated_score
        )

        st.session_state.wheel_score = final_score
        st.session_state.wheel_spun = True

        placeholder.empty()

        st.rerun()

    if st.session_state.wheel_spun:

        final_score = st.session_state.wheel_score

        st.markdown("---")

        st.markdown(
            f"""
            <div style="
                text-align:center;
                padding:25px;
                border-radius:18px;
                background:#f5f7fa;
            ">

                <div style="
                    font-size:20px;
                    font-weight:700;
                ">
                    🎯 YOUR OBE SCORE
                </div>

                <div style="
                    font-size:64px;
                    font-weight:900;
                ">
                    {final_score:.1f}%
                </div>

                <div style="
                    font-size:24px;
                    font-weight:700;
                ">
                    {score_band(final_score)}
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        # 80% OR ABOVE = BALLOONS
        if final_score >= 80:

            st.balloons()

            st.success(
                "🎉 Congratulations! Your assessment achieved "
                "80% or above."
            )

        else:

            st.info(
                "🔧 Use the question revision tool to strengthen "
                "the assessment and spin again."
            )

        st.subheader(
            "📊 Score Analysis"
        )

        st.write(
            score_analysis(final_score)
        )

        st.markdown(
            "### Score Interpretation"
        )

        if final_score >= 80:

            st.markdown(
                """
                **Strong areas**

                - Learning-outcome alignment is generally strong.
                - Questions are mostly appropriate for their intended
                  cognitive levels.
                - Wording is generally clear.
                - Responses are reasonably measurable.

                **Next step:** Review the few questions below 75% and
                make targeted improvements.
                """
            )

        elif final_score >= 70:

            st.markdown(
                """
                **Recommended focus**

                - Strengthen CLO connections.
                - Check Bloom's action verbs.
                - Improve measurability.
                - Make unclear questions more precise.

                Use **Improve a Question** to make these changes
                automatically.
                """
            )

        else:

            st.markdown(
                """
                **Priority focus**

                - CLO/PLO alignment
                - Bloom's Taxonomy
                - Question clarity
                - Measurability
                - Relevance

                Start with the lowest-scoring questions.
                """
            )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title(
        "🎓 OBE Quiz Checker"
    )

    st.write(
        "Check your assessment for CLO, PLO, "
        "Bloom's Taxonomy, clarity, relevance, "
        "and measurability."
    )

    st.markdown("---")

    st.info(
        "Upload a complete assessment. "
        "The tool automatically extracts and analyzes "
        "the questions."
    )


# ============================================================
# MAIN
# ============================================================

st.title(
    "🎓 OBE Quiz Checker"
)

st.write(
    "Check your assessment questions for CLO, PLO, "
    "Bloom's Taxonomy, clarity, relevance, and measurability "
    "— and improve weak questions with practical revisions."
)


# ============================================================
# ASSESSMENT INFORMATION
# ============================================================

st.header(
    "1. Assessment Information"
)

col1, col2 = st.columns(2)

with col1:

    course_name = st.text_input(
        "Course / Subject",
        placeholder="e.g., Biology, Programming, English I"
    )

with col2:

    assessment_name = st.text_input(
        "Assessment Name",
        placeholder="e.g., Quiz 1, Midterm, Assignment"
    )


# ============================================================
# OUTCOMES
# ============================================================

st.header(
    "2. Learning Outcomes"
)

col1, col2 = st.columns(2)

with col1:

    clo_input = st.text_area(
        "CLOs",
        placeholder=(
            "Enter one CLO per line.\n"
            "Example:\n"
            "Explain the process of photosynthesis.\n"
            "Analyze factors affecting plant growth."
        ),
        height=150
    )

with col2:

    plo_input = st.text_area(
        "PLOs",
        placeholder=(
            "Enter one PLO per line.\n"
            "Example:\n"
            "Apply knowledge to solve problems.\n"
            "Communicate solutions effectively."
        ),
        height=150
    )


clos = parse_outcomes(
    clo_input
)

plos = parse_outcomes(
    plo_input
)


# ============================================================
# BLOOM TARGET
# ============================================================

target_bloom = st.selectbox(
    "Target Bloom's Taxonomy Level",
    ["Not specified"] + BLOOM_LEVELS
)

if target_bloom == "Not specified":
    target_bloom = ""


# ============================================================
# FILE UPLOAD
# ============================================================

st.header(
    "3. Upload Complete Assessment"
)

uploaded_file = st.file_uploader(
    "Upload assessment",
    type=[
        "pdf",
        "docx",
        "pptx",
        "xlsx",
        "xls",
        "csv",
        "txt",
        "md",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "bmp",
        "tiff",
        "svg"
    ]
)


if uploaded_file is not None:

    st.success(
        f"Uploaded: {uploaded_file.name}"
    )

    if st.button(
        "📖 Read Assessment",
        use_container_width=True
    ):

        try:

            with st.spinner(
                "Reading your assessment..."
            ):

                extracted_text = read_uploaded_file(
                    uploaded_file
                )

            if not extracted_text.strip():

                st.error(
                    "No readable text was found in the file."
                )

            else:

                st.session_state.uploaded_text = extracted_text

                questions = extract_questions(
                    extracted_text
                )

                st.session_state.questions = questions
                st.session_state.analysis = []
                st.session_state.analyzed = False
                st.session_state.wheel_score = None
                st.session_state.wheel_spun = False

                st.success(
                    f"{len(questions)} question(s) extracted."
                )

        except Exception as error:

            st.error(
                "Could not read the assessment."
            )

            st.code(
                str(error)
            )


# ============================================================
# SHOW EXTRACTED TEXT
# ============================================================

if st.session_state.uploaded_text:

    with st.expander(
        "📄 View Extracted Assessment Text"
    ):

        st.text(
            st.session_state.uploaded_text
        )


# ============================================================
# EXTRACTED QUESTIONS
# ============================================================

if st.session_state.questions:

    st.header(
        "4. Extracted Questions"
    )

    st.write(
        f"Questions found: "
        f"**{len(st.session_state.questions)}**"
    )

    for i, question in enumerate(
        st.session_state.questions,
        start=1
    ):

        st.write(
            f"**Q{i}.** {question}"
        )


# ============================================================
# ANALYZE
# ============================================================

if st.session_state.questions:

    st.header(
        "5. Analyze Assessment"
    )

    if st.button(
        "🔍 Analyze Assessment",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Analyzing CLO, PLO, Bloom's Taxonomy, "
            "clarity, relevance and measurability..."
        ):

            results = analyze_questions(
                st.session_state.questions,
                clos,
                plos,
                target_bloom
            )

        st.session_state.analysis = results
        st.session_state.analyzed = True
        st.session_state.wheel_score = None
        st.session_state.wheel_spun = False

        st.success(
            "Assessment analysis completed."
        )


# ============================================================
# RESULTS
# ============================================================

if (
    st.session_state.analyzed
    and st.session_state.analysis
):

    results = st.session_state.analysis

    calculated_score = calculate_overall_score(
        results
    )

    # --------------------------------------------------------
    # OVERALL SCORE
    # --------------------------------------------------------

    st.header(
        "6. Overall Alignment"
    )

    score_col1, score_col2 = st.columns(2)

    with score_col1:

        st.metric(
            "Calculated Alignment",
            f"{calculated_score:.1f}%"
        )

    with score_col2:

        attained_count = sum(
            1
            for r in results
            if r["overall"] >= 75
        )

        st.metric(
            "Attained Questions",
            f"{attained_count}/{len(results)}"
        )

    # --------------------------------------------------------
    # ONE GRAPH ONLY
    # --------------------------------------------------------

    st.subheader(
        "📊 Alignment Overview"
    )

    graph_data = pd.DataFrame({
        "Area": [
            "CLO Match",
            "PLO Match",
            "Bloom",
            "Relevance",
            "Clarity",
            "Measurability"
        ],
        "Score": [
            round(
                sum(r["clo"] for r in results)
                / len(results),
                1
            ),
            round(
                sum(r["plo"] for r in results)
                / len(results),
                1
            ),
            round(
                sum(r["bloom_score"] for r in results)
                / len(results),
                1
            ),
            round(
                sum(r["relevance"] for r in results)
                / len(results),
                1
            ),
            round(
                sum(r["clarity"] for r in results)
                / len(results),
                1
            ),
            round(
                sum(r["measurability"] for r in results)
                / len(results),
                1
            )
        ]
    })

    st.bar_chart(
        graph_data.set_index("Area")
    )

    # --------------------------------------------------------
    # SCORE WHEEL
    # --------------------------------------------------------

    st.header(
        "7. 🎡 Workshop Score Wheel"
    )

    show_score_wheel(
        calculated_score
    )

    # --------------------------------------------------------
    # ATTAINED QUESTIONS
    # --------------------------------------------------------

    st.header(
        "8. 🏆 Attained Questions"
    )

    attained = [
        r
        for r in results
        if r["overall"] >= 75
    ]

    if attained:

        for item in attained:

            st.success(
                f"🏆 {item['overall']:.1f}% — "
                f"{item['question']}"
            )

    else:

        st.info(
            "No question has reached 75% yet. "
            "Use the automatic revision tool below."
        )

    # --------------------------------------------------------
    # QUESTION OVERVIEW
    # --------------------------------------------------------

    st.header(
        "9. Question Overview"
    )

    table_rows = []

    for i, item in enumerate(
        results,
        start=1
    ):

        table_rows.append({
            "Question": f"Q{i}",
            "Type": item["type"],
            "Bloom": item["bloom"],
            "CLO": item["clo"],
            "PLO": item["plo"],
            "Clarity": item["clarity"],
            "Measurability": item["measurability"],
            "Overall": item["overall"],
            "Status": item["status"]
        })

    overview_df = pd.DataFrame(
        table_rows
    )

    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # IMPROVE QUESTION
    # --------------------------------------------------------

    st.header(
        "10. 🛠️ Improve a Question"
    )

    question_labels = []

    for i, item in enumerate(results):

        question_labels.append(
            f"Q{i + 1} — "
            f"{item['overall']:.1f}% — "
            f"{item['question'][:100]}"
        )

    selected_label = st.selectbox(
        "Select a question to improve",
        question_labels
    )

    selected_index = question_labels.index(
        selected_label
    )

    selected_question = st.session_state.questions[
        selected_index
    ]

    selected_analysis = results[
        selected_index
    ]

    st.subheader(
        "Current Question"
    )

    st.warning(
        selected_question
    )

    # --------------------------------------------------------
    # CURRENT ANALYSIS
    # --------------------------------------------------------

    metric_cols = st.columns(4)

    metric_cols[0].metric(
        "CLO",
        f"{selected_analysis['clo']:.1f}%"
    )

    metric_cols[1].metric(
        "PLO",
        f"{selected_analysis['plo']:.1f}%"
    )

    metric_cols[2].metric(
        "Bloom",
        f"{selected_analysis['bloom_score']:.1f}%"
    )

    metric_cols[3].metric(
        "Overall",
        f"{selected_analysis['overall']:.1f}%"
    )

    st.write(
        f"**Question Type:** "
        f"{selected_analysis['type']}"
    )

    st.write(
        f"**Detected Bloom Level:** "
        f"{selected_analysis['bloom']}"
    )

    if selected_analysis["clo_match"]:

        st.write(
            f"**Best CLO Match:** "
            f"{selected_analysis['clo_match']}"
        )

    if selected_analysis["plo_match"]:

        st.write(
            f"**Best PLO Match:** "
            f"{selected_analysis['plo_match']}"
        )

    # --------------------------------------------------------
    # PRACTICAL REVISION
    # --------------------------------------------------------

    revisions = generate_revisions(
        selected_question,
        selected_analysis,
        clos,
        plos
    )

    st.subheader(
        "💡 Practical Automatic Revision"
    )

    st.info(
        "The tool has prepared practical revisions "
        "based on the question itself and the identified "
        "alignment area. You do not need to rewrite the "
        "question manually."
    )

    for revision_number, revision in enumerate(
        revisions,
        start=1
    ):

        st.markdown(
            f"### Option {revision_number}: "
            f"{revision['focus']}"
        )

        st.write(
            "**Why this change?**"
        )

        st.write(
            revision["why"]
        )

        st.write(
            "**Revised Question:**"
        )

        st.success(
            revision["revision"]
        )

        revised_analysis = evaluate_question(
            revision["revision"],
            clos,
            plos,
            target_bloom
        )

        old_score = selected_analysis[
            "overall"
        ]

        new_score = revised_analysis[
            "overall"
        ]

        difference = round(
            new_score - old_score,
            1
        )

        if difference > 0:

            st.write(
                f"**Score:** "
                f"{old_score:.1f}% → "
                f"**{new_score:.1f}%** "
                f"📈 (+{difference:.1f})"
            )

        elif difference < 0:

            st.write(
                f"**Score:** "
                f"{old_score:.1f}% → "
                f"**{new_score:.1f}%**"
            )

        else:

            st.write(
                f"**Score:** "
                f"{old_score:.1f}% → "
                f"**{new_score:.1f}%**"
            )

        button_key = (
            f"use_revision_"
            f"{selected_index}_"
            f"{revision_number}"
        )

        if st.button(
            "✅ Use This Revision",
            key=button_key,
            use_container_width=True
        ):

            st.session_state.questions[
                selected_index
            ] = revision["revision"]

            st.session_state.analysis = (
                analyze_questions(
                    st.session_state.questions,
                    clos,
                    plos,
                    target_bloom
                )
            )

            st.session_state.wheel_score = None
            st.session_state.wheel_spun = False

            st.success(
                f"Question updated successfully: "
                f"{old_score:.1f}% → "
                f"{new_score:.1f}%"
            )

            if new_score >= 75 and old_score < 75:
                st.balloons()

            st.rerun()

    # --------------------------------------------------------
    # WORKSHOP SUMMARY
    # --------------------------------------------------------

    st.header(
        "11. 🎓 Workshop Summary"
    )

    summary_cols = st.columns(4)

    strong_count = sum(
        1
        for r in results
        if r["overall"] >= 85
    )

    attained_count = sum(
        1
        for r in results
        if 75 <= r["overall"] < 85
    )

    revision_count = sum(
        1
        for r in results
        if r["overall"] < 75
    )

    summary_cols[0].metric(
        "Questions",
        len(results)
    )

    summary_cols[1].metric(
        "Strong",
        strong_count
    )

    summary_cols[2].metric(
        "Attained",
        attained_count
    )

    summary_cols[3].metric(
        "Needs Revision",
        revision_count
    )

    if st.session_state.wheel_spun:

        final_score = (
            st.session_state.wheel_score
        )

        st.info(
            f"🎡 Workshop Score: "
            f"{final_score:.1f}% — "
            f"{score_band(final_score)}"
        )

    # --------------------------------------------------------
    # EXPORT
    # --------------------------------------------------------

    st.header(
        "12. 📥 Export Report"
    )

    export_rows = []

    for i, item in enumerate(
        st.session_state.analysis,
        start=1
    ):

        export_rows.append({
            "Course": course_name,
            "Assessment": assessment_name,
            "Question": f"Q{i}",
            "Question Text": item["question"],
            "Question Type": item["type"],
            "Bloom Level": item["bloom"],
            "CLO Match": item["clo"],
            "PLO Match": item["plo"],
            "Bloom Score": item["bloom_score"],
            "Relevance": item["relevance"],
            "Clarity": item["clarity"],
            "Measurability": item["measurability"],
            "Overall": item["overall"],
            "Status": item["status"]
        })

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "📥 Download OBE Quiz Checker Report",
        data=csv_data,
        file_name="obe_quiz_checker_report.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "🎓 OBE Quiz Checker — Assessment alignment and "
    "practical revision assistant"
)
