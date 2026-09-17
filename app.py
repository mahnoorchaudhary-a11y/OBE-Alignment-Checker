import io
import re
import pandas as pd
import streamlit as st

# Optional document libraries
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    from docx import Document
except Exception:
    Document = None


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
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "mention", "select"
    ],
    "Understand": [
        "explain", "describe", "summarize", "interpret",
        "classify", "discuss", "illustrate", "compare"
    ],
    "Apply": [
        "apply", "use", "demonstrate", "solve", "calculate",
        "implement", "practice", "construct"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "examine",
        "distinguish", "investigate", "compare", "organize",
        "identify relationship"
    ],
    "Evaluate": [
        "evaluate", "assess", "justify", "critique",
        "judge", "defend", "appraise", "recommend"
    ],
    "Create": [
        "create", "design", "develop", "formulate",
        "produce", "construct", "compose", "propose"
    ]
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "with", "by", "from", "at", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these",
    "those", "it", "its", "as", "into", "about", "which",
    "what", "how", "why", "when", "where", "who", "can",
    "could", "should", "would", "will", "may", "might",
    "do", "does", "did", "your", "their", "his", "her",
    "our", "you", "we", "they", "them", "than", "then",
    "through", "using", "used", "given", "following"
}


# ============================================================
# TEXT PROCESSING
# ============================================================

def normalize_text(text):
    if text is None:
        return ""

    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text):
    words = normalize_text(text).split()
    return {
        w for w in words
        if len(w) > 2 and w not in STOP_WORDS
    }


def important_words(text, limit=18):
    words = list(tokenize(text))
    return words[:limit]


# ============================================================
# CONCEPT DETECTION
# ============================================================

CONCEPT_GROUPS = {
    "main idea": [
        "main idea", "central idea", "main point",
        "central point", "primary idea"
    ],

    "reading comprehension": [
        "reading", "comprehension", "passage",
        "text", "understand", "interpret"
    ],

    "patterns of organization": [
        "pattern of organization", "organization",
        "organizational pattern", "sequence",
        "cause and effect", "compare contrast",
        "comparison", "contrast", "chronological",
        "problem solution"
    ],

    "paraphrasing": [
        "paraphrase", "paraphrasing", "rewrite",
        "restatement", "own words"
    ],

    "author purpose": [
        "author purpose", "author's purpose",
        "purpose of the author", "writer purpose",
        "writer's purpose"
    ],

    "author tone": [
        "author tone", "author's tone",
        "tone of the author", "writer tone"
    ],

    "writing": [
        "write", "writing", "essay", "paragraph",
        "composition", "draft"
    ],

    "critical thinking": [
        "critical thinking", "reasoning", "argument",
        "evidence", "claim", "argumentation"
    ],

    "communication": [
        "communication", "communicate", "speaking",
        "listening", "presentation"
    ],

    "grammar": [
        "grammar", "sentence", "verb", "noun",
        "pronoun", "tense", "syntax"
    ],

    "vocabulary": [
        "vocabulary", "word meaning", "meaning",
        "synonym", "antonym", "context"
    ],

    "research": [
        "research", "source", "citation",
        "reference", "literature"
    ],

    "analysis": [
        "analysis", "analyze", "analyse",
        "examine", "evaluate"
    ],

    "problem solving": [
        "problem solving", "solve", "solution",
        "problem"
    ]
}


def detect_concept(text):
    normalized = normalize_text(text)

    best_concept = ""
    best_score = 0

    for concept, keywords in CONCEPT_GROUPS.items():
        score = 0

        for keyword in keywords:
            if keyword in normalized:
                score += 3

        if score > best_score:
            best_score = score
            best_concept = concept

    return best_concept


def extract_topic(text):
    concept = detect_concept(text)

    if concept:
        return concept

    words = important_words(text, 8)

    if words:
        return " ".join(words[:5])

    return "the stated topic"


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):
    q = normalize_text(question)

    detected = []

    for level in BLOOM_LEVELS:
        for verb in BLOOM_VERBS[level]:
            if verb in q:
                detected.append(level)
                break

    if detected:
        return detected[-1]

    return "Needs Review"


def bloom_alignment(intended, detected):
    if detected == "Needs Review":
        return 40

    intended_rank = BLOOM_RANK[intended]
    detected_rank = BLOOM_RANK[detected]

    difference = abs(intended_rank - detected_rank)

    if difference == 0:
        return 100
    elif difference == 1:
        return 65
    elif difference == 2:
        return 45
    else:
        return 25


# ============================================================
# FAST TEXT SIMILARITY
# ============================================================

def text_similarity(question, outcome):
    q_words = tokenize(question)
    o_words = tokenize(outcome)

    if not q_words or not o_words:
        return 0

    intersection = q_words.intersection(o_words)

    score = len(intersection) / max(1, len(o_words))

    # Small concept bonus
    q_normal = normalize_text(question)
    o_normal = normalize_text(outcome)

    concept_q = detect_concept(q_normal)
    concept_o = detect_concept(o_normal)

    if concept_q and concept_q == concept_o:
        score += 0.45

    # Important word overlap
    important_overlap = 0

    for word in q_words:
        if word in o_words:
            important_overlap += 1

    score += min(0.15, important_overlap * 0.02)

    return min(100, round(score * 100, 1))


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_text_from_uploaded_file(uploaded_file):
    if uploaded_file is None:
        return ""

    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    # TXT
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")

    # DOCX
    if name.endswith(".docx"):
        if Document is None:
            return ""

        try:
            doc = Document(io.BytesIO(data))
            paragraphs = [
                p.text for p in doc.paragraphs
                if p.text.strip()
            ]

            # Also read tables
            for table in doc.tables:
                for row in table.rows:
                    paragraphs.append(
                        " ".join(cell.text for cell in row.cells)
                    )

            return "\n".join(paragraphs)

        except Exception:
            return ""

    # PDF
    if name.endswith(".pdf"):
        if PdfReader is None:
            return ""

        try:
            reader = PdfReader(io.BytesIO(data))
            pages = []

            for page in reader.pages:
                try:
                    text = page.extract_text() or ""
                    pages.append(text)
                except Exception:
                    continue

            return "\n".join(pages)

        except Exception:
            return ""

    # Excel
    if name.endswith(".xlsx") or name.endswith(".xls"):
        try:
            excel = pd.ExcelFile(io.BytesIO(data))
            all_text = []

            for sheet in excel.sheet_names:
                df = pd.read_excel(
                    io.BytesIO(data),
                    sheet_name=sheet,
                    header=None
                )

                for row in df.astype(str).values.tolist():
                    all_text.append(" ".join(row))

            return "\n".join(all_text)

        except Exception:
            return ""

    return ""


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):
    if not text:
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    questions = []

    # First attempt: numbered questions
    numbered = re.findall(
        r"(?:^|\n)\s*(?:Q(?:uestion)?\s*)?(\d+)[\.\):\-]\s*(.+?)(?=\n\s*(?:Q(?:uestion)?\s*)?\d+[\.\):\-]|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    for number, content in numbered:
        content = re.sub(r"\s+", " ", content).strip()

        if len(content) >= 8:
            questions.append({
                "number": int(number),
                "text": content
            })

    if questions:
        return questions

    # Second attempt: lines ending in ?
    lines = text.split("\n")

    for line in lines:
        clean = re.sub(r"\s+", " ", line).strip()

        if "?" in clean and len(clean) >= 8:
            parts = re.split(r"(?<=\?)\s+", clean)

            for part in parts:
                if "?" in part and len(part.strip()) >= 8:
                    questions.append({
                        "number": len(questions) + 1,
                        "text": part.strip()
                    })

    # Final fallback: paragraphs
    if not questions:
        paragraphs = re.split(r"\n\s*\n", text)

        for paragraph in paragraphs:
            clean = re.sub(r"\s+", " ", paragraph).strip()

            if len(clean) >= 20:
                questions.append({
                    "number": len(questions) + 1,
                    "text": clean
                })

    return questions


# ============================================================
# CLO / PLO PARSING
# ============================================================

def parse_outcomes(text, prefix):
    outcomes = {}

    if not text:
        return outcomes

    lines = text.splitlines()

    for line in lines:
        clean = line.strip()

        if not clean:
            continue

        pattern = rf"^\s*({prefix}\s*\d+)\s*[:\-\)]\s*(.+)$"

        match = re.match(pattern, clean, flags=re.IGNORECASE)

        if match:
            code = match.group(1).upper().replace(" ", "")
            description = match.group(2).strip()

            outcomes[code] = description

    # If no labels were found, treat each non-empty line as an outcome
    if not outcomes:
        counter = 1

        for line in lines:
            clean = line.strip()

            if len(clean) >= 5:
                outcomes[f"{prefix}{counter}"] = clean
                counter += 1

    return outcomes


# ============================================================
# FAST ANALYSIS
# ============================================================

def analyze_question(question, clos, plos, intended_bloom):
    best_clo_name = ""
    best_clo_score = 0

    best_plo_name = ""
    best_plo_score = 0

    for code, description in clos.items():
        score = text_similarity(question, description)

        if score > best_clo_score:
            best_clo_score = score
            best_clo_name = code

    for code, description in plos.items():
        score = text_similarity(question, description)

        if score > best_plo_score:
            best_plo_score = score
            best_plo_name = code

    detected = detect_bloom(question)
    bloom_score = bloom_alignment(
        intended_bloom,
        detected
    )

    combined = (
        best_clo_score * 0.35
        + best_plo_score * 0.25
        + bloom_score * 0.40
    )

    return {
        "Question No.": question["number"],
        "Question": question["text"],
        "Best CLO": best_clo_name,
        "CLO Alignment %": round(best_clo_score, 1),
        "Best PLO": best_plo_name,
        "PLO Alignment %": round(best_plo_score, 1),
        "Intended Bloom": intended_bloom,
        "Detected Bloom": detected,
        "Bloom Alignment %": round(bloom_score, 1),
        "Combined Alignment %": round(combined, 1)
    }


def analyze_quiz(questions, clos, plos, intended_bloom):
    results = []

    # Cache outcome text processing
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
# SUGGESTED QUESTIONS
# ============================================================

def generate_three_questions(clo_text, plo_text, bloom):
    concept = detect_concept(clo_text)
    topic = extract_topic(clo_text)

    # -------------------------
    # Patterns of organization
    # -------------------------
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

    # -------------------------
    # Main idea
    # -------------------------
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

    # -------------------------
    # Paraphrasing
    # -------------------------
    if concept == "paraphrasing":

        if bloom == "Remember":
            return [
                "Identify the statement that accurately represents the meaning of the given passage.",
                "Recognize the key meaning that must be preserved when rewriting the given passage.",
                "Identify the central meaning of the given passage before rewriting it in your own words."
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

    # -------------------------
    # Author purpose
    # -------------------------
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

    # -------------------------
    # Author tone
    # -------------------------
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

    # -------------------------
    # Generic
    # -------------------------

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
# SUGGESTION GENERATION
# ============================================================

def generate_revision_suggestion(result, clos, plos):
    clo_code = result["Best CLO"]
    plo_code = result["Best PLO"]

    clo_text = clos.get(clo_code, "")
    plo_text = plos.get(plo_code, "")

    combined = result["Combined Alignment %"]
    clo_score = result["CLO Alignment %"]
    plo_score = result["PLO Alignment %"]
    bloom_score = result["Bloom Alignment %"]

    # Strong existing alignment
    if clo_score >= 85 and plo_score >= 85 and bloom_score >= 85:
        return (
            "This question is appropriately aligned with the selected learning "
            "outcome, broader skill, and intended cognitive level. It represents "
            "a strong basis for 100% alignment with the specified assessment requirements."
        )

    issues = []

    if clo_score < 70:
        issues.append(
            "Strengthen the connection between the question and the selected learning outcome."
        )

    if plo_score < 70:
        issues.append(
            "Make the assessed skill more clearly connected to the selected broader learning goal."
        )

    if bloom_score < 70:
        issues.append(
            f"Revise the task so that it more clearly requires the intended "
            f"{result['Intended Bloom']} cognitive process."
        )

    alternatives = generate_three_questions(
        clo_text,
        plo_text,
        result["Intended Bloom"]
    )

    suggestion = " ".join(issues)

    suggestion += " Suggested alternatives: "

    for i, question in enumerate(alternatives, start=1):
        suggestion += f"{i}. {question} "

    return suggestion.strip()


# ============================================================
# DATAFRAME ANALYSIS
# ============================================================

def calculate_overall(results):
    if not results:
        return 0

    return round(
        sum(r["Combined Alignment %"] for r in results)
        / len(results),
        1
    )


def calculate_dimension_average(results, column):
    if not results:
        return 0

    values = [
        r[column]
        for r in results
        if isinstance(r[column], (int, float))
    ]

    if not values:
        return 0

    return round(sum(values) / len(values), 1)


def get_clo_score(results, clo_code):
    values = [
        r["CLO Alignment %"]
        for r in results
        if r["Best CLO"] == clo_code
    ]

    if not values:
        return 0

    return round(sum(values) / len(values), 1)


def get_plo_score(results, plo_code):
    values = [
        r["PLO Alignment %"]
        for r in results
        if r["Best PLO"] == plo_code
    ]

    if not values:
        return 0

    return round(sum(values) / len(values), 1)


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

if "questions" not in st.session_state:
    st.session_state.questions = []

if "clos" not in st.session_state:
    st.session_state.clos = {}

if "plos" not in st.session_state:
    st.session_state.plos = {}

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False


# ============================================================
# TITLE
# ============================================================

st.title("🎓 OBE Quiz Alignment Checker")

st.write(
    "Analyze a quiz against selected learning outcomes and Bloom's Taxonomy."
)


# ============================================================
# INPUT SECTION
# ============================================================

st.header("1. Assessment Information")

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

st.header("2. Course Learning Outcomes")

clo_text = st.text_area(
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

st.header("3. Program Learning Outcomes")

plo_text = st.text_area(
    "Enter PLOs",
    height=150,
    placeholder=(
        "PLO1: Communication Skills\n"
        "PLO2: Critical Thinking\n"
        "PLO3: Problem Solving"
    )
)


# ============================================================
# BLOOM
# ============================================================

st.header("4. Intended Bloom's Level")

intended_bloom = st.selectbox(
    "Select the cognitive level intended for this quiz",
    BLOOM_LEVELS,
    index=2
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.header("5. Upload Quiz")

uploaded_file = st.file_uploader(
    "Upload your complete quiz",
    type=["pdf", "docx", "txt", "xlsx", "xls"],
    help="Upload the complete quiz instead of entering questions individually."
)


# ============================================================
# ANALYZE BUTTON
# ============================================================

analyze_clicked = st.button(
    "🔍 Analyze Quiz",
    type="primary",
    use_container_width=True
)


if analyze_clicked:

    if not clo_text.strip():
        st.error("Please enter at least one CLO.")
        st.stop()

    if not plo_text.strip():
        st.error("Please enter at least one PLO.")
        st.stop()

    if uploaded_file is None:
        st.error("Please upload the quiz.")
        st.stop()

    with st.spinner("Reading and analyzing the quiz..."):

        clos = parse_outcomes(clo_text, "CLO")
        plos = parse_outcomes(plo_text, "PLO")

        quiz_text = extract_text_from_uploaded_file(
            uploaded_file
        )

        questions = extract_questions(quiz_text)

        if not questions:
            st.error(
                "No questions could be detected. "
                "Please check the quiz format or use a text-based PDF/DOCX/TXT file."
            )
            st.stop()

        results = analyze_quiz(
            questions,
            clos,
            plos,
            intended_bloom
        )

        st.session_state.analysis_results = results
        st.session_state.questions = questions
        st.session_state.clos = clos
        st.session_state.plos = plos
        st.session_state.analysis_done = True


# ============================================================
# ANALYSIS RESULTS
# ============================================================

if st.session_state.analysis_done:

    results = st.session_state.analysis_results
    clos = st.session_state.clos
    plos = st.session_state.plos

    st.divider()

    st.header("📊 Quiz Analysis")

    # ========================================================
    # OVERALL GRAPH AT TOP
    # ========================================================

    overall = calculate_overall(results)

    avg_clo = calculate_dimension_average(
        results,
        "CLO Alignment %"
    )

    avg_plo = calculate_dimension_average(
        results,
        "PLO Alignment %"
    )

    avg_bloom = calculate_dimension_average(
        results,
        "Bloom Alignment %"
    )

    st.subheader("📈 Overall Alignment")

    graph_df = pd.DataFrame({
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
    })

    st.bar_chart(
        graph_df.set_index("Dimension"),
        y="Alignment",
        use_container_width=True
    )

    st.caption(
        "These percentages evaluate quiz-level alignment. "
        "They are not student attainment percentages."
    )

    # ========================================================
    # QUICK SUMMARY
    # ========================================================

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Overall Alignment",
            f"{overall}%"
        )

    with c2:
        st.metric(
            "CLO Alignment",
            f"{avg_clo}%"
        )

    with c3:
        st.metric(
            "PLO Alignment",
            f"{avg_plo}%"
        )

    with c4:
        st.metric(
            "Bloom Alignment",
            f"{avg_bloom}%"
        )

    st.info(
        f"{len(results)} question(s) analyzed."
    )

    # ========================================================
    # CLO REVIEW - ONE AT A TIME
    # ========================================================

    st.divider()

    st.header("🎯 CLO Review")

    if clos:

        selected_clo = st.selectbox(
            "Select one CLO to review",
            list(clos.keys()),
            format_func=lambda x: f"{x}: {clos[x]}"
        )

        selected_clo_score = get_clo_score(
            results,
            selected_clo
        )

        st.metric(
            "Selected CLO Alignment",
            f"{selected_clo_score}%"
        )

        st.write("**Selected CLO:**")
        st.write(clos[selected_clo])

        clo_questions = [
            r for r in results
            if r["Best CLO"] == selected_clo
        ]

        st.write(
            f"**Questions mapped to {selected_clo}: "
            f"{len(clo_questions)}**"
        )

        if clo_questions:

            clo_display = pd.DataFrame([
                {
                    "Question No.": r["Question No."],
                    "Question": r["Question"],
                    "Alignment %": r["CLO Alignment %"],
                    "Detected Bloom": r["Detected Bloom"]
                }
                for r in clo_questions
            ])

            st.dataframe(
                clo_display,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "No question is strongly mapped to this CLO."
            )

            st.write("Suggested questions:")

            alternatives = generate_three_questions(
                clos[selected_clo],
                "",
                intended_bloom
            )

            for i, q in enumerate(alternatives, 1):
                st.info(f"{i}. {q}")

    # ========================================================
    # PLO REVIEW - ONE AT A TIME
    # ========================================================

    st.divider()

    st.header("🎯 PLO Review")

    if plos:

        selected_plo = st.selectbox(
            "Select one PLO to review",
            list(plos.keys()),
            format_func=lambda x: f"{x}: {plos[x]}"
        )

        selected_plo_score = get_plo_score(
            results,
            selected_plo
        )

        st.metric(
            "Selected PLO Alignment",
            f"{selected_plo_score}%"
        )

        st.write("**Selected PLO:**")
        st.write(plos[selected_plo])

        plo_questions = [
            r for r in results
            if r["Best PLO"] == selected_plo
        ]

        st.write(
            f"**Questions mapped to {selected_plo}: "
            f"{len(plo_questions)}**"
        )

        if plo_questions:

            plo_display = pd.DataFrame([
                {
                    "Question No.": r["Question No."],
                    "Question": r["Question"],
                    "Alignment %": r["PLO Alignment %"],
                    "Detected Bloom": r["Detected Bloom"]
                }
                for r in plo_questions
            ])

            st.dataframe(
                plo_display,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "No question is strongly mapped to this PLO."
            )

    # ========================================================
    # BLOOM NUMERICAL TABLE
    # ========================================================

    st.divider()

    st.header("🧠 Bloom's Taxonomy Analysis")

    bloom_rows = []

    for level in BLOOM_LEVELS:

        level_questions = [
            r for r in results
            if r["Detected Bloom"] == level
        ]

        if level_questions:
            average = round(
                sum(
                    r["Bloom Alignment %"]
                    for r in level_questions
                ) / len(level_questions),
                1
            )
        else:
            average = 0

        bloom_rows.append({
            "Bloom Level": level,
            "Questions": len(level_questions),
            "Alignment %": average
        })

    bloom_df = pd.DataFrame(bloom_rows)

    st.dataframe(
        bloom_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # COMPLETE QUESTION ANALYSIS
    # ========================================================

    st.divider()

    st.header("📝 Complete Question Analysis")

    display_results = []

    for r in results:

        display_results.append({
            "Question No.": r["Question No."],
            "Question": r["Question"],
            "Best CLO": r["Best CLO"],
            "CLO Alignment %": r["CLO Alignment %"],
            "Best PLO": r["Best PLO"],
            "PLO Alignment %": r["PLO Alignment %"],
            "Intended Bloom": r["Intended Bloom"],
            "Detected Bloom": r["Detected Bloom"],
            "Bloom Alignment %": r["Bloom Alignment %"],
            "Combined Alignment %": r["Combined Alignment %"]
        })

    results_df = pd.DataFrame(display_results)

    st.dataframe(
        results_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # INDIVIDUAL QUESTION REVIEW
    # ========================================================

    st.divider()

    st.header("🔎 Individual Question Review")

    question_options = {
        f"Q{r['Question No.']}: {r['Question'][:100]}": r
        for r in results
    }

    selected_question_label = st.selectbox(
        "Select one question to review",
        list(question_options.keys())
    )

    selected_question = question_options[
        selected_question_label
    ]

    st.write(
        f"### Question {selected_question['Question No.']}"
    )

    st.write(
        selected_question["Question"]
    )

    a, b, c, d, e = st.columns(5)

    with a:
        st.metric(
            "CLO",
            f"{selected_question['CLO Alignment %']}%"
        )

    with b:
        st.metric(
            "PLO",
            f"{selected_question['PLO Alignment %']}%"
        )

    with c:
        st.metric(
            "Bloom",
            f"{selected_question['Bloom Alignment %']}%"
        )

    with d:
        st.metric(
            "Overall",
            f"{selected_question['Combined Alignment %']}%"
        )

    with e:
        st.metric(
            "Detected",
            selected_question["Detected Bloom"]
        )

    # Generate detailed suggestion ONLY for selected question
    selected_suggestion = generate_revision_suggestion(
        selected_question,
        clos,
        plos
    )

    st.subheader("Suggestions")

    if "Suggested alternatives:" in selected_suggestion:

        parts = selected_suggestion.split(
            "Suggested alternatives:"
        )

        st.write(parts[0].strip())

        alternatives_text = parts[1].strip()

        alternative_questions = re.findall(
            r"\d+\.\s*(.*?)(?=\s+\d+\.\s*|$)",
            alternatives_text
        )

        for i, question in enumerate(
            alternative_questions[:3],
            1
        ):
            st.info(
                f"{i}. {question.strip()}"
            )

    else:
        st.success(
            selected_suggestion
        )

    # ========================================================
    # WEAK QUESTIONS
    # ========================================================

    st.divider()

    st.header("⚠️ Questions Requiring Attention")

    weak_questions = [
        r for r in results
        if r["Combined Alignment %"] < 60
    ]

    if weak_questions:

        weak_display = pd.DataFrame([
            {
                "Question No.": r["Question No."],
                "Question": r["Question"],
                "Best CLO": r["Best CLO"],
                "Best PLO": r["Best PLO"],
                "Detected Bloom": r["Detected Bloom"],
                "Combined Alignment %": r["Combined Alignment %"]
            }
            for r in weak_questions
        ])

        st.dataframe(
            weak_display,
            use_container_width=True,
            hide_index=True
        )

        st.info(
            "Select a question above in Individual Question Review "
            "to generate three alternative questions."
        )

    else:

        st.success(
            "No questions currently fall below the attention threshold."
        )

    # ========================================================
    # CSV EXPORT
    # ========================================================

    st.divider()

    st.header("📥 Export Analysis")

    export_df = pd.DataFrame(results)

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="Download Analysis as CSV",
        data=csv_data,
        file_name="OBE_Quiz_Alignment_Analysis.csv",
        mime="text/csv",
        use_container_width=True
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.divider()

    st.header("📌 Summary")

    strong_count = sum(
        1 for r in results
        if r["Combined Alignment %"] >= 85
    )

    review_count = sum(
        1 for r in results
        if r["Combined Alignment %"] < 60
    )

    moderate_count = len(results) - strong_count - review_count

    s1, s2, s3 = st.columns(3)

    with s1:
        st.metric(
            "Strongly Aligned",
            strong_count
        )

    with s2:
        st.metric(
            "Moderate / Review",
            moderate_count
        )

    with s3:
        st.metric(
            "Needs Attention",
            review_count
        )

    st.caption(
        "The alignment percentages are analytical indicators based on "
        "text similarity and Bloom's-level matching. They should support "
        "faculty review rather than replace academic judgment."
    )
