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
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Alignment Checker",
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

BLOOM_RANK = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6
}

BLOOM_VERBS = {
    "Remember": [
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "recognize",
        "mention",
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
        "construct",
        "compose",
        "propose"
    ]
}

STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "by",
    "from",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "as",
    "into",
    "about",
    "which",
    "what",
    "how",
    "why",
    "when",
    "where",
    "who",
    "can",
    "could",
    "should",
    "would",
    "will",
    "may",
    "might",
    "do",
    "does",
    "did",
    "your",
    "their",
    "his",
    "her",
    "our",
    "you",
    "we",
    "they",
    "them",
    "than",
    "then",
    "through",
    "using",
    "used",
    "given",
    "following"
}

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
        "passage",
        "interpret"
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
# TEXT NORMALIZATION
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

    q = normalize_text(question)

    # Search from higher levels first so that
    # explicit higher-order verbs are prioritized.

    for level in reversed(BLOOM_LEVELS):

        for verb in BLOOM_VERBS[level]:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                q
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
        min(
            100,
            score * 100
        ),
        1
    )


# ============================================================
# PDF EXTRACTION
# ============================================================

def extract_pdf_text(data):

    extracted = ""

    # --------------------------------------------------------
    # FIRST: PYPDF
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # OCR FALLBACK
    # --------------------------------------------------------

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

            ocr_pages = []

            for image in images:

                try:

                    page_text = (
                        pytesseract
                        .image_to_string(
                            image
                        )
                    )

                    if page_text.strip():

                        ocr_pages.append(
                            page_text
                        )

                except Exception:
                    continue

            if ocr_pages:

                extracted = "\n".join(
                    ocr_pages
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

            text = paragraph.text.strip()

            if text:
                parts.append(text)

        for table in document.tables:

            for row in table.rows:

                cells = []

                for cell in row.cells:

                    cell_text = (
                        cell.text.strip()
                    )

                    if cell_text:
                        cells.append(
                            cell_text
                        )

                if cells:

                    parts.append(
                        " ".join(cells)
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

    # TXT
    if name.endswith(".txt"):

        try:

            return file_bytes.decode(
                "utf-8",
                errors="ignore"
            )

        except Exception:

            return ""

    # PDF
    if name.endswith(".pdf"):

        return extract_pdf_text(
            file_bytes
        )

    # DOCX
    if name.endswith(".docx"):

        return extract_docx_text(
            file_bytes
        )

    # Excel
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

    # Remove repeated spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    # Remove common MCQ options and
    # everything following the first option
    text = re.split(
        r"\s+\(?[A-Da-d]\)?[\.\:\)]\s+",
        text,
        maxsplit=1
    )[0]

    # Remove accidental question numbering
    text = re.sub(
        r"^(?:question|ques|q)?\s*\d+\s*[\.\:\)\-]\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


# ============================================================
# QUESTION DETECTION
# ============================================================

def extract_questions(text):

    if not text:
        return []

    # --------------------------------------------------------
    # NORMALIZE LINE BREAKS
    # --------------------------------------------------------

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    # Fix spaces
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # Remove excessive blank lines
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    lines = []

    for line in text.split("\n"):

        line = line.strip()

        if line:
            lines.append(line)

    if not lines:
        return []

    # --------------------------------------------------------
    # REMOVE HEADINGS
    # --------------------------------------------------------

    heading_patterns = [
        r"^quiz$",
        r"^quiz\s*\d+$",
        r"^mcqs?$",
        r"^multiple\s+choice\s+questions?$",
        r"^questions?$",
        r"^assessment$",
        r"^test$",
        r"^test\s*\d+$",
        r"^answer\s+key$",
        r"^instructions?$"
    ]

    filtered = []

    for line in lines:

        is_heading = False

        for pattern in heading_patterns:

            if re.fullmatch(
                pattern,
                line,
                flags=re.IGNORECASE
            ):

                is_heading = True
                break

        if not is_heading:

            filtered.append(line)

    lines = filtered

    # --------------------------------------------------------
    # REMOVE METADATA
    # --------------------------------------------------------

    metadata_prefixes = (
        "name:",
        "student name:",
        "roll no:",
        "roll number:",
        "registration no:",
        "date:",
        "course:",
        "section:",
        "time:",
        "total marks:",
        "marks:"
    )

    filtered = []

    for line in lines:

        lower = line.lower()

        if lower.startswith(
            metadata_prefixes
        ):
            continue

        filtered.append(line)

    lines = filtered

    # --------------------------------------------------------
    # NUMBERED QUESTION DETECTION
    # --------------------------------------------------------

    numbered_pattern = re.compile(
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

    question_blocks = []

    current_number = None
    current_text = []

    for line in lines:

        match = numbered_pattern.match(
            line
        )

        if match:

            # Save previous question
            if current_text:

                question_blocks.append(
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

            if number_match:

                current_number = int(
                    number_match.group()
                )

            else:

                current_number = (
                    len(question_blocks)
                    + 1
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

                # Ignore MCQ option lines
                if re.match(
                    r"^\(?[A-Da-d]\)?[\.\:\)]\s+",
                    line
                ):
                    continue

                # Ignore answer lines
                if re.match(
                    r"^(answer|ans)\s*:",
                    line,
                    flags=re.IGNORECASE
                ):
                    continue

                current_text.append(
                    line
                )

    # Save final block
    if current_text:

        question_blocks.append(
            (
                current_number,
                " ".join(
                    current_text
                )
            )
        )

    results = []

    for number, content in question_blocks:

        content = clean_question_text(
            content
        )

        if len(content.split()) < 3:
            continue

        # Avoid marks-only lines
        if re.fullmatch(
            r"\d+\s*marks?",
            content,
            flags=re.IGNORECASE
        ):
            continue

        results.append(
            {
                "number": number,
                "text": content
            }
        )

    if results:

        # Remove duplicate questions
        unique = []
        seen = set()

        for item in results:

            key = normalize_text(
                item["text"]
            )

            if key not in seen:

                seen.add(key)
                unique.append(item)

        return unique

    # --------------------------------------------------------
    # QUESTION-MARK DETECTION
    # --------------------------------------------------------

    joined = " ".join(lines)

    # Find sentences ending in ?
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
    # COMMAND-STYLE QUESTIONS
    # --------------------------------------------------------

    command_starters = (
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
        "construct ",
        "read "
    )

    results = []

    for line in lines:

        clean = re.sub(
            r"\s+",
            " ",
            line
        ).strip()

        if len(clean.split()) < 4:
            continue

        lower = clean.lower()

        if any(
            lower.startswith(
                starter
            )
            for starter in command_starters
        ):

            if re.match(
                r"^\(?[A-Da-d]\)?[\.\:\)]\s+",
                clean
            ):
                continue

            results.append(
                {
                    "number": len(results) + 1,
                    "text": clean
                }
            )

    if results:
        return results

    # --------------------------------------------------------
    # FALLBACK: PARAGRAPH QUESTIONS
    # --------------------------------------------------------

    paragraphs = re.split(
        r"\n\s*\n",
        text
    )

    results = []

    question_words = (
        "what ",
        "why ",
        "how ",
        "which ",
        "who ",
        "where ",
        "when ",
        "identify ",
        "define ",
        "explain ",
        "describe ",
        "analyze ",
        "analyse ",
        "compare ",
        "differentiate ",
        "evaluate ",
        "discuss ",
        "state ",
        "calculate ",
        "determine ",
        "paraphrase ",
        "rewrite "
    )

    for paragraph in paragraphs:

        paragraph = re.sub(
            r"\s+",
            " ",
            paragraph
        ).strip()

        if len(
            paragraph.split()
        ) < 5:

            continue

        lower = paragraph.lower()

        if (
            "?" in paragraph
            or lower.startswith(
                question_words
            )
        ):

            results.append(
                {
                    "number": len(results) + 1,
                    "text": clean_question_text(
                        paragraph
                    )
                }
            )

    if results:
        return results

    # --------------------------------------------------------
    # LAST RESORT
    # --------------------------------------------------------

    results = []

    for line in lines:

        clean = re.sub(
            r"\s+",
            " ",
            line
        ).strip()

        if len(
            clean.split()
        ) < 6:

            continue

        lower = clean.lower()

        if any(
            lower.startswith(prefix)
            for prefix in [
                "answer key",
                "instructions",
                "instruction",
                "note:",
                "marks:",
                "total:",
                "name:",
                "date:",
                "course:",
                "section:"
            ]
        ):
            continue

        if re.match(
            r"^\(?[A-Da-d]\)?[\.\:\)]\s+",
            clean
        ):
            continue

        results.append(
            {
                "number": len(results) + 1,
                "text": clean
            }
        )

    return results


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(
    text,
    prefix
):

    outcomes = {}

    if not text:
        return outcomes

    lines = text.splitlines()

    pattern = re.compile(
        rf"^\s*"
        rf"({prefix}\s*\d+)"
        rf"\s*[\:\-\)]\s*"
        rf"(.+)$",
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

            code = (
                match.group(1)
                .upper()
                .replace(" ", "")
            )

            description = (
                match.group(2)
                .strip()
            )

            outcomes[
                code
            ] = description

    return outcomes


# ============================================================
# ANALYZE QUESTION
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

    # --------------------------------------------------------
    # CLO
    # --------------------------------------------------------

    for code, description in clos.items():

        score = text_similarity(
            question["text"],
            description
        )

        if score > best_clo_score:

            best_clo_score = score
            best_clo = code

    # --------------------------------------------------------
    # PLO
    # --------------------------------------------------------

    for code, description in plos.items():

        score = text_similarity(
            question["text"],
            description
        )

        if score > best_plo_score:

            best_plo_score = score
            best_plo = code

    # --------------------------------------------------------
    # BLOOM
    # --------------------------------------------------------

    detected_bloom = detect_bloom(
        question["text"]
    )

    bloom_score = bloom_alignment(
        intended_bloom,
        detected_bloom
    )

    # --------------------------------------------------------
    # COMBINED
    # --------------------------------------------------------

    combined = (
        best_clo_score * 0.35
        +
        best_plo_score * 0.25
        +
        bloom_score * 0.40
    )

    return {
        "Question No.": question[
            "number"
        ],
        "Question": question[
            "text"
        ],
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
        "Combined Alignment %": round(
            combined,
            1
        )
    }


def analyze_quiz(
    questions,
    clos,
    plos,
    intended_bloom
):

    results = []

    for question in questions:

        results.append(
            analyze_question(
                question,
                clos,
                plos,
                intended_bloom
            )
        )

    return results


# ============================================================
# QUESTION SUGGESTIONS
# ============================================================

def generate_three_questions(
    clo_text,
    plo_text,
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
                "Name the organizational pattern that structures the ideas in the given paragraph.",
                "Recognize the pattern used to arrange the information in the given paragraph."
            ]

        if bloom == "Understand":

            return [
                "Explain how the organizational pattern helps the reader understand the ideas in the paragraph.",
                "Describe the organizational pattern used in the paragraph and explain its role in presenting the information.",
                "Explain how the arrangement of ideas contributes to the meaning and clarity of the paragraph."
            ]

        if bloom == "Apply":

            return [
                "Apply your knowledge of organizational patterns to identify the structure used in the given paragraph.",
                "Examine the given paragraph and determine which organizational pattern best describes the arrangement of its ideas.",
                "Use your understanding of organizational patterns to classify the structure of the given paragraph."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the given paragraph by identifying its pattern of organization and examining how the arrangement of ideas supports the writer's purpose.",
                "Examine the paragraph and analyze the relationship among its ideas. Identify the organizational pattern and justify your response using textual evidence.",
                "Analyze how the ideas in the given paragraph are organized. Identify the pattern used and explain how individual details contribute to the overall structure."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate whether the organizational pattern used in the paragraph effectively supports the writer's purpose. Justify your response with evidence.",
                "Assess the effectiveness of the paragraph's organization and explain how the arrangement of ideas affects clarity and meaning.",
                "Evaluate the writer's choice of organizational pattern and defend your judgment using specific evidence from the paragraph."
            ]

        return [
            "Design an alternative organizational structure for the paragraph that would communicate the ideas more effectively. Explain your choice.",
            "Develop a revised organization for the paragraph and explain how your structure improves the presentation of the ideas.",
            "Create an alternative arrangement of the paragraph's ideas and justify how it would improve clarity and coherence."
        ]

    # --------------------------------------------------------
    # MAIN IDEA
    # --------------------------------------------------------

    if concept == "main idea":

        if bloom == "Remember":

            return [
                "Identify the main idea of the given paragraph.",
                "State the central idea presented in the given paragraph.",
                "Select the statement that best expresses the main idea of the given paragraph."
            ]

        if bloom == "Understand":

            return [
                "Explain the main idea of the given paragraph in your own words.",
                "Describe the central idea communicated by the given paragraph.",
                "Summarize the main point of the given paragraph in a clear statement."
            ]

        if bloom == "Apply":

            return [
                "Apply the main-idea identification strategy to determine the central point of the given paragraph.",
                "Read the paragraph and use its supporting details to determine the statement that best expresses its main idea.",
                "Use the information provided in the paragraph to identify the statement that most accurately represents its central idea."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the supporting details in the paragraph and determine how they contribute to its main idea.",
                "Examine the relationship between the paragraph's details and identify the central idea they collectively support.",
                "Analyze the paragraph and explain how its key details help establish the main idea."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate which statement most accurately represents the main idea of the paragraph and justify your choice using supporting details.",
                "Assess the proposed main idea of the paragraph and determine whether it is fully supported by the information presented.",
                "Evaluate the relationship between the central idea and supporting details and justify your conclusion."
            ]

        return [
            "Develop a concise statement that clearly communicates the central idea of the paragraph.",
            "Create an appropriate central statement that integrates the key information presented in the paragraph.",
            "Formulate a clear main-idea statement that accurately represents the most important information in the paragraph."
        ]

    # --------------------------------------------------------
    # PARAPHRASING
    # --------------------------------------------------------

    if concept == "paraphrasing":

        if bloom == "Remember":

            return [
                "Identify the central meaning that must be preserved when rewriting the given passage.",
                "Recognize the essential meaning of the given passage before rewriting it.",
                "Identify the key idea that should remain unchanged in an accurate paraphrase."
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
            "Create an accurate paraphrase of the given passage using original wording and sentence structure while preserving its meaning.",
            "Develop a clear paraphrase that communicates the original ideas without copying the original wording.",
            "Produce a well-constructed paraphrase that retains the essential meaning while substantially changing the language and structure."
        ]

    # --------------------------------------------------------
    # AUTHOR PURPOSE
    # --------------------------------------------------------

    if concept == "author purpose":

        if bloom == "Remember":

            return [
                "Identify the author's primary purpose in writing the given passage.",
                "Name the purpose that best explains why the author wrote the passage.",
                "Recognize the main purpose served by the author's presentation of the information."
            ]

        if bloom == "Understand":

            return [
                "Explain the author's purpose in writing the given passage.",
                "Describe how the author's purpose is reflected in the information presented.",
                "Explain why the author presents the ideas in the given passage."
            ]

        if bloom == "Apply":

            return [
                "Use evidence from the passage to identify the author's primary purpose.",
                "Apply your understanding of common writing purposes to determine why the author wrote the passage.",
                "Examine the information presented and determine which purpose best explains the author's approach."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the author's choice of information and language to determine the primary purpose of the passage.",
                "Examine the ideas and supporting details in the passage and explain how they reveal the author's purpose.",
                "Analyze how the author's language, examples, and organization contribute to the overall purpose of the passage."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate whether the author's choice of evidence effectively supports the purpose of the passage. Justify your response.",
                "Assess how effectively the author's language and supporting details communicate the intended purpose.",
                "Evaluate the effectiveness of the author's approach in achieving the purpose of the passage."
            ]

        return [
            "Develop an alternative approach that could communicate the same purpose more effectively.",
            "Create a revised opening that establishes the author's intended purpose clearly for the reader.",
            "Design an alternative presentation of the ideas that would strengthen the author's intended purpose."
        ]

    # --------------------------------------------------------
    # AUTHOR TONE
    # --------------------------------------------------------

    if concept == "author tone":

        if bloom == "Remember":

            return [
                "Identify the tone conveyed by the author in the given passage.",
                "Name the tone that best describes the author's attitude toward the subject.",
                "Recognize the tone created by the author's choice of language."
            ]

        if bloom == "Understand":

            return [
                "Explain how the author's word choice creates the tone of the passage.",
                "Describe the author's attitude toward the subject as conveyed through the language used.",
                "Explain how the language of the passage communicates the author's tone."
            ]

        if bloom == "Apply":

            return [
                "Use evidence from the passage to determine the author's tone.",
                "Apply your understanding of tone to identify the attitude expressed by the author.",
                "Examine the author's word choice and determine the tone communicated in the passage."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the author's word choice and explain how it contributes to the tone of the passage.",
                "Examine specific language choices in the passage and analyze how they communicate the author's attitude.",
                "Analyze how the author's language, emphasis, and examples work together to establish the tone."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate whether the author's tone is appropriate for the purpose and intended audience of the passage. Justify your response.",
                "Assess the effectiveness of the author's tone in communicating the intended message.",
                "Evaluate how successfully the author's choice of tone supports the purpose of the passage."
            ]

        return [
            "Create a revised version of the passage using a different appropriate tone while preserving its central message.",
            "Develop an alternative version of the passage that communicates the same message through a deliberately different tone.",
            "Rewrite the passage using a tone appropriate for a different audience while maintaining its essential meaning."
        ]

    # --------------------------------------------------------
    # GENERIC
    # --------------------------------------------------------

    if bloom == "Remember":

        return [
            f"Identify the key concept related to {topic}.",
            f"Define the central concept associated with {topic}.",
            f"State the essential feature of {topic}."
        ]

    if bloom == "Understand":

        return [
            f"Explain the central idea related to {topic} in your own words.",
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
# QUESTION SUGGESTION ANALYSIS
# ============================================================

def get_suggestion(
    result,
    clos,
    plos
):

    clo_code = result["Best CLO"]
    plo_code = result["Best PLO"]

    clo_text = clos.get(
        clo_code,
        ""
    )

    plo_text = plos.get(
        plo_code,
        ""
    )

    clo_score = result[
        "CLO Alignment %"
    ]

    plo_score = result[
        "PLO Alignment %"
    ]

    bloom_score = result[
        "Bloom Alignment %"
    ]

    # Strong question
    if (
        clo_score >= 85
        and plo_score >= 85
        and bloom_score >= 85
    ):

        return {
            "strong": True,
            "message": (
                "This question is appropriately aligned with "
                "the selected learning outcome, broader learning "
                "goal, and intended cognitive level. It represents "
                "a strong basis for 100% alignment with the "
                "specified assessment requirements."
            ),
            "alternatives": []
        }

    issues = []

    if clo_score < 70:

        issues.append(
            "Strengthen the connection between the question "
            "and the selected learning outcome."
        )

    if plo_score < 70:

        issues.append(
            "Make the assessed skill more clearly connected "
            "to the intended broader learning goal."
        )

    if bloom_score < 70:

        issues.append(
            "Revise the task so that it more clearly requires "
            f"the intended {result['Intended Bloom']} cognitive process."
        )

    alternatives = generate_three_questions(
        clo_text,
        plo_text,
        result["Intended Bloom"]
    )

    return {
        "strong": False,
        "message": " ".join(issues),
        "alternatives": alternatives
    }


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
# APPLICATION TITLE
# ============================================================

st.title(
    "🎓 OBE Quiz Alignment Checker"
)

st.write(
    "Analyze quiz questions against learning outcomes "
    "and the intended Bloom's Taxonomy level."
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
        "Course Name",
        placeholder="e.g., English I"
    )

with col2:

    assessment_name = st.text_input(
        "Assessment Name",
        placeholder="e.g., Quiz 1"
    )


# ============================================================
# CLO INPUT
# ============================================================

st.header(
    "2. Course Learning Outcomes"
)

clo_input = st.text_area(
    "Enter CLOs",
    height=150,
    placeholder=(
        "CLO1: Identify the main idea of a paragraph.\n"
        "CLO2: Analyze patterns of organization.\n"
        "CLO3: Apply paraphrasing techniques."
    )
)


# ============================================================
# PLO INPUT
# ============================================================

st.header(
    "3. Program Learning Outcomes"
)

plo_input = st.text_area(
    "Enter PLOs",
    height=150,
    placeholder=(
        "PLO1: Communication Skills.\n"
        "PLO2: Critical Thinking.\n"
        "PLO3: Problem Solving."
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
# FILE UPLOAD
# ============================================================

st.header(
    "5. Upload Quiz"
)

uploaded_file = st.file_uploader(
    "Upload the complete quiz",
    type=[
        "pdf",
        "docx",
        "txt",
        "xlsx",
        "xls"
    ],
    help=(
        "Supported formats: PDF, DOCX, TXT, XLSX and XLS."
    )
)


# ============================================================
# ANALYZE BUTTON
# ============================================================

if st.button(
    "🔍 Analyze Quiz",
    type="primary",
    use_container_width=True
):

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

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

        st.error(
            "Please enter at least one CLO."
        )

        st.stop()

    if not plo_input.strip():

        st.error(
            "Please enter at least one PLO."
        )

        st.stop()

    if uploaded_file is None:

        st.error(
            "Please upload the quiz file."
        )

        st.stop()

    # --------------------------------------------------------
    # PARSE OUTCOMES
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
            "No CLOs could be detected. "
            "Use a format such as CLO1: Identify..."
        )

        st.stop()

    if not plos:

        st.error(
            "No PLOs could be detected. "
            "Use a format such as PLO1: Communication Skills."
        )

        st.stop()

    # --------------------------------------------------------
    # READ FILE
    # --------------------------------------------------------

    file_bytes = (
        uploaded_file.getvalue()
    )

    with st.spinner(
        "Reading the uploaded quiz..."
    ):

        quiz_text = extract_uploaded_file(
            file_bytes,
            uploaded_file.name
        )

    # --------------------------------------------------------
    # CHECK TEXT
    # --------------------------------------------------------

    if not quiz_text.strip():

        st.error(
            "The file was uploaded, but no readable text "
            "could be extracted."
        )

        st.info(
            "For scanned PDFs, OCR dependencies must be "
            "available. DOCX or TXT files can be used as "
            "an immediate alternative."
        )

        st.stop()

    # --------------------------------------------------------
    # EXTRACT QUESTIONS
    # --------------------------------------------------------

    with st.spinner(
        "Detecting questions..."
    ):

        questions = extract_questions(
            quiz_text
        )

    # --------------------------------------------------------
    # QUESTION DETECTION FAILURE
    # --------------------------------------------------------

    if not questions:

        st.error(
            "No questions could be detected."
        )

        st.warning(
            "The document was readable, but its question "
            "structure could not be identified."
        )

        with st.expander(
            "🔎 View extracted text"
        ):

            st.text(
                quiz_text[:25000]
            )

        st.info(
            "Check the extracted text above. It shows exactly "
            "what the application received from your file."
        )

        st.stop()

    # --------------------------------------------------------
    # QUESTION PREVIEW
    # --------------------------------------------------------

    st.success(
        f"{len(questions)} question(s) detected successfully."
    )

    with st.expander(
        "👁️ Preview detected questions"
    ):

        for question in questions:

            st.write(
                f"**Q{question['number']}.** "
                f"{question['text']}"
            )

    # --------------------------------------------------------
    # ANALYSIS
    # --------------------------------------------------------

    with st.spinner(
        f"Analyzing {len(questions)} question(s)..."
    ):

        results = analyze_quiz(
            questions,
            clos,
            plos,
            intended_bloom
        )

    # --------------------------------------------------------
    # STORE RESULTS
    # --------------------------------------------------------

    st.session_state.results = results

    st.session_state.clos = clos

    st.session_state.plos = plos

    st.session_state.analysis_done = True

    st.success(
        "Quiz analysis completed successfully."
    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.analysis_done:

    results = (
        st.session_state.results
    )

    clos = (
        st.session_state.clos
    )

    plos = (
        st.session_state.plos
    )

    st.divider()

    st.header(
        "📊 Analysis Results"
    )

    # ========================================================
    # OVERALL SCORES
    # ========================================================

    overall = round(
        sum(
            r["Combined Alignment %"]
            for r in results
        )
        /
        max(1, len(results)),
        1
    )

    avg_clo = round(
        sum(
            r["CLO Alignment %"]
            for r in results
        )
        /
        max(1, len(results)),
        1
    )

    avg_plo = round(
        sum(
            r["PLO Alignment %"]
            for r in results
        )
        /
        max(1, len(results)),
        1
    )

    avg_bloom = round(
        sum(
            r["Bloom Alignment %"]
            for r in results
        )
        /
        max(1, len(results)),
        1
    )

    # ========================================================
    # ONLY GRAPH
    # ========================================================

    st.subheader(
        "📈 Overall Alignment"
    )

    graph_df = pd.DataFrame(
        {
            "Dimension": [
                "Overall",
                "CLO",
                "PLO",
                "Bloom"
            ],
            "Alignment": [
                overall,
                avg_clo,
                avg_plo,
                avg_bloom
            ]
        }
    )

    st.bar_chart(
        graph_df.set_index(
            "Dimension"
        ),
        y="Alignment",
        use_container_width=True
    )

    st.caption(
        "The percentages indicate quiz-level alignment. "
        "They do not represent student attainment."
    )

    # ========================================================
    # METRICS
    # ========================================================

    m1, m2, m3, m4 = st.columns(4)

    with m1:

        st.metric(
            "Overall",
            f"{overall}%"
        )

    with m2:

        st.metric(
            "CLO",
            f"{avg_clo}%"
        )

    with m3:

        st.metric(
            "PLO",
            f"{avg_plo}%"
        )

    with m4:

        st.metric(
            "Bloom",
            f"{avg_bloom}%"
        )

    # ========================================================
    # ONE CLO AT A TIME
    # ========================================================

    st.divider()

    st.header(
        "🎯 CLO Review"
    )

    selected_clo = st.selectbox(
        "Select one CLO",
        list(clos.keys()),
        format_func=lambda code:
            f"{code}: {clos[code]}",
        key="selected_clo"
    )

    clo_results = [
        r
        for r in results
        if r["Best CLO"] == selected_clo
    ]

    if clo_results:

        clo_alignment = round(
            sum(
                r["CLO Alignment %"]
                for r in clo_results
            )
            /
            len(clo_results),
            1
        )

    else:

        clo_alignment = 0

    st.metric(
        "Selected CLO Alignment",
        f"{clo_alignment}%"
    )

    st.write(
        f"**{selected_clo}:** "
        f"{clos[selected_clo]}"
    )

    if clo_results:

        st.write(
            f"Questions mapped to this CLO: "
            f"**{len(clo_results)}**"
        )

        clo_table = pd.DataFrame(
            [
                {
                    "Question No.": r[
                        "Question No."
                    ],
                    "Question": r[
                        "Question"
                    ],
                    "Alignment %": r[
                        "CLO Alignment %"
                    ],
                    "Detected Bloom": r[
                        "Detected Bloom"
                    ]
                }
                for r in clo_results
            ]
        )

        st.dataframe(
            clo_table,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "No question is currently mapped to this CLO."
        )

        st.write(
            "**Suggested questions:**"
        )

        suggestions = generate_three_questions(
            clos[selected_clo],
            "",
            intended_bloom
        )

        for i, suggestion in enumerate(
            suggestions,
            1
        ):

            st.info(
                f"{i}. {suggestion}"
            )

    # ========================================================
    # ONE PLO AT A TIME
    # ========================================================

    st.divider()

    st.header(
        "🎯 PLO Review"
    )

    selected_plo = st.selectbox(
        "Select one PLO",
        list(plos.keys()),
        format_func=lambda code:
            f"{code}: {plos[code]}",
        key="selected_plo"
    )

    plo_results = [
        r
        for r in results
        if r["Best PLO"] == selected_plo
    ]

    if plo_results:

        plo_alignment = round(
            sum(
                r["PLO Alignment %"]
                for r in plo_results
            )
            /
            len(plo_results),
            1
        )

    else:

        plo_alignment = 0

    st.metric(
        "Selected PLO Alignment",
        f"{plo_alignment}%"
    )

    st.write(
        f"**{selected_plo}:** "
        f"{plos[selected_plo]}"
    )

    if plo_results:

        st.write(
            f"Questions mapped to this PLO: "
            f"**{len(plo_results)}**"
        )

        plo_table = pd.DataFrame(
            [
                {
                    "Question No.": r[
                        "Question No."
                    ],
                    "Question": r[
                        "Question"
                    ],
                    "Alignment %": r[
                        "PLO Alignment %"
                    ],
                    "Detected Bloom": r[
                        "Detected Bloom"
                    ]
                }
                for r in plo_results
            ]
        )

        st.dataframe(
            plo_table,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "No question is currently mapped to this PLO."
        )

    # ========================================================
    # BLOOM TABLE
    # ========================================================

    st.divider()

    st.header(
        "🧠 Bloom's Taxonomy Analysis"
    )

    bloom_rows = []

    for level in BLOOM_LEVELS:

        level_results = [
            r
            for r in results
            if r["Detected Bloom"] == level
        ]

        if level_results:

            score = round(
                sum(
                    r["Bloom Alignment %"]
                    for r in level_results
                )
                /
                len(level_results),
                1
            )

        else:

            score = 0

        bloom_rows.append(
            {
                "Bloom Level": level,
                "Questions": len(
                    level_results
                ),
                "Alignment %": score
            }
        )

    bloom_df = pd.DataFrame(
        bloom_rows
    )

    st.dataframe(
        bloom_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # COMPLETE QUESTION ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "📝 Complete Question Analysis"
    )

    results_df = pd.DataFrame(
        results
    )

    st.dataframe(
        results_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # INDIVIDUAL QUESTION REVIEW
    # ========================================================

    st.divider()

    st.header(
        "🔎 Individual Question Review"
    )

    question_options = list(
        range(len(results))
    )

    selected_question_index = st.selectbox(
        "Select one question to review",
        question_options,
        format_func=lambda index:
            (
                f"Q{results[index]['Question No.']}: "
                f"{results[index]['Question'][:100]}"
            ),
        key="selected_question"
    )

    selected_result = results[
        selected_question_index
    ]

    st.subheader(
        f"Question "
        f"{selected_result['Question No.']}"
    )

    st.write(
        selected_result["Question"]
    )

    q1, q2, q3, q4 = st.columns(4)

    with q1:

        st.metric(
            "CLO Alignment",
            f"{selected_result['CLO Alignment %']}%"
        )

    with q2:

        st.metric(
            "PLO Alignment",
            f"{selected_result['PLO Alignment %']}%"
        )

    with q3:

        st.metric(
            "Bloom Alignment",
            f"{selected_result['Bloom Alignment %']}%"
        )

    with q4:

        st.metric(
            "Combined Alignment",
            f"{selected_result['Combined Alignment %']}%"
        )

    # --------------------------------------------------------
    # Suggestion
    # --------------------------------------------------------

    suggestion = get_suggestion(
        selected_result,
        clos,
        plos
    )

    st.subheader(
        "💡 Question Improvement"
    )

    if suggestion["strong"]:

        st.success(
            suggestion["message"]
        )

    else:

        if suggestion["message"]:

            st.write(
                suggestion["message"]
            )

        st.write(
            "**Suggested alternative questions:**"
        )

        for i, alternative in enumerate(
            suggestion["alternatives"],
            1
        ):

            st.info(
                f"{i}. {alternative}"
            )

    # ========================================================
    # QUESTIONS NEEDING ATTENTION
    # ========================================================

    st.divider()

    st.header(
        "⚠️ Questions Requiring Attention"
    )

    weak_questions = [
        r
        for r in results
        if r["Combined Alignment %"] < 60
    ]

    if weak_questions:

        weak_df = pd.DataFrame(
            [
                {
                    "Question No.": r[
                        "Question No."
                    ],
                    "Question": r[
                        "Question"
                    ],
                    "Best CLO": r[
                        "Best CLO"
                    ],
                    "Best PLO": r[
                        "Best PLO"
                    ],
                    "Detected Bloom": r[
                        "Detected Bloom"
                    ],
                    "Combined Alignment %": r[
                        "Combined Alignment %"
                    ]
                }
                for r in weak_questions
            ]
        )

        st.dataframe(
            weak_df,
            use_container_width=True,
            hide_index=True
        )

        st.info(
            "Select a question in Individual Question Review "
            "to generate three alternative questions."
        )

    else:

        st.success(
            "No questions currently fall below the "
            "attention threshold."
        )

    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header(
        "📥 Export Analysis"
    )

    export_df = pd.DataFrame(
        results
    )

    csv_data = (
        export_df
        .to_csv(index=False)
        .encode("utf-8")
    )

    st.download_button(
        label="Download Analysis as CSV",
        data=csv_data,
        file_name=(
            "OBE_Quiz_Alignment_Analysis.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.divider()

    st.header(
        "📌 Summary"
    )

    strong = sum(
        1
        for r in results
        if r["Combined Alignment %"] >= 85
    )

    attention = sum(
        1
        for r in results
        if r["Combined Alignment %"] < 60
    )

    moderate = (
        len(results)
        -
        strong
        -
        attention
    )

    s1, s2, s3 = st.columns(3)

    with s1:

        st.metric(
            "Strong Alignment",
            strong
        )

    with s2:

        st.metric(
            "Moderate Alignment",
            moderate
        )

    with s3:

        st.metric(
            "Needs Attention",
            attention
        )

    st.caption(
        "The alignment percentages are indicators based on "
        "question/outcome text similarity and Bloom's-level "
        "matching. They are not student attainment percentages."
    )
