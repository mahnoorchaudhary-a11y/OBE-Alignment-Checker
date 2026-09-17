import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ============================================================

# PAGE CONFIGURATION

# ============================================================

st.set_page_config(
page_title="OBE Alignment Checker",
page_icon="🎯",
layout="wide"
)

# ============================================================

# CUSTOM CSS

# ============================================================

st.markdown("""

<style>
.main-title {
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 4px;
}

.sub-title {
    color: #666;
    font-size: 16px;
    margin-bottom: 20px;
}

.good {
    padding: 12px;
    border-radius: 8px;
    background: #eaf7ee;
}

.warn {
    padding: 12px;
    border-radius: 8px;
    background: #fff6df;
}

.bad {
    padding: 12px;
    border-radius: 8px;
    background: #fdecec;
}

.file-box {
    padding: 15px;
    border-radius: 10px;
    border: 1px solid #ddd;
    margin-top: 10px;
}
</style>

""", unsafe_allow_html=True)

# ============================================================

# BLOOM'S TAXONOMY

# ============================================================

BLOOM_VERBS = {
"Remember": [
"define", "identify", "list", "name", "recall",
"state", "mention", "recognize", "select"
],

```
"Understand": [
    "describe", "explain", "summarize", "interpret",
    "classify", "discuss", "illustrate", "outline",
    "paraphrase"
],

"Apply": [
    "apply", "calculate", "demonstrate", "use",
    "solve", "implement", "execute", "practice",
    "compute"
],

"Analyze": [
    "analyze", "analyse", "compare", "contrast",
    "differentiate", "examine", "investigate",
    "categorize", "distinguish"
],

"Evaluate": [
    "evaluate", "assess", "justify", "critique",
    "judge", "defend", "argue", "recommend",
    "appraise"
],

"Create": [
    "create", "design", "develop", "construct",
    "formulate", "propose", "produce", "generate",
    "plan"
]
```

}

# ============================================================

# STOPWORDS

# ============================================================

STOPWORDS = {
"the", "and", "for", "with", "from", "that", "this",
"what", "which", "where", "when", "how", "why",
"are", "was", "were", "has", "have", "had",
"will", "would", "should", "could", "can", "may",
"into", "about", "your", "their", "them", "than",
"then", "also", "using", "used", "following",
"given", "question", "questions"
}

# ============================================================

# BASIC TEXT FUNCTIONS

# ============================================================

def clean_text(text):
return re.sub(r"\s+", " ", str(text or "")).strip()

def meaningful_words(text):
words = set(
re.findall(
r"[a-zA-Z]{3,}",
clean_text(text).lower()
)
)

```
return words - STOPWORDS
```

# ============================================================

# BLOOM DETECTION

# ============================================================

def detect_bloom(question):

```
q = clean_text(question).lower()

found = []

for level, verbs in BLOOM_VERBS.items():

    for verb in verbs:

        if re.search(
            r"\b" + re.escape(verb) + r"\b",
            q
        ):
            found.append(level)
            break

if not found:
    return "Not detected"

order = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]

for level in reversed(order):

    if level in found:
        return level

return found[0]
```

# ============================================================

# MARK EXTRACTION

# ============================================================

def extract_marks(question):

```
patterns = [

    r"\(\s*(\d+(?:\.\d+)?)\s*marks?\s*\)",

    r"\[\s*(\d+(?:\.\d+)?)\s*marks?\s*\]",

    r"(\d+(?:\.\d+)?)\s*marks?\b",

    r"\(\s*(\d+(?:\.\d+)?)\s*\)"

]

for pattern in patterns:

    match = re.search(
        pattern,
        question,
        re.I
    )

    if match:

        try:
            return float(match.group(1))

        except Exception:
            pass

return None
```

# ============================================================

# QUESTION PARSER

# ============================================================

def parse_questions(text):

```
if not text:
    return []

text = (
    text
    .replace("\r\n", "\n")
    .replace("\r", "\n")
)

# --------------------------------------------------------
# Normalize common question labels
# --------------------------------------------------------

text = re.sub(
    r"\bQuestion\s+(\d+)",
    r"\1.",
    text,
    flags=re.I
)

text = re.sub(
    r"\bQ\s*(\d+)\s*[:\-]",
    r"\1.",
    text,
    flags=re.I
)

text = re.sub(
    r"\bQ\s*(\d+)\s*\.",
    r"\1.",
    text,
    flags=re.I
)

# --------------------------------------------------------
# Numbered questions
# --------------------------------------------------------

numbered = re.findall(
    r"(?is)"
    r"(?:^|\n)"
    r"\s*(\d{1,3})"
    r"\s*[\.\):\-]"
    r"\s*(.*?)"
    r"(?="
    r"\n\s*\d{1,3}\s*[\.\):\-]"
    r"|$"
    r")",
    text
)

questions = []

for number, content in numbered:

    cleaned = clean_text(content)

    # Remove common answer-key / page noise
    cleaned = re.sub(
        r"\bPage\s+\d+\b",
        "",
        cleaned,
        flags=re.I
    )

    cleaned = clean_text(cleaned)

    if len(cleaned) >= 10:

        questions.append(cleaned)

if questions:
    return questions

# --------------------------------------------------------
# Alternative format: lines beginning with Q
# --------------------------------------------------------

q_lines = re.findall(
    r"(?im)^\s*Q(?:uestion)?\s*\d+\s*[\.\):\-]?\s*(.+)$",
    text
)

q_lines = [
    clean_text(x)
    for x in q_lines
    if len(clean_text(x)) >= 10
]

if q_lines:
    return q_lines

# --------------------------------------------------------
# Fallback: meaningful lines
# --------------------------------------------------------

lines = []

for line in text.split("\n"):

    line = clean_text(line)

    if len(line) >= 30:

        if not re.match(
            r"^(page|student|name|roll|date|course|marks?)\b",
            line,
            re.I
        ):
            lines.append(line)

return lines
```

# ============================================================

# PDF EXTRACTION

# ============================================================

def extract_pdf(file):

```
try:

    # PyMuPDF
    import fitz

except ImportError:

    return (
        "ERROR: PyMuPDF is not installed. "
        "Please add 'PyMuPDF' to requirements.txt "
        "and redeploy the Streamlit app."
    )

try:

    file.seek(0)

    pdf_bytes = file.read()

    if not pdf_bytes:

        return "ERROR: The uploaded PDF is empty."

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    all_pages = []

    total_pages = len(document)

    for page_number, page in enumerate(document, start=1):

        try:

            text = page.get_text(
                "text",
                sort=True
            )

            if text:

                all_pages.append(
                    f"\n--- PAGE {page_number} ---\n"
                    + text
                )

        except Exception:
            continue

    document.close()

    extracted_text = "\n".join(all_pages).strip()

    # ----------------------------------------------------
    # No selectable text
    # ----------------------------------------------------

    if len(extracted_text) < 20:

        return (
            "ERROR: The PDF was opened successfully, "
            "but no selectable text was found.\n\n"
            "This usually means the PDF is a scanned/image-only "
            "document. Please use a text-based PDF or OCR the PDF "
            "before uploading it."
        )

    return extracted_text

except Exception as e:

    return (
        "ERROR: Could not read PDF.\n"
        + str(e)
    )
```

# ============================================================

# DOCX EXTRACTION

# ============================================================

def extract_docx(file):

```
try:

    from docx import Document

    file.seek(0)

    doc = Document(file)

    parts = []

    # Paragraphs
    for paragraph in doc.paragraphs:

        text = clean_text(paragraph.text)

        if text:
            parts.append(text)

    # Tables
    for table in doc.tables:

        for row in table.rows:

            row_text = []

            for cell in row.cells:

                cell_text = clean_text(cell.text)

                if cell_text:
                    row_text.append(cell_text)

            if row_text:
                parts.append(" ".join(row_text))

    return "\n".join(parts)

except Exception as e:

    return (
        "ERROR: Could not read DOCX. "
        + str(e)
    )
```

# ============================================================

# EXCEL EXTRACTION

# ============================================================

def extract_excel(file):

```
try:

    file.seek(0)

    excel_file = pd.ExcelFile(file)

    parts = []

    for sheet in excel_file.sheet_names:

        df = pd.read_excel(
            file,
            sheet_name=sheet,
            header=None
        )

        parts.append(
            "\n--- SHEET: "
            + str(sheet)
            + " ---\n"
        )

        parts.append(
            df.fillna("")
            .astype(str)
            .to_string(
                index=False,
                header=False
            )
        )

    return "\n".join(parts)

except Exception as e:

    return (
        "ERROR: Could not read Excel. "
        + str(e)
    )
```

# ============================================================

# TXT EXTRACTION

# ============================================================

def extract_txt(file):

```
try:

    file.seek(0)

    data = file.read()

    if isinstance(data, bytes):

        return data.decode(
            "utf-8",
            errors="ignore"
        )

    return str(data)

except Exception as e:

    return (
        "ERROR: Could not read TXT file. "
        + str(e)
    )
```

# ============================================================

# UNIVERSAL FILE READER

# ============================================================

def extract_uploaded_file(file):

```
name = file.name.lower()

if name.endswith(".pdf"):

    return extract_pdf(file)

if name.endswith(".docx"):

    return extract_docx(file)

if name.endswith((".xlsx", ".xls")):

    return extract_excel(file)

if name.endswith(".txt"):

    return extract_txt(file)

return (
    "ERROR: Unsupported file format."
)
```

# ============================================================

# ALIGNMENT SCORING

# ============================================================

def alignment_score(question, outcome):

```
q = meaningful_words(question)

o = meaningful_words(outcome)

if not q or not o:
    return 0

overlap = q & o

return min(
    100,
    round(
        len(overlap)
        /
        max(1, min(len(o), 8))
        * 100
    )
)
```

# ============================================================

# BEST OUTCOME

# ============================================================

def best_outcome(question, outcomes):

```
if not outcomes:

    return "Not identified", 0

scored = [
    (
        outcome,
        alignment_score(
            question,
            outcome
        )
    )
    for outcome in outcomes
]

return max(
    scored,
    key=lambda x: x[1]
)
```

# ============================================================

# BLOOM MAPPING

# ============================================================

def parse_bloom_mapping(text):

```
result = {}

for line in text.splitlines():

    if ":" not in line:
        continue

    clo, bloom = line.split(
        ":",
        1
    )

    bloom = bloom.strip().title()

    if bloom in BLOOM_VERBS:

        result[
            clo.strip()
        ] = bloom

return result
```

# ============================================================

# QUESTION EVALUATION

# ============================================================

def evaluate_question(
question,
clos,
plos,
bloom_mapping
):

```
bloom = detect_bloom(question)

marks = extract_marks(question)

clo, clo_score = best_outcome(
    question,
    clos
)

plo, plo_score = best_outcome(
    question,
    plos
)

expected = bloom_mapping.get(clo)

bloom_match = "Review"

if expected:

    if bloom == expected:

        bloom_match = "Yes"

    else:

        bloom_match = "Review"

suggestions = []

# CLO
if clo_score < 30:

    suggestions.append(
        "Strengthen the connection with the selected CLO "
        "by making the intended skill or concept more explicit."
    )

elif clo_score < 60:

    suggestions.append(
        "Review whether the question directly measures "
        "the selected CLO rather than only covering a related topic."
    )

# PLO
if plo_score < 20:

    suggestions.append(
        "Review the PLO mapping. The question wording "
        "does not strongly indicate the selected PLO."
    )

elif plo_score < 50:

    suggestions.append(
        "Check whether the assessed skill is clearly "
        "represented in the selected PLO."
    )

# Bloom
if bloom == "Not detected":

    suggestions.append(
        "Use a clear Bloom action verb such as explain, "
        "apply, analyze, evaluate, or design."
    )

if expected and bloom != expected:

    suggestions.append(
        f"Review whether the task actually requires "
        f"the intended Bloom level: {expected}."
    )

# Marks
if marks is None:

    suggestions.append(
        "Add marks to make the assessment weight clear."
    )

elif marks <= 1 and bloom in [
    "Analyze",
    "Evaluate",
    "Create"
]:

    suggestions.append(
        "Review whether the marks are sufficient "
        "for the cognitive demand of the task."
    )

if not suggestions:

    suggestions.append(
        "The question shows reasonable alignment indicators. "
        "Faculty review is still required."
    )

return {

    "Question": question,

    "CLO": clo,

    "CLO Score": clo_score,

    "PLO": plo,

    "PLO Score": plo_score,

    "Expected Bloom":
        expected or "Not specified",

    "Detected Bloom":
        bloom,

    "Marks":
        marks
        if marks is not None
        else "Not specified",

    "Bloom Match":
        bloom_match,

    "Suggestions":
        suggestions
}
```

# ============================================================

# REVIEW SCORE

# ============================================================

def review_score(result):

```
bloom = (
    100
    if result["Bloom Match"] == "Yes"
    else 50
)

marks = (
    100
    if result["Marks"] != "Not specified"
    else 50
)

return round(
    result["CLO Score"] * 0.45
    +
    result["PLO Score"] * 0.25
    +
    bloom * 0.20
    +
    marks * 0.10
)
```

# ============================================================

# SESSION STATE

# ============================================================

if "questions" not in st.session_state:

```
st.session_state.questions = []
```

if "results" not in st.session_state:

```
st.session_state.results = None
```

if "extracted_text" not in st.session_state:

```
st.session_state.extracted_text = ""
```

# ============================================================

# HEADER

# ============================================================

st.markdown(
'<div class="main-title">'
'🎯 OBE Alignment Checker'
'</div>',
unsafe_allow_html=True
)

st.markdown(
'<div class="sub-title">'
'Upload an assessment and review CLO, PLO, '
'Bloom’s Taxonomy, marks, and assessment alignment.'
'</div>',
unsafe_allow_html=True
)

# ============================================================

# SIDEBAR

# ============================================================

with st.sidebar:

```
st.header("Assessment Setup")

course = st.text_input(
    "Course Name",
    placeholder="e.g., English I"
)

st.subheader("CLOs")

clo_text = st.text_area(
    "Enter one CLO per line",
    placeholder=(
        "CLO1: Identify main ideas\n"
        "CLO2: Analyze patterns of organization\n"
        "CLO3: Apply paraphrasing skills"
    ),
    height=150
)

st.subheader("PLOs")

plo_text = st.text_area(
    "Enter one PLO per line",
    placeholder=(
        "PLO1: Knowledge\n"
        "PLO2: Problem Analysis\n"
        "PLO3: Communication Skills"
    ),
    height=120
)

st.subheader("Expected Bloom Levels")

bloom_text = st.text_area(
    "Optional",
    placeholder=(
        "CLO1: Understand\n"
        "CLO2: Analyze\n"
        "CLO3: Apply"
    ),
    height=100
)
```

# ============================================================

# PREPARE CLO / PLO

# ============================================================

clos = [
clean_text(x)
for x in clo_text.splitlines()
if clean_text(x)
]

plos = [
clean_text(x)
for x in plo_text.splitlines()
if clean_text(x)
]

bloom_mapping = parse_bloom_mapping(
bloom_text
)

# ============================================================

# FILE UPLOAD

# ============================================================

st.subheader(
"1. Upload Your Existing Assessment"
)

uploaded = st.file_uploader(
"Upload Quiz / Assignment / Exam",
type=[
"pdf",
"docx",
"xlsx",
"xls",
"txt"
]
)

if uploaded:

```
st.success(
    "Uploaded: " + uploaded.name
)

st.caption(
    "Supported formats: PDF, DOCX, XLSX, XLS and TXT"
)

# --------------------------------------------------------
# READ ASSESSMENT
# --------------------------------------------------------

if st.button(
    "📄 Read Assessment",
    use_container_width=True
):

    with st.spinner(
        "Reading your assessment..."
    ):

        extracted = extract_uploaded_file(
            uploaded
        )

    if extracted.startswith("ERROR:"):

        st.error(extracted)

        # Specific PDF guidance
        if uploaded.name.lower().endswith(".pdf"):

            st.warning(
                "If this is a scanned PDF, "
                "please convert it to a searchable/text PDF "
                "before uploading."
            )

    else:

        st.session_state.extracted_text = extracted

        questions = parse_questions(
            extracted
        )

        st.session_state.questions = questions

        st.session_state.results = None

        if questions:

            st.success(
                f"{len(questions)} questions detected successfully."
            )

            with st.expander(
                "👁️ Preview extracted assessment"
            ):

                for i, question in enumerate(
                    questions,
                    1
                ):

                    st.write(
                        f"**Q{i}.** {question}"
                    )

        else:

            st.warning(
                "The file was read, but no questions "
                "could be detected."
            )

            with st.expander(
                "Show extracted text"
            ):

                st.text(
                    extracted[:10000]
                )
```

# ============================================================

# ANALYZE

# ============================================================

analyze = st.button(
"🔍 Analyze Assessment",
type="primary",
use_container_width=True
)

if analyze:

```
if not uploaded:

    st.warning(
        "Please upload an assessment first."
    )

elif not clos:

    st.warning(
        "Please enter at least one CLO."
    )

elif not plos:

    st.warning(
        "Please enter at least one PLO."
    )

elif not st.session_state.questions:

    st.warning(
        "Please click 'Read Assessment' first."
    )

else:

    with st.spinner(
        "Analyzing CLO, PLO and Bloom alignment..."
    ):

        st.session_state.results = [
            evaluate_question(
                question,
                clos,
                plos,
                bloom_mapping
            )
            for question
            in st.session_state.questions
        ]
```

# ============================================================

# RESULTS

# ============================================================

if st.session_state.results:

```
results = st.session_state.results

scores = [
    review_score(result)
    for result in results
]

overall = round(
    sum(scores) / len(scores)
)

strong = sum(
    score >= 70
    for score in scores
)

st.divider()

st.subheader(
    "2. Alignment Results"
)

a, b, c, d = st.columns(4)

a.metric(
    "Overall Review Score",
    f"{overall}%"
)

b.metric(
    "Questions",
    len(results)
)

c.metric(
    "Reasonably Aligned",
    strong
)

d.metric(
    "Needs Review",
    len(results) - strong
)

st.info(
    "This tool is a review aid. Faculty should make "
    "the final academic decision about CLO, PLO, Bloom, "
    "marks, content, and wording."
)

# ========================================================
# OVERVIEW
# ========================================================

overview = []

for i, result in enumerate(
    results,
    1
):

    overview.append({

        "Q":
            f"Q{i}",

        "CLO":
            result["CLO"],

        "CLO Alignment":
            f'{result["CLO Score"]}%',

        "PLO":
            result["PLO"],

        "PLO Alignment":
            f'{result["PLO Score"]}%',

        "Expected Bloom":
            result["Expected Bloom"],

        "Detected Bloom":
            result["Detected Bloom"],

        "Marks":
            result["Marks"],

        "Review Score":
            f'{review_score(result)}%'
    })

st.subheader(
    "Question Overview"
)

st.dataframe(
    pd.DataFrame(overview),
    use_container_width=True,
    hide_index=True
)


# ========================================================
# DETAILED REVIEW
# ========================================================

st.subheader(
    "3. Detailed Question Review"
)

for i, result in enumerate(
    results,
    1
):

    with st.expander(
        f"Q{i} — Review Score: "
        f"{review_score(result)}%"
    ):

        st.markdown(
            "**Question**"
        )

        st.write(
            result["Question"]
        )

        x1, x2, x3, x4 = st.columns(4)

        x1.metric(
            "CLO Alignment",
            f'{result["CLO Score"]}%'
        )

        x2.metric(
            "PLO Alignment",
            f'{result["PLO Score"]}%'
        )

        x3.metric(
            "Detected Bloom",
            result["Detected Bloom"]
        )

        x4.metric(
            "Marks",
            result["Marks"]
        )

        st.write(
            f'**Selected CLO:** {result["CLO"]}'
        )

        st.write(
            f'**Selected PLO:** {result["PLO"]}'
        )

        st.write(
            f'**Expected Bloom:** '
            f'{result["Expected Bloom"]}'
        )

        score = review_score(result)

        if score >= 70:

            st.markdown(
                '<div class="good">'
                '<b>Initial review:</b> '
                'Several alignment indicators are present.'
                '</div>',
                unsafe_allow_html=True
            )

        elif score >= 40:

            st.markdown(
                '<div class="warn">'
                '<b>Initial review:</b> '
                'Some alignment indicators are present; '
                'review the question.'
                '</div>',
                unsafe_allow_html=True
            )

        else:

            st.markdown(
                '<div class="bad">'
                '<b>Initial review:</b> '
                'Important alignment areas require review.'
                '</div>',
                unsafe_allow_html=True
            )

        st.markdown(
            "**Suggested Improvements**"
        )

        for suggestion in result[
            "Suggestions"
        ]:

            st.write(
                "• " + suggestion
            )

        # ------------------------------------------------
        # RECHECK
        # ------------------------------------------------

        revised = st.text_area(
            "Edit this question and re-check it",
            value=result["Question"],
            key=f"rev_{i}",
            height=130
        )

        if st.button(
            f"🔄 Re-check Q{i}",
            key=f"check_{i}"
        ):

            new_result = evaluate_question(
                revised,
                clos,
                plos,
                bloom_mapping
            )

            old_score = review_score(
                result
            )

            new_score = review_score(
                new_result
            )

            z1, z2, z3 = st.columns(3)

            z1.metric(
                "Previous",
                f"{old_score}%"
            )

            z2.metric(
                "Revised",
                f"{new_score}%"
            )

            z3.metric(
                "Change",
                f"{new_score - old_score:+d}%"
            )

            st.write(
                f'**CLO:** '
                f'{new_result["CLO"]} '
                f'({new_result["CLO Score"]}%)'
            )

            st.write(
                f'**PLO:** '
                f'{new_result["PLO"]} '
                f'({new_result["PLO Score"]}%)'
            )

            st.write(
                f'**Bloom:** '
                f'{new_result["Detected Bloom"]}'
            )

            st.markdown(
                "**New Suggestions**"
            )

            for suggestion in new_result[
                "Suggestions"
            ]:

                st.write(
                    "• " + suggestion
                )


# ========================================================
# BLOOM DISTRIBUTION
# ========================================================

st.subheader(
    "4. Bloom's Taxonomy Distribution"
)

bloom_counts = {}

for result in results:

    level = result[
        "Detected Bloom"
    ]

    bloom_counts[level] = (
        bloom_counts.get(level, 0) + 1
    )

bloom_df = pd.DataFrame(
    list(
        bloom_counts.items()
    ),
    columns=[
        "Bloom Level",
        "Questions"
    ]
)

if not bloom_df.empty:

    st.bar_chart(
        bloom_df.set_index(
            "Bloom Level"
        )
    )


# ========================================================
# CLO COVERAGE
# ========================================================

st.subheader(
    "5. CLO Coverage"
)

clo_counts = {
    clo: 0
    for clo in clos
}

for result in results:

    if result["CLO"] in clo_counts:

        clo_counts[
            result["CLO"]
        ] += 1

clo_df = pd.DataFrame([

    {
        "CLO": clo,

        "Questions": count,

        "Coverage %":
            round(
                count
                /
                len(results)
                *
                100,
                1
            )
    }

    for clo, count
    in clo_counts.items()

])

st.dataframe(
    clo_df,
    use_container_width=True,
    hide_index=True
)


# ========================================================
# DOWNLOAD REPORT
# ========================================================

st.subheader(
    "6. Download Review Report"
)

report = []

for i, result in enumerate(
    results,
    1
):

    report.append({

        "Question No.":
            i,

        "Question":
            result["Question"],

        "CLO":
            result["CLO"],

        "CLO Alignment %":
            result["CLO Score"],

        "PLO":
            result["PLO"],

        "PLO Alignment %":
            result["PLO Score"],

        "Expected Bloom":
            result["Expected Bloom"],

        "Detected Bloom":
            result["Detected Bloom"],

        "Marks":
            result["Marks"],

        "Bloom Review":
            result["Bloom Match"],

        "Review Score %":
            review_score(result),

        "Suggestions":
            " | ".join(
                result["Suggestions"]
            )
    })

report_df = pd.DataFrame(
    report
)

# CSV
st.download_button(
    "⬇️ Download CSV Report",

    report_df.to_csv(
        index=False
    ).encode("utf-8"),

    "OBE_Alignment_Review.csv",

    "text/csv",

    use_container_width=True
)

# Excel
try:

    buffer = BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl"
    ) as writer:

        report_df.to_excel(
            writer,
            index=False,
            sheet_name="Question Review"
        )

        clo_df.to_excel(
            writer,
            index=False,
            sheet_name="CLO Coverage"
        )

        bloom_df.to_excel(
            writer,
            index=False,
            sheet_name="Bloom Distribution"
        )

    st.download_button(
        "📊 Download Excel Report",

        buffer.getvalue(),

        "OBE_Alignment_Review.xlsx",

        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

        use_container_width=True
    )

except Exception as e:

    st.caption(
        "Excel export is unavailable. "
        "CSV export remains available."
    )
```

# ============================================================

# FACULTY FINAL REVIEW CHECKLIST

# ============================================================

st.divider()

with st.expander(
"✅ Faculty Final Review Checklist"
):

```
checks = [

    "Each question measures a clearly identified CLO.",

    "The selected PLO genuinely reflects the assessed skill.",

    "The action verb matches the intended Bloom level.",

    "Marks are appropriate for the task.",

    "All important CLOs receive suitable assessment coverage.",

    "Questions assess taught content.",

    "The marking scheme or rubric matches the question.",

    "The teacher has reviewed and approved the final wording."
]

for i, item in enumerate(checks):

    st.checkbox(
        item,
        key=f"final_{i}"
    )
```

# ============================================================

# FOOTER

# ============================================================

st.caption(
"OBE Alignment Checker • "
"Faculty judgment remains central to the final assessment."
)
