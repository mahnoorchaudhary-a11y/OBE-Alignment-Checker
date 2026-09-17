import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(
page_title="OBE Alignment Checker",
page_icon="🎯",
layout="wide"
)

st.title("🎯 OBE Alignment Checker")
st.caption(
"Upload an assessment and review CLO, PLO, "
"Bloom's Taxonomy, marks, and alignment."
)

BLOOM_VERBS = {
"Remember": [
"define", "identify", "list", "name",
"recall", "state", "mention", "recognize"
],
"Understand": [
"describe", "explain", "summarize",
"interpret", "classify", "discuss",
"illustrate", "outline", "paraphrase"
],
"Apply": [
"apply", "calculate", "demonstrate",
"use", "solve", "implement",
"execute", "practice", "compute"
],
"Analyze": [
"analyze", "analyse", "compare",
"contrast", "differentiate", "examine",
"investigate", "categorize", "distinguish"
],
"Evaluate": [
"evaluate", "assess", "justify",
"critique", "judge", "defend",
"argue", "recommend", "appraise"
],
"Create": [
"create", "design", "develop",
"construct", "formulate", "propose",
"produce", "generate", "plan"
]
}

STOPWORDS = {
"the", "and", "for", "with", "from", "that",
"this", "what", "which", "where", "when",
"how", "why", "are", "was", "were", "has",
"have", "had", "will", "would", "should",
"could", "can", "may", "into", "about",
"your", "their", "them", "than", "then",
"also", "using", "used", "following",
"given", "question", "questions"
}

def clean_text(text):
text = str(text or "")
text = re.sub(r"\s+", " ", text)
return text.strip()

def meaningful_words(text):
text = clean_text(text).lower()

```
words = re.findall(
    r"[a-zA-Z]{3,}",
    text
)

return set(words) - STOPWORDS
```

def detect_bloom(question):
question = clean_text(question).lower()

```
found = []

for level, verbs in BLOOM_VERBS.items():
    for verb in verbs:
        pattern = r"\b" + re.escape(verb) + r"\b"

        if re.search(pattern, question):
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

def extract_marks(question):
patterns = [
r"\(\s*(\d+(?:\.\d+)?)\s*marks?\s*\)",
r"\(\s*(\d+(?:\.\d+)?)\s*marks?\s*\)",
r"(\d+(?:.\d+)?)\s*marks?\b",
r"\(\s*(\d+(?:\.\d+)?)\s*\)"
]

```
for pattern in patterns:
    match = re.search(
        pattern,
        question,
        re.IGNORECASE
    )

    if match:
        try:
            return float(match.group(1))
        except Exception:
            pass

return None
```

# ============================================================

# PDF READER

# ============================================================

def extract_pdf(file):
try:
import fitz
except ImportError:
return (
"ERROR: PyMuPDF is not installed. "
"Please add PyMuPDF to requirements.txt."
)

```
try:
    file.seek(0)
    pdf_data = file.read()

    if not pdf_data:
        return "ERROR: The PDF file is empty."

    document = fitz.open(
        stream=pdf_data,
        filetype="pdf"
    )

    page_texts = []

    for page_number in range(len(document)):
        page = document[page_number]

        try:
            text = page.get_text(
                "text",
                sort=True
            )
        except Exception:
            text = ""

        if text and text.strip():
            page_texts.append(
                "PAGE "
                + str(page_number + 1)
                + "\n"
                + text
            )

    document.close()

    result = "\n\n".join(page_texts).strip()

    if len(result) < 20:
        return (
            "ERROR: The PDF opened successfully, "
            "but no selectable text was found. "
            "This appears to be a scanned/image PDF. "
            "OCR is required for scanned PDFs."
        )

    return result

except Exception as error:
    return (
        "ERROR: Could not read PDF. "
        + str(error)
    )
```

# ============================================================

# DOCX READER

# ============================================================

def extract_docx(file):
try:
from docx import Document

```
    file.seek(0)
    document = Document(file)

    parts = []

    for paragraph in document.paragraphs:
        text = clean_text(paragraph.text)

        if text:
            parts.append(text)

    for table in document.tables:
        for row in table.rows:
            row_text = []

            for cell in row.cells:
                text = clean_text(cell.text)

                if text:
                    row_text.append(text)

            if row_text:
                parts.append(
                    " ".join(row_text)
                )

    return "\n".join(parts)

except Exception as error:
    return (
        "ERROR: Could not read DOCX. "
        + str(error)
    )
```

# ============================================================

# EXCEL READER

# ============================================================

def extract_excel(file):
try:
file.seek(0)

```
    excel = pd.ExcelFile(file)
    parts = []

    for sheet in excel.sheet_names:
        df = pd.read_excel(
            file,
            sheet_name=sheet,
            header=None
        )

        parts.append(
            "SHEET: " + str(sheet)
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

except Exception as error:
    return (
        "ERROR: Could not read Excel. "
        + str(error)
    )
```

# ============================================================

# TXT READER

# ============================================================

def extract_txt(file):
try:
file.seek(0)

```
    data = file.read()

    if isinstance(data, bytes):
        return data.decode(
            "utf-8",
            errors="ignore"
        )

    return str(data)

except Exception as error:
    return (
        "ERROR: Could not read TXT. "
        + str(error)
    )
```

def extract_uploaded_file(file):
filename = file.name.lower()

```
if filename.endswith(".pdf"):
    return extract_pdf(file)

if filename.endswith(".docx"):
    return extract_docx(file)

if filename.endswith(".xlsx"):
    return extract_excel(file)

if filename.endswith(".xls"):
    return extract_excel(file)

if filename.endswith(".txt"):
    return extract_txt(file)

return "ERROR: Unsupported file type."
```

# ============================================================

# QUESTION PARSER

# ============================================================

def parse_questions(text):
if not text:
return []

```
text = text.replace("\r\n", "\n")
text = text.replace("\r", "\n")

# Convert Question 1 / Q1 / Q 1 to 1.
text = re.sub(
    r"\bQuestion\s+(\d+)\s*[:.)-]",
    r"\1.",
    text,
    flags=re.IGNORECASE
)

text = re.sub(
    r"\bQ\s*(\d+)\s*[:.)-]",
    r"\1.",
    text,
    flags=re.IGNORECASE
)

pattern = (
    r"(?is)"
    r"(?:^|\n)"
    r"\s*(\d{1,3})"
    r"\s*[\.\):\-]"
    r"\s*(.*?)"
    r"(?="
    r"\n\s*\d{1,3}\s*[\.\):\-]"
    r"|$"
    r")"
)

matches = re.findall(
    pattern,
    text
)

questions = []

for number, content in matches:
    content = clean_text(content)

    content = re.sub(
        r"\bPAGE\s+\d+\b",
        "",
        content,
        flags=re.IGNORECASE
    )

    content = clean_text(content)

    if len(content) >= 10:
        questions.append(content)

if questions:
    return questions

# Fallback: each long line
lines = []

for line in text.split("\n"):
    line = clean_text(line)

    if len(line) >= 30:
        lines.append(line)

return lines
```

# ============================================================

# ALIGNMENT

# ============================================================

def alignment_score(question, outcome):
q_words = meaningful_words(question)
o_words = meaningful_words(outcome)

```
if not q_words or not o_words:
    return 0

overlap = q_words.intersection(o_words)

score = (
    len(overlap)
    /
    max(1, min(len(o_words), 8))
    * 100
)

return min(100, round(score))
```

def best_outcome(question, outcomes):
if not outcomes:
return "Not identified", 0

```
scored = []

for outcome in outcomes:
    score = alignment_score(
        question,
        outcome
    )

    scored.append(
        (outcome, score)
    )

return max(
    scored,
    key=lambda item: item[1]
)
```

def parse_bloom_mapping(text):
mapping = {}

```
for line in text.splitlines():

    if ":" not in line:
        continue

    clo, bloom = line.split(
        ":",
        1
    )

    clo = clean_text(clo)
    bloom = clean_text(bloom).title()

    if bloom in BLOOM_VERBS:
        mapping[clo] = bloom

return mapping
```

def evaluate_question(
question,
clos,
plos,
bloom_mapping
):
bloom = detect_bloom(question)
marks = extract_marks(question)

```
clo, clo_score = best_outcome(
    question,
    clos
)

plo, plo_score = best_outcome(
    question,
    plos
)

expected = bloom_mapping.get(clo)

if expected and bloom == expected:
    bloom_match = "Yes"
else:
    bloom_match = "Review"

suggestions = []

if clo_score < 30:
    suggestions.append(
        "Strengthen the connection with the selected CLO "
        "by making the intended skill or concept more explicit."
    )

elif clo_score < 60:
    suggestions.append(
        "Review whether the question directly measures "
        "the selected CLO."
    )

if plo_score < 20:
    suggestions.append(
        "Review the PLO mapping because the question "
        "does not strongly indicate the selected PLO."
    )

elif plo_score < 50:
    suggestions.append(
        "Check whether the assessed skill is clearly "
        "represented in the selected PLO."
    )

if bloom == "Not detected":
    suggestions.append(
        "Use a clear Bloom action verb such as explain, "
        "apply, analyze, evaluate, or design."
    )

if expected and bloom != expected:
    suggestions.append(
        "Review whether the task actually requires "
        "the intended Bloom level: "
        + expected
        + "."
    )

if marks is None:
    suggestions.append(
        "Add marks to make the assessment weight clear."
    )

if (
    marks is not None
    and marks <= 1
    and bloom in ["Analyze", "Evaluate", "Create"]
):
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
    "Expected Bloom": (
        expected
        if expected
        else "Not specified"
    ),
    "Detected Bloom": bloom,
    "Marks": (
        marks
        if marks is not None
        else "Not specified"
    ),
    "Bloom Match": bloom_match,
    "Suggestions": suggestions
}
```

def review_score(result):
bloom_score = (
100
if result["Bloom Match"] == "Yes"
else 50
)

```
marks_score = (
    100
    if result["Marks"] != "Not specified"
    else 50
)

return round(
    result["CLO Score"] * 0.45
    + result["PLO Score"] * 0.25
    + bloom_score * 0.20
    + marks_score * 0.10
)
```

# ============================================================

# SESSION STATE

# ============================================================

if "questions" not in st.session_state:
st.session_state.questions = []

if "results" not in st.session_state:
st.session_state.results = None

# ============================================================

# SIDEBAR

# ============================================================

with st.sidebar:

```
st.header("Assessment Setup")

course = st.text_input(
    "Course Name",
    placeholder="e.g. English I"
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

clos = [
clean_text(line)
for line in clo_text.splitlines()
if clean_text(line)
]

plos = [
clean_text(line)
for line in plo_text.splitlines()
if clean_text(line)
]

bloom_mapping = parse_bloom_mapping(
bloom_text
)

# ============================================================

# UPLOAD

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

if st.button(
    "📄 Read Assessment",
    use_container_width=True
):

    with st.spinner(
        "Reading assessment..."
    ):

        extracted = extract_uploaded_file(
            uploaded
        )

    if extracted.startswith("ERROR:"):

        st.error(extracted)

        if uploaded.name.lower().endswith(".pdf"):

            st.info(
                "If your PDF is scanned or consists of images, "
                "normal PDF text extraction cannot read it. "
                "An OCR version of the PDF is required."
            )

    else:

        questions = parse_questions(
            extracted
        )

        st.session_state.questions = questions
        st.session_state.results = None

        if questions:

            st.success(
                str(len(questions))
                + " questions detected."
            )

            with st.expander(
                "Preview extracted questions"
            ):

                for i, question in enumerate(
                    questions,
                    1
                ):

                    st.write(
                        "**Q"
                        + str(i)
                        + ".** "
                        + question
                    )

        else:

            st.warning(
                "The file was read, but no questions "
                "were detected."
            )

            with st.expander(
                "Show extracted text"
            ):

                st.text(
                    extracted[:15000]
                )
```

# ============================================================

# ANALYZE

# ============================================================

if st.button(
"🔍 Analyze Assessment",
type="primary",
use_container_width=True
):

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
        "Analyzing assessment..."
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
    str(overall) + "%"
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

# Overview

overview = []

for i, result in enumerate(
    results,
    1
):

    overview.append({
        "Q": "Q" + str(i),
        "CLO": result["CLO"],
        "CLO Alignment":
            str(result["CLO Score"]) + "%",
        "PLO": result["PLO"],
        "PLO Alignment":
            str(result["PLO Score"]) + "%",
        "Expected Bloom":
            result["Expected Bloom"],
        "Detected Bloom":
            result["Detected Bloom"],
        "Marks":
            result["Marks"],
        "Review Score":
            str(review_score(result)) + "%"
    })

st.subheader(
    "Question Overview"
)

st.dataframe(
    pd.DataFrame(overview),
    use_container_width=True,
    hide_index=True
)

# Detailed review

st.subheader(
    "3. Detailed Question Review"
)

for i, result in enumerate(
    results,
    1
):

    with st.expander(
        "Q"
        + str(i)
        + " — Review Score: "
        + str(review_score(result))
        + "%"
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
            str(result["CLO Score"]) + "%"
        )

        x2.metric(
            "PLO Alignment",
            str(result["PLO Score"]) + "%"
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
            "**Selected CLO:** "
            + result["CLO"]
        )

        st.write(
            "**Selected PLO:** "
            + result["PLO"]
        )

        st.write(
            "**Expected Bloom:** "
            + result["Expected Bloom"]
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

        revised = st.text_area(
            "Edit this question and re-check it",
            value=result["Question"],
            key="revision_" + str(i),
            height=120
        )

        if st.button(
            "🔄 Re-check Q" + str(i),
            key="recheck_" + str(i)
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
                str(old_score) + "%"
            )

            z2.metric(
                "Revised",
                str(new_score) + "%"
            )

            z3.metric(
                "Change",
                "{:+d}%".format(
                    new_score - old_score
                )
            )

            st.write(
                "**CLO:** "
                + new_result["CLO"]
                + " ("
                + str(new_result["CLO Score"])
                + "%)"
            )

            st.write(
                "**PLO:** "
                + new_result["PLO"]
                + " ("
                + str(new_result["PLO Score"])
                + "%)"
            )

            st.write(
                "**Bloom:** "
                + new_result["Detected Bloom"]
            )

# Bloom chart

st.subheader(
    "4. Bloom's Taxonomy Distribution"
)

bloom_counts = {}

for result in results:

    level = result[
        "Detected Bloom"
    ]

    bloom_counts[level] = (
        bloom_counts.get(level, 0)
        \+ 1
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

# CLO coverage

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
        "Coverage %": round(
            count
            / len(results)
            * 100,
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

# Download report

st.subheader(
    "6. Download Review Report"
)

report = []

for i, result in enumerate(
    results,
    1
):

    report.append({
        "Question No.": i,
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

st.download_button(
    "⬇️ Download CSV Report",
    report_df.to_csv(
        index=False
    ).encode("utf-8"),
    "OBE_Alignment_Review.csv",
    "text/csv",
    use_container_width=True
)

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

except Exception:

    st.caption(
        "Excel export unavailable. "
        "CSV export is available."
    )
```

# ============================================================

# FINAL FACULTY CHECKLIST

# ============================================================

st.divider()

with st.expander(
"✅ Faculty Final Review Checklist"
):

```
checklist = [
    "Each question measures a clearly identified CLO.",
    "The selected PLO genuinely reflects the assessed skill.",
    "The action verb matches the intended Bloom level.",
    "Marks are appropriate for the task.",
    "Important CLOs receive suitable assessment coverage.",
    "Questions assess taught content.",
    "The marking scheme or rubric matches the question.",
    "The teacher has reviewed and approved the final wording."
]

for i, item in enumerate(checklist):

    st.checkbox(
        item,
        key="faculty_check_" + str(i)
    )
```

st.caption(
"OBE Alignment Checker • "
"Faculty judgment remains central to the final assessment."
)
