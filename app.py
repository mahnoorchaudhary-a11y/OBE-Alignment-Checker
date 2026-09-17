import streamlit as st
import pandas as pd
import sqlite3
import re
import io
import os
from collections import Counter

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Attainment Tracker",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# DATABASE
# ============================================================

DB_FILE = "obe_tracker.db"


def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


conn = get_connection()


def execute(query, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    return cur


def fetchall(query, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()


def fetchone(query, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchone()


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database():

    execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT NOT NULL,
            semester TEXT,
            section TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS clos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            description TEXT NOT NULL,
            target REAL DEFAULT 60,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS plos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            description TEXT NOT NULL,
            target REAL DEFAULT 60,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            clo_id INTEGER NOT NULL,
            plo_id INTEGER NOT NULL,
            weight REAL DEFAULT 1,
            FOREIGN KEY(course_id) REFERENCES courses(id),
            FOREIGN KEY(clo_id) REFERENCES clos(id),
            FOREIGN KEY(plo_id) REFERENCES plos(id)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            total_marks REAL NOT NULL,
            intended_bloom TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            question_no TEXT NOT NULL,
            question_text TEXT,
            max_marks REAL NOT NULL,
            clo_id INTEGER,
            plo_id INTEGER,
            bloom_level TEXT,
            detected_bloom TEXT,
            FOREIGN KEY(assessment_id) REFERENCES assessments(id),
            FOREIGN KEY(clo_id) REFERENCES clos(id),
            FOREIGN KEY(plo_id) REFERENCES plos(id)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            student_name TEXT,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            marks REAL DEFAULT 0,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(question_id) REFERENCES questions(id)
        )
    """)


initialize_database()


# ============================================================
# BLOOM TAXONOMY
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
        "define",
        "list",
        "name",
        "identify",
        "state",
        "recall",
        "recognize",
        "mention",
        "label",
        "select"
    ],
    "Understand": [
        "explain",
        "summarize",
        "interpret",
        "discuss",
        "classify",
        "describe",
        "outline",
        "paraphrase",
        "illustrate"
    ],
    "Apply": [
        "apply",
        "use",
        "demonstrate",
        "solve",
        "calculate",
        "implement",
        "execute",
        "perform"
    ],
    "Analyze": [
        "analyze",
        "analyse",
        "examine",
        "compare",
        "contrast",
        "differentiate",
        "distinguish",
        "investigate",
        "categorize"
    ],
    "Evaluate": [
        "evaluate",
        "justify",
        "critique",
        "assess",
        "judge",
        "defend",
        "appraise",
        "recommend",
        "argue"
    ],
    "Create": [
        "create",
        "design",
        "develop",
        "formulate",
        "produce",
        "compose",
        "plan",
        "propose",
        "generate"
    ]
}


# ============================================================
# TEXT FUNCTIONS
# ============================================================

def clean_text(text):
    text = str(text or "")
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_bloom(text):

    text = clean_text(text).lower()

    scores = {
        level: 0
        for level in BLOOM_LEVELS
    }

    evidence = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                text
            ):
                scores[level] += 1
                evidence.append(verb)

    if "why" in text:
        scores["Analyze"] += 1

    if "justify" in text:
        scores["Evaluate"] += 2

    if "design" in text:
        scores["Create"] += 2

    if max(scores.values()) == 0:
        return "Needs Review", evidence

    best = max(
        scores,
        key=scores.get
    )

    return best, list(dict.fromkeys(evidence))


# ============================================================
# FILE READING
# ============================================================

def read_pdf(uploaded_file):

    try:

        from pypdf import PdfReader

        uploaded_file.seek(0)

        reader = PdfReader(uploaded_file)

        pages = []

        for page in reader.pages:

            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            if text.strip():
                pages.append(text)

        result = "\n\n".join(pages)

        if result.strip():
            return clean_text(result), "PDF text"

    except Exception:
        pass

    # OCR fallback
    try:

        import pytesseract
        from pdf2image import convert_from_bytes

        uploaded_file.seek(0)

        pdf_bytes = uploaded_file.read()

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

        result = "\n\n".join(pages)

        if result.strip():
            return clean_text(result), "PDF OCR"

    except Exception as e:

        return "", f"OCR failed: {e}"

    return "", "No readable text found in PDF"


def read_docx(uploaded_file):

    try:

        from docx import Document

        document = Document(uploaded_file)

        text = []

        for paragraph in document.paragraphs:

            if paragraph.text.strip():
                text.append(paragraph.text)

        return clean_text("\n".join(text)), "DOCX"

    except Exception as e:

        return "", str(e)


def read_excel(uploaded_file):

    try:

        excel = pd.ExcelFile(uploaded_file)

        pieces = []

        for sheet in excel.sheet_names:

            df = pd.read_excel(
                uploaded_file,
                sheet_name=sheet,
                header=None
            )

            pieces.append(
                f"Sheet: {sheet}"
            )

            for row in df.astype(str).values:

                line = " ".join(
                    x for x in row
                    if x.lower() != "nan"
                )

                if line.strip():
                    pieces.append(line)

            uploaded_file.seek(0)

        return clean_text("\n".join(pieces)), "Excel"

    except Exception as e:

        return "", str(e)


def read_txt(uploaded_file):

    try:

        raw = uploaded_file.read()

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

        return "", "Could not decode TXT"

    except Exception as e:

        return "", str(e)


def read_uploaded_file(uploaded_file):

    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if name.endswith(".docx"):
        return read_docx(uploaded_file)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return read_excel(uploaded_file)

    if name.endswith(".txt"):
        return read_txt(uploaded_file)

    return "", "Unsupported file"


# ============================================================
# PARSE QUESTIONS
# ============================================================

def parse_questions(text):

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

        if len(content) >= 5:

            questions.append({
                "question_no": f"Q{number}",
                "text": content
            })

    return questions


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🎓 OBE Tracker")

page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Dashboard",
        "🏫 Course Setup",
        "🎯 CLO & PLO Mapping",
        "📝 Assessment Setup",
        "📄 Quiz Analysis",
        "👥 Student Marks",
        "📊 CLO Attainment",
        "📊 PLO Attainment",
        "🧠 Bloom Attainment",
        "👤 Student Performance",
        "📑 Reports"
    ]
)


# ============================================================
# COURSE SELECTION
# ============================================================

courses = fetchall(
    "SELECT * FROM courses ORDER BY id DESC"
)

course_options = {
    f"{row['code']} - {row['name']} - {row['section']}": row["id"]
    for row in courses
}

selected_course_id = None

if course_options:

    selected_course_label = st.sidebar.selectbox(
        "Current Course",
        list(course_options.keys())
    )

    selected_course_id = course_options[
        selected_course_label
    ]

else:

    st.sidebar.warning(
        "Please create a course first."
    )


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":

    st.title("🎓 OBE Attainment Dashboard")

    st.write(
        "Manage courses, CLOs, PLOs, assessments, "
        "student marks and attainment."
    )

    if not selected_course_id:

        st.info(
            "Start by creating a course under Course Setup."
        )

    else:

        course = fetchone(
            "SELECT * FROM courses WHERE id=?",
            (selected_course_id,)
        )

        clo_count = fetchone(
            "SELECT COUNT(*) AS c FROM clos WHERE course_id=?",
            (selected_course_id,)
        )["c"]

        plo_count = fetchone(
            "SELECT COUNT(*) AS c FROM plos WHERE course_id=?",
            (selected_course_id,)
        )["c"]

        assessment_count = fetchone(
            "SELECT COUNT(*) AS c FROM assessments WHERE course_id=?",
            (selected_course_id,)
        )["c"]

        student_count = fetchone(
            "SELECT COUNT(*) AS c FROM students WHERE course_id=?",
            (selected_course_id,)
        )["c"]

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "CLOs",
            clo_count
        )

        col2.metric(
            "PLOs",
            plo_count
        )

        col3.metric(
            "Assessments",
            assessment_count
        )

        col4.metric(
            "Students",
            student_count
        )

        st.divider()

        st.subheader(
            f"Course: {course['code']} - {course['name']}"
        )

        st.write(
            f"Semester: {course['semester']}  |  "
            f"Section: {course['section']}"
        )

        st.info(
            "Complete Course Setup, CLO/PLO Mapping, "
            "Assessment Setup and Student Marks before "
            "reviewing attainment."
        )


# ============================================================
# COURSE SETUP
# ============================================================

elif page == "🏫 Course Setup":

    st.title("🏫 Course Setup")

    st.write(
        "Create the course that will become the foundation "
        "of all OBE attainment calculations."
    )

    with st.form("course_form"):

        code = st.text_input(
            "Course Code",
            placeholder="e.g. ENG101"
        )

        name = st.text_input(
            "Course Name",
            placeholder="e.g. English I"
        )

        semester = st.text_input(
            "Semester",
            placeholder="Fall 2026"
        )

        section = st.text_input(
            "Section",
            placeholder="BSBA-1E1"
        )

        submitted = st.form_submit_button(
            "➕ Create Course",
            use_container_width=True
        )

        if submitted:

            if not name.strip():

                st.error(
                    "Course name is required."
                )

            else:

                execute(
                    """
                    INSERT INTO courses
                    (code, name, semester, section)
                    VALUES (?, ?, ?, ?)
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

    st.subheader(
        "Existing Courses"
    )

    courses_df = pd.read_sql_query(
        "SELECT id, code, name, semester, section FROM courses ORDER BY id DESC",
        conn
    )

    if not courses_df.empty:

        st.dataframe(
            courses_df,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# CLO/PLO MAPPING
# ============================================================

elif page == "🎯 CLO & PLO Mapping":

    st.title("🎯 CLO & PLO Setup")

    if not selected_course_id:

        st.warning(
            "Create and select a course first."
        )
        st.stop()

    course = fetchone(
        "SELECT * FROM courses WHERE id=?",
        (selected_course_id,)
    )

    st.subheader(
        f"{course['code']} - {course['name']}"
    )

    # --------------------------------------------------------
    # CLO
    # --------------------------------------------------------

    st.header("Course Learning Outcomes")

    with st.form("clo_form"):

        clo_code = st.text_input(
            "CLO Code",
            placeholder="CLO1"
        )

        clo_description = st.text_area(
            "CLO Description",
            placeholder="Analyze patterns of organization in academic texts."
        )

        clo_target = st.number_input(
            "CLO Attainment Target (%)",
            min_value=0.0,
            max_value=100.0,
            value=60.0
        )

        add_clo = st.form_submit_button(
            "Add CLO"
        )

        if add_clo:

            if clo_code and clo_description:

                execute(
                    """
                    INSERT INTO clos
                    (course_id, code, description, target)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        selected_course_id,
                        clo_code.upper().strip(),
                        clo_description.strip(),
                        clo_target
                    )
                )

                st.success(
                    f"{clo_code} added."
                )

                st.rerun()

            else:

                st.error(
                    "Enter both CLO code and description."
                )

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

    # --------------------------------------------------------
    # PLO
    # --------------------------------------------------------

    st.header("Program Learning Outcomes")

    with st.form("plo_form"):

        plo_code = st.text_input(
            "PLO Code",
            placeholder="PLO1"
        )

        plo_description = st.text_area(
            "PLO Description",
            placeholder="Demonstrate effective communication skills."
        )

        plo_target = st.number_input(
            "PLO Attainment Target (%)",
            min_value=0.0,
            max_value=100.0,
            value=60.0
        )

        add_plo = st.form_submit_button(
            "Add PLO"
        )

        if add_plo:

            if plo_code and plo_description:

                execute(
                    """
                    INSERT INTO plos
                    (course_id, code, description, target)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        selected_course_id,
                        plo_code.upper().strip(),
                        plo_description.strip(),
                        plo_target
                    )
                )

                st.success(
                    f"{plo_code} added."
                )

                st.rerun()

            else:

                st.error(
                    "Enter both PLO code and description."
                )

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

    # --------------------------------------------------------
    # MAPPING
    # --------------------------------------------------------

    st.divider()

    st.header(
        "CLO → PLO Mapping"
    )

    if clos and plos:

        clo_dict = {
            f"{x['code']} - {x['description']}": x["id"]
            for x in clos
        }

        plo_dict = {
            f"{x['code']} - {x['description']}": x["id"]
            for x in plos
        }

        with st.form("mapping_form"):

            selected_clo = st.selectbox(
                "Select CLO",
                list(clo_dict.keys())
            )

            selected_plo = st.selectbox(
                "Select PLO",
                list(plo_dict.keys())
            )

            weight = st.number_input(
                "Mapping Weight",
                min_value=0.0,
                max_value=1.0,
                value=1.0,
                step=0.1
            )

            add_mapping = st.form_submit_button(
                "Add Mapping"
            )

            if add_mapping:

                execute(
                    """
                    INSERT INTO mappings
                    (course_id, clo_id, plo_id, weight)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        selected_course_id,
                        clo_dict[selected_clo],
                        plo_dict[selected_plo],
                        weight
                    )
                )

                st.success(
                    "CLO-PLO mapping saved."
                )

                st.rerun()

        mappings = fetchall(
            """
            SELECT
                m.id,
                c.code AS CLO,
                p.code AS PLO,
                m.weight
            FROM mappings m
            JOIN clos c ON m.clo_id=c.id
            JOIN plos p ON m.plo_id=p.id
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

    else:

        st.info(
            "Add CLOs and PLOs before creating mappings."
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

    clos = fetchall(
        "SELECT * FROM clos WHERE course_id=?",
        (selected_course_id,)
    )

    plos = fetchall(
        "SELECT * FROM plos WHERE course_id=?",
        (selected_course_id,)
    )

    with st.form("assessment_form"):

        assessment_name = st.text_input(
            "Assessment Name",
            placeholder="Quiz 1"
        )

        total_marks = st.number_input(
            "Total Marks",
            min_value=1.0,
            value=10.0
        )

        intended_bloom = st.selectbox(
            "Intended Bloom Level",
            BLOOM_LEVELS
        )

        create_assessment = st.form_submit_button(
            "Create Assessment",
            use_container_width=True
        )

        if create_assessment:

            if not assessment_name.strip():

                st.error(
                    "Enter assessment name."
                )

            else:

                execute(
                    """
                    INSERT INTO assessments
                    (course_id, name, total_marks, intended_bloom)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        selected_course_id,
                        assessment_name.strip(),
                        total_marks,
                        intended_bloom
                    )
                )

                st.success(
                    "Assessment created."
                )

                st.rerun()

    st.divider()

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

        st.info(
            "After creating an assessment, go to Quiz Analysis "
            "to upload the quiz and assign each detected question "
            "to its CLO, PLO and Bloom level."
        )


# ============================================================
# QUIZ ANALYSIS
# ============================================================

elif page == "📄 Quiz Analysis":

    st.title("📄 Quiz Analysis & Question Mapping")

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

        st.warning(
            "Create an assessment first."
        )
        st.stop()

    assessment_dict = {
        f"{x['name']} ({x['total_marks']} marks)": x["id"]
        for x in assessments
    }

    selected_assessment_label = st.selectbox(
        "Select Assessment",
        list(assessment_dict.keys())
    )

    assessment_id = assessment_dict[
        selected_assessment_label
    ]

    assessment = fetchone(
        "SELECT * FROM assessments WHERE id=?",
        (assessment_id,)
    )

    st.info(
        f"Intended Bloom Level: **{assessment['intended_bloom']}**"
    )

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
            "🔍 Extract Questions",
            type="primary"
        ):

            text, method = read_uploaded_file(
                uploaded
            )

            if not text:

                st.error(
                    f"Could not read file: {method}"
                )

            else:

                questions = parse_questions(
                    text
                )

                if not questions:

                    st.error(
                        "No numbered questions were detected. "
                        "Use Q1, Q2, Q3 or 1., 2., 3."
                    )

                else:

                    st.session_state[
                        "quiz_questions"
                    ] = questions

                    st.success(
                        f"{len(questions)} questions detected using {method}."
                    )

    questions = st.session_state.get(
        "quiz_questions",
        []
    )

    if questions:

        clos = fetchall(
            "SELECT * FROM clos WHERE course_id=?",
            (selected_course_id,)
        )

        plos = fetchall(
            "SELECT * FROM plos WHERE course_id=?",
            (selected_course_id,)
        )

        clo_options = {
            f"{x['code']} - {x['description']}": x["id"]
            for x in clos
        }

        plo_options = {
            f"{x['code']} - {x['description']}": x["id"]
            for x in plos
        }

        st.divider()

        st.subheader(
            "Question Mapping"
        )

        st.write(
            "The tool detects Bloom level automatically. "
            "You can verify or correct the mapping before "
            "student attainment is calculated."
        )

        mapping_rows = []

        for q in questions:

            detected, evidence = detect_bloom(
                q["text"]
            )

            st.markdown(
                f"### {q['question_no']}"
            )

            st.write(
                q["text"]
            )

            col1, col2, col3, col4 = st.columns(4)

            with col1:

                marks = st.number_input(
                    f"Maximum Marks - {q['question_no']}",
                    min_value=0.0,
                    value=1.0,
                    key=f"marks_{q['question_no']}"
                )

            with col2:

                bloom_index = (
                    BLOOM_LEVELS.index(detected)
                    if detected in BLOOM_LEVELS
                    else 0
                )

                bloom = st.selectbox(
                    f"Bloom - {q['question_no']}",
                    BLOOM_LEVELS,
                    index=bloom_index,
                    key=f"bloom_{q['question_no']}"
                )

            with col3:

                clo_label = st.selectbox(
                    f"CLO - {q['question_no']}",
                    list(clo_options.keys()),
                    key=f"clo_{q['question_no']}"
                )

            with col4:

                plo_label = st.selectbox(
                    f"PLO - {q['question_no']}",
                    list(plo_options.keys()),
                    key=f"plo_{q['question_no']}"
                )

            st.caption(
                f"Detected Bloom: {detected} | "
                f"Evidence: {', '.join(evidence) if evidence else 'None'}"
            )

            mapping_rows.append({
                "question_no": q["question_no"],
                "text": q["text"],
                "marks": marks,
                "bloom": bloom,
                "clo_id": clo_options[clo_label],
                "plo_id": plo_options[plo_label]
            })

        st.divider()

        if st.button(
            "💾 Save Question Mapping",
            type="primary",
            use_container_width=True
        ):

            # Delete old mappings for this assessment
            execute(
                "DELETE FROM questions WHERE assessment_id=?",
                (assessment_id,)
            )

            for row in mapping_rows:

                detected, _ = detect_bloom(
                    row["text"]
                )

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
                        bloom_level,
                        detected_bloom
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        assessment_id,
                        row["question_no"],
                        row["text"],
                        row["marks"],
                        row["clo_id"],
                        row["plo_id"],
                        row["bloom"],
                        detected
                    )
                )

            st.success(
                "Question mapping saved successfully."
            )

            st.info(
                "The questions are now connected to the "
                "Course → CLO → PLO → Bloom structure. "
                "Next, upload student marks."
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

        st.warning(
            "Create an assessment first."
        )
        st.stop()

    assessment_dict = {
        f"{x['name']}": x["id"]
        for x in assessments
    }

    assessment_name = st.selectbox(
        "Select Assessment",
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
            "No question mapping exists for this assessment. "
            "Go to Quiz Analysis first."
        )
        st.stop()

    st.subheader(
        "Expected Marks File Format"
    )

    example = pd.DataFrame([
        {
            "Student ID": "BSBA001",
            "Student Name": "Student One",
            **{
                q["question_no"]: 0
                for q in questions
            }
        }
    ])

    st.dataframe(
        example,
        use_container_width=True,
        hide_index=True
    )

    uploaded_marks = st.file_uploader(
        "Upload Student Marks Excel File",
        type=["xlsx", "xls"],
        key="marks_upload"
    )

    if uploaded_marks:

        marks_df = pd.read_excel(
            uploaded_marks
        )

        st.subheader(
            "Uploaded Marks Preview"
        )

        st.dataframe(
            marks_df.head(20),
            use_container_width=True,
            hide_index=True
        )

        student_id_column = None
        student_name_column = None

        for col in marks_df.columns:

            normalized = str(col).strip().lower()

            if normalized in [
                "student id",
                "student_id",
                "id",
                "roll no",
                "roll number",
                "registration number"
            ]:

                student_id_column = col

            if normalized in [
                "student name",
                "student_name",
                "name"
            ]:

                student_name_column = col

        if student_id_column is None:

            st.error(
                "The marks file must contain a Student ID column."
            )

        else:

            missing_questions = []

            for q in questions:

                if q["question_no"] not in marks_df.columns:
                    missing_questions.append(
                        q["question_no"]
                    )

            if missing_questions:

                st.error(
                    "These question columns are missing: "
                    + ", ".join(missing_questions)
                )

            else:

                if st.button(
                    "💾 Save Student Marks",
                    type="primary",
                    use_container_width=True
                ):

                    saved_students = 0
                    saved_marks = 0

                    for _, row in marks_df.iterrows():

                        student_id = str(
                            row[student_id_column]
                        ).strip()

                        if not student_id:
                            continue

                        student_name = ""

                        if student_name_column is not None:

                            student_name = str(
                                row[student_name_column]
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
                                student_id
                            )
                        )

                        if existing:

                            student_db_id = existing["id"]

                            execute(
                                """
                                UPDATE students
                                SET student_name=?
                                WHERE id=?
                                """,
                                (
                                    student_name,
                                    student_db_id
                                )
                            )

                        else:

                            cur = execute(
                                """
                                INSERT INTO students
                                (
                                    course_id,
                                    student_id,
                                    student_name
                                )
                                VALUES (?, ?, ?)
                                """,
                                (
                                    selected_course_id,
                                    student_id,
                                    student_name
                                )
                            )

                            student_db_id = cur.lastrowid

                            saved_students += 1

                        for q in questions:

                            value = row[
                                q["question_no"]
                            ]

                            try:
                                score = float(value)
                            except Exception:
                                score = 0.0

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
                                    (
                                        student_id,
                                        question_id,
                                        marks
                                    )
                                    VALUES (?, ?, ?)
                                    """,
                                    (
                                        student_db_id,
                                        q["id"],
                                        score
                                    )
                                )

                            saved_marks += 1

                    st.success(
                        f"Marks saved successfully. "
                        f"{saved_students} new students and "
                        f"{saved_marks} mark records processed."
                    )


# ============================================================
# CLO ATTAINMENT
# ============================================================

elif page == "📊 CLO Attainment":

    st.title("📊 CLO Attainment")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    query = """
        SELECT
            c.code AS CLO,
            c.description AS Description,
            c.target AS Target,
            q.max_marks,
            m.marks
        FROM questions q
        JOIN clos c
            ON q.clo_id = c.id
        JOIN marks m
            ON q.id = m.question_id
        JOIN students s
            ON m.student_id = s.id
        WHERE s.course_id=?
    """

    rows = fetchall(
        query,
        (selected_course_id,)
    )

    if not rows:

        st.info(
            "No student marks are available yet."
        )
        st.stop()

    data = []

    clo_codes = sorted(
        set(
            row["CLO"]
            for row in rows
        )
    )

    for clo_code in clo_codes:

        clo_rows = [
            row
            for row in rows
            if row["CLO"] == clo_code
        ]

        total_obtained = sum(
            float(x["marks"])
            for x in clo_rows
        )

        total_possible = sum(
            float(x["max_marks"])
            for x in clo_rows
        )

        attainment = (
            total_obtained /
            total_possible *
            100
            if total_possible
            else 0
        )

        target = float(
            clo_rows[0]["Target"]
        )

        status = (
            "Achieved"
            if attainment >= target
            else "Below Target"
        )

        data.append({
            "CLO": clo_code,
            "Attainment %": round(
                attainment,
                2
            ),
            "Target %": target,
            "Status": status
        })

    result_df = pd.DataFrame(
        data
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )

    st.subheader(
        "CLO Attainment Chart"
    )

    chart_df = result_df.set_index(
        "CLO"
    )[["Attainment %", "Target %"]]

    st.bar_chart(
        chart_df
    )

    achieved = (
        result_df["Status"] == "Achieved"
    ).sum()

    st.metric(
        "CLOs Meeting Target",
        f"{achieved}/{len(result_df)}"
    )


# ============================================================
# PLO ATTAINMENT
# ============================================================

elif page == "📊 PLO Attainment":

    st.title("📊 PLO Attainment")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    query = """
        SELECT
            p.code AS PLO,
            p.description AS Description,
            p.target AS Target,
            q.max_marks,
            m.marks
        FROM questions q
        JOIN plos p
            ON q.plo_id = p.id
        JOIN marks m
            ON q.id = m.question_id
        JOIN students s
            ON m.student_id = s.id
        WHERE s.course_id=?
    """

    rows = fetchall(
        query,
        (selected_course_id,)
    )

    if not rows:

        st.info(
            "No PLO-linked marks are available yet."
        )
        st.stop()

    data = []

    for plo_code in sorted(
        set(
            row["PLO"]
            for row in rows
        )
    ):

        plo_rows = [
            row
            for row in rows
            if row["PLO"] == plo_code
        ]

        obtained = sum(
            float(x["marks"])
            for x in plo_rows
        )

        possible = sum(
            float(x["max_marks"])
            for x in plo_rows
        )

        attainment = (
            obtained / possible * 100
            if possible
            else 0
        )

        target = float(
            plo_rows[0]["Target"]
        )

        status = (
            "Achieved"
            if attainment >= target
            else "Below Target"
        )

        data.append({
            "PLO": plo_code,
            "Attainment %": round(
                attainment,
                2
            ),
            "Target %": target,
            "Status": status
        })

    result_df = pd.DataFrame(
        data
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )

    st.subheader(
        "PLO Attainment Chart"
    )

    st.bar_chart(
        result_df.set_index(
            "PLO"
        )[[
            "Attainment %",
            "Target %"
        ]]
    )


# ============================================================
# BLOOM ATTAINMENT
# ============================================================

elif page == "🧠 Bloom Attainment":

    st.title("🧠 Bloom Level Attainment")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    query = """
        SELECT
            q.bloom_level AS Bloom,
            q.max_marks,
            m.marks
        FROM questions q
        JOIN marks m
            ON q.id=m.question_id
        JOIN students s
            ON m.student_id=s.id
        WHERE s.course_id=?
    """

    rows = fetchall(
        query,
        (selected_course_id,)
    )

    if not rows:

        st.info(
            "No marks are available yet."
        )
        st.stop()

    data = []

    for bloom in BLOOM_LEVELS:

        bloom_rows = [
            row
            for row in rows
            if row["Bloom"] == bloom
        ]

        if not bloom_rows:
            continue

        obtained = sum(
            float(x["marks"])
            for x in bloom_rows
        )

        possible = sum(
            float(x["max_marks"])
            for x in bloom_rows
        )

        attainment = (
            obtained / possible * 100
            if possible
            else 0
        )

        data.append({
            "Bloom Level": bloom,
            "Questions": len(bloom_rows),
            "Attainment %": round(
                attainment,
                2
            )
        })

    result_df = pd.DataFrame(
        data
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )

    st.subheader(
        "Bloom Attainment"
    )

    if not result_df.empty:

        st.bar_chart(
            result_df.set_index(
                "Bloom Level"
            )[[
                "Attainment %"
            ]]
        )

    # --------------------------------------------------------
    # Question-level Bloom check
    # --------------------------------------------------------

    st.subheader(
        "Intended vs Detected Bloom"
    )

    questions = fetchall(
        """
        SELECT
            question_no,
            question_text,
            bloom_level,
            detected_bloom
        FROM questions q
        JOIN assessments a
            ON q.assessment_id=a.id
        WHERE a.course_id=?
        ORDER BY q.id
        """,
        (selected_course_id,)
    )

    if questions:

        bloom_check = pd.DataFrame([
            {
                "Question": q["question_no"],
                "Intended Bloom": q["bloom_level"],
                "Detected Bloom": q["detected_bloom"],
                "Alignment":
                    "Aligned"
                    if q["bloom_level"]
                    == q["detected_bloom"]
                    else "Needs Review"
            }
            for q in questions
        ])

        st.dataframe(
            bloom_check,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# INDIVIDUAL STUDENT PERFORMANCE
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
            "No students found. Upload student marks first."
        )
        st.stop()

    student_options = {
        f"{x['student_id']} - {x['student_name']}": x["id"]
        for x in students
    }

    selected_student = st.selectbox(
        "Select Student",
        list(student_options.keys())
    )

    student_db_id = student_options[
        selected_student
    ]

    rows = fetchall(
        """
        SELECT
            q.question_no,
            q.max_marks,
            q.bloom_level,
            c.code AS CLO,
            p.code AS PLO,
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
        (student_db_id,)
    )

    if not rows:

        st.info(
            "No marks found for this student."
        )
        st.stop()

    total_obtained = sum(
        float(x["marks"])
        for x in rows
    )

    total_possible = sum(
        float(x["max_marks"])
        for x in rows
    )

    percentage = (
        total_obtained /
        total_possible *
        100
        if total_possible
        else 0
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Marks",
        f"{total_obtained:.2f}/{total_possible:.2f}"
    )

    col2.metric(
        "Percentage",
        f"{percentage:.2f}%"
    )

    col3.metric(
        "Questions",
        len(rows)
    )

    student_df = pd.DataFrame([
        dict(x)
        for x in rows
    ])

    st.subheader(
        "Question Performance"
    )

    st.dataframe(
        student_df,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # Student CLO performance
    # --------------------------------------------------------

    st.subheader(
        "Student CLO Attainment"
    )

    clo_data = []

    for clo in sorted(
        student_df["CLO"].dropna().unique()
    ):

        temp = student_df[
            student_df["CLO"] == clo
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
            "Attainment %": round(
                attainment,
                2
            )
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

elif page == "📑 Reports":

    st.title("📑 OBE Reports")

    if not selected_course_id:

        st.warning(
            "Select a course first."
        )
        st.stop()

    tabs = st.tabs([
        "Course",
        "CLO",
        "PLO",
        "Bloom",
        "Student Marks"
    ])

    with tabs[0]:

        course = fetchone(
            "SELECT * FROM courses WHERE id=?",
            (selected_course_id,)
        )

        st.write(
            f"**Course Code:** {course['code']}"
        )

        st.write(
            f"**Course Name:** {course['name']}"
        )

        st.write(
            f"**Semester:** {course['semester']}"
        )

        st.write(
            f"**Section:** {course['section']}"
        )

    with tabs[1]:

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

    with tabs[2]:

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

    with tabs[3]:

        rows = fetchall(
            """
            SELECT
                q.question_no,
                q.bloom_level,
                q.detected_bloom,
                q.max_marks
            FROM questions q
            JOIN assessments a
                ON q.assessment_id=a.id
            WHERE a.course_id=?
            """,
            (selected_course_id,)
        )

        if rows:

            st.dataframe(
                pd.DataFrame([
                    dict(x)
                    for x in rows
                ]),
                use_container_width=True,
                hide_index=True
            )

    with tabs[4]:

        rows = fetchall(
            """
            SELECT
                s.student_id,
                s.student_name,
                q.question_no,
                m.marks,
                q.max_marks
            FROM marks m
            JOIN students s
                ON m.student_id=s.id
            JOIN questions q
                ON m.question_id=q.id
            WHERE s.course_id=?
            ORDER BY s.student_id
            """,
            (selected_course_id,)
        )

        if rows:

            report_df = pd.DataFrame([
                dict(x)
                for x in rows
            ])

            st.dataframe(
                report_df,
                use_container_width=True,
                hide_index=True
            )

            csv = report_df.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                "Download Student Marks CSV",
                csv,
                "student_marks_report.csv",
                "text/csv"
            )

            excel_buffer = io.BytesIO()

            with pd.ExcelWriter(
                excel_buffer,
                engine="openpyxl"
            ) as writer:

                report_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Student Marks"
                )

            st.download_button(
                "Download Excel Report",
                excel_buffer.getvalue(),
                "OBE_student_marks_report.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
