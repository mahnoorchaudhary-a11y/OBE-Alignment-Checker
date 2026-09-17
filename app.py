import streamlit as st
import pandas as pd
import sqlite3
import re
import io
from collections import Counter

# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎓",
    layout="wide"
)

DB_FILE = "obe_tracker.db"

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
        "recall", "recognize", "mention", "label", "select"
    ],
    "Understand": [
        "explain", "summarize", "interpret", "discuss",
        "classify", "describe", "outline", "paraphrase",
        "illustrate"
    ],
    "Apply": [
        "apply", "use", "demonstrate", "solve", "calculate",
        "implement", "execute", "perform"
    ],
    "Analyze": [
        "analyze", "analyse", "examine", "compare",
        "contrast", "differentiate", "distinguish",
        "investigate", "categorize", "break down"
    ],
    "Evaluate": [
        "evaluate", "justify", "critique", "assess",
        "judge", "defend", "appraise", "recommend",
        "argue", "validate"
    ],
    "Create": [
        "create", "design", "develop", "formulate",
        "produce", "compose", "plan", "propose",
        "generate", "construct"
    ]
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in",
    "on", "for", "with", "by", "from", "at", "as",
    "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its",
    "their", "they", "them", "you", "your", "we",
    "our", "which", "what", "how", "why", "when",
    "where", "who", "can", "could", "should", "would",
    "will", "may", "might", "do", "does", "did",
    "into", "than", "then", "also", "given"
}

# ============================================================
# DATABASE
# ============================================================

def get_conn():
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


conn = get_conn()


def execute(query, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    return cur


def fetchone(query, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchone()


def fetchall(query, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()


def init_db():

    execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT NOT NULL,
            semester TEXT,
            section TEXT
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS clos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            code TEXT,
            description TEXT,
            target REAL DEFAULT 60
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS plos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            code TEXT,
            description TEXT,
            target REAL DEFAULT 60
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            clo_id INTEGER,
            plo_id INTEGER,
            weight REAL DEFAULT 1
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            name TEXT,
            total_marks REAL,
            intended_bloom TEXT
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER,
            question_no TEXT,
            question_text TEXT,
            max_marks REAL,
            clo_id INTEGER,
            plo_id INTEGER,
            intended_bloom TEXT,
            detected_bloom TEXT,
            bloom_score REAL,
            clo_score REAL,
            plo_score REAL
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            student_id TEXT,
            student_name TEXT
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            question_id INTEGER,
            marks REAL
        )
    """)


init_db()

# ============================================================
# TEXT PROCESSING
# ============================================================

def clean_text(text):
    text = str(text or "")
    text = text.replace("\x00", " ")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def words(text):
    text = clean_text(text).lower()
    return [
        w for w in re.findall(r"[a-zA-Z]{3,}", text)
        if w not in STOPWORDS
    ]


def normalize_word(word):

    word = word.lower().strip()

    replacements = {
        "analyzing": "analyze",
        "analysing": "analyze",
        "analyzed": "analyze",
        "analysed": "analyze",
        "analyses": "analyze",
        "explaining": "explain",
        "explained": "explain",
        "applying": "apply",
        "applied": "apply",
        "evaluating": "evaluate",
        "evaluated": "evaluate",
        "creating": "create",
        "created": "create",
        "developing": "develop",
        "developed": "develop",
        "comparing": "compare",
        "compared": "compare",
        "identifying": "identify",
        "identified": "identify"
    }

    if word in replacements:
        return replacements[word]

    if word.endswith("ing") and len(word) > 5:
        word = word[:-3]

    if word.endswith("ed") and len(word) > 5:
        word = word[:-2]

    return word


def normalized_words(text):

    return [
        normalize_word(w)
        for w in words(text)
    ]


# ============================================================
# CONCEPT EXPANSION
# ============================================================

CONCEPT_GROUPS = {

    "analyze": {
        "analyze", "analyse", "examine", "investigate",
        "differentiate", "distinguish", "compare",
        "contrast", "interpret", "break", "structure",
        "relationship", "pattern", "cause", "effect"
    },

    "evaluate": {
        "evaluate", "assess", "judge", "critique",
        "justify", "defend", "appraise", "recommend",
        "evidence", "validity", "argument", "opinion"
    },

    "communication": {
        "communication", "communicate", "write", "writing",
        "speak", "speaking", "present", "presentation",
        "explain", "express", "language", "audience",
        "message", "argument", "discussion"
    },

    "critical_thinking": {
        "critical", "thinking", "analyze", "analyse",
        "evaluate", "evidence", "reason", "reasoning",
        "argument", "infer", "inference", "compare",
        "distinguish", "justify", "critique"
    },

    "problem_solving": {
        "problem", "solve", "solution", "apply",
        "calculate", "design", "develop", "strategy",
        "method", "decision", "implement", "formulate"
    },

    "reading": {
        "read", "reading", "text", "passage", "main",
        "idea", "purpose", "tone", "pattern",
        "organization", "author", "meaning",
        "comprehension", "interpret"
    },

    "writing": {
        "write", "writing", "essay", "paragraph",
        "compose", "draft", "revise", "organize",
        "argument", "thesis", "sentence", "academic"
    }
}


def expanded_concepts(text):

    result = set(
        normalized_words(text)
    )

    for group, terms in CONCEPT_GROUPS.items():

        if result.intersection(
            {normalize_word(x) for x in terms}
        ):

            result.update(
                normalize_word(x)
                for x in terms
            )

    return result


# ============================================================
# OUTCOME MATCHING
# ============================================================

def outcome_similarity(question, outcome):

    q = expanded_concepts(question)
    o = expanded_concepts(outcome)

    if not q or not o:
        return 0.0, []

    overlap = q.intersection(o)

    if not overlap:
        return 0.0, []

    # Dice-style score
    score = (
        2 * len(overlap)
        /
        (len(q) + len(o))
    ) * 100

    # Give additional weight to direct wording
    direct_q = set(normalized_words(question))
    direct_o = set(normalized_words(outcome))

    direct_overlap = direct_q.intersection(
        direct_o
    )

    if direct_overlap:
        score += min(
            20,
            len(direct_overlap) * 5
        )

    score = min(
        100,
        round(score, 1)
    )

    return score, sorted(
        overlap
    )


def classify_alignment(score):

    if score >= 60:
        return "Strong Alignment"

    if score >= 35:
        return "Good Alignment"

    if score >= 20:
        return "Partial Alignment"

    if score > 0:
        return "Weak Alignment"

    return "Needs Review"


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    q = clean_text(question).lower()

    scores = {
        level: 0
        for level in BLOOM_LEVELS
    }

    evidence = []

    # Examine first part of question more heavily.
    command_part = q[:300]

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                command_part
            ):

                scores[level] += 3
                evidence.append(
                    (verb, level)
                )

    if "why" in command_part:
        scores["Analyze"] += 2

    if "how" in command_part:
        scores["Understand"] += 1

    if "compare and contrast" in command_part:
        scores["Analyze"] += 4

    if "justify" in command_part:
        scores["Evaluate"] += 4

    if "design" in command_part:
        scores["Create"] += 4

    if max(scores.values()) == 0:

        return {
            "level": "Needs Review",
            "evidence": []
        }

    best = max(
        scores,
        key=scores.get
    )

    return {
        "level": best,
        "evidence": list(
            dict.fromkeys(
                x[0]
                for x in evidence
            )
        )
    }


def bloom_alignment(intended, detected):

    if detected == "Needs Review":
        return 40.0, "Needs Review"

    if intended == detected:
        return 100.0, "Aligned"

    difference = abs(
        BLOOM_RANK[intended]
        -
        BLOOM_RANK[detected]
    )

    if difference == 1:
        return 65.0, "Partially Aligned"

    return 30.0, "Not Aligned"


# ============================================================
# FILE READING
# ============================================================

def read_pdf(file):

    try:

        from pypdf import PdfReader

        file.seek(0)

        reader = PdfReader(file)

        pages = []

        for page in reader.pages:

            text = page.extract_text() or ""

            if text.strip():
                pages.append(text)

        result = clean_text(
            "\n\n".join(pages)
        )

        if result:
            return result, "PDF text extraction"

    except Exception:
        pass

    # OCR
    try:

        import pytesseract
        from pdf2image import convert_from_bytes

        file.seek(0)

        pdf_bytes = file.read()

        images = convert_from_bytes(
            pdf_bytes,
            dpi=250
        )

        pages = []

        for image in images:

            text = pytesseract.image_to_string(
                image,
                config="--oem 3 --psm 6"
            )

            if text.strip():
                pages.append(text)

        result = clean_text(
            "\n\n".join(pages)
        )

        return result, "PDF OCR"

    except Exception as e:

        return "", f"OCR failed: {e}"


def read_docx(file):

    try:

        from docx import Document

        document = Document(file)

        text = "\n".join(
            p.text
            for p in document.paragraphs
            if p.text.strip()
        )

        return clean_text(text), "DOCX"

    except Exception as e:

        return "", str(e)


def read_txt(file):

    raw = file.read()

    for encoding in [
        "utf-8",
        "utf-16",
        "latin-1"
    ]:

        try:

            return clean_text(
                raw.decode(encoding)
            ), "TXT"

        except Exception:
            continue

    return "", "Could not read TXT"


def read_excel(file):

    try:

        sheets = pd.read_excel(
            file,
            sheet_name=None,
            header=None
        )

        parts = []

        for name, df in sheets.items():

            parts.append(
                f"Sheet {name}"
            )

            for row in df.astype(str).values:

                line = " ".join(
                    x
                    for x in row
                    if x.lower() != "nan"
                )

                if line.strip():
                    parts.append(line)

        return clean_text(
            "\n".join(parts)
        ), "Excel"

    except Exception as e:

        return "", str(e)


def read_file(file):

    name = file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(file)

    if name.endswith(".docx"):
        return read_docx(file)

    if name.endswith(".txt"):
        return read_txt(file)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return read_excel(file)

    return "", "Unsupported file"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    text = clean_text(text)

    pattern = (
        r"(?:^|\n)\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d+)"
        r"\s*[\.\):\-]\s*"
        r"(.*?)"
        r"(?="
        r"(?:\n\s*(?:Q(?:uestion)?\s*)?\d+\s*[\.\):\-])"
        r"|$)"
    )

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
                "number": f"Q{number}",
                "text": content
            })

    return questions


# ============================================================
# NAVIGATION
# ============================================================

st.sidebar.title("🎓 OBE Alignment Checker")

page = st.sidebar.radio(
    "Go to",
    [
        "🏠 Dashboard",
        "🏫 Course Setup",
        "🎯 CLO/PLO Setup",
        "📝 Assessment Setup",
        "🔍 OBE Analysis",
        "👥 Student Marks",
        "📊 Attainment Dashboard",
        "👤 Student Performance",
        "📥 Reports"
    ]
)

courses = fetchall(
    "SELECT * FROM courses ORDER BY id DESC"
)

course_dict = {
    f"{c['code']} - {c['name']} - {c['section']}":
    c["id"]
    for c in courses
}

selected_course_id = None

if course_dict:

    selected_label = st.sidebar.selectbox(
        "Active Course",
        list(course_dict.keys())
    )

    selected_course_id = course_dict[
        selected_label
    ]


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":

    st.title("🎓 OBE Alignment & Attainment Dashboard")

    if not selected_course_id:

        st.info(
            "Create a course first from Course Setup."
        )

    else:

        course = fetchone(
            "SELECT * FROM courses WHERE id=?",
            (selected_course_id,)
        )

        clo_count = fetchone(
            "SELECT COUNT(*) c FROM clos WHERE course_id=?",
            (selected_course_id,)
        )["c"]

        plo_count = fetchone(
            "SELECT COUNT(*) c FROM plos WHERE course_id=?",
            (selected_course_id,)
        )["c"]

        assessment_count = fetchone(
            "SELECT COUNT(*) c FROM assessments WHERE course_id=?",
            (selected_course_id,)
        )["c"]

        student_count = fetchone(
            "SELECT COUNT(*) c FROM students WHERE course_id=?",
            (selected_course_id,)
        )["c"]

        st.subheader(
            f"{course['code']} - {course['name']}"
        )

        st.write(
            f"{course['semester']} | Section: "
            f"{course['section']}"
        )

        a, b, c, d = st.columns(4)

        a.metric("CLOs", clo_count)
        b.metric("PLOs", plo_count)
        c.metric("Assessments", assessment_count)
        d.metric("Students", student_count)

        st.divider()

        st.info(
            "The active course is the central reference. "
            "Its CLOs, PLOs, mappings and assessments are "
            "used throughout the analysis and attainment reports."
        )


# ============================================================
# COURSE SETUP
# ============================================================

elif page == "🏫 Course Setup":

    st.title("🏫 Course Setup")

    with st.form("course_form"):

        code = st.text_input(
            "Course Code"
        )

        name = st.text_input(
            "Course Name"
        )

        semester = st.text_input(
            "Semester",
            value="Fall 2026"
        )

        section = st.text_input(
            "Section"
        )

        save = st.form_submit_button(
            "Create Course",
            use_container_width=True
        )

        if save:

            if not name.strip():

                st.error(
                    "Course name is required."
                )

            else:

                execute(
                    """
                    INSERT INTO courses
                    (code,name,semester,section)
                    VALUES (?,?,?,?)
                    """,
                    (
                        code.strip(),
                        name.strip(),
                        semester.strip(),
                        section.strip()
                    )
                )

                st.success(
                    "Course created successfully."
                )

                st.rerun()

    st.divider()

    existing = pd.read_sql_query(
        """
        SELECT
            id,
            code,
            name,
            semester,
            section
        FROM courses
        ORDER BY id DESC
        """,
        conn
    )

    if not existing.empty:

        st.dataframe(
            existing,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# CLO/PLO SETUP
# ============================================================

elif page == "🎯 CLO/PLO Setup":

    st.title("🎯 CLO & PLO Setup")

    if not selected_course_id:

        st.warning(
            "Create a course first."
        )
        st.stop()

    course = fetchone(
        "SELECT * FROM courses WHERE id=?",
        (selected_course_id,)
    )

    st.subheader(
        f"Course: {course['code']} - {course['name']}"
    )

    # ---------------- CLO ----------------

    st.header("Course Learning Outcomes")

    with st.form("add_clo"):

        code = st.text_input(
            "CLO Code",
            placeholder="CLO1"
        )

        description = st.text_area(
            "CLO Description"
        )

        target = st.number_input(
            "Target Attainment %",
            0.0,
            100.0,
            60.0
        )

        save_clo = st.form_submit_button(
            "Add CLO"
        )

        if save_clo:

            if code and description:

                execute(
                    """
                    INSERT INTO clos
                    (course_id,code,description,target)
                    VALUES (?,?,?,?)
                    """,
                    (
                        selected_course_id,
                        code.upper().strip(),
                        description.strip(),
                        target
                    )
                )

                st.success(
                    f"{code} saved."
                )

                st.rerun()

    clos = fetchall(
        "SELECT * FROM clos WHERE course_id=?",
        (selected_course_id,)
    )

    if clos:

        st.dataframe(
            pd.DataFrame([
                dict(x)
                for x in clos
            ]),
            use_container_width=True,
            hide_index=True
        )

    # ---------------- PLO ----------------

    st.header("Program Learning Outcomes")

    with st.form("add_plo"):

        code = st.text_input(
            "PLO Code",
            placeholder="PLO1"
        )

        description = st.text_area(
            "PLO Description"
        )

        target = st.number_input(
            "PLO Target Attainment %",
            0.0,
            100.0,
            60.0
        )

        save_plo = st.form_submit_button(
            "Add PLO"
        )

        if save_plo:

            if code and description:

                execute(
                    """
                    INSERT INTO plos
                    (course_id,code,description,target)
                    VALUES (?,?,?,?)
                    """,
                    (
                        selected_course_id,
                        code.upper().strip(),
                        description.strip(),
                        target
                    )
                )

                st.success(
                    f"{code} saved."
                )

                st.rerun()

    plos = fetchall(
        "SELECT * FROM plos WHERE course_id=?",
        (selected_course_id,)
    )

    if plos:

        st.dataframe(
            pd.DataFrame([
                dict(x)
                for x in plos
            ]),
            use_container_width=True,
            hide_index=True
        )

    # ---------------- MAPPING ----------------

    st.divider()

    st.header("CLO → PLO Mapping")

    if clos and plos:

        clo_options = {
            f"{x['code']} - {x['description']}":
            x["id"]
            for x in clos
        }

        plo_options = {
            f"{x['code']} - {x['description']}":
            x["id"]
            for x in plos
        }

        with st.form("mapping"):

            clo = st.selectbox(
                "CLO",
                list(clo_options.keys())
            )

            plo = st.selectbox(
                "PLO",
                list(plo_options.keys())
            )

            weight = st.number_input(
                "Mapping Weight",
                0.0,
                1.0,
                1.0
            )

            save_mapping = st.form_submit_button(
                "Save Mapping"
            )

            if save_mapping:

                execute(
                    """
                    INSERT INTO mappings
                    (course_id,clo_id,plo_id,weight)
                    VALUES (?,?,?,?)
                    """,
                    (
                        selected_course_id,
                        clo_options[clo],
                        plo_options[plo],
                        weight
                    )
                )

                st.success(
                    "Mapping saved."
                )

                st.rerun()

        mappings = fetchall(
            """
            SELECT
                c.code CLO,
                p.code PLO,
                m.weight
            FROM mappings m
            JOIN clos c ON c.id=m.clo_id
            JOIN plos p ON p.id=m.plo_id
            WHERE m.course_id=?
            """,
            (selected_course_id,)
        )

        if mappings:

            st.dataframe(
                pd.DataFrame([
                    dict(x)
                    for x in mappings
                ]),
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# ASSESSMENT SETUP
# ============================================================

elif page == "📝 Assessment Setup":

    st.title("📝 Assessment Setup")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    with st.form("assessment"):

        name = st.text_input(
            "Assessment Name",
            placeholder="Quiz 1"
        )

        total = st.number_input(
            "Total Marks",
            min_value=1.0,
            value=10.0
        )

        bloom = st.selectbox(
            "Intended Bloom Level",
            BLOOM_LEVELS,
            index=3
        )

        save = st.form_submit_button(
            "Create Assessment",
            use_container_width=True
        )

        if save:

            execute(
                """
                INSERT INTO assessments
                (course_id,name,total_marks,intended_bloom)
                VALUES (?,?,?,?)
                """,
                (
                    selected_course_id,
                    name.strip(),
                    total,
                    bloom
                )
            )

            st.success(
                "Assessment created."
            )

            st.rerun()

    assessments = fetchall(
        """
        SELECT *
        FROM assessments
        WHERE course_id=?
        ORDER BY id DESC
        """,
        (selected_course_id,)
    )

    if assessments:

        st.dataframe(
            pd.DataFrame([
                dict(x)
                for x in assessments
            ]),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# OBE ANALYSIS
# ============================================================

elif page == "🔍 OBE Analysis":

    st.title("🔍 OBE Analysis Results")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    assessments = fetchall(
        """
        SELECT *
        FROM assessments
        WHERE course_id=?
        ORDER BY id DESC
        """,
        (selected_course_id,)
    )

    if not assessments:

        st.info(
            "Create an assessment first."
        )
        st.stop()

    assessment_dict = {
        f"{x['name']} | {x['total_marks']} marks":
        x["id"]
        for x in assessments
    }

    selected_assessment = st.selectbox(
        "Assessment",
        list(assessment_dict.keys())
    )

    assessment_id = assessment_dict[
        selected_assessment
    ]

    assessment = fetchone(
        "SELECT * FROM assessments WHERE id=?",
        (assessment_id,)
    )

    # ========================================================
    # SHOW COURSE SETUP DIRECTLY IN RESULTS
    # ========================================================

    course = fetchone(
        "SELECT * FROM courses WHERE id=?",
        (selected_course_id,)
    )

    clos = fetchall(
        "SELECT * FROM clos WHERE course_id=?",
        (selected_course_id,)
    )

    plos = fetchall(
        "SELECT * FROM plos WHERE course_id=?",
        (selected_course_id,)
    )

    st.subheader("Course Setup Used for This Analysis")

    c1, c2, c3 = st.columns(3)

    c1.info(
        f"**Course**\n\n"
        f"{course['code']} - {course['name']}"
    )

    c2.info(
        f"**Assessment**\n\n"
        f"{assessment['name']}"
    )

    c3.info(
        f"**Intended Bloom**\n\n"
        f"{assessment['intended_bloom']}"
    )

    st.markdown("**CLOs used:**")

    for clo in clos:

        st.write(
            f"**{clo['code']}** — "
            f"{clo['description']}"
        )

    st.markdown("**PLOs used:**")

    for plo in plos:

        st.write(
            f"**{plo['code']}** — "
            f"{plo['description']}"
        )

    # ========================================================
    # UPLOAD
    # ========================================================

    uploaded = st.file_uploader(
        "Upload Quiz",
        type=[
            "pdf",
            "docx",
            "txt",
            "xlsx",
            "xls"
        ]
    )

    if uploaded:

        if st.button(
            "Analyze Quiz",
            type="primary",
            use_container_width=True
        ):

            text, method = read_file(
                uploaded
            )

            if not text:

                st.error(
                    f"Could not read file: {method}"
                )
                st.stop()

            questions = extract_questions(
                text
            )

            if not questions:

                st.error(
                    "No numbered questions detected."
                )
                st.stop()

            st.session_state[
                "analysis_questions"
            ] = questions

            st.success(
                f"{len(questions)} questions detected."
            )

    questions = st.session_state.get(
        "analysis_questions",
        []
    )

    if questions:

        st.divider()

        st.subheader(
            "Question-Level OBE Analysis"
        )

        clo_options = {
            f"{x['code']} — {x['description']}":
            x["id"]
            for x in clos
        }

        plo_options = {
            f"{x['code']} — {x['description']}":
            x["id"]
            for x in plos
        }

        analysis_rows = []

        for q in questions:

            detected = detect_bloom(
                q["text"]
            )

            bloom_score, bloom_status = bloom_alignment(
                assessment["intended_bloom"],
                detected["level"]
            )

            # Find best CLO
            best_clo = None
            best_clo_score = 0
            best_clo_terms = []

            for clo in clos:

                score, terms = outcome_similarity(
                    q["text"],
                    clo["description"]
                )

                if score > best_clo_score:

                    best_clo = clo
                    best_clo_score = score
                    best_clo_terms = terms

            # Find best PLO
            best_plo = None
            best_plo_score = 0
            best_plo_terms = []

            for plo in plos:

                score, terms = outcome_similarity(
                    q["text"],
                    plo["description"]
                )

                if score > best_plo_score:

                    best_plo = plo
                    best_plo_score = score
                    best_plo_terms = terms

            st.markdown(
                f"### {q['number']}"
            )

            st.write(
                q["text"]
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                st.metric(
                    "Bloom Alignment",
                    f"{bloom_score:.0f}%"
                )

                st.write(
                    f"Intended: **{assessment['intended_bloom']}**"
                )

                st.write(
                    f"Detected: **{detected['level']}**"
                )

                st.caption(
                    "Evidence: "
                    +
                    (
                        ", ".join(
                            detected["evidence"]
                        )
                        if detected["evidence"]
                        else "No clear verb detected"
                    )
                )

            with col2:

                st.metric(
                    "CLO Alignment",
                    f"{best_clo_score:.0f}%"
                )

                if best_clo:

                    st.write(
                        f"**{best_clo['code']}**"
                    )

                    st.caption(
                        best_clo["description"]
                    )

                    if best_clo_terms:

                        st.caption(
                            "Concept evidence: "
                            +
                            ", ".join(
                                best_clo_terms[:12]
                            )
                        )

            with col3:

                st.metric(
                    "PLO Alignment",
                    f"{best_plo_score:.0f}%"
                )

                if best_plo:

                    st.write(
                        f"**{best_plo['code']}**"
                    )

                    st.caption(
                        best_plo["description"]
                    )

                    if best_plo_terms:

                        st.caption(
                            "Concept evidence: "
                            +
                            ", ".join(
                                best_plo_terms[:12]
                            )
                        )

            # Feedback
            if bloom_status == "Aligned":

                st.success(
                    f"Bloom: The question demonstrates "
                    f"the intended {assessment['intended_bloom']} level."
                )

            else:

                st.warning(
                    f"Bloom: Intended "
                    f"{assessment['intended_bloom']}, "
                    f"but detected {detected['level']}."
                )

            if best_clo_score >= 60:

                st.success(
                    f"CLO: Strong alignment with "
                    f"{best_clo['code']}."
                )

            elif best_clo_score >= 35:

                st.warning(
                    f"CLO: Partial/good alignment with "
                    f"{best_clo['code']}."
                )

            else:

                st.warning(
                    "CLO: The question needs faculty review "
                    "for CLO alignment."
                )

            if best_plo_score >= 60:

                st.success(
                    f"PLO: Strong alignment with "
                    f"{best_plo['code']}."
                )

            elif best_plo_score >= 35:

                st.warning(
                    f"PLO: Partial/good alignment with "
                    f"{best_plo['code']}."
                )

            else:

                st.warning(
                    "PLO: The question needs faculty review "
                    "for PLO alignment."
                )

            # Save analysis
            analysis_rows.append({
                "Question": q["number"],
                "Question Text": q["text"],
                "Intended Bloom":
                    assessment["intended_bloom"],
                "Detected Bloom":
                    detected["level"],
                "Bloom Alignment %":
                    bloom_score,
                "Bloom Status":
                    bloom_status,
                "CLO":
                    best_clo["code"]
                    if best_clo else "",
                "CLO Description":
                    best_clo["description"]
                    if best_clo else "",
                "CLO Alignment %":
                    best_clo_score,
                "CLO Status":
                    classify_alignment(
                        best_clo_score
                    ),
                "PLO":
                    best_plo["code"]
                    if best_plo else "",
                "PLO Description":
                    best_plo["description"]
                    if best_plo else "",
                "PLO Alignment %":
                    best_plo_score,
                "PLO Status":
                    classify_alignment(
                        best_plo_score
                    )
            })

            st.divider()

        # ====================================================
        # CORRECTED OVERALL CALCULATIONS
        # ====================================================

        results_df = pd.DataFrame(
            analysis_rows
        )

        question_count = len(
            results_df
        )

        average_clo = results_df[
            "CLO Alignment %"
        ].mean()

        average_plo = results_df[
            "PLO Alignment %"
        ].mean()

        average_bloom = results_df[
            "Bloom Alignment %"
        ].mean()

        overall_score = (
            average_bloom * 0.40
            +
            average_clo * 0.35
            +
            average_plo * 0.25
        )

        st.divider()

        st.header(
            "📊 OBE Analysis Results"
        )

        a, b, c, d = st.columns(4)

        a.metric(
            "Questions",
            question_count
        )

        b.metric(
            "Average CLO Alignment",
            f"{average_clo:.1f}%"
        )

        c.metric(
            "Average PLO Alignment",
            f"{average_plo:.1f}%"
        )

        d.metric(
            "Overall Review Score",
            f"{overall_score:.1f}%"
        )

        # ====================================================
        # BLOOM SUMMARY
        # ====================================================

        st.subheader(
            "🧠 Bloom Analysis"
        )

        bloom_aligned_count = int(
            (
                results_df[
                    "Bloom Status"
                ] == "Aligned"
            ).sum()
        )

        st.write(
            f"{bloom_aligned_count} of "
            f"{question_count} questions match the "
            f"intended Bloom level."
        )

        st.dataframe(
            results_df[
                [
                    "Question",
                    "Intended Bloom",
                    "Detected Bloom",
                    "Bloom Alignment %",
                    "Bloom Status"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        # ====================================================
        # CLO SUMMARY
        # ====================================================

        st.subheader(
            "🎯 CLO Alignment"
        )

        clo_summary = (
            results_df.groupby("CLO")
            ["CLO Alignment %"]
            .mean()
            .reset_index()
        )

        clo_summary.columns = [
            "CLO",
            "Average Alignment %"
        ]

        st.dataframe(
            clo_summary,
            use_container_width=True,
            hide_index=True
        )

        if not clo_summary.empty:

            st.bar_chart(
                clo_summary.set_index(
                    "CLO"
                )
            )

        # ====================================================
        # PLO SUMMARY
        # ====================================================

        st.subheader(
            "🎓 PLO Alignment"
        )

        plo_summary = (
            results_df.groupby("PLO")
            ["PLO Alignment %"]
            .mean()
            .reset_index()
        )

        plo_summary.columns = [
            "PLO",
            "Average Alignment %"
        ]

        st.dataframe(
            plo_summary,
            use_container_width=True,
            hide_index=True
        )

        if not plo_summary.empty:

            st.bar_chart(
                plo_summary.set_index(
                    "PLO"
                )
            )

        # ====================================================
        # REVISION QUESTIONS
        # ====================================================

        st.subheader(
            "⚠️ Questions Requiring Review"
        )

        review = results_df[
            (
                results_df["Bloom Alignment %"] < 100
            )
            |
            (
                results_df["CLO Alignment %"] < 35
            )
            |
            (
                results_df["PLO Alignment %"] < 35
            )
        ]

        if review.empty:

            st.success(
                "No major alignment problems were detected."
            )

        else:

            st.dataframe(
                review[
                    [
                        "Question",
                        "Detected Bloom",
                        "CLO",
                        "CLO Alignment %",
                        "PLO",
                        "PLO Alignment %"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

        # ====================================================
        # SAVE TO DATABASE
        # ====================================================

        st.divider()

        if st.button(
            "💾 Save Analysis to Assessment",
            use_container_width=True
        ):

            execute(
                "DELETE FROM questions WHERE assessment_id=?",
                (assessment_id,)
            )

            for _, row in results_df.iterrows():

                clo_id = None
                plo_id = None

                if row["CLO"]:

                    clo_row = fetchone(
                        """
                        SELECT id
                        FROM clos
                        WHERE course_id=?
                        AND code=?
                        """,
                        (
                            selected_course_id,
                            row["CLO"]
                        )
                    )

                    if clo_row:
                        clo_id = clo_row["id"]

                if row["PLO"]:

                    plo_row = fetchone(
                        """
                        SELECT id
                        FROM plos
                        WHERE course_id=?
                        AND code=?
                        """,
                        (
                            selected_course_id,
                            row["PLO"]
                        )
                    )

                    if plo_row:
                        plo_id = plo_row["id"]

                execute(
                    """
                    INSERT INTO questions
                    (
                        assessment_id,
                        question_no,
                        question_text,
                        max_marks,
                        clo_id,
                        plo_id,
                        intended_bloom,
                        detected_bloom,
                        bloom_score,
                        clo_score,
                        plo_score
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        assessment_id,
                        row["Question"],
                        row["Question Text"],
                        1,
                        clo_id,
                        plo_id,
                        row["Intended Bloom"],
                        row["Detected Bloom"],
                        row["Bloom Alignment %"],
                        row["CLO Alignment %"],
                        row["PLO Alignment %"]
                    )
                )

            st.success(
                "Analysis saved. The results are now connected "
                "to the course, assessment, CLO, PLO and Bloom data."
            )

        # ====================================================
        # DOWNLOAD
        # ====================================================

        csv = results_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "📥 Download OBE Analysis CSV",
            csv,
            "OBE_Analysis_Report.csv",
            "text/csv",
            use_container_width=True
        )


# ============================================================
# STUDENT MARKS
# ============================================================

elif page == "👥 Student Marks":

    st.title("👥 Student Marks")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    assessments = fetchall(
        """
        SELECT *
        FROM assessments
        WHERE course_id=?
        ORDER BY id DESC
        """,
        (selected_course_id,)
    )

    if not assessments:

        st.info(
            "Create an assessment first."
        )
        st.stop()

    assessment_dict = {
        x["name"]: x["id"]
        for x in assessments
    }

    assessment_name = st.selectbox(
        "Assessment",
        list(assessment_dict.keys())
    )

    assessment_id = assessment_dict[
        assessment_name
    ]

    questions = fetchall(
        """
        SELECT *
        FROM questions
        WHERE assessment_id=?
        ORDER BY id
        """,
        (assessment_id,)
    )

    if not questions:

        st.warning(
            "Analyze and save the quiz first."
        )
        st.stop()

    st.subheader(
        "Marks File Format"
    )

    example = {
        "Student ID": ["S001"],
        "Student Name": ["Student One"]
    }

    for q in questions:
        example[q["question_no"]] = [0]

    st.dataframe(
        pd.DataFrame(example),
        use_container_width=True,
        hide_index=True
    )

    uploaded = st.file_uploader(
        "Upload Student Marks",
        type=["xlsx", "xls"]
    )

    if uploaded:

        df = pd.read_excel(
            uploaded
        )

        st.dataframe(
            df.head(),
            use_container_width=True,
            hide_index=True
        )

        id_col = None
        name_col = None

        for col in df.columns:

            c = str(col).lower().strip()

            if c in [
                "student id",
                "student_id",
                "id",
                "roll no",
                "roll number"
            ]:
                id_col = col

            if c in [
                "student name",
                "student_name",
                "name"
            ]:
                name_col = col

        if id_col is None:

            st.error(
                "Student ID column is required."
            )

        else:

            missing = [
                q["question_no"]
                for q in questions
                if q["question_no"] not in df.columns
            ]

            if missing:

                st.error(
                    "Missing question columns: "
                    + ", ".join(missing)
                )

            elif st.button(
                "💾 Save Marks",
                type="primary",
                use_container_width=True
            ):

                for _, row in df.iterrows():

                    sid = str(
                        row[id_col]
                    ).strip()

                    if not sid:
                        continue

                    sname = ""

                    if name_col is not None:

                        sname = str(
                            row[name_col]
                        ).strip()

                    existing = fetchone(
                        """
                        SELECT id
                        FROM students
                        WHERE course_id=?
                        AND student_id=?
                        """,
                        (
                            selected_course_id,
                            sid
                        )
                    )

                    if existing:

                        student_db_id = existing["id"]

                    else:

                        cur = execute(
                            """
                            INSERT INTO students
                            (course_id,student_id,student_name)
                            VALUES (?,?,?)
                            """,
                            (
                                selected_course_id,
                                sid,
                                sname
                            )
                        )

                        student_db_id = cur.lastrowid

                    for q in questions:

                        try:
                            score = float(
                                row[q["question_no"]]
                            )
                        except Exception:
                            score = 0

                        existing_mark = fetchone(
                            """
                            SELECT id
                            FROM marks
                            WHERE student_id=?
                            AND question_id=?
                            """,
                            (
                                student_db_id,
                                q["id"]
                            )
                        )

                        if existing_mark:

                            execute(
                                """
                                UPDATE marks
                                SET marks=?
                                WHERE id=?
                                """,
                                (
                                    score,
                                    existing_mark["id"]
                                )
                            )

                        else:

                            execute(
                                """
                                INSERT INTO marks
                                (student_id,question_id,marks)
                                VALUES (?,?,?)
                                """,
                                (
                                    student_db_id,
                                    q["id"],
                                    score
                                )
                            )

                st.success(
                    "Student marks saved successfully."
                )


# ============================================================
# ATTAINMENT DASHBOARD
# ============================================================

elif page == "📊 Attainment Dashboard":

    st.title("📊 OBE Attainment Dashboard")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    rows = fetchall(
        """
        SELECT
            c.code CLO,
            c.description CLO_Description,
            c.target CLO_Target,
            q.max_marks,
            m.marks
        FROM marks m
        JOIN questions q
            ON m.question_id=q.id
        JOIN students s
            ON m.student_id=s.id
        JOIN clos c
            ON q.clo_id=c.id
        WHERE s.course_id=?
        """,
        (selected_course_id,)
    )

    if not rows:

        st.info(
            "Student marks have not been entered yet."
        )
        st.stop()

    data = []

    for clo_code in sorted(
        set(
            x["CLO"]
            for x in rows
        )
    ):

        subset = [
            x
            for x in rows
            if x["CLO"] == clo_code
        ]

        obtained = sum(
            float(x["marks"])
            for x in subset
        )

        possible = sum(
            float(x["max_marks"])
            for x in subset
        )

        attainment = (
            obtained /
            possible *
            100
            if possible
            else 0
        )

        target = float(
            subset[0]["CLO_Target"]
        )

        data.append({
            "CLO": clo_code,
            "Attainment %": round(
                attainment,
                2
            ),
            "Target %": target,
            "Status":
                "Achieved"
                if attainment >= target
                else "Below Target"
        })

    result = pd.DataFrame(
        data
    )

    st.dataframe(
        result,
        use_container_width=True,
        hide_index=True
    )

    st.bar_chart(
        result.set_index(
            "CLO"
        )[[
            "Attainment %",
            "Target %"
        ]]
    )

    st.divider()

    st.subheader(
        "PLO Attainment"
    )

    plo_rows = fetchall(
        """
        SELECT
            p.code PLO,
            p.target Target,
            q.max_marks,
            m.marks
        FROM marks m
        JOIN questions q
            ON m.question_id=q.id
        JOIN students s
            ON m.student_id=s.id
        JOIN plos p
            ON q.plo_id=p.id
        WHERE s.course_id=?
        """,
        (selected_course_id,)
    )

    plo_data = []

    for plo_code in sorted(
        set(
            x["PLO"]
            for x in plo_rows
        )
    ):

        subset = [
            x
            for x in plo_rows
            if x["PLO"] == plo_code
        ]

        obtained = sum(
            float(x["marks"])
            for x in subset
        )

        possible = sum(
            float(x["max_marks"])
            for x in subset
        )

        attainment = (
            obtained /
            possible *
            100
            if possible
            else 0
        )

        target = float(
            subset[0]["Target"]
        )

        plo_data.append({
            "PLO": plo_code,
            "Attainment %": round(
                attainment,
                2
            ),
            "Target %": target,
            "Status":
                "Achieved"
                if attainment >= target
                else "Below Target"
        })

    if plo_data:

        plo_df = pd.DataFrame(
            plo_data
        )

        st.dataframe(
            plo_df,
            use_container_width=True,
            hide_index=True
        )

        st.bar_chart(
            plo_df.set_index(
                "PLO"
            )[[
                "Attainment %",
                "Target %"
            ]]
        )


# ============================================================
# STUDENT PERFORMANCE
# ============================================================

elif page == "👤 Student Performance":

    st.title("👤 Individual Student Performance")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    students = fetchall(
        """
        SELECT *
        FROM students
        WHERE course_id=?
        ORDER BY student_id
        """,
        (selected_course_id,)
    )

    if not students:

        st.info(
            "No students found."
        )
        st.stop()

    options = {
        f"{x['student_id']} - {x['student_name']}":
        x["id"]
        for x in students
    }

    selected = st.selectbox(
        "Student",
        list(options.keys())
    )

    student_id = options[
        selected
    ]

    rows = fetchall(
        """
        SELECT
            q.question_no,
            q.max_marks,
            q.bloom_level,
            c.code CLO,
            p.code PLO,
            m.marks
        FROM marks m
        JOIN questions q
            ON m.question_id=q.id
        LEFT JOIN clos c
            ON q.clo_id=c.id
        LEFT JOIN plos p
            ON q.plo_id=p.id
        WHERE m.student_id=?
        ORDER BY q.id
        """,
        (student_id,)
    )

    if rows:

        df = pd.DataFrame([
            dict(x)
            for x in rows
        ])

        obtained = df["marks"].sum()
        possible = df["max_marks"].sum()

        percentage = (
            obtained / possible * 100
            if possible
            else 0
        )

        a, b = st.columns(2)

        a.metric(
            "Total Marks",
            f"{obtained:.1f}/{possible:.1f}"
        )

        b.metric(
            "Overall Percentage",
            f"{percentage:.1f}%"
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.subheader(
            "Student CLO Performance"
        )

        clo_data = []

        for clo in sorted(
            df["CLO"].dropna().unique()
        ):

            temp = df[
                df["CLO"] == clo
            ]

            obtained = temp["marks"].sum()
            possible = temp["max_marks"].sum()

            attainment = (
                obtained / possible * 100
                if possible
                else 0
            )

            clo_data.append({
                "CLO": clo,
                "Attainment %":
                    round(attainment, 2)
            })

        if clo_data:

            clo_df = pd.DataFrame(
                clo_data
            )

            st.dataframe(
                clo_df,
                use_container_width=True,
                hide_index=True
            )

            st.bar_chart(
                clo_df.set_index(
                    "CLO"
                )
            )


# ============================================================
# REPORTS
# ============================================================

elif page == "📥 Reports":

    st.title("📥 OBE Reports")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    questions = fetchall(
        """
        SELECT
            q.question_no,
            q.question_text,
            q.intended_bloom,
            q.detected_bloom,
            q.bloom_score,
            c.code CLO,
            q.clo_score,
            p.code PLO,
            q.plo_score
        FROM questions q
        LEFT JOIN clos c
            ON q.clo_id=c.id
        LEFT JOIN plos p
            ON q.plo_id=p.id
        JOIN assessments a
            ON q.assessment_id=a.id
        WHERE a.course_id=?
        ORDER BY q.id
        """,
        (selected_course_id,)
    )

    if not questions:

        st.info(
            "No saved analysis is available."
        )

    else:

        report = pd.DataFrame([
            dict(x)
            for x in questions
        ])

        st.dataframe(
            report,
            use_container_width=True,
            hide_index=True
        )

        csv = report.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "Download CSV",
            csv,
            "OBE_Report.csv",
            "text/csv",
            use_container_width=True
        )

        excel = io.BytesIO()

        with pd.ExcelWriter(
            excel,
            engine="openpyxl"
        ) as writer:

            report.to_excel(
                writer,
                index=False,
                sheet_name="OBE Analysis"
            )

        st.download_button(
            "Download Excel",
            excel.getvalue(),
            "OBE_Report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
