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
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# CONSTANTS
# ============================================================

BLOOM_LEVELS = {
    "Remember": {
        "verbs": [
            "define", "list", "name", "identify", "state", "recall",
            "recognize", "match", "select", "label", "mention"
        ],
        "rank": 1
    },
    "Understand": {
        "verbs": [
            "describe", "explain", "summarize", "interpret", "classify",
            "discuss", "illustrate", "paraphrase", "compare", "differentiate"
        ],
        "rank": 2
    },
    "Apply": {
        "verbs": [
            "apply", "use", "calculate", "solve", "demonstrate",
            "implement", "execute", "compute", "operate", "practice"
        ],
        "rank": 3
    },
    "Analyze": {
        "verbs": [
            "analyze", "analyse", "examine", "investigate", "differentiate",
            "deconstruct", "categorize", "compare", "contrast", "infer",
            "break down", "identify relationships"
        ],
        "rank": 4
    },
    "Evaluate": {
        "verbs": [
            "evaluate", "assess", "judge", "justify", "critique",
            "defend", "appraise", "validate", "recommend", "argue"
        ],
        "rank": 5
    },
    "Create": {
        "verbs": [
            "create", "design", "develop", "construct", "formulate",
            "produce", "propose", "generate", "plan", "develop"
        ],
        "rank": 6
    }
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for",
    "with", "by", "from", "as", "at", "is", "are", "was", "were",
    "be", "been", "being", "that", "this", "these", "those", "it",
    "its", "their", "they", "them", "he", "she", "his", "her",
    "you", "your", "we", "our", "which", "who", "whom", "what",
    "when", "where", "why", "how", "into", "through", "about",
    "than", "then", "also", "such", "can", "could", "should",
    "would", "may", "might", "will", "shall", "do", "does", "did",
    "have", "has", "had", "not", "no", "yes", "each", "every",
    "any", "all", "both", "more", "most", "some", "one", "two"
}

GENERIC_OUTCOME_WORDS = {
    "apply", "use", "understand", "demonstrate", "knowledge",
    "ability", "skills", "skill", "knowledge", "discipline",
    "field", "concepts", "concept", "principles", "principle",
    "information", "appropriate", "relevant", "effectively",
    "effectively", "problems", "problem", "solutions", "solution",
    "communicate", "communication", "work", "team", "professional",
    "practice", "practice", "ethical", "ethically"
}

GENERIC_QUESTION_PHRASES = {
    "what is",
    "what are",
    "define",
    "write a note on",
    "write notes on",
    "discuss",
    "explain",
    "describe",
    "give an account of",
    "what do you know about",
    "tell me about",
    "comment on"
}


# ============================================================
# TEXT UTILITIES
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = text.replace("\u2018", "'")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokens(text):
    words = normalize(text).split()
    return [
        w for w in words
        if len(w) > 2 and w not in STOPWORDS
    ]


def token_set(text):
    return set(tokens(text))


def stem(word):
    word = word.lower().strip()

    suffixes = [
        "ization", "isation", "ations", "ation",
        "ments", "ment", "ingly", "edly",
        "ing", "ers", "ies", "es", "ed", "ly", "s"
    ]

    for suffix in suffixes:
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[:-len(suffix)]

    return word


def stemmed_tokens(text):
    return {stem(w) for w in tokens(text)}


def overlap_score(text_a, text_b):
    a = stemmed_tokens(text_a)
    b = stemmed_tokens(text_b)

    if not a or not b:
        return 0.0

    intersection = len(a & b)

    precision = intersection / len(a)
    recall = intersection / len(b)

    if precision + recall == 0:
        return 0.0

    f1 = 2 * precision * recall / (precision + recall)

    return f1 * 100


def meaningful_outcome_tokens(text):
    words = stemmed_tokens(text)

    return {
        w for w in words
        if w not in {
            stem(x) for x in GENERIC_OUTCOME_WORDS
        }
    }


# ============================================================
# QUESTION CLEANING
# ============================================================

def finalize_question(text):
    """
    Ensures the final question has exactly one question mark.
    Removes . ? / .? / !! etc.
    """

    text = clean_text(text)

    text = re.sub(r"[.!?]+$", "", text).strip()

    text = re.sub(r"\s+\?", "?", text)

    if not text:
        return ""

    return text + "?"


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text, prefix):
    if not text:
        return []

    lines = str(text).splitlines()

    outcomes = []

    for line in lines:
        line = clean_text(line)

        if not line:
            continue

        # Remove numbering
        line = re.sub(
            r"^\s*(?:CLO|PLO)?\s*[-_:]?\s*\d+\s*[\.\):\-]?\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        # Remove bullets
        line = re.sub(r"^[\-\*\u2022]+\s*", "", line)

        # If the line contains a prefix, keep content after it
        if prefix:
            line = re.sub(
                rf"^\s*{prefix}\s*\d*\s*[:\-]\s*",
                "",
                line,
                flags=re.IGNORECASE
            )

        line = clean_text(line)

        if len(line) >= 5:
            outcomes.append(line)

    return outcomes


# ============================================================
# BLOOM FUNCTIONS
# ============================================================

def detect_bloom(question):
    q = normalize(question)

    matches = []

    for level, data in BLOOM_LEVELS.items():
        for verb in data["verbs"]:
            if re.search(
                rf"\b{re.escape(normalize(verb))}\b",
                q
            ):
                matches.append(
                    (
                        level,
                        data["rank"],
                        len(normalize(verb).split())
                    )
                )

    if not matches:
        return "Understand"

    matches.sort(
        key=lambda x: (x[1], x[2]),
        reverse=True
    )

    return matches[0][0]


def bloom_alignment(question, target_bloom):
    detected = detect_bloom(question)

    target_rank = BLOOM_LEVELS.get(
        target_bloom,
        BLOOM_LEVELS["Understand"]
    )["rank"]

    detected_rank = BLOOM_LEVELS.get(
        detected,
        BLOOM_LEVELS["Understand"]
    )["rank"]

    if detected == target_bloom:
        return 100.0

    difference = abs(target_rank - detected_rank)

    if difference == 1:
        return 78.0

    if difference == 2:
        return 62.0

    if difference == 3:
        return 45.0

    return 30.0


def outcome_action_level(outcome):
    return detect_bloom(outcome)


def action_alignment(question, outcome):
    q_level = detect_bloom(question)
    o_level = outcome_action_level(outcome)

    q_rank = BLOOM_LEVELS[q_level]["rank"]
    o_rank = BLOOM_LEVELS[o_level]["rank"]

    difference = abs(q_rank - o_rank)

    if difference == 0:
        return 100.0

    if difference == 1:
        return 82.0

    if difference == 2:
        return 66.0

    if difference == 3:
        return 50.0

    return 35.0


# ============================================================
# SUBJECT RELEVANCE
# ============================================================

def subject_score(question, course_name, course_content):
    q_tokens = stemmed_tokens(question)

    if not q_tokens:
        return 20.0

    course_tokens = stemmed_tokens(
        f"{course_name} {course_content}"
    )

    if not course_tokens:
        return 70.0

    meaningful_course = {
        x for x in course_tokens
        if x not in {
            stem(v) for v in GENERIC_OUTCOME_WORDS
        }
    }

    overlap = len(q_tokens & meaningful_course)

    if overlap == 0:
        return 35.0

    coverage = overlap / max(
        1,
        min(len(q_tokens), 8)
    )

    score = 45 + coverage * 55

    # Topic-specific question should score higher
    if overlap >= 3:
        score += 5

    return min(100.0, score)


# ============================================================
# CLO ALIGNMENT
# ============================================================

def clo_alignment(question, clo):
    if not clo:
        return 0.0

    q_tokens = stemmed_tokens(question)

    clo_tokens = meaningful_outcome_tokens(clo)

    if not clo_tokens:
        # Generic CLO: rely on action and question content
        action = action_alignment(question, clo)

        if action >= 80:
            return 82.0

        return action

    matched = q_tokens & clo_tokens

    coverage = len(matched) / len(clo_tokens)

    action = action_alignment(question, clo)

    # Strong weighting toward actual CLO concept coverage
    score = (
        coverage * 70
        + action * 30
    )

    # Extra credit for direct concept coverage
    if len(matched) >= 2:
        score += 5

    if len(matched) >= 4:
        score += 5

    return min(100.0, score)


# ============================================================
# PLO ALIGNMENT
# ============================================================

def plo_alignment(question, plo, course_name, course_content):
    if not plo:
        return 0.0

    q_tokens = stemmed_tokens(question)

    plo_tokens = meaningful_outcome_tokens(plo)

    discipline_tokens = stemmed_tokens(
        f"{course_name} {course_content}"
    )

    if plo_tokens:
        matched_plo = q_tokens & plo_tokens
        plo_coverage = len(matched_plo) / len(plo_tokens)
    else:
        plo_coverage = 0.0

    # Generic PLOs such as:
    # "Apply knowledge of the discipline"
    # require actual course/domain evidence.
    domain_matches = q_tokens & discipline_tokens

    domain_coverage = min(
        1.0,
        len(domain_matches) / max(1, min(4, len(discipline_tokens)))
    )

    action = action_alignment(question, plo)

    if plo_tokens:
        score = (
            plo_coverage * 55
            + domain_coverage * 20
            + action * 25
        )
    else:
        score = (
            domain_coverage * 55
            + action * 45
        )

    if len(domain_matches) >= 2:
        score += 5

    return min(100.0, score)


# ============================================================
# SPECIFICITY
# ============================================================

def specificity_score(question):
    q = clean_text(question)
    q_norm = normalize(q)

    if not q_norm:
        return 0.0

    score = 45.0

    q_words = q_norm.split()

    # Reasonable length
    if len(q_words) >= 8:
        score += 12

    if len(q_words) >= 12:
        score += 8

    if len(q_words) >= 18:
        score += 5

    # Direct action
    detected = detect_bloom(q)

    if detected:
        score += 10

    # Objects / constraints
    if re.search(
        r"\b(using|given|based on|using the|from the|with|for|"
        r"compare|contrast|calculate|justify|provide|identify|"
        r"explain|analyze|evaluate|design|develop)\b",
        q_norm
    ):
        score += 10

    # Number/detail indicators
    if re.search(
        r"\b\d+\b|\btwo\b|\bthree\b|\bfour\b|\bfirst\b|\bsecond\b",
        q_norm
    ):
        score += 5

    # Penalize vague wording
    vague_phrases = [
        "discuss the topic",
        "write something about",
        "tell me about",
        "say something about",
        "what do you know about",
        "discuss",
        "explain the topic"
    ]

    for phrase in vague_phrases:
        if phrase in q_norm:
            score -= 12

    return max(0.0, min(100.0, score))


# ============================================================
# QUESTION QUALITY
# ============================================================

def quality_score(question):
    q = clean_text(question)
    q_norm = normalize(q)

    if not q_norm:
        return 0.0

    score = 55.0

    words = q_norm.split()

    if 8 <= len(words) <= 35:
        score += 12

    if 36 <= len(words) <= 50:
        score += 5

    if len(words) < 6:
        score -= 15

    if len(words) > 60:
        score -= 10

    # Avoid vague/open wording
    vague = [
        "something",
        "anything",
        "in general",
        "as much as possible",
        "etc",
        "and so on"
    ]

    for item in vague:
        if item in q_norm:
            score -= 8

    # Penalize duplicated words
    counts = Counter(words)

    duplicates = [
        word for word, count in counts.items()
        if count >= 4 and len(word) > 3
    ]

    score -= len(duplicates) * 5

    # Good question structure
    if q.endswith("?"):
        score += 8

    # Multiple question marks are bad
    if q.count("?") > 1:
        score -= 10

    return max(0.0, min(100.0, score))


# ============================================================
# FIND BEST CLO / PLO
# ============================================================

def find_best_clo(question, clos):
    if not clos:
        return "", 0.0

    results = []

    for clo in clos:
        score = clo_alignment(question, clo)

        results.append(
            (clo, score)
        )

    results.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return results[0]


def find_best_plo(question, plos, course_name, course_content):
    if not plos:
        return "", 0.0

    results = []

    for plo in plos:
        score = plo_alignment(
            question,
            plo,
            course_name,
            course_content
        )

        results.append(
            (plo, score)
        )

    results.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return results[0]


# ============================================================
# COMPLETE QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    course_name,
    course_content,
    clos,
    plos,
    target_bloom
):

    question = finalize_question(question)

    best_clo, clo_score = find_best_clo(
        question,
        clos
    )

    best_plo, plo_score = find_best_plo(
        question,
        plos,
        course_name,
        course_content
    )

    subject = subject_score(
        question,
        course_name,
        course_content
    )

    bloom = bloom_alignment(
        question,
        target_bloom
    )

    specificity = specificity_score(
        question
    )

    quality = quality_score(
        question
    )

    # --------------------------------------------------------
    # QUESTION-SPECIFIC WEIGHTING
    # --------------------------------------------------------

    overall = (
        subject * 0.20
        + clo_score * 0.25
        + plo_score * 0.25
        + bloom * 0.15
        + specificity * 0.10
        + quality * 0.05
    )

    # --------------------------------------------------------
    # STRICT ATTAINMENT
    # --------------------------------------------------------

    clo_attained = clo_score >= 80
    plo_attained = plo_score >= 80
    bloom_attained = bloom >= 80
    subject_attained = subject >= 80

    alignment_attained = (
        overall >= 80
        and clo_attained
        and plo_attained
        and bloom_attained
        and subject_attained
    )

    return {
        "question": question,
        "overall_score": round(overall, 2),
        "subject_score": round(subject, 2),
        "clo_score": round(clo_score, 2),
        "plo_score": round(plo_score, 2),
        "bloom_score": round(bloom, 2),
        "specificity_score": round(specificity, 2),
        "quality_score": round(quality, 2),
        "detected_bloom": detect_bloom(question),
        "best_clo": best_clo,
        "best_plo": best_plo,
        "clo_attained": clo_attained,
        "plo_attained": plo_attained,
        "bloom_attained": bloom_attained,
        "subject_attained": subject_attained,
        "alignment_attained": alignment_attained
    }


# ============================================================
# FILE READING
# ============================================================

def read_pdf(file):
    try:
        import fitz

        doc = fitz.open(
            stream=file.read(),
            filetype="pdf"
        )

        pages = []

        for page in doc:
            text = page.get_text("text")

            if text:
                pages.append(text)

        return "\n".join(pages)

    except Exception as e:
        return f"PDF_READER_ERROR: {e}"


def read_docx(file):
    try:
        from docx import Document

        document = Document(
            io.BytesIO(file.read())
        )

        paragraphs = [
            p.text
            for p in document.paragraphs
            if p.text.strip()
        ]

        return "\n".join(paragraphs)

    except Exception as e:
        return f"DOCX_READER_ERROR: {e}"


def read_excel(file):
    try:
        data = pd.read_excel(
            io.BytesIO(file.read()),
            sheet_name=None
        )

        output = []

        for sheet_name, df in data.items():

            output.append(
                f"Sheet: {sheet_name}"
            )

            for _, row in df.iterrows():

                values = [
                    clean_text(v)
                    for v in row.tolist()
                    if pd.notna(v)
                ]

                if values:
                    output.append(
                        " | ".join(values)
                    )

        return "\n".join(output)

    except Exception as e:
        return f"EXCEL_READER_ERROR: {e}"


def read_csv(file):
    try:
        df = pd.read_csv(
            io.BytesIO(file.read())
        )

        output = []

        for _, row in df.iterrows():

            values = [
                clean_text(v)
                for v in row.tolist()
                if pd.notna(v)
            ]

            if values:
                output.append(
                    " | ".join(values)
                )

        return "\n".join(output)

    except Exception as e:
        return f"CSV_READER_ERROR: {e}"


def read_txt(file):
    try:
        return file.read().decode(
            "utf-8",
            errors="ignore"
        )

    except Exception:
        try:
            file.seek(0)
            return str(file.read())
        except Exception as e:
            return f"TXT_READER_ERROR: {e}"


def read_uploaded_file(file):
    name = file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(file)

    if name.endswith(".docx"):
        return read_docx(file)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return read_excel(file)

    if name.endswith(".csv"):
        return read_csv(file)

    if name.endswith(".txt"):
        return read_txt(file)

    return ""


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):
    text = clean_text(text)

    if not text:
        return []

    # First try line-based extraction
    raw_lines = [
        clean_text(x)
        for x in text.splitlines()
        if clean_text(x)
    ]

    questions = []

    for line in raw_lines:

        # Remove numbering
        candidate = re.sub(
            r"^\s*(?:Q(?:uestion)?\s*)?\d+\s*[\.\):\-]\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        candidate = clean_text(candidate)

        if len(candidate.split()) < 4:
            continue

        # Explicit question
        if "?" in candidate:
            parts = re.split(r"(?<=\?)\s+", candidate)

            for part in parts:
                part = finalize_question(part)

                if len(part.split()) >= 4:
                    questions.append(part)

        # Instruction/question style without ?
        elif re.match(
            r"^(define|describe|explain|identify|"
            r"analyze|analyse|evaluate|compare|contrast|"
            r"calculate|solve|apply|discuss|justify|"
            r"design|develop|construct|write|state|list|"
            r"demonstrate|differentiate|interpret|"
            r"assess|critique|classify)\b",
            candidate,
            flags=re.IGNORECASE
        ):
            questions.append(
                finalize_question(candidate)
            )

    # If line parsing produced nothing,
    # split text into sentence-like segments.
    if not questions:

        pieces = re.split(
            r"(?<=[?.])\s+",
            text
        )

        for piece in pieces:

            piece = clean_text(piece)

            if len(piece.split()) >= 5:

                questions.append(
                    finalize_question(piece)
                )

    # Remove duplicates while preserving order
    unique = []

    seen = set()

    for q in questions:

        key = normalize(q)

        if key not in seen:
            seen.add(key)
            unique.append(q)

    return unique


# ============================================================
# TOPIC EXTRACTION
# ============================================================

def choose_topic(
    question,
    course_name,
    course_content,
    clo
):
    """
    Selects meaningful concepts from CLO + course content
    that can be used in a direct assessment revision.
    """

    q_tokens = stemmed_tokens(question)

    content_words = [
        w for w in tokens(
            f"{course_name} {course_content} {clo}"
        )
        if w not in GENERIC_OUTCOME_WORDS
    ]

    counts = Counter(
        stem(w)
        for w in content_words
    )

    # Prefer concepts already appearing in the question
    question_topics = [
        w for w in q_tokens
        if w in counts
    ]

    if question_topics:
        ranked = sorted(
            question_topics,
            key=lambda x: counts[x],
            reverse=True
        )

        return " ".join(ranked[:5])

    ranked = [
        word for word, count in counts.most_common(10)
        if len(word) > 3
    ]

    return " ".join(ranked[:5])


# ============================================================
# OUTCOME CONCEPT EXTRACTION
# ============================================================

def extract_core_concepts(outcome):
    words = tokens(outcome)

    concepts = []

    for word in words:

        if word in GENERIC_OUTCOME_WORDS:
            continue

        if len(word) <= 3:
            continue

        concepts.append(word)

    # Preserve order and remove duplicates
    result = []

    for word in concepts:

        if word not in result:
            result.append(word)

    return result[:8]


# ============================================================
# REVISION CANDIDATES
# ============================================================

def generate_candidates(
    question,
    course_name,
    course_content,
    clo,
    plo,
    target_bloom
):

    topic = choose_topic(
        question,
        course_name,
        course_content,
        clo
    )

    concepts = extract_core_concepts(
        clo
    )

    if not concepts:
        concepts = extract_core_concepts(
            plo
        )

    if not concepts:
        concepts = tokens(
            f"{topic}"
        )[:5]

    concept_phrase = " ".join(
        concepts[:5]
    )

    # Keep the student's assessment wording direct.
    candidates = []

    if target_bloom == "Remember":

        candidates.extend([
            f"Identify and list the key {concept_phrase} relevant to {topic}",
            f"State the main {concept_phrase} associated with {topic}",
            f"Identify the essential {concept_phrase} in {topic}"
        ])

    elif target_bloom == "Understand":

        candidates.extend([
            f"Explain the key {concept_phrase} in {topic} and describe how they are related",
            f"Describe the main {concept_phrase} in {topic} and explain their significance",
            f"Explain {concept_phrase} in {topic} using a relevant example"
        ])

    elif target_bloom == "Apply":

        candidates.extend([
            f"Apply {concept_phrase} to solve a relevant problem involving {topic}",
            f"Use {concept_phrase} to solve the given problem related to {topic}",
            f"Demonstrate how {concept_phrase} can be applied to a specific problem in {topic}"
        ])

    elif target_bloom == "Analyze":

        candidates.extend([
            f"Analyze the relationship among {concept_phrase} in {topic} and explain the factors that produce the observed result",
            f"Analyze {concept_phrase} in {topic} by identifying their relationships and explaining their effects",
            f"Examine {concept_phrase} in {topic} and explain how the identified factors influence the outcome",
            f"Compare the relevant aspects of {concept_phrase} in {topic} and explain the differences in their effects"
        ])

    elif target_bloom == "Evaluate":

        candidates.extend([
            f"Evaluate {concept_phrase} in {topic} and justify which factor has the greatest effect",
            f"Assess {concept_phrase} in {topic} and justify your conclusion using relevant evidence",
            f"Critique the use of {concept_phrase} in {topic} and justify an appropriate conclusion",
            f"Evaluate the effectiveness of {concept_phrase} in addressing the given issue in {topic}"
        ])

    elif target_bloom == "Create":

        candidates.extend([
            f"Design a solution using {concept_phrase} to address a specific problem in {topic}",
            f"Develop a solution that integrates {concept_phrase} to address the given problem in {topic}",
            f"Construct a suitable approach using {concept_phrase} for a problem related to {topic}",
            f"Formulate a solution using {concept_phrase} and justify how it addresses the problem in {topic}"
        ])

    # Add concept-specific repair candidates
    if concepts:

        first = concepts[0]

        candidates.extend([
            f"{target_bloom} {first} in the context of {topic}",
            f"{target_bloom} the role of {first} in {topic}",
            f"{target_bloom} how {first} affects {topic}"
        ])

    return [
        finalize_question(c)
        for c in candidates
        if c
    ]


# ============================================================
# REVISION RANKING
# ============================================================

def revision_rank(result):
    """
    Prioritize CLO and PLO first.
    A revision with high overall score but weak CLO/PLO
    must not outrank an aligned revision.
    """

    return (
        result["clo_score"],
        result["plo_score"],
        result["overall_score"],
        result["bloom_score"],
        result["subject_score"],
        result["specificity_score"]
    )


def revision_attained(result):
    """
    STRICT RULE:
    CLO and PLO MUST BOTH be >= 80.
    """

    return (
        result["overall_score"] >= 80
        and result["clo_score"] >= 80
        and result["plo_score"] >= 80
        and result["bloom_score"] >= 80
        and result["subject_score"] >= 80
    )


# ============================================================
# REPAIR LOOP
# ============================================================

def repair_candidate(
    candidate,
    result,
    course_name,
    course_content,
    clo,
    plo,
    target_bloom
):

    topic = choose_topic(
        candidate,
        course_name,
        course_content,
        clo
    )

    concepts = extract_core_concepts(clo)

    if not concepts:
        concepts = extract_core_concepts(plo)

    concept_phrase = " ".join(
        concepts[:5]
    )

    # Targeted repair based on the weakest dimension
    if result["clo_score"] < 80:

        if target_bloom == "Analyze":
            return finalize_question(
                f"Analyze {concept_phrase} in {topic} by explaining the relationships among the relevant factors and their effects"
            )

        if target_bloom == "Evaluate":
            return finalize_question(
                f"Evaluate {concept_phrase} in {topic} and justify your conclusion using relevant evidence"
            )

        if target_bloom == "Create":
            return finalize_question(
                f"Develop a solution using {concept_phrase} to address a specific problem in {topic}"
            )

        if target_bloom == "Apply":
            return finalize_question(
                f"Apply {concept_phrase} to solve a specific problem related to {topic}"
            )

        return finalize_question(
            f"Explain {concept_phrase} in {topic} and describe their significance"
        )

    if result["plo_score"] < 80:

        return finalize_question(
            f"{target_bloom} {concept_phrase} by applying the relevant principles to the problem presented in {topic}"
        )

    if result["bloom_score"] < 80:

        return finalize_question(
            f"{target_bloom} {concept_phrase} in relation to {topic}"
        )

    if result["subject_score"] < 80:

        return finalize_question(
            f"{target_bloom} {concept_phrase} in the context of {course_name} and {topic}"
        )

    return finalize_question(
        f"{target_bloom} {concept_phrase} in {topic}"
    )


# ============================================================
# GENERATE BEST REVISION
# ============================================================

def create_revision(
    question,
    course_name,
    course_content,
    clos,
    plos,
    target_bloom
):

    best_clo, _ = find_best_clo(
        question,
        clos
    )

    best_plo, _ = find_best_plo(
        question,
        plos,
        course_name,
        course_content
    )

    candidates = generate_candidates(
        question,
        course_name,
        course_content,
        best_clo,
        best_plo,
        target_bloom
    )

    evaluated = []

    # --------------------------------------------------------
    # FIRST PASS
    # --------------------------------------------------------

    for candidate in candidates:

        result = evaluate_question(
            candidate,
            course_name,
            course_content,
            clos,
            plos,
            target_bloom
        )

        evaluated.append({
            "question": candidate,
            "result": result,
            "attained": revision_attained(result)
        })

    # --------------------------------------------------------
    # REPAIR WEAK CANDIDATES
    # --------------------------------------------------------

    first_pass = sorted(
        evaluated,
        key=lambda x: revision_rank(
            x["result"]
        ),
        reverse=True
    )

    repair_pool = first_pass[:5]

    for item in repair_pool:

        repaired = repair_candidate(
            item["question"],
            item["result"],
            course_name,
            course_content,
            best_clo,
            best_plo,
            target_bloom
        )

        result = evaluate_question(
            repaired,
            course_name,
            course_content,
            clos,
            plos,
            target_bloom
        )

        evaluated.append({
            "question": repaired,
            "result": result,
            "attained": revision_attained(result)
        })

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique = {}

    for item in evaluated:

        key = normalize(
            item["question"]
        )

        if key not in unique:

            unique[key] = item

        else:

            # Keep the better-scoring version
            old = unique[key]

            if revision_rank(
                item["result"]
            ) > revision_rank(
                old["result"]
            ):
                unique[key] = item

    evaluated = list(
        unique.values()
    )

    # --------------------------------------------------------
    # SORT SUCCESSFUL REVISIONS FIRST
    # --------------------------------------------------------

    evaluated.sort(
        key=lambda x: (
            x["attained"],
            revision_rank(x["result"])
        ),
        reverse=True
    )

    return evaluated


# ============================================================
# SESSION STATE
# ============================================================

if "evaluation_results" not in st.session_state:
    st.session_state.evaluation_results = []

if "revision_results" not in st.session_state:
    st.session_state.revision_results = {}

if "selected_revisions" not in st.session_state:
    st.session_state.selected_revisions = {}

if "uploaded_text" not in st.session_state:
    st.session_state.uploaded_text = ""


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Assessment Alignment Checker")

st.write(
    "Evaluate assessment questions against subject relevance, "
    "CLOs, PLOs and Bloom's Taxonomy, then generate and verify "
    "direct assessment revisions."
)

st.divider()


# ============================================================
# COURSE INFORMATION
# ============================================================

st.subheader("1. Course Information")

course_name = st.text_input(
    "Course / Subject Name",
    placeholder="e.g., Chemistry, English I, Database Systems"
)

course_content = st.text_area(
    "Course Content / Topics",
    placeholder=(
        "Enter the major topics, concepts or syllabus content "
        "for the course."
    ),
    height=140
)


# ============================================================
# CLO
# ============================================================

st.subheader("2. Course Learning Outcomes (CLOs)")

clo_text = st.text_area(
    "Enter CLOs — one per line",
    placeholder=(
        "CLO 1: Explain the fundamental concepts of the subject\n"
        "CLO 2: Analyze relevant problems using appropriate principles"
    ),
    height=150
)

clos = parse_outcomes(
    clo_text,
    "CLO"
)


# ============================================================
# PLO
# ============================================================

st.subheader("3. Program Learning Outcomes (PLOs)")

plo_text = st.text_area(
    "Enter PLOs — one per line",
    placeholder=(
        "PLO 1: Apply knowledge of the discipline\n"
        "PLO 2: Analyze complex problems"
    ),
    height=150
)

plos = parse_outcomes(
    plo_text,
    "PLO"
)


# ============================================================
# BLOOM
# ============================================================

st.subheader("4. Target Bloom's Level")

target_bloom = st.selectbox(
    "Select the expected Bloom's Taxonomy level",
    list(BLOOM_LEVELS.keys()),
    index=1
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.subheader("5. Assessment File")

uploaded_file = st.file_uploader(
    "Upload an assessment file",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "csv",
        "txt"
    ]
)

if uploaded_file:

    text = read_uploaded_file(
        uploaded_file
    )

    if text.startswith(
        (
            "PDF_READER_ERROR:",
            "DOCX_READER_ERROR:",
            "EXCEL_READER_ERROR:",
            "CSV_READER_ERROR:",
            "TXT_READER_ERROR:"
        )
    ):

        st.error(text)

    else:

        st.session_state.uploaded_text = text

        st.success(
            f"File loaded successfully: {uploaded_file.name}"
        )

        with st.expander(
            "Preview extracted assessment text"
        ):
            st.text(
                text[:10000]
            )


# ============================================================
# MANUAL QUESTION
# ============================================================

st.subheader("6. Manual Question")

manual_question = st.text_area(
    "Enter a question manually if you do not want to use a file",
    placeholder=(
        "Example: Analyze how temperature affects the rate "
        "of a chemical reaction"
    ),
    height=100
)


# ============================================================
# EVALUATE BUTTON
# ============================================================

if st.button(
    "🔍 Evaluate Assessment",
    type="primary",
    use_container_width=True
):

    if not course_name.strip():

        st.error(
            "Please enter the course / subject name."
        )

    elif not clos:

        st.error(
            "Please enter at least one CLO."
        )

    elif not plos:

        st.error(
            "Please enter at least one PLO."
        )

    else:

        questions = []

        # Manual question
        if manual_question.strip():

            questions.append(
                finalize_question(
                    manual_question
                )
            )

        # Uploaded file questions
        if st.session_state.uploaded_text:

            extracted = extract_questions(
                st.session_state.uploaded_text
            )

            questions.extend(
                extracted
            )

        # Remove duplicates
        unique_questions = []

        seen = set()

        for q in questions:

            key = normalize(q)

            if key not in seen:

                seen.add(key)

                unique_questions.append(q)

        if not unique_questions:

            st.warning(
                "No assessment questions could be detected. "
                "Enter a question manually or upload a readable assessment file."
            )

        else:

            results = []

            for index, question in enumerate(
                unique_questions,
                start=1
            ):

                result = evaluate_question(
                    question,
                    course_name,
                    course_content,
                    clos,
                    plos,
                    target_bloom
                )

                result["number"] = index

                results.append(
                    result
                )

            st.session_state.evaluation_results = results
            st.session_state.revision_results = {}
            st.session_state.selected_revisions = {}

            st.success(
                f"{len(results)} question(s) evaluated successfully."
            )


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.evaluation_results

if results:

    st.divider()

    st.header("📊 Assessment Evaluation")

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    summary_rows = []

    for result in results:

        summary_rows.append({
            "Question": result["number"],
            "Score": result["overall_score"],
            "CLO": result["clo_score"],
            "PLO": result["plo_score"],
            "Bloom": result["bloom_score"],
            "Subject": result["subject_score"],
            "Status": (
                "🟢 Attained"
                if result["alignment_attained"]
                else "🔴 Not Attained"
            )
        })

    summary_df = pd.DataFrame(
        summary_rows
    )

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # INDIVIDUAL QUESTIONS
    # --------------------------------------------------------

    for result in results:

        number = result["number"]

        status_text = (
            "🟢 ALIGNMENT ATTAINED"
            if result["alignment_attained"]
            else "🔴 ALIGNMENT NOT ATTAINED"
        )

        with st.expander(
            f"Question {number} — "
            f"{result['overall_score']:.1f}/100 — "
            f"{status_text}"
        ):

            st.markdown(
                f"**Question:** {result['question']}"
            )

            st.write(
                f"**Matched CLO:** {result['best_clo']}"
            )

            st.write(
                f"**Matched PLO:** {result['best_plo']}"
            )

            st.write(
                f"**Detected Bloom Level:** "
                f"{result['detected_bloom']}"
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Overall Score",
                    f"{result['overall_score']:.1f}/100"
                )

            with col2:
                st.metric(
                    "CLO",
                    f"{result['clo_score']:.1f}/100"
                )

            with col3:
                st.metric(
                    "PLO",
                    f"{result['plo_score']:.1f}/100"
                )

            col4, col5, col6 = st.columns(3)

            with col4:
                st.metric(
                    "Bloom",
                    f"{result['bloom_score']:.1f}/100"
                )

            with col5:
                st.metric(
                    "Subject",
                    f"{result['subject_score']:.1f}/100"
                )

            with col6:
                st.metric(
                    "Specificity",
                    f"{result['specificity_score']:.1f}/100"
                )

            st.write(
                f"**Question Quality:** "
                f"{result['quality_score']:.1f}/100"
            )

            st.divider()

            if result["alignment_attained"]:

                st.success(
                    "✓ Alignment Attained"
                )

            else:

                st.warning(
                    "Alignment not attained. "
                    "A revision is required."
                )

            # ------------------------------------------------
            # REVISION BUTTON
            # ------------------------------------------------

            button_key = (
                f"revision_{number}"
            )

            if st.button(
                "🛠 Generate Tool Suggestions",
                key=button_key
            ):

                revisions = create_revision(
                    result["question"],
                    course_name,
                    course_content,
                    clos,
                    plos,
                    target_bloom
                )

                st.session_state.revision_results[
                    number
                ] = revisions

                st.session_state.selected_revisions.pop(
                    number,
                    None
                )

            # ------------------------------------------------
            # REVISION SUGGESTIONS
            # ------------------------------------------------

            revisions = st.session_state.revision_results.get(
                number,
                []
            )

            if revisions:

                st.markdown(
                    "### 🛠 Tool Suggestions"
                )

                st.info(
                    "Each suggestion below has been evaluated "
                    "independently. CLO and PLO must both reach "
                    "80% or higher before the suggestion is "
                    "considered attained."
                )

                suggestion_labels = []

                for i, item in enumerate(
                    revisions
                ):

                    r = item["result"]

                    if item["attained"]:

                        label = (
                            f"Suggestion {i + 1} — "
                            f"🟢 Attained — "
                            f"{r['overall_score']:.1f}/100 | "
                            f"CLO {r['clo_score']:.1f} | "
                            f"PLO {r['plo_score']:.1f}"
                        )

                    else:

                        label = (
                            f"Suggestion {i + 1} — "
                            f"🔴 Not Attained — "
                            f"{r['overall_score']:.1f}/100 | "
                            f"CLO {r['clo_score']:.1f} | "
                            f"PLO {r['plo_score']:.1f}"
                        )

                    suggestion_labels.append(
                        label
                    )

                selected_index = st.radio(
                    "Select a revision suggestion",
                    range(len(revisions)),
                    format_func=lambda i:
                        suggestion_labels[i],
                    key=f"radio_{number}"
                )

                selected_item = revisions[
                    selected_index
                ]

                selected_result = selected_item[
                    "result"
                ]

                st.markdown(
                    "#### Selected Revision"
                )

                st.info(
                    selected_item["question"]
                )

                # --------------------------------------------
                # SELECTED REVISION METRICS
                # --------------------------------------------

                c1, c2, c3, c4 = st.columns(4)

                with c1:
                    st.metric(
                        "Revised Score",
                        f"{selected_result['overall_score']:.1f}/100"
                    )

                with c2:
                    st.metric(
                        "CLO",
                        f"{selected_result['clo_score']:.1f}/100"
                    )

                with c3:
                    st.metric(
                        "PLO",
                        f"{selected_result['plo_score']:.1f}/100"
                    )

                with c4:
                    st.metric(
                        "Bloom",
                        f"{selected_result['bloom_score']:.1f}/100"
                    )

                # --------------------------------------------
                # ATTAINMENT CHECK
                # --------------------------------------------

                if revision_attained(
                    selected_result
                ):

                    st.success(
                        f"✓ Alignment Attained — "
                        f"Revised Score: "
                        f"{selected_result['overall_score']:.1f}/100"
                    )

                    st.markdown(
                        f"""
**Alignment Status:** 🟢 **ATTAINED**

- **Overall Alignment:** {selected_result['overall_score']:.1f}/100
- **CLO Alignment:** {selected_result['clo_score']:.1f}/100 — **Attained**
- **PLO Alignment:** {selected_result['plo_score']:.1f}/100 — **Attained**
- **Bloom Alignment:** {selected_result['bloom_score']:.1f}/100 — **Attained**
- **Subject Relevance:** {selected_result['subject_score']:.1f}/100 — **Attained**
"""
                    )

                    if st.button(
                        "✅ Apply This Revision",
                        key=f"apply_{number}"
                    ):

                        st.session_state.selected_revisions[
                            number
                        ] = selected_item

                        st.success(
                            "Revision applied successfully. "
                            "The selected question has attained "
                            "CLO and PLO alignment."
                        )

                else:

                    st.error(
                        "🔴 Alignment Not Attained"
                    )

                    st.warning(
                        "This suggestion cannot be marked as attained "
                        "because one or more required dimensions are "
                        "below 80%. Select a suggestion marked "
                        "🟢 Attained."
                    )

                    # Show exactly why it failed
                    failed_items = []

                    if selected_result[
                        "overall_score"
                    ] < 80:
                        failed_items.append(
                            f"Overall: {selected_result['overall_score']:.1f}"
                        )

                    if selected_result[
                        "clo_score"
                    ] < 80:
                        failed_items.append(
                            f"CLO: {selected_result['clo_score']:.1f}"
                        )

                    if selected_result[
                        "plo_score"
                    ] < 80:
                        failed_items.append(
                            f"PLO: {selected_result['plo_score']:.1f}"
                        )

                    if selected_result[
                        "bloom_score"
                    ] < 80:
                        failed_items.append(
                            f"Bloom: {selected_result['bloom_score']:.1f}"
                        )

                    if selected_result[
                        "subject_score"
                    ] < 80:
                        failed_items.append(
                            f"Subject: {selected_result['subject_score']:.1f}"
                        )

                    if failed_items:

                        st.write(
                            "**Dimensions below the attainment "
                            "threshold:** "
                            + " | ".join(
                                failed_items
                            )
                        )

            # ------------------------------------------------
            # APPLIED REVISION
            # ------------------------------------------------

            applied = st.session_state.selected_revisions.get(
                number
            )

            if applied:

                st.divider()

                st.markdown(
                    "### ✅ Applied Revision"
                )

                st.success(
                    applied["question"]
                )

                applied_result = applied[
                    "result"
                ]

                st.success(
                    f"✓ Alignment Attained — "
                    f"Revised Score: "
                    f"{applied_result['overall_score']:.1f}/100"
                )

                cols = st.columns(5)

                metrics = [
                    (
                        "Overall",
                        applied_result["overall_score"]
                    ),
                    (
                        "CLO",
                        applied_result["clo_score"]
                    ),
                    (
                        "PLO",
                        applied_result["plo_score"]
                    ),
                    (
                        "Bloom",
                        applied_result["bloom_score"]
                    ),
                    (
                        "Subject",
                        applied_result["subject_score"]
                    )
                ]

                for col, (
                    label,
                    value
                ) in zip(
                    cols,
                    metrics
                ):

                    with col:

                        st.metric(
                            label,
                            f"{value:.1f}/100"
                        )


    # ========================================================
    # BEFORE / AFTER COMPARISON
    # ========================================================

    if st.session_state.selected_revisions:

        st.divider()

        st.header(
            "📈 Before vs After Revision"
        )

        comparison_rows = []

        for result in results:

            number = result["number"]

            if number not in st.session_state.selected_revisions:
                continue

            applied = st.session_state.selected_revisions[
                number
            ]

            after = applied["result"]

            comparison_rows.append({
                "Question": number,

                "Original Score":
                    result["overall_score"],

                "Revised Score":
                    after["overall_score"],

                "Original CLO":
                    result["clo_score"],

                "Revised CLO":
                    after["clo_score"],

                "Original PLO":
                    result["plo_score"],

                "Revised PLO":
                    after["plo_score"],

                "Original Bloom":
                    result["bloom_score"],

                "Revised Bloom":
                    after["bloom_score"],

                "Original Subject":
                    result["subject_score"],

                "Revised Subject":
                    after["subject_score"],

                "Final Status":
                    "🟢 Alignment Attained"
            })

        if comparison_rows:

            comparison_df = pd.DataFrame(
                comparison_rows
            )

            st.dataframe(
                comparison_df,
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# EXPORT
# ============================================================

if results:

    st.divider()

    st.header("📥 Export Results")

    export_rows = []

    for result in results:

        row = {
            "Question No":
                result["number"],

            "Original Question":
                result["question"],

            "Original Score":
                result["overall_score"],

            "Original CLO Score":
                result["clo_score"],

            "Original PLO Score":
                result["plo_score"],

            "Original Bloom Score":
                result["bloom_score"],

            "Original Subject Score":
                result["subject_score"],

            "Original Specificity":
                result["specificity_score"],

            "Original Quality":
                result["quality_score"],

            "Original Status":
                "Attained"
                if result["alignment_attained"]
                else "Not Attained"
        }

        applied = st.session_state.selected_revisions.get(
            result["number"]
        )

        if applied:

            revised = applied["result"]

            row.update({
                "Revised Question":
                    applied["question"],

                "Revised Score":
                    revised["overall_score"],

                "Revised CLO Score":
                    revised["clo_score"],

                "Revised PLO Score":
                    revised["plo_score"],

                "Revised Bloom Score":
                    revised["bloom_score"],

                "Revised Subject Score":
                    revised["subject_score"],

                "Revised Specificity":
                    revised["specificity_score"],

                "Revised Quality":
                    revised["quality_score"],

                "Final Status":
                    "Alignment Attained"
            })

        export_rows.append(
            row
        )

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Evaluation Results",
        data=csv_data,
        file_name="OBE_Assessment_Alignment_Results.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Assessment Alignment Checker | "
    "Scores are calculated separately for each question. "
    "CLO and PLO attainment require a score of 80 or above."
)
