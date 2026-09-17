import streamlit as st
import pandas as pd
import re
import io

# ============================================================
# PAGE CONFIG
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
        "define", "list", "name", "identify", "state",
        "recall", "recognize", "recognise", "mention",
        "label", "select", "match", "repeat"
    ],
    "Understand": [
        "explain", "summarize", "summarise", "interpret",
        "discuss", "classify", "describe", "outline",
        "paraphrase", "illustrate", "translate", "clarify"
    ],
    "Apply": [
        "apply", "use", "demonstrate", "solve",
        "calculate", "implement", "execute", "perform",
        "practice", "show", "compute"
    ],
    "Analyze": [
        "analyze", "analyse", "examine", "compare",
        "contrast", "differentiate", "distinguish",
        "investigate", "categorize", "categorise",
        "break down", "deconstruct", "inspect"
    ],
    "Evaluate": [
        "evaluate", "justify", "critique", "assess",
        "judge", "defend", "appraise", "recommend",
        "argue", "validate", "rate", "review"
    ],
    "Create": [
        "create", "design", "develop", "formulate",
        "produce", "compose", "plan", "propose",
        "generate", "construct", "invent"
    ]
}

BLOOM_ACTION = {
    "Remember": "Identify or state",
    "Understand": "Explain or describe",
    "Apply": "Apply or demonstrate",
    "Analyze": "Analyze, compare, or differentiate",
    "Evaluate": "Evaluate and justify",
    "Create": "Design, develop, or create"
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in",
    "on", "for", "with", "by", "is", "are", "was",
    "were", "be", "been", "being", "this", "that",
    "these", "those", "from", "as", "at", "it", "its",
    "into", "about", "which", "what", "how", "why",
    "when", "where", "who", "whom", "can", "could",
    "should", "would", "will", "may", "might", "do",
    "does", "did"
}

# ============================================================
# TEXT FUNCTIONS
# ============================================================

def normalize_text(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text):
    text = normalize_text(text)

    return {
        word
        for word in text.split()
        if word not in STOP_WORDS and len(word) > 2
    }


def expanded_concepts(text):

    words = tokenize(text)
    concepts = set(words)

    concept_groups = {
        "main idea": {
            "main", "idea", "central", "point",
            "theme", "message", "purpose"
        },
        "reading": {
            "read", "reading", "comprehension",
            "understand", "understanding", "passage",
            "text"
        },
        "organization": {
            "organization", "organisation", "pattern",
            "structure", "sequence", "cause", "effect",
            "compare", "contrast", "problem", "solution"
        },
        "paraphrasing": {
            "paraphrase", "paraphrasing", "rewrite",
            "restatement", "restating"
        },
        "author purpose": {
            "author", "purpose", "intent", "intention",
            "inform", "persuade", "entertain"
        },
        "tone": {
            "tone", "attitude", "feeling", "mood"
        },
        "writing": {
            "write", "writing", "essay", "paragraph",
            "sentence", "composition"
        },
        "critical thinking": {
            "critical", "thinking", "reason", "reasoning",
            "evidence", "argument", "claim"
        },
        "communication": {
            "communication", "communicate", "language",
            "speaking", "listening", "presentation"
        },
        "grammar": {
            "grammar", "grammatical", "verb", "noun",
            "sentence", "syntax"
        },
        "vocabulary": {
            "vocabulary", "word", "meaning", "definition",
            "lexical"
        },
        "research": {
            "research", "source", "citation", "reference",
            "evidence", "data"
        },
        "analysis": {
            "analyze", "analyse", "analysis", "examine",
            "evaluate", "critique", "compare"
        }
    }

    for group in concept_groups.values():

        if words.intersection(group):
            concepts.update(group)

    return concepts


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    q = normalize_text(question)

    scores = {
        level: 0
        for level in BLOOM_LEVELS
    }

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                q
            ):
                scores[level] += 1

    if "why" in q:
        scores["Analyze"] += 1

    if "how" in q:
        scores["Understand"] += 1

    if "compare and contrast" in q:
        scores["Analyze"] += 3

    if "justify" in q:
        scores["Evaluate"] += 3

    if "design" in q:
        scores["Create"] += 3

    if "create" in q:
        scores["Create"] += 3

    best_level = max(
        scores,
        key=scores.get
    )

    if scores[best_level] == 0:
        return "Needs Review"

    return best_level


def bloom_alignment(intended, detected):

    if detected == "Needs Review":
        return 40

    distance = abs(
        BLOOM_RANK[intended]
        - BLOOM_RANK[detected]
    )

    if distance == 0:
        return 100

    if distance == 1:
        return 65

    if distance == 2:
        return 45

    return 25


# ============================================================
# CLO / PLO SIMILARITY
# ============================================================

def outcome_similarity(question, outcome):

    q_words = expanded_concepts(question)
    o_words = expanded_concepts(outcome)

    if not q_words or not o_words:
        return 0, []

    intersection = q_words.intersection(o_words)

    dice = (
        2 * len(intersection)
        / (len(q_words) + len(o_words))
    )

    score = dice * 100

    q_norm = normalize_text(question)
    o_norm = normalize_text(outcome)

    # Exact outcome phrase
    if o_norm in q_norm:
        score += 25

    # Important words
    for word in tokenize(outcome):

        if word in q_norm.split():
            score += 2

    score = min(score, 100)

    evidence = sorted(
        list(intersection)
    )[:10]

    return score, evidence


# ============================================================
# FILE READING
# ============================================================

def extract_text_from_upload(uploaded_file):

    filename = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    # TXT
    if filename.endswith(".txt"):

        return data.decode(
            "utf-8",
            errors="ignore"
        )

    # DOCX
    if filename.endswith(".docx"):

        try:

            from docx import Document

            document = Document(
                io.BytesIO(data)
            )

            return "\n".join(
                p.text
                for p in document.paragraphs
                if p.text.strip()
            )

        except Exception as e:

            raise Exception(
                f"Could not read DOCX file: {e}"
            )

    # PDF
    if filename.endswith(".pdf"):

        try:

            from pypdf import PdfReader

            reader = PdfReader(
                io.BytesIO(data)
            )

            pages = []

            for page in reader.pages:

                text = page.extract_text()

                if text:
                    pages.append(text)

            extracted = "\n".join(pages)

            if extracted.strip():
                return extracted

        except Exception:
            pass

        # OCR fallback
        try:

            from pdf2image import convert_from_bytes
            import pytesseract

            images = convert_from_bytes(data)

            pages = []

            for image in images:

                text = pytesseract.image_to_string(
                    image
                )

                if text.strip():
                    pages.append(text)

            extracted = "\n".join(pages)

            if extracted.strip():
                return extracted

        except Exception as e:

            raise Exception(
                "Could not read PDF. "
                "Please make sure pypdf is included "
                "in requirements.txt. "
                f"Details: {e}"
            )

        raise Exception(
            "The PDF contains no readable text."
        )

    # Excel
    if filename.endswith(".xlsx") or filename.endswith(".xls"):

        try:

            excel_file = pd.ExcelFile(
                io.BytesIO(data)
            )

            all_text = []

            for sheet in excel_file.sheet_names:

                df = pd.read_excel(
                    excel_file,
                    sheet_name=sheet,
                    header=None
                )

                for row in df.values:

                    row_text = " ".join(
                        str(x)
                        for x in row
                        if pd.notna(x)
                    )

                    if row_text.strip():
                        all_text.append(row_text)

            return "\n".join(all_text)

        except Exception as e:

            raise Exception(
                f"Could not read Excel file: {e}"
            )

    raise Exception(
        "Unsupported file type."
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    questions = []

    pattern = re.compile(
        r"^(?:q(?:uestion)?\s*)?"
        r"(\d+)\s*[\.\)\:\-]\s*(.+)$",
        re.IGNORECASE
    )

    current_question = None
    current_number = None

    for line in lines:

        match = pattern.match(line)

        if match:

            if current_question:

                questions.append(
                    (
                        current_number,
                        current_question.strip()
                    )
                )

            current_number = int(
                match.group(1)
            )

            current_question = match.group(2)

        else:

            if current_question:

                current_question += (
                    " " + line
                )

    if current_question:

        questions.append(
            (
                current_number,
                current_question.strip()
            )
        )

    # Question mark fallback
    if len(questions) == 0:

        for line in lines:

            if "?" in line:

                questions.append(
                    (
                        len(questions) + 1,
                        line.strip()
                    )
                )

    # Paragraph fallback
    if len(questions) == 0:

        for line in lines:

            if len(line.split()) >= 5:

                questions.append(
                    (
                        len(questions) + 1,
                        line
                    )
                )

    return questions


# ============================================================
# GENERATE 100% TARGET QUESTION
# ============================================================

def generate_target_question(
    clo_code,
    clo_text,
    plo_code,
    plo_text,
    bloom
):

    action = BLOOM_ACTION[bloom]

    if bloom == "Remember":

        question = (
            f"{action} the key concept or knowledge "
            f"described in {clo_code}: {clo_text}. "
            f"In your answer, demonstrate the knowledge "
            f"relevant to {plo_code}: {plo_text}."
        )

    elif bloom == "Understand":

        question = (
            f"{action} the concept described in "
            f"{clo_code}: {clo_text}. "
            f"Explain your answer using the knowledge "
            f"required by {plo_code}: {plo_text}."
        )

    elif bloom == "Apply":

        question = (
            f"{action} the knowledge or skill described "
            f"in {clo_code}: {clo_text} to the given "
            f"situation. Show how your response demonstrates "
            f"{plo_code}: {plo_text}."
        )

    elif bloom == "Analyze":

        question = (
            f"{action} the issue, text, or situation in "
            f"relation to {clo_code}: {clo_text}. "
            f"Use evidence to explain your analysis and "
            f"demonstrate {plo_code}: {plo_text}."
        )

    elif bloom == "Evaluate":

        question = (
            f"{action} the issue, text, or solution described "
            f"in {clo_code}: {clo_text}. "
            f"Support your judgment with evidence and "
            f"demonstrate {plo_code}: {plo_text}."
        )

    else:

        question = (
            f"{action} a response, solution, product, or "
            f"argument that directly addresses {clo_code}: "
            f"{clo_text}. Your work should demonstrate "
            f"{plo_code}: {plo_text}."
        )

    return question


# ============================================================
# ANALYZE QUESTIONS
# ============================================================

def analyze_questions(
    questions,
    clos,
    plos,
    intended_bloom
):

    rows = []

    for number, question in questions:

        # CLO
        clo_scores = []

        for clo in clos:

            score, evidence = outcome_similarity(
                question,
                clo["text"]
            )

            clo_scores.append(
                {
                    "code": clo["code"],
                    "score": score,
                    "evidence": evidence
                }
            )

        best_clo = max(
            clo_scores,
            key=lambda x: x["score"]
        )

        # PLO
        plo_scores = []

        for plo in plos:

            score, evidence = outcome_similarity(
                question,
                plo["text"]
            )

            plo_scores.append(
                {
                    "code": plo["code"],
                    "score": score,
                    "evidence": evidence
                }
            )

        best_plo = max(
            plo_scores,
            key=lambda x: x["score"]
        )

        # Bloom
        detected_bloom = detect_bloom(
            question
        )

        bloom_score = bloom_alignment(
            intended_bloom,
            detected_bloom
        )

        combined = (
            best_clo["score"] * 0.35
            + best_plo["score"] * 0.25
            + bloom_score * 0.40
        )

        # Generate target question
        target_question = generate_target_question(
            best_clo["code"],
            next(
                c["text"]
                for c in clos
                if c["code"] == best_clo["code"]
            ),
            best_plo["code"],
            next(
                p["text"]
                for p in plos
                if p["code"] == best_plo["code"]
            ),
            intended_bloom
        )

        # Suggestions
        suggestions = []

        if (
            best_clo["score"] < 100
            or best_plo["score"] < 100
            or bloom_score < 100
        ):

            suggestions.append(
                f"Revise Q{number} to directly assess "
                f"{best_clo['code']}, demonstrate "
                f"{best_plo['code']}, and target the "
                f"{intended_bloom} level."
            )

            suggestions.append(
                f"Suggested question: {target_question}"
            )

            suggestions.append(
                "Target alignment after revision: "
                "CLO 100% | PLO 100% | Bloom 100% | "
                "Overall 100%"
            )

        else:

            suggestions.append(
                "Already strongly aligned. "
                "No major revision required."
            )

            suggestions.append(
                "Target alignment: 100%"
            )

        suggestion_text = " ".join(
            suggestions
        )

        rows.append(
            {
                "Question No.": number,
                "Question": question,
                "Best CLO": best_clo["code"],
                "CLO Alignment %": round(
                    best_clo["score"],
                    1
                ),
                "Best PLO": best_plo["code"],
                "PLO Alignment %": round(
                    best_plo["score"],
                    1
                ),
                "Intended Bloom": intended_bloom,
                "Detected Bloom": detected_bloom,
                "Bloom Alignment %": bloom_score,
                "Combined Alignment %": round(
                    combined,
                    1
                ),
                "Suggestions": suggestion_text,
                "Suggested Question": target_question,
                "Target CLO %": 100,
                "Target PLO %": 100,
                "Target Bloom %": 100,
                "Target Overall %": 100
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# TITLE
# ============================================================

st.title(
    "🎓 OBE Quiz Alignment Checker"
)

st.write(
    "Enter the course outcomes, program outcomes, "
    "and intended Bloom's level. Upload a quiz and "
    "the tool will analyze every question and suggest "
    "revisions designed for 100% alignment."
)

st.info(
    "The suggested questions are **100%-target questions**. "
    "They are designed to explicitly address the selected "
    "CLO, PLO, and intended Bloom level."
)

# ============================================================
# ASSESSMENT INFORMATION
# ============================================================

st.header(
    "1️⃣ Assessment Information"
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
# CLOs
# ============================================================

st.header(
    "2️⃣ Enter CLOs"
)

num_clos = st.number_input(
    "Number of CLOs",
    min_value=1,
    max_value=20,
    value=3,
    step=1
)

clos = []

for i in range(int(num_clos)):

    col1, col2 = st.columns(
        [1, 4]
    )

    with col1:

        code = st.text_input(
            f"CLO {i + 1} Code",
            value=f"CLO{i + 1}",
            key=f"clo_code_{i}"
        )

    with col2:

        description = st.text_input(
            f"CLO {i + 1} Description",
            key=f"clo_description_{i}",
            placeholder="Enter the complete CLO statement"
        )

    if description.strip():

        clos.append(
            {
                "code": code.strip(),
                "text": description.strip()
            }
        )

# ============================================================
# PLOs
# ============================================================

st.header(
    "3️⃣ Enter PLOs"
)

num_plos = st.number_input(
    "Number of PLOs",
    min_value=1,
    max_value=20,
    value=3,
    step=1
)

plos = []

for i in range(int(num_plos)):

    col1, col2 = st.columns(
        [1, 4]
    )

    with col1:

        code = st.text_input(
            f"PLO {i + 1} Code",
            value=f"PLO{i + 1}",
            key=f"plo_code_{i}"
        )

    with col2:

        description = st.text_input(
            f"PLO {i + 1} Description",
            key=f"plo_description_{i}",
            placeholder="Enter the complete PLO statement"
        )

    if description.strip():

        plos.append(
            {
                "code": code.strip(),
                "text": description.strip()
            }
        )

# ============================================================
# BLOOM
# ============================================================

st.header(
    "4️⃣ Intended Bloom's Level"
)

intended_bloom = st.selectbox(
    "Select the intended cognitive level",
    BLOOM_LEVELS
)

st.write(
    f"**Selected Bloom level:** {intended_bloom}"
)

# ============================================================
# UPLOAD
# ============================================================

st.header(
    "5️⃣ Upload Quiz"
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

st.divider()

analyze_button = st.button(
    "🔍 Analyze Quiz",
    type="primary",
    use_container_width=True
)

# ============================================================
# MAIN ANALYSIS
# ============================================================

if analyze_button:

    if not course_name.strip():

        st.error(
            "Please enter the course name."
        )
        st.stop()

    if not assessment_name.strip():

        st.error(
            "Please enter the assessment name."
        )
        st.stop()

    if len(clos) == 0:

        st.error(
            "Please enter at least one CLO."
        )
        st.stop()

    if len(plos) == 0:

        st.error(
            "Please enter at least one PLO."
        )
        st.stop()

    if uploaded_file is None:

        st.error(
            "Please upload a quiz."
        )
        st.stop()

    # --------------------------------------------------------
    # READ FILE
    # --------------------------------------------------------

    try:

        with st.spinner(
            "Reading quiz..."
        ):

            extracted_text = (
                extract_text_from_upload(
                    uploaded_file
                )
            )

    except Exception as e:

        st.error(
            str(e)
        )
        st.stop()

    if not extracted_text.strip():

        st.error(
            "No readable text was found."
        )
        st.stop()

    # --------------------------------------------------------
    # QUESTIONS
    # --------------------------------------------------------

    questions = extract_questions(
        extracted_text
    )

    if len(questions) == 0:

        st.error(
            "No questions were detected. "
            "Use numbered questions such as "
            "1., 2., 3. or questions ending with ?."
        )
        st.stop()

    # --------------------------------------------------------
    # ANALYSIS
    # --------------------------------------------------------

    results_df = analyze_questions(
        questions,
        clos,
        plos,
        intended_bloom
    )

    # ========================================================
    # RESULTS
    # ========================================================

    st.divider()

    st.header(
        "📊 Quiz Alignment Results"
    )

    avg_clo = results_df[
        "CLO Alignment %"
    ].mean()

    avg_plo = results_df[
        "PLO Alignment %"
    ].mean()

    avg_bloom = results_df[
        "Bloom Alignment %"
    ].mean()

    overall = (
        avg_clo * 0.35
        + avg_plo * 0.25
        + avg_bloom * 0.40
    )

    # ========================================================
    # METRICS
    # ========================================================

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Overall Alignment",
            f"{overall:.1f}%"
        )

    with c2:

        st.metric(
            "CLO Alignment",
            f"{avg_clo:.1f}%"
        )

    with c3:

        st.metric(
            "PLO Alignment",
            f"{avg_plo:.1f}%"
        )

    with c4:

        st.metric(
            "Bloom Alignment",
            f"{avg_bloom:.1f}%"
        )

    st.info(
        "Current scores measure the alignment of the uploaded "
        "quiz. The suggested questions are designed to target "
        "**100% CLO + 100% PLO + 100% Bloom alignment**."
    )

    # ========================================================
    # OVERALL GRAPH
    # ========================================================

    st.subheader(
        "📈 Overall Alignment"
    )

    overall_chart = pd.DataFrame(
        {
            "Area": [
                "CLO",
                "PLO",
                "Bloom",
                "Overall"
            ],
            "Percentage": [
                avg_clo,
                avg_plo,
                avg_bloom,
                overall
            ]
        }
    )

    st.bar_chart(
        overall_chart.set_index(
            "Area"
        ),
        use_container_width=True
    )

    # ========================================================
    # CLO BY CLO
    # ========================================================

    st.divider()

    st.header(
        "🎯 CLO-by-CLO Analysis"
    )

    selected_clo_code = st.selectbox(
        "Select one CLO",
        [
            c["code"]
            for c in clos
        ],
        key="selected_clo"
    )

    selected_clo = next(
        c
        for c in clos
        if c["code"] == selected_clo_code
    )

    clo_questions = results_df[
        results_df["Best CLO"]
        == selected_clo_code
    ].copy()

    if len(clo_questions) > 0:

        clo_alignment = clo_questions[
            "CLO Alignment %"
        ].mean()

        coverage = (
            len(clo_questions)
            / len(results_df)
        ) * 100

    else:

        clo_alignment = 0
        coverage = 0

    st.info(
        f"**{selected_clo_code}:** "
        f"{selected_clo['text']}"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Current CLO Alignment",
            f"{clo_alignment:.1f}%"
        )

    with c2:

        st.metric(
            "Questions",
            len(clo_questions)
        )

    with c3:

        st.metric(
            "Coverage",
            f"{coverage:.1f}%"
        )

    # --------------------------------------------------------
    # CLO GRAPH
    # --------------------------------------------------------

    st.subheader(
        "📊 Selected CLO Graph"
    )

    if len(clo_questions) > 0:

        graph = clo_questions[
            [
                "Question No.",
                "CLO Alignment %"
            ]
        ].copy()

        graph["Question"] = (
            "Q"
            + graph[
                "Question No."
            ].astype(str)
        )

        graph = graph[
            [
                "Question",
                "CLO Alignment %"
            ]
        ].set_index(
            "Question"
        )

        st.bar_chart(
            graph,
            use_container_width=True
        )

    else:

        st.warning(
            "No question is currently mapped to this CLO."
        )

    # --------------------------------------------------------
    # SELECTED CLO QUESTIONS
    # --------------------------------------------------------

    st.subheader(
        f"📝 Questions for {selected_clo_code}"
    )

    if len(clo_questions) > 0:

        st.dataframe(
            clo_questions[
                [
                    "Question No.",
                    "Question",
                    "CLO Alignment %",
                    "Best PLO",
                    "PLO Alignment %",
                    "Intended Bloom",
                    "Detected Bloom",
                    "Bloom Alignment %"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    # --------------------------------------------------------
    # CLO SUGGESTED QUESTIONS
    # --------------------------------------------------------

    st.subheader(
        "💡 Suggested Questions — Target 100%"
    )

    if len(clo_questions) > 0:

        for _, row in clo_questions.iterrows():

            st.markdown(
                f"### Q{int(row['Question No.'])}"
            )

            st.write(
                f"**Current question:** "
                f"{row['Question']}"
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:

                st.metric(
                    "Current CLO",
                    f"{row['CLO Alignment %']:.1f}%"
                )

            with c2:

                st.metric(
                    "Current PLO",
                    f"{row['PLO Alignment %']:.1f}%"
                )

            with c3:

                st.metric(
                    "Current Bloom",
                    f"{row['Bloom Alignment %']:.1f}%"
                )

            with c4:

                st.metric(
                    "Target",
                    "100%"
                )

            st.info(
                f"**Suggested Question:** "
                f"{row['Suggested Question']}"
            )

            st.success(
                "🎯 Target after revision: "
                "**CLO 100% | PLO 100% | Bloom 100% | "
                "Overall 100%**"
            )

            st.divider()

    else:

        # Generate one question for uncovered CLO
        selected_plo = plos[0]

        suggestion = generate_target_question(
            selected_clo["code"],
            selected_clo["text"],
            selected_plo["code"],
            selected_plo["text"],
            intended_bloom
        )

        st.info(
            f"**Suggested question for "
            f"{selected_clo_code}:**\n\n"
            f"{suggestion}"
        )

        st.success(
            "🎯 Target: "
            "CLO 100% | PLO 100% | Bloom 100% | "
            "Overall 100%"
        )

    # ========================================================
    # COMPLETE QUESTION ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "📝 Complete Question Analysis"
    )

    # Important:
    # Suggestions are kept in ONE column.

    complete_table = results_df[
        [
            "Question No.",
            "Question",
            "Best CLO",
            "CLO Alignment %",
            "Best PLO",
            "PLO Alignment %",
            "Intended Bloom",
            "Detected Bloom",
            "Bloom Alignment %",
            "Combined Alignment %",
            "Suggestions"
        ]
    ].copy()

    st.dataframe(
        complete_table,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # 100% TARGET SUMMARY
    # ========================================================

    st.divider()

    st.header(
        "🎯 100% Alignment Target"
    )

    st.write(
        "The tool uses the participant's entered CLO, PLO, "
        "and intended Bloom level to design a revised question "
        "that explicitly targets all three requirements."
    )

    target_table = pd.DataFrame(
        {
            "Alignment Area": [
                "CLO",
                "PLO",
                "Bloom",
                "Overall"
            ],
            "Target": [
                "100%",
                "100%",
                "100%",
                "100%"
            ]
        }
    )

    st.dataframe(
        target_table,
        use_container_width=True,
        hide_index=True
    )

    st.success(
        "The suggested question is a 100%-alignment target. "
        "The tool explicitly incorporates the selected CLO, "
        "PLO, and Bloom cognitive demand into the suggested "
        "question."
    )

    # ========================================================
    # BLOOM ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "🧠 Bloom's Taxonomy Analysis"
    )

    bloom_counts = (
        results_df[
            "Detected Bloom"
        ]
        .value_counts()
        .reindex(
            BLOOM_LEVELS,
            fill_value=0
        )
    )

    st.bar_chart(
        bloom_counts,
        use_container_width=True
    )

    bloom_table = pd.DataFrame(
        {
            "Bloom Level": bloom_counts.index,
            "Questions": bloom_counts.values
        }
    )

    st.dataframe(
        bloom_table,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # WEAK QUESTIONS
    # ========================================================

    st.divider()

    st.header(
        "🔎 Questions Requiring Revision"
    )

    weak_questions = results_df[
        results_df[
            "Combined Alignment %"
        ] < 70
    ].copy()

    if len(weak_questions) > 0:

        st.warning(
            f"{len(weak_questions)} question(s) "
            "have alignment below 70%."
        )

        for _, row in weak_questions.iterrows():

            with st.expander(
                f"Q{int(row['Question No.'])} "
                f"— Current Score: "
                f"{row['Combined Alignment %']:.1f}%"
            ):

                st.write(
                    f"**Current Question:** "
                    f"{row['Question']}"
                )

                st.write(
                    f"**CLO:** {row['Best CLO']} "
                    f"({row['CLO Alignment %']:.1f}%)"
                )

                st.write(
                    f"**PLO:** {row['Best PLO']} "
                    f"({row['PLO Alignment %']:.1f}%)"
                )

                st.write(
                    f"**Intended Bloom:** "
                    f"{row['Intended Bloom']}"
                )

                st.write(
                    f"**Detected Bloom:** "
                    f"{row['Detected Bloom']}"
                )

                st.write(
                    f"**Bloom Alignment:** "
                    f"{row['Bloom Alignment %']:.1f}%"
                )

                st.subheader(
                    "Suggested 100% Target Question"
                )

                st.info(
                    row["Suggested Question"]
                )

                st.success(
                    "Target: CLO 100% | PLO 100% | "
                    "Bloom 100% | Overall 100%"
                )

    else:

        st.success(
            "All questions currently have an alignment "
            "score of 70% or higher."
        )

    # ========================================================
    # DOWNLOAD
    # ========================================================

    st.divider()

    st.header(
        "📥 Download Results"
    )

    csv_data = results_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Complete Analysis",
        data=csv_data,
        file_name=(
            "OBE_Quiz_Alignment_Analysis.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )

    # ========================================================
    # FINAL
    # ========================================================

    st.divider()

    st.header(
        "✅ Analysis Complete"
    )

    st.write(
        f"**Course:** {course_name}"
    )

    st.write(
        f"**Assessment:** {assessment_name}"
    )

    st.write(
        f"**Questions analyzed:** {len(results_df)}"
    )

    st.write(
        f"**Intended Bloom:** {intended_bloom}"
    )

    st.write(
        f"**Current overall alignment:** "
        f"{overall:.1f}%"
    )

    st.info(
        "Use the suggested questions as revised assessment "
        "items. They are constructed to explicitly target "
        "100% alignment with the selected CLO, PLO, and "
        "Bloom level."
    )
