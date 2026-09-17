import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="OBE Alignment Checker", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.main-title {font-size:34px;font-weight:800;margin-bottom:4px;}
.sub-title {color:#666;font-size:16px;margin-bottom:20px;}
.good {padding:10px;border-radius:8px;background:#eaf7ee;}
.warn {padding:10px;border-radius:8px;background:#fff6df;}
.bad {padding:10px;border-radius:8px;background:#fdecec;}
</style>
""", unsafe_allow_html=True)

BLOOM_VERBS = {
    "Remember": ["define","identify","list","name","recall","state","mention","recognize","select"],
    "Understand": ["describe","explain","summarize","interpret","classify","discuss","illustrate","outline","paraphrase"],
    "Apply": ["apply","calculate","demonstrate","use","solve","implement","execute","practice","compute"],
    "Analyze": ["analyze","analyse","compare","contrast","differentiate","examine","investigate","categorize","distinguish"],
    "Evaluate": ["evaluate","assess","justify","critique","judge","defend","argue","recommend","appraise"],
    "Create": ["create","design","develop","construct","formulate","propose","produce","generate","plan"]
}

STOPWORDS = {
    "the","and","for","with","from","that","this","what","which","where","when","how","why",
    "are","was","were","has","have","had","will","would","should","could","can","may","into",
    "about","your","their","them","than","then","also","using","used","following","given",
    "question","questions"
}

def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()

def meaningful_words(text):
    all_words = set(re.findall(r"[a-zA-Z]{3,}", clean_text(text).lower()))
    return all_words - STOPWORDS

def detect_bloom(question):
    q = clean_text(question).lower()
    found = []
    for level, verbs in BLOOM_VERBS.items():
        if any(re.search(r"\b" + re.escape(v) + r"\b", q) for v in verbs):
            found.append(level)
    if not found:
        return "Not detected"
    order = ["Remember","Understand","Apply","Analyze","Evaluate","Create"]
    for level in reversed(order):
        if level in found:
            return level
    return found[0]

def extract_marks(question):
    patterns = [
        r"\(\s*(\d+(?:\.\d+)?)\s*marks?\s*\)",
        r"\[\s*(\d+(?:\.\d+)?)\s*marks?\s*\]",
        r"(\d+(?:\.\d+)?)\s*marks?\b",
        r"\(\s*(\d+(?:\.\d+)?)\s*\)"
    ]
    for pattern in patterns:
        match = re.search(pattern, question, re.I)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                pass
    return None

def parse_questions(text):
    text = text.replace("\r\n","\n").replace("\r","\n")
    numbered = re.findall(
        r"(?is)(?:^|\n)\s*(?:Question\s*)?(\d+)\s*[\.\):\-]\s*(.*?)(?=\n\s*(?:Question\s*)?\d+\s*[\.\):\-]\s*|$)",
        text
    )
    questions = [clean_text(item[1]) for item in numbered if len(clean_text(item[1])) >= 10]
    if questions:
        return questions

    lines = [clean_text(x) for x in text.split("\n") if len(clean_text(x)) >= 20]
    return lines

def extract_pdf(file):
    try:
        from pypdf import PdfReader
        reader = PdfReader(file)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as e:
        return "ERROR: Could not read PDF. " + str(e)

def extract_docx(file):
    try:
        from docx import Document
        doc = Document(file)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    except Exception as e:
        return "ERROR: Could not read DOCX. " + str(e)

def extract_excel(file):
    try:
        sheets = pd.ExcelFile(file)
        parts = []
        for sheet in sheets.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet, header=None)
            parts.append("Sheet: " + sheet)
            parts.append(df.fillna("").astype(str).to_string(index=False, header=False))
        return "\n".join(parts)
    except Exception as e:
        return "ERROR: Could not read Excel. " + str(e)

def extract_uploaded_file(file):
    name = file.name.lower()
    if name.endswith(".pdf"):
        return extract_pdf(file)
    if name.endswith(".docx"):
        return extract_docx(file)
    if name.endswith((".xlsx",".xls")):
        return extract_excel(file)
    if name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")
    return ""

def alignment_score(question, outcome):
    q = meaningful_words(question)
    o = meaningful_words(outcome)
    if not q or not o:
        return 0
    overlap = q & o
    return min(100, round(len(overlap) / max(1, min(len(o), 8)) * 100))

def best_outcome(question, outcomes):
    if not outcomes:
        return "Not identified", 0
    scored = [(x, alignment_score(question, x)) for x in outcomes]
    return max(scored, key=lambda x: x[1])

def parse_bloom_mapping(text):
    result = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        clo, bloom = line.split(":", 1)
        bloom = bloom.strip().title()
        if bloom in BLOOM_VERBS:
            result[clo.strip()] = bloom
    return result

def evaluate_question(question, clos, plos, bloom_mapping):
    bloom = detect_bloom(question)
    marks = extract_marks(question)
    clo, clo_score = best_outcome(question, clos)
    plo, plo_score = best_outcome(question, plos)

    expected = bloom_mapping.get(clo)
    bloom_match = "Review"

    if expected:
        bloom_match = "Yes" if bloom == expected else "Review"

    suggestions = []

    if clo_score < 30:
        suggestions.append("Strengthen the connection with the selected CLO by making the intended skill or concept more explicit.")
    elif clo_score < 60:
        suggestions.append("Review whether the question directly measures the selected CLO rather than only covering a related topic.")

    if plo_score < 20:
        suggestions.append("Review the PLO mapping. The question wording does not strongly indicate the selected PLO.")
    elif plo_score < 50:
        suggestions.append("Check whether the assessed skill is clearly represented in the selected PLO.")

    if bloom == "Not detected":
        suggestions.append("Use a clear Bloom action verb such as explain, apply, analyze, evaluate, or design.")

    if expected and bloom != expected:
        suggestions.append(f"Revise the task if necessary so that it actually requires the intended Bloom level: {expected}.")

    if marks is None:
        suggestions.append("Add marks to make the assessment weight clear.")
    elif marks <= 1 and bloom in ["Analyze","Evaluate","Create"]:
        suggestions.append("Review whether the marks are sufficient for the cognitive demand of the task.")

    if not suggestions:
        suggestions.append("The question shows reasonable alignment indicators. Faculty review is still required.")

    return {
        "Question": question,
        "CLO": clo,
        "CLO Score": clo_score,
        "PLO": plo,
        "PLO Score": plo_score,
        "Expected Bloom": expected or "Not specified",
        "Detected Bloom": bloom,
        "Marks": marks if marks is not None else "Not specified",
        "Bloom Match": bloom_match,
        "Suggestions": suggestions
    }

def review_score(r):
    bloom = 100 if r["Bloom Match"] == "Yes" else 50
    marks = 100 if r["Marks"] != "Not specified" else 50
    return round(r["CLO Score"]*.45 + r["PLO Score"]*.25 + bloom*.20 + marks*.10)

if "questions" not in st.session_state:
    st.session_state.questions = []
if "results" not in st.session_state:
    st.session_state.results = None

st.markdown('<div class="main-title">🎯 OBE Alignment Checker</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Upload an existing assessment and review CLO, PLO, Bloom’s Taxonomy, and marks alignment.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Assessment Setup")
    course = st.text_input("Course Name", placeholder="e.g., English I")

    st.subheader("CLOs")
    clo_text = st.text_area(
        "Enter one CLO per line",
        placeholder="CLO1: Identify main ideas\nCLO2: Analyze patterns of organization\nCLO3: Apply paraphrasing skills",
        height=150
    )

    st.subheader("PLOs")
    plo_text = st.text_area(
        "Enter one PLO per line",
        placeholder="PLO1: Knowledge\nPLO2: Problem Analysis\nPLO3: Communication Skills",
        height=120
    )

    st.subheader("Expected Bloom Levels")
    bloom_text = st.text_area(
        "Optional",
        placeholder="CLO1: Understand\nCLO2: Analyze\nCLO3: Apply",
        height=100
    )

clos = [clean_text(x) for x in clo_text.splitlines() if clean_text(x)]
plos = [clean_text(x) for x in plo_text.splitlines() if clean_text(x)]
bloom_mapping = parse_bloom_mapping(bloom_text)

st.subheader("1. Upload Your Existing Assessment")
uploaded = st.file_uploader("Upload Quiz / Assignment / Exam", type=["pdf","docx","xlsx","xls","txt"])

if uploaded:
    st.success("Uploaded: " + uploaded.name)

    if st.button("📄 Read Assessment", use_container_width=True):
        extracted = extract_uploaded_file(uploaded)
        if extracted.startswith("ERROR:"):
            st.error(extracted)
        else:
            questions = parse_questions(extracted)
            st.session_state.questions = questions
            st.session_state.results = None
            if questions:
                st.success(f"{len(questions)} questions detected.")
                with st.expander("Preview extracted questions"):
                    for i, q in enumerate(questions, 1):
                        st.write(f"**Q{i}.** {q}")
            else:
                st.warning("No questions were detected. Try a numbered DOCX/TXT file.")

analyze = st.button("🔍 Analyze Assessment", type="primary", use_container_width=True)

if analyze:
    if not uploaded:
        st.warning("Please upload an assessment first.")
    elif not clos:
        st.warning("Please enter at least one CLO.")
    elif not plos:
        st.warning("Please enter at least one PLO.")
    elif not st.session_state.questions:
        st.warning("Please click 'Read Assessment' first.")
    else:
        st.session_state.results = [
            evaluate_question(q, clos, plos, bloom_mapping)
            for q in st.session_state.questions
        ]

if st.session_state.results:
    results = st.session_state.results
    scores = [review_score(x) for x in results]
    overall = round(sum(scores)/len(scores))
    strong = sum(x >= 70 for x in scores)

    st.divider()
    st.subheader("2. Alignment Results")

    a,b,c,d = st.columns(4)
    a.metric("Overall Review Score", f"{overall}%")
    b.metric("Questions", len(results))
    c.metric("Reasonably Aligned", strong)
    d.metric("Needs Review", len(results)-strong)

    st.info("This tool is a review aid. Faculty should make the final academic decision about CLO, PLO, Bloom, marks, content, and wording.")

    overview = []
    for i,r in enumerate(results,1):
        overview.append({
            "Q": f"Q{i}",
            "CLO": r["CLO"],
            "CLO Alignment": f'{r["CLO Score"]}%',
            "PLO": r["PLO"],
            "PLO Alignment": f'{r["PLO Score"]}%',
            "Expected Bloom": r["Expected Bloom"],
            "Detected Bloom": r["Detected Bloom"],
            "Marks": r["Marks"],
            "Review Score": f'{review_score(r)}%'
        })

    st.subheader("Question Overview")
    st.dataframe(pd.DataFrame(overview), use_container_width=True, hide_index=True)

    st.subheader("3. Detailed Question Review")

    for i,r in enumerate(results,1):
        with st.expander(f"Q{i} — Review Score: {review_score(r)}%"):
            st.markdown("**Question**")
            st.write(r["Question"])

            x1,x2,x3,x4 = st.columns(4)
            x1.metric("CLO Alignment", f'{r["CLO Score"]}%')
            x2.metric("PLO Alignment", f'{r["PLO Score"]}%')
            x3.metric("Detected Bloom", r["Detected Bloom"])
            x4.metric("Marks", r["Marks"])

            st.write(f"**Selected CLO:** {r['CLO']}")
            st.write(f"**Selected PLO:** {r['PLO']}")
            st.write(f"**Expected Bloom:** {r['Expected Bloom']}")

            score = review_score(r)
            if score >= 70:
                st.markdown('<div class="good"><b>Initial review:</b> several alignment indicators are present.</div>', unsafe_allow_html=True)
            elif score >= 40:
                st.markdown('<div class="warn"><b>Initial review:</b> some alignment indicators are present; review the question.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="bad"><b>Initial review:</b> important alignment areas require review.</div>', unsafe_allow_html=True)

            st.markdown("**Suggested Improvements**")
            for s in r["Suggestions"]:
                st.write("• " + s)

            revised = st.text_area("Edit this question and re-check it", value=r["Question"], key=f"rev_{i}", height=130)

            if st.button(f"🔄 Re-check Q{i}", key=f"check_{i}"):
                new = evaluate_question(revised, clos, plos, bloom_mapping)
                old_score = review_score(r)
                new_score = review_score(new)

                z1,z2,z3 = st.columns(3)
                z1.metric("Previous", f"{old_score}%")
                z2.metric("Revised", f"{new_score}%")
                z3.metric("Change", f"{new_score-old_score:+d}%")

                st.write(f"**CLO:** {new['CLO']} ({new['CLO Score']}%)")
                st.write(f"**PLO:** {new['PLO']} ({new['PLO Score']}%)")
                st.write(f"**Bloom:** {new['Detected Bloom']}")

                for s in new["Suggestions"]:
                    st.write("• " + s)

    st.subheader("4. Bloom's Taxonomy Distribution")
    bloom_counts = {}
    for r in results:
        bloom_counts[r["Detected Bloom"]] = bloom_counts.get(r["Detected Bloom"],0)+1
    bloom_df = pd.DataFrame(list(bloom_counts.items()), columns=["Bloom Level","Questions"])
    if not bloom_df.empty:
        st.bar_chart(bloom_df.set_index("Bloom Level"))

    st.subheader("5. CLO Coverage")
    clo_counts = {clo:0 for clo in clos}
    for r in results:
        if r["CLO"] in clo_counts:
            clo_counts[r["CLO"]] += 1

    clo_df = pd.DataFrame([
        {"CLO":clo, "Questions":count, "Coverage %":round(count/len(results)*100,1)}
        for clo,count in clo_counts.items()
    ])
    st.dataframe(clo_df, use_container_width=True, hide_index=True)

    st.subheader("6. Download Review Report")

    report = []
    for i,r in enumerate(results,1):
        report.append({
            "Question No.":i,
            "Question":r["Question"],
            "CLO":r["CLO"],
            "CLO Alignment %":r["CLO Score"],
            "PLO":r["PLO"],
            "PLO Alignment %":r["PLO Score"],
            "Expected Bloom":r["Expected Bloom"],
            "Detected Bloom":r["Detected Bloom"],
            "Marks":r["Marks"],
            "Bloom Review":r["Bloom Match"],
            "Review Score %":review_score(r),
            "Suggestions":" | ".join(r["Suggestions"])
        })

    report_df = pd.DataFrame(report)
    st.download_button(
        "⬇️ Download CSV Report",
        report_df.to_csv(index=False).encode("utf-8"),
        "OBE_Alignment_Review.csv",
        "text/csv",
        use_container_width=True
    )

    try:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            report_df.to_excel(writer,index=False,sheet_name="Question Review")
            clo_df.to_excel(writer,index=False,sheet_name="CLO Coverage")
            bloom_df.to_excel(writer,index=False,sheet_name="Bloom Distribution")

        st.download_button(
            "📊 Download Excel Report",
            buffer.getvalue(),
            "OBE_Alignment_Review.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    except Exception:
        st.caption("Excel export is unavailable; CSV export is available.")

st.divider()
with st.expander("✅ Faculty Final Review Checklist"):
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
    for i,item in enumerate(checks):
        st.checkbox(item, key=f"final_{i}")

st.caption("OBE Alignment Checker • Faculty judgment remains central to the final assessment.")
