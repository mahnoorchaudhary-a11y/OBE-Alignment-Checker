import io
import re
import pandas as pd
import streamlit as st

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Alignment Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# BLOOM LEVELS
# ============================================================

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]

BLOOM_RANK = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6
}


# ============================================================
# BLOOM VERBS
# ============================================================

BLOOM_VERBS = {
    "Remember": [
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "recognize",
        "recognise",
        "select"
    ],

    "Understand": [
        "explain",
        "describe",
        "summarize",
        "summarise",
        "interpret",
        "classify",
        "discuss",
        "illustrate"
    ],

    "Apply": [
        "apply",
        "use",
        "demonstrate",
        "solve",
        "calculate",
        "implement",
        "construct"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "differentiate",
        "examine",
        "distinguish",
        "investigate",
        "organize",
        "organise"
    ],

    "Evaluate": [
        "evaluate",
        "assess",
        "justify",
        "critique",
        "judge",
        "defend",
        "appraise",
        "recommend"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "formulate",
        "produce",
        "compose",
        "propose",
        "generate"
    ]
}


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to",
    "in", "on", "for", "with", "by", "from",
    "at", "is", "are", "was", "were", "be",
    "been", "being", "this", "that", "these",
    "those", "it", "its", "as", "into", "about",
    "which", "what", "how", "why", "when",
    "where", "who", "can", "could", "should",
    "would", "will", "may", "might", "do",
    "does", "did", "your", "their", "his",
    "her", "our", "you", "we", "they",
    "them", "than", "then", "through",
    "using", "used", "given", "following"
}


# ============================================================
# CONCEPT GROUPS
# ============================================================

CONCEPT_GROUPS = {

    "main idea": [
        "main idea",
        "central idea",
        "main point",
        "central point"
    ],

    "patterns of organization": [
        "pattern of organization",
        "organizational pattern",
        "organization",
        "organisation",
        "cause and effect",
        "compare and contrast",
        "comparison",
        "contrast",
        "chronological",
        "sequence",
        "problem solution",
        "problem-solution"
    ],

    "paraphrasing": [
        "paraphrase",
        "paraphrasing",
        "rewrite",
        "rewriting",
        "own words"
    ],

    "author purpose": [
        "author purpose",
        "author's purpose",
        "writer purpose",
        "writer's purpose"
    ],

    "author tone": [
        "author tone",
        "author's tone",
        "writer tone",
        "writer's tone"
    ],

    "writing": [
        "writing",
        "write",
        "essay",
        "paragraph",
        "composition"
    ],

    "reading comprehension": [
        "reading",
        "comprehension",
        "passage"
    ],

    "critical thinking": [
        "critical thinking",
        "reasoning",
        "evidence",
        "argument",
        "claim"
    ],

    "communication": [
        "communication",
        "communicate",
        "speaking",
        "listening",
        "presentation"
    ],

    "grammar": [
        "grammar",
        "sentence",
        "verb",
        "noun",
        "tense",
        "syntax"
    ],

    "vocabulary": [
        "vocabulary",
        "word meaning",
        "synonym",
        "antonym"
    ],

    "research": [
        "research",
        "source",
        "citation",
        "reference"
    ],

    "problem solving": [
        "problem solving",
        "problem-solving",
        "problem",
        "solution",
        "solve"
    ]
}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text).lower()

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


def tokenize(text):

    words = normalize_text(text).split()

    return {
        word
        for word in words
        if len(word) > 2
        and word not in STOP_WORDS
    }


# ============================================================
# CONCEPT DETECTION
# ============================================================

def detect_concept(text):

    normalized = normalize_text(text)

    best_concept = ""
    best_score = 0

    for concept, keywords in CONCEPT_GROUPS.items():

        score = 0

        for keyword in keywords:

            if normalize_text(keyword) in normalized:
                score += 1

        if score > best_score:

            best_score = score
            best_concept = concept

    return best_concept


def extract_topic(text):

    concept = detect_concept(text)

    if concept:
        return concept

    words = list(tokenize(text))

    if words:
        return " ".join(words[:6])

    return "the stated topic"


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    text = normalize_text(question)

    for level in reversed(BLOOM_LEVELS):

        for verb in BLOOM_VERBS[level]:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                text
            ):

                return level

    return "Needs Review"


def bloom_alignment(
    intended,
    detected
):

    if detected == "Needs Review":
        return 40

    difference = abs(
        BLOOM_RANK[intended]
        -
        BLOOM_RANK[detected]
    )

    if difference == 0:
        return 100

    if difference == 1:
        return 65

    if difference == 2:
        return 45

    return 25


# ============================================================
# TEXT SIMILARITY
# ============================================================

def text_similarity(
    question,
    outcome
):

    q_words = tokenize(question)
    o_words = tokenize(outcome)

    if not q_words or not o_words:
        return 0

    overlap = len(
        q_words.intersection(o_words)
    )

    score = (
        overlap /
        max(1, len(o_words))
    )

    q_concept = detect_concept(
        question
    )

    o_concept = detect_concept(
        outcome
    )

    if (
        q_concept
        and o_concept
        and q_concept == o_concept
    ):

        score += 0.45

    return round(
        min(100, score * 100),
        1
    )


# ============================================================
# PDF EXTRACTION
# ============================================================

def extract_pdf_text(data):

    extracted = ""

    if PdfReader is not None:

        try:

            reader = PdfReader(
                io.BytesIO(data)
            )

            pages = []

            for page in reader.pages:

                try:

                    page_text = (
                        page.extract_text()
                        or ""
                    )

                    if page_text.strip():

                        pages.append(
                            page_text
                        )

                except Exception:
                    continue

            extracted = "\n".join(
                pages
            )

        except Exception:
            extracted = ""

    # OCR fallback

    if (
        len(extracted.strip()) < 50
        and pytesseract is not None
        and convert_from_bytes is not None
    ):

        try:

            images = convert_from_bytes(
                data,
                dpi=160
            )

            pages = []

            for image in images:

                try:

                    page_text = (
                        pytesseract
                        .image_to_string(
                            image
                        )
                    )

                    if page_text.strip():

                        pages.append(
                            page_text
                        )

                except Exception:
                    continue

            if pages:

                extracted = "\n".join(
                    pages
                )

        except Exception:
            pass

    return extracted


# ============================================================
# DOCX EXTRACTION
# ============================================================

def extract_docx_text(data):

    if Document is None:
        return ""

    try:

        document = Document(
            io.BytesIO(data)
        )

        parts = []

        for paragraph in document.paragraphs:

            value = paragraph.text.strip()

            if value:
                parts.append(value)

        for table in document.tables:

            for row in table.rows:

                row_values = []

                for cell in row.cells:

                    value = (
                        cell.text.strip()
                    )

                    if value:
                        row_values.append(value)

                if row_values:

                    parts.append(
                        " ".join(row_values)
                    )

        return "\n".join(parts)

    except Exception:
        return ""


# ============================================================
# EXCEL EXTRACTION
# ============================================================

def extract_excel_text(data):

    try:

        excel = pd.ExcelFile(
            io.BytesIO(data)
        )

        parts = []

        for sheet in excel.sheet_names:

            df = pd.read_excel(
                io.BytesIO(data),
                sheet_name=sheet,
                header=None
            )

            for row in (
                df
                .fillna("")
                .astype(str)
                .values
            ):

                line = " ".join(
                    str(value).strip()
                    for value in row
                    if str(value).strip()
                )

                if line:
                    parts.append(line)

        return "\n".join(parts)

    except Exception:
        return ""


# ============================================================
# FILE EXTRACTION
# ============================================================

@st.cache_data(
    show_spinner=False
)
def extract_uploaded_file(
    file_bytes,
    file_name
):

    name = file_name.lower()

    if name.endswith(".txt"):

        return file_bytes.decode(
            "utf-8",
            errors="ignore"
        )

    if name.endswith(".pdf"):

        return extract_pdf_text(
            file_bytes
        )

    if name.endswith(".docx"):

        return extract_docx_text(
            file_bytes
        )

    if (
        name.endswith(".xlsx")
        or name.endswith(".xls")
    ):

        return extract_excel_text(
            file_bytes
        )

    return ""


# ============================================================
# CLEAN QUESTION
# ============================================================

def clean_question_text(text):

    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    text = re.sub(
        r"^(?:question|ques|q)?\s*\d+\s*[\.\:\)\-]\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    if not text:
        return []

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    if not lines:
        return []

    # --------------------------------------------------------
    # NUMBERED QUESTIONS
    # --------------------------------------------------------

    pattern = re.compile(
        r"""
        ^
        \s*
        (?:
            question\s*\d+
            |
            ques\s*\d+
            |
            q\s*\d+
            |
            \d+
        )
        \s*
        [\.\:\)\-]
        \s*
        (.*)
        $
        """,
        flags=re.IGNORECASE | re.VERBOSE
    )

    blocks = []

    current_number = None
    current_text = []

    for line in lines:

        match = pattern.match(
            line
        )

        if match:

            if current_text:

                blocks.append(
                    (
                        current_number,
                        " ".join(
                            current_text
                        )
                    )
                )

            number_match = re.search(
                r"\d+",
                line
            )

            current_number = int(
                number_match.group()
            )

            content = match.group(
                1
            ).strip()

            current_text = []

            if content:

                current_text.append(
                    content
                )

        else:

            if current_number is not None:

                # Ignore MCQ options
                if re.match(
                    r"^\(?[A-Da-d]\)?[\.\:\)]\s+",
                    line
                ):
                    continue

                current_text.append(
                    line
                )

    if current_text:

        blocks.append(
            (
                current_number,
                " ".join(
                    current_text
                )
            )
        )

    results = []

    for number, content in blocks:

        content = clean_question_text(
            content
        )

        if len(content.split()) >= 3:

            results.append(
                {
                    "number": number,
                    "text": content
                }
            )

    if results:
        return results

    # --------------------------------------------------------
    # QUESTION MARK FORMAT
    # --------------------------------------------------------

    joined = " ".join(lines)

    sentences = re.findall(
        r"[^?]{8,}\?",
        joined
    )

    results = []

    for sentence in sentences:

        sentence = clean_question_text(
            sentence
        )

        if len(sentence.split()) >= 3:

            results.append(
                {
                    "number": len(results) + 1,
                    "text": sentence
                }
            )

    if results:
        return results

    # --------------------------------------------------------
    # COMMAND FORMAT
    # --------------------------------------------------------

    starters = (
        "identify ",
        "define ",
        "state ",
        "list ",
        "name ",
        "explain ",
        "describe ",
        "summarize ",
        "summarise ",
        "discuss ",
        "analyze ",
        "analyse ",
        "compare ",
        "contrast ",
        "differentiate ",
        "distinguish ",
        "evaluate ",
        "assess ",
        "justify ",
        "examine ",
        "interpret ",
        "apply ",
        "calculate ",
        "determine ",
        "solve ",
        "demonstrate ",
        "illustrate ",
        "classify ",
        "select ",
        "choose ",
        "write ",
        "rewrite ",
        "paraphrase ",
        "develop ",
        "design ",
        "create ",
        "formulate ",
        "construct "
    )

    results = []

    for line in lines:

        lower = line.lower()

        if (
            len(line.split()) >= 4
            and lower.startswith(starters)
        ):

            results.append(
                {
                    "number": len(results) + 1,
                    "text": line
                }
            )

    return results


# ============================================================
# FLEXIBLE CLO/PLO PARSER
# ============================================================

def parse_outcomes(
    text,
    prefix
):

    outcomes = {}

    if not text:
        return outcomes

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    lines = text.split("\n")

    # Handles:
    # CLO1:
    # CLO 1:
    # CLO-1:
    # CLO1 -
    # CLO 1
    pattern = re.compile(
        rf"^\s*"
        rf"{prefix}"
        rf"\s*[-_]?\s*"
        rf"(\d+)"
        rf"\s*"
        rf"(?:[\:\-\)\.]|\s)"
        rf"\s*"
        rf"(.+?)"
        rf"\s*$",
        flags=re.IGNORECASE
    )

    for line in lines:

        line = line.strip()

        if not line:
            continue

        match = pattern.match(
            line
        )

        if match:

            number = match.group(1)

            description = (
                match.group(2)
                .strip()
            )

            if description:

                code = (
                    f"{prefix.upper()}{number}"
                )

                outcomes[code] = (
                    description
                )

    # --------------------------------------------------------
    # INLINE FALLBACK
    # --------------------------------------------------------

    if not outcomes:

        inline_pattern = re.compile(
            rf"{prefix}"
            rf"\s*[-_]?\s*(\d+)"
            rf"\s*[\:\-\)\.]"
            rf"\s*"
            rf"(.*?)(?="
            rf"{prefix}"
            rf"\s*[-_]?\s*\d+"
            rf"\s*[\:\-\)\.]"
            rf"|$)",
            flags=re.IGNORECASE | re.DOTALL
        )

        matches = inline_pattern.findall(
            text
        )

        for number, description in matches:

            description = re.sub(
                r"\s+",
                " ",
                description
            ).strip()

            if description:

                code = (
                    f"{prefix.upper()}{number}"
                )

                outcomes[code] = (
                    description
                )

    return outcomes


# ============================================================
# QUESTION ANALYSIS
# ============================================================

def analyze_question(
    question,
    clos,
    plos,
    intended_bloom
):

    best_clo = ""
    best_clo_score = 0

    best_plo = ""
    best_plo_score = 0

    for code, description in clos.items():

        score = text_similarity(
            question["text"],
            description
        )

        if score > best_clo_score:

            best_clo_score = score
            best_clo = code

    for code, description in plos.items():

        score = text_similarity(
            question["text"],
            description
        )

        if score > best_plo_score:

            best_plo_score = score
            best_plo = code

    detected_bloom = detect_bloom(
        question["text"]
    )

    bloom_score = bloom_alignment(
        intended_bloom,
        detected_bloom
    )

    overall = (
        best_clo_score * 0.35
        +
        best_plo_score * 0.25
        +
        bloom_score * 0.40
    )

    return {
        "Question No.": question["number"],
        "Question": question["text"],
        "Best CLO": best_clo,
        "CLO Alignment %": round(
            best_clo_score,
            1
        ),
        "Best PLO": best_plo,
        "PLO Alignment %": round(
            best_plo_score,
            1
        ),
        "Intended Bloom": intended_bloom,
        "Detected Bloom": detected_bloom,
        "Bloom Alignment %": round(
            bloom_score,
            1
        ),
        "Overall Alignment %": round(
            overall,
            1
        )
    }


# ============================================================
# SUGGESTED QUESTIONS
# ============================================================

def generate_suggestions(
    clo_text,
    bloom
):

    concept = detect_concept(
        clo_text
    )

    topic = extract_topic(
        clo_text
    )

    # --------------------------------------------------------
    # PATTERNS OF ORGANIZATION
    # --------------------------------------------------------

    if concept == "patterns of organization":

        if bloom == "Remember":

            return [
                "Identify the pattern of organization used in the given paragraph.",
                "Name the organizational pattern used to arrange the ideas in the paragraph.",
                "Recognize the pattern used to structure the information in the given paragraph."
            ]

        if bloom == "Understand":

            return [
                "Explain how the organizational pattern helps the reader understand the ideas in the paragraph.",
                "Describe the organizational pattern used in the paragraph and explain its role in presenting the information.",
                "Explain how the arrangement of ideas contributes to the clarity and meaning of the paragraph."
            ]

        if bloom == "Apply":

            return [
                "Apply your knowledge of organizational patterns to identify the structure used in the given paragraph.",
                "Use the characteristics of organizational patterns to classify the structure of the given paragraph.",
                "Examine the given paragraph and determine which organizational pattern best describes the arrangement of its ideas."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the given paragraph by identifying its pattern of organization and examining how the arrangement of ideas supports the writer's purpose.",
                "Examine the paragraph and analyze the relationship among its ideas. Identify the organizational pattern and justify your response with textual evidence.",
                "Analyze how the ideas in the paragraph are organized and explain how the individual details contribute to its overall structure."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate whether the organizational pattern effectively supports the writer's purpose and justify your response with evidence.",
                "Assess the effectiveness of the paragraph's organization and explain how the arrangement of ideas affects clarity and meaning.",
                "Evaluate the writer's choice of organizational pattern and defend your judgment using specific evidence from the paragraph."
            ]

        return [
            "Design an alternative organizational structure for the paragraph that would communicate the ideas more effectively and explain your choice.",
            "Develop a revised organization for the paragraph and explain how the new structure improves clarity and coherence.",
            "Create an alternative arrangement of the ideas and justify how it would improve the effectiveness of the paragraph."
        ]

    # --------------------------------------------------------
    # MAIN IDEA
    # --------------------------------------------------------

    if concept == "main idea":

        if bloom == "Remember":

            return [
                "Identify the main idea of the given paragraph.",
                "State the central idea presented in the paragraph.",
                "Select the statement that best expresses the main idea of the paragraph."
            ]

        if bloom == "Understand":

            return [
                "Explain the main idea of the given paragraph in your own words.",
                "Describe the central idea communicated by the paragraph.",
                "Summarize the main point of the paragraph in a clear statement."
            ]

        if bloom == "Apply":

            return [
                "Use the supporting details in the paragraph to determine its central idea.",
                "Apply an appropriate reading strategy to identify the statement that best expresses the paragraph's main idea.",
                "Use the information provided in the paragraph to identify its central idea."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the supporting details in the paragraph and explain how they contribute to its main idea.",
                "Examine the relationship among the paragraph's details and identify the central idea they collectively support.",
                "Analyze the paragraph and explain how its key details establish the main idea."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate which statement most accurately represents the main idea and justify your choice using supporting details.",
                "Assess whether the proposed main idea is fully supported by the information presented in the paragraph.",
                "Evaluate the relationship between the central idea and supporting details and justify your conclusion."
            ]

        return [
            "Develop a concise statement that clearly communicates the central idea of the paragraph.",
            "Create a central statement that integrates the key information presented in the paragraph.",
            "Formulate a clear main-idea statement that accurately represents the most important information."
        ]

    # --------------------------------------------------------
    # PARAPHRASING
    # --------------------------------------------------------

    if concept == "paraphrasing":

        if bloom == "Remember":

            return [
                "Identify the essential meaning that should be preserved when rewriting the passage.",
                "Recognize the key idea that must remain unchanged in an accurate paraphrase.",
                "Identify the central meaning of the passage before rewriting it."
            ]

        if bloom == "Understand":

            return [
                "Explain the meaning of the given passage in your own words.",
                "Describe the central message of the passage without changing its original meaning.",
                "Summarize the meaning of the passage using clear and original wording."
            ]

        if bloom == "Apply":

            return [
                "Rewrite the given passage in your own words while preserving its original meaning.",
                "Paraphrase the following passage using your own wording and sentence structure without changing its meaning.",
                "Read the passage and produce an accurate paraphrase that retains the central meaning while using substantially different wording."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the original passage and explain how its central meaning can be retained while its wording and sentence structure are changed.",
                "Examine the passage and distinguish the essential meaning from the wording that can be changed in an effective paraphrase.",
                "Analyze the passage and produce a paraphrase that preserves its key ideas while demonstrating substantial changes in wording and structure."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate the accuracy of the given paraphrase by comparing it with the original passage and identifying any changes in meaning.",
                "Assess whether the paraphrase preserves the essential meaning of the original passage and justify your evaluation.",
                "Evaluate the effectiveness of the paraphrase in retaining the original message while using sufficiently different wording."
            ]

        return [
            "Create an accurate paraphrase of the passage using original wording and sentence structure while preserving its meaning.",
            "Develop a clear paraphrase that communicates the original ideas without copying the original wording.",
            "Produce a well-constructed paraphrase that retains the essential meaning while substantially changing the language and structure."
        ]

    # --------------------------------------------------------
    # GENERIC
    # --------------------------------------------------------

    if bloom == "Remember":

        return [
            f"Identify the key concept associated with {topic}.",
            f"Define the central concept related to {topic}.",
            f"State the essential feature of {topic}."
        ]

    if bloom == "Understand":

        return [
            f"Explain the central concept related to {topic} in your own words.",
            f"Describe the key features of {topic} and explain their significance.",
            f"Summarize the main concept involved in {topic}."
        ]

    if bloom == "Apply":

        return [
            f"Apply the relevant principles of {topic} to the given situation.",
            f"Use your understanding of {topic} to solve the given problem.",
            f"Demonstrate how the principles of {topic} can be applied in the given context."
        ]

    if bloom == "Analyze":

        return [
            f"Analyze the given situation and explain how the principles of {topic} are reflected in it.",
            f"Examine the components of the given situation and analyze their relationship to {topic}.",
            f"Analyze the available information and determine how it demonstrates the key principles of {topic}."
        ]

    if bloom == "Evaluate":

        return [
            f"Evaluate the effectiveness of the approach used in the given situation and justify your response using evidence related to {topic}.",
            f"Assess the given situation using relevant principles of {topic} and justify your conclusion.",
            f"Evaluate the available evidence and defend your judgment using appropriate principles related to {topic}."
        ]

    return [
        f"Design a solution that applies the key principles of {topic} to the given situation.",
        f"Develop an approach that effectively addresses the given situation using principles of {topic}.",
        f"Create a practical solution that demonstrates effective application of {topic}."
    ]


# ============================================================
# IMPROVEMENT ANALYSIS
# ============================================================

def get_improvement(
    result,
    clos
):

    clo_score = result[
        "CLO Alignment %"
    ]

    plo_score = result[
        "PLO Alignment %"
    ]

    bloom_score = result[
        "Bloom Alignment %"
    ]

    issues = []

    if clo_score < 85:

        issues.append(
            "The question needs a stronger connection "
            "with the selected course learning outcome."
        )

    if plo_score < 85:

        issues.append(
            "The question needs a clearer connection "
            "with the broader learning goal."
        )

    if bloom_score < 85:

        issues.append(
            "The cognitive task should be revised to "
            f"more clearly reflect the intended "
            f"{result['Intended Bloom']} level."
        )

    if not issues:

        return (
            "This question is appropriately aligned "
            "with the selected learning outcome, broader "
            "learning goal, and intended cognitive level. "
            "It represents a strong basis for 100% alignment "
            "with the specified assessment requirements."
        )

    return " ".join(issues)


# ============================================================
# SESSION STATE
# ============================================================

if "results" not in st.session_state:
    st.session_state.results = None

if "clos" not in st.session_state:
    st.session_state.clos = {}

if "plos" not in st.session_state:
    st.session_state.plos = {}

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False


# ============================================================
# TITLE
# ============================================================

st.title(
    "🎓 OBE Quiz Alignment Checker"
)

st.write(
    "Analyze assessment questions against CLOs, PLOs, "
    "and the intended Bloom's Taxonomy level."
)


# ============================================================
# COURSE INFORMATION
# ============================================================

st.header(
    "1. Assessment Information"
)

c1, c2 = st.columns(2)

with c1:

    course_name = st.text_input(
        "Course Name",
        placeholder="e.g., English I"
    )

with c2:

    assessment_name = st.text_input(
        "Assessment Name",
        placeholder="e.g., Quiz 1"
    )


# ============================================================
# CLO
# ============================================================

st.header(
    "2. Course Learning Outcomes"
)

clo_input = st.text_area(
    "Enter CLOs",
    height=160,
    placeholder=(
        "CLO1: Identify the main idea of a paragraph.\n"
        "CLO2: Analyze patterns of organization.\n"
        "CLO3: Apply paraphrasing techniques."
    )
)


# ============================================================
# PLO
# ============================================================

st.header(
    "3. Program Learning Outcomes"
)

plo_input = st.text_area(
    "Enter PLOs",
    height=160,
    placeholder=(
        "PLO1: Demonstrate effective communication skills.\n"
        "PLO2: Apply critical thinking skills.\n"
        "PLO3: Demonstrate problem-solving abilities."
    )
)


# ============================================================
# BLOOM
# ============================================================

st.header(
    "4. Intended Bloom's Level"
)

intended_bloom = st.selectbox(
    "Select the intended cognitive level",
    BLOOM_LEVELS,
    index=2
)


# ============================================================
# QUIZ UPLOAD
# ============================================================

st.header(
    "5. Upload Complete Quiz"
)

uploaded_file = st.file_uploader(
    "Upload PDF, DOCX, TXT, XLSX or XLS",
    type=[
        "pdf",
        "docx",
        "txt",
        "xlsx",
        "xls"
    ]
)


# ============================================================
# ANALYZE
# ============================================================

if st.button(
    "🔍 Analyze Assessment",
    type="primary",
    use_container_width=True
):

    if not course_name.strip():

        st.warning(
            "Please enter the course name."
        )

        st.stop()

    if not assessment_name.strip():

        st.warning(
            "Please enter the assessment name."
        )

        st.stop()

    if not clo_input.strip():

        st.warning(
            "Please enter the CLOs."
        )

        st.stop()

    if not plo_input.strip():

        st.warning(
            "Please enter the PLOs."
        )

        st.stop()

    if uploaded_file is None:

        st.warning(
            "Please upload the quiz."
        )

        st.stop()

    # --------------------------------------------------------
    # PARSE CLO/PLO
    # --------------------------------------------------------

    clos = parse_outcomes(
        clo_input,
        "CLO"
    )

    plos = parse_outcomes(
        plo_input,
        "PLO"
    )

    if not clos:

        st.error(
            "No CLOs were detected. "
            "Please use formats such as "
            "CLO1: Identify the main idea."
        )

        st.stop()

    if not plos:

        st.error(
            "No PLOs were detected. "
            "Please use formats such as "
            "PLO1: Communication Skills."
        )

        st.stop()

    # --------------------------------------------------------
    # FILE
    # --------------------------------------------------------

    file_bytes = uploaded_file.getvalue()

    with st.spinner(
        "Reading assessment..."
    ):

        quiz_text = extract_uploaded_file(
            file_bytes,
            uploaded_file.name
        )

    if not quiz_text.strip():

        st.error(
            "The file was uploaded, but no readable "
            "text could be extracted."
        )

        with st.expander(
            "Troubleshooting"
        ):

            st.write(
                "If this is a scanned PDF, OCR may not be "
                "available on your Streamlit deployment. "
                "Try DOCX or TXT format."
            )

        st.stop()

    # --------------------------------------------------------
    # QUESTIONS
    # --------------------------------------------------------

    with st.spinner(
        "Detecting assessment questions..."
    ):

        questions = extract_questions(
            quiz_text
        )

    if not questions:

        st.error(
            "No questions could be detected."
        )

        with st.expander(
            "🔎 View extracted text"
        ):

            st.text(
                quiz_text[:30000]
            )

        st.stop()

    # --------------------------------------------------------
    # ANALYSIS
    # --------------------------------------------------------

    with st.spinner(
        "Performing complete OBE alignment analysis..."
    ):

        analysis = []

        for question in questions:

            analysis.append(
                analyze_question(
                    question,
                    clos,
                    plos,
                    intended_bloom
                )
            )

    st.session_state.results = analysis
    st.session_state.clos = clos
    st.session_state.plos = plos
    st.session_state.analysis_done = True

    st.success(
        f"{len(questions)} question(s) analyzed successfully."
    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.analysis_done:

    results = st.session_state.results
    clos = st.session_state.clos
    plos = st.session_state.plos

    st.divider()

    st.header(
        "📊 Complete OBE Analysis"
    )

    # ========================================================
    # INDIVIDUAL CLO SCORES
    # ========================================================

    clo_scores = []

    for code in clos:

        mapped = [
            r
            for r in results
            if r["Best CLO"] == code
        ]

        if mapped:

            score = round(
                sum(
                    r["CLO Alignment %"]
                    for r in mapped
                )
                /
                len(mapped),
                1
            )

        else:

            score = 0

        clo_scores.append(
            {
                "Dimension": code,
                "Type": "CLO",
                "Alignment": score
            }
        )

    # ========================================================
    # INDIVIDUAL PLO SCORES
    # ========================================================

    plo_scores = []

    for code in plos:

        mapped = [
            r
            for r in results
            if r["Best PLO"] == code
        ]

        if mapped:

            score = round(
                sum(
                    r["PLO Alignment %"]
                    for r in mapped
                )
                /
                len(mapped),
                1
            )

        else:

            score = 0

        plo_scores.append(
            {
                "Dimension": code,
                "Type": "PLO",
                "Alignment": score
            }
        )

    # ========================================================
    # BLOOM SCORES
    # ========================================================

    bloom_scores = []

    for level in BLOOM_LEVELS:

        mapped = [
            r
            for r in results
            if r["Detected Bloom"] == level
        ]

        if mapped:

            score = round(
                sum(
                    r["Bloom Alignment %"]
                    for r in mapped
                )
                /
                len(mapped),
                1
            )

        else:

            score = 0

        bloom_scores.append(
            {
                "Dimension": level,
                "Type": "Bloom",
                "Alignment": score
            }
        )

    # ========================================================
    # OVERALL GRAPH
    # ========================================================

    st.subheader(
        "📈 CLO, PLO and Bloom's Alignment"
    )

    all_graph_data = (
        clo_scores
        +
        plo_scores
        +
        bloom_scores
    )

    graph_df = pd.DataFrame(
        all_graph_data
    )

    st.bar_chart(
        graph_df.set_index(
            "Dimension"
        )["Alignment"],
        use_container_width=True
    )

    st.caption(
        "This graph shows assessment-level alignment. "
        "Actual student attainment requires student marks."
    )

    # ========================================================
    # SUMMARY SCORES
    # ========================================================

    overall = round(
        sum(
            r["Overall Alignment %"]
            for r in results
        )
        /
        len(results),
        1
    )

    avg_clo = round(
        sum(
            r["CLO Alignment %"]
            for r in results
        )
        /
        len(results),
        1
    )

    avg_plo = round(
        sum(
            r["PLO Alignment %"]
            for r in results
        )
        /
        len(results),
        1
    )

    avg_bloom = round(
        sum(
            r["Bloom Alignment %"]
            for r in results
        )
        /
        len(results),
        1
    )

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric(
            "Overall Alignment",
            f"{overall}%"
        )

    with m2:
        st.metric(
            "CLO Alignment",
            f"{avg_clo}%"
        )

    with m3:
        st.metric(
            "PLO Alignment",
            f"{avg_plo}%"
        )

    with m4:
        st.metric(
            "Bloom Alignment",
            f"{avg_bloom}%"
        )

    # ========================================================
    # CLO REVIEW
    # ========================================================

    st.divider()

    st.header(
        "🎯 CLO Analysis — One CLO at a Time"
    )

    selected_clo = st.selectbox(
        "Select CLO",
        list(clos.keys()),
        format_func=lambda x:
            f"{x}: {clos[x]}",
        key="clo_selector"
    )

    selected_clo_results = [
        r
        for r in results
        if r["Best CLO"] == selected_clo
    ]

    if selected_clo_results:

        selected_clo_score = round(
            sum(
                r["CLO Alignment %"]
                for r in selected_clo_results
            )
            /
            len(selected_clo_results),
            1
        )

    else:

        selected_clo_score = 0

    st.metric(
        f"{selected_clo} Alignment",
        f"{selected_clo_score}%"
    )

    st.write(
        f"**Learning Outcome:** "
        f"{clos[selected_clo]}"
    )

    if selected_clo_results:

        st.write(
            "**Questions mapped to this CLO:**"
        )

        for r in selected_clo_results:

            st.write(
                f"**Q{r['Question No.']}** — "
                f"{r['Question']}"
            )

            st.caption(
                f"Alignment: "
                f"{r['CLO Alignment %']}%"
            )

    else:

        st.warning(
            "No assessment question is currently mapped "
            "strongly enough to this CLO."
        )

        st.write(
            "**Suggested questions to achieve full alignment:**"
        )

        suggestions = generate_suggestions(
            clos[selected_clo],
            intended_bloom
        )

        for i, question in enumerate(
            suggestions,
            1
        ):

            st.info(
                f"{i}. {question}"
            )

    # ========================================================
    # PLO REVIEW
    # ========================================================

    st.divider()

    st.header(
        "🎯 PLO Analysis — One PLO at a Time"
    )

    selected_plo = st.selectbox(
        "Select PLO",
        list(plos.keys()),
        format_func=lambda x:
            f"{x}: {plos[x]}",
        key="plo_selector"
    )

    selected_plo_results = [
        r
        for r in results
        if r["Best PLO"] == selected_plo
    ]

    if selected_plo_results:

        selected_plo_score = round(
            sum(
                r["PLO Alignment %"]
                for r in selected_plo_results
            )
            /
            len(selected_plo_results),
            1
        )

    else:

        selected_plo_score = 0

    st.metric(
        f"{selected_plo} Alignment",
        f"{selected_plo_score}%"
    )

    st.write(
        f"**Program Outcome:** "
        f"{plos[selected_plo]}"
    )

    if selected_plo_results:

        for r in selected_plo_results:

            st.write(
                f"**Q{r['Question No.']}** — "
                f"{r['Question']}"
            )

            st.caption(
                f"Alignment: "
                f"{r['PLO Alignment %']}%"
            )

    else:

        st.warning(
            "No assessment question is currently mapped "
            "strongly enough to this PLO."
        )

    # ========================================================
    # BLOOM ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "🧠 Bloom's Taxonomy Analysis"
    )

    bloom_table = []

    for level in BLOOM_LEVELS:

        matching = [
            r
            for r in results
            if r["Detected Bloom"] == level
        ]

        bloom_table.append(
            {
                "Bloom Level": level,
                "Questions": len(
                    matching
                ),
                "Alignment %":
                    round(
                        sum(
                            r[
                                "Bloom Alignment %"
                            ]
                            for r in matching
                        )
                        /
                        max(
                            1,
                            len(matching)
                        ),
                        1
                    )
            }
        )

    bloom_df = pd.DataFrame(
        bloom_table
    )

    st.dataframe(
        bloom_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # QUESTION ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "📝 Question-by-Question Analysis"
    )

    analysis_df = pd.DataFrame(
        results
    )

    st.dataframe(
        analysis_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # INDIVIDUAL QUESTION
    # ========================================================

    st.divider()

    st.header(
        "🔎 Detailed Question Review"
    )

    selected_index = st.selectbox(
        "Select a question",
        range(len(results)),
        format_func=lambda i:
            (
                f"Q{results[i]['Question No.']}: "
                f"{results[i]['Question'][:90]}"
            ),
        key="question_selector"
    )

    selected = results[
        selected_index
    ]

    st.subheader(
        f"Q{selected['Question No.']}"
    )

    st.write(
        selected["Question"]
    )

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        st.metric(
            "CLO",
            f"{selected['CLO Alignment %']}%"
        )

    with a2:
        st.metric(
            "PLO",
            f"{selected['PLO Alignment %']}%"
        )

    with a3:
        st.metric(
            "Bloom",
            f"{selected['Bloom Alignment %']}%"
        )

    with a4:
        st.metric(
            "Overall",
            f"{selected['Overall Alignment %']}%"
        )

    # ========================================================
    # IMPROVEMENT
    # ========================================================

    st.subheader(
        "💡 Alignment Recommendation"
    )

    message = get_improvement(
        selected,
        clos
    )

    if (
        selected["CLO Alignment %"] >= 85
        and selected["PLO Alignment %"] >= 85
        and selected["Bloom Alignment %"] >= 85
    ):

        st.success(
            message
        )

    else:

        st.warning(
            message
        )

        st.write(
            "### Three suggested questions"
        )

        selected_clo_code = (
            selected["Best CLO"]
        )

        selected_clo_text = clos.get(
            selected_clo_code,
            ""
        )

        suggestions = generate_suggestions(
            selected_clo_text,
            selected["Intended Bloom"]
        )

        for i, suggestion in enumerate(
            suggestions,
            1
        ):

            st.info(
                f"**Suggested Question {i}**\n\n"
                f"{suggestion}"
            )

        st.caption(
            "These alternatives are constructed to strengthen "
            "alignment with the selected learning outcome, "
            "broader learning goal, and intended Bloom level. "
            "They should be reviewed by the instructor before use."
        )

    # ========================================================
    # QUESTIONS NEEDING REVISION
    # ========================================================

    st.divider()

    st.header(
        "⚠️ Questions Requiring Revision"
    )

    weak_questions = [
        r
        for r in results
        if r["Overall Alignment %"] < 70
    ]

    if weak_questions:

        for r in weak_questions:

            st.write(
                f"**Q{r['Question No.']}** — "
                f"{r['Question']}"
            )

            st.caption(
                f"CLO: {r['CLO Alignment %']}% | "
                f"PLO: {r['PLO Alignment %']}% | "
                f"Bloom: {r['Bloom Alignment %']}% | "
                f"Overall: {r['Overall Alignment %']}%"
            )

    else:

        st.success(
            "No questions currently require major revision."
        )

    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header(
        "📥 Export Analysis"
    )

    csv = (
        pd.DataFrame(results)
        .to_csv(index=False)
        .encode("utf-8")
    )

    st.download_button(
        "Download Complete Analysis",
        data=csv,
        file_name="OBE_Quiz_Alignment_Analysis.csv",
        mime="text/csv",
        use_container_width=True
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.divider()

    st.header(
        "📌 Analysis Summary"
    )

    st.write(
        f"**Assessment:** {assessment_name}"
    )

    st.write(
        f"**Course:** {course_name}"
    )

    st.write(
        f"**Questions analyzed:** {len(results)}"
    )

    st.write(
        f"**Intended Bloom level:** {intended_bloom}"
    )

    st.write(
        f"**Overall alignment:** {overall}%"
    )

    st.info(
        "A 100% target means that the assessment question "
        "should appropriately address the intended learning "
        "outcome, broader learning goal, and cognitive level. "
        "The generated alternatives are suggestions for "
        "revision, not automatic replacements for instructor judgment."
    )
