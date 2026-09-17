import streamlit as st
import pandas as pd
import re

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="OBE Assessment Studio",
    page_icon="🎓",
    layout="wide"
)

# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>
.main-title {
    font-size: 38px;
    font-weight: 800;
    margin-bottom: 5px;
}

.subtitle {
    font-size: 17px;
    color: #666;
    margin-bottom: 25px;
}

.section-title {
    font-size: 24px;
    font-weight: 700;
    margin-top: 25px;
    margin-bottom: 12px;
}

.score-box {
    padding: 20px;
    border-radius: 12px;
    text-align: center;
    border: 1px solid #ddd;
    margin: 8px 0;
}

.big-score {
    font-size: 42px;
    font-weight: 800;
}

.good {
    background-color: #eaf7ee;
    border-left: 6px solid #2e8b57;
}

.medium {
    background-color: #fff8e6;
    border-left: 6px solid #e0a000;
}

.low {
    background-color: #fdecec;
    border-left: 6px solid #d9534f;
}

.info-box {
    background-color: #f2f7ff;
    padding: 15px;
    border-radius: 10px;
    border-left: 5px solid #3182ce;
}

.warning-box {
    background-color: #fff8e6;
    padding: 15px;
    border-radius: 10px;
    border-left: 5px solid #e0a000;
}

.success-box {
    background-color: #eaf7ee;
    padding: 15px;
    border-radius: 10px;
    border-left: 5px solid #2e8b57;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# CONSTANTS
# =========================================================

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]

QUESTION_TYPES = [
    "Short Answer",
    "Essay / Written",
    "Problem Solving",
    "MCQ",
    "Oral Presentation / Speaking",
    "Viva / Oral Question",
    "Debate / Discussion",
    "Practical / Laboratory",
    "Case Study",
    "Project / Task"
]

# =========================================================
# SESSION STATE
# =========================================================

defaults = {
    "question": "",
    "answer": "",
    "marking_scheme": "",
    "checked": False,
    "approval": "",
    "alignment_data": None
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def clean_text(text):
    if text is None:
        return ""

    return re.sub(
        r"[^a-z0-9\s]",
        " ",
        str(text).lower()
    )


def word_count(text):
    return len(str(text).split())


def contains_any(text, terms):
    text = clean_text(text)

    return any(term in text for term in terms)


# =========================================================
# BLOOM DETECTION
# =========================================================

BLOOM_VERBS = {
    "Remember": [
        "define",
        "list",
        "name",
        "identify",
        "recall",
        "state",
        "recognize"
    ],

    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "classify",
        "discuss",
        "illustrate"
    ],

    "Apply": [
        "calculate",
        "solve",
        "apply",
        "demonstrate",
        "use",
        "implement",
        "perform"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate",
        "categorize",
        "distinguish"
    ],

    "Evaluate": [
        "evaluate",
        "justify",
        "assess",
        "critique",
        "defend",
        "argue",
        "judge",
        "take a position",
        "give your opinion",
        "do you think",
        "agree or disagree",
        "support your position"
    ],

    "Create": [
        "design",
        "create",
        "develop",
        "construct",
        "formulate",
        "produce",
        "propose",
        "develop a"
    ]
}


def detect_bloom(question):

    q = clean_text(question)

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if verb in q:
                return level

    return "Not clearly detected"


def check_bloom_alignment(selected_bloom, question):

    if not selected_bloom:
        return 0, "Bloom's level has not been selected."

    if not question:
        return 0, "Question is missing."

    detected = detect_bloom(question)

    if detected == selected_bloom:
        return 100, (
            f"The wording clearly supports the selected "
            f"Bloom's level: {selected_bloom}."
        )

    # Special evaluation language
    if selected_bloom == "Evaluate":

        evaluation_phrases = [
            "take a position",
            "give your opinion",
            "justify",
            "support your position",
            "do you think",
            "agree or disagree",
            "defend",
            "argue",
            "critique",
            "assess",
            "evaluate"
        ]

        if any(p in clean_text(question) for p in evaluation_phrases):
            return 100, (
                "The question requires judgment, justification, "
                "or a supported position."
            )

    # Special analysis language
    if selected_bloom == "Analyze":

        analysis_phrases = [
            "compare",
            "contrast",
            "analyze",
            "analyse",
            "examine",
            "differentiate",
            "relationship",
            "cause and effect"
        ]

        if any(p in clean_text(question) for p in analysis_phrases):
            return 100, (
                "The question requires analysis of information, "
                "relationships, or differences."
            )

    # Special application language
    if selected_bloom == "Apply":

        application_phrases = [
            "calculate",
            "solve",
            "apply",
            "use",
            "demonstrate",
            "perform",
            "implement"
        ]

        if any(p in clean_text(question) for p in application_phrases):
            return 100, (
                "The question requires application of knowledge."
            )

    # Teacher-selected Bloom is not automatically perfect,
    # but we allow a reasonable advisory score.
    return 75, (
        f"The selected Bloom level is {selected_bloom}, "
        f"but the wording does not strongly show that level. "
        f"Consider revising the action verb."
    )


# =========================================================
# CLO ALIGNMENT
# =========================================================

def check_clo_alignment(clo, question, qtype):

    if not clo or not question:
        return 0, "CLO or question is missing."

    clo_text = clean_text(clo)
    q_text = clean_text(question)
    qtype_text = clean_text(qtype)

    # -----------------------------------------------------
    # SPEAKING / ORAL CLO
    # -----------------------------------------------------

    speaking_clo = contains_any(
        clo_text,
        [
            "speaking",
            "oral communication",
            "oral",
            "speak",
            "spoken",
            "presentation",
            "communicate ideas clearly",
            "communicate ideas",
            "communication skills",
            "oral skills"
        ]
    )

    if speaking_clo:

        direct_oral_types = [
            "oral presentation",
            "speaking",
            "viva",
            "oral question",
            "debate",
            "discussion"
        ]

        written_types = [
            "essay",
            "written",
            "short answer",
            "problem solving",
            "mcq",
            "case study"
        ]

        if any(term in qtype_text for term in direct_oral_types):

            # Also verify that question contains an oral action
            oral_question_terms = [
                "speak",
                "present",
                "oral",
                "viva",
                "debate",
                "discuss verbally",
                "give a presentation",
                "deliver a presentation",
                "explain orally"
            ]

            if any(term in q_text for term in oral_question_terms):
                return 100, (
                    "The question directly assesses speaking/oral "
                    "performance."
                )

            return 90, (
                "The selected question type assesses speaking, "
                "but the question wording could make the oral "
                "requirement more explicit."
            )

        if any(term in qtype_text for term in written_types):

            return 25, (
                "The CLO focuses on speaking, but this assessment "
                "primarily measures written performance."
            )

        if any(term in q_text for term in [
            "speak",
            "present",
            "oral",
            "viva",
            "debate"
        ]):

            return 85, (
                "The question contains an identifiable speaking "
                "component."
            )

        return 35, (
            "The question does not clearly assess speaking "
            "performance."
        )

    # -----------------------------------------------------
    # WRITING CLO
    # -----------------------------------------------------

    writing_clo = contains_any(
        clo_text,
        [
            "writing",
            "written",
            "essay",
            "write",
            "composition",
            "written communication"
        ]
    )

    if writing_clo:

        if any(term in qtype_text for term in [
            "essay",
            "written",
            "writing",
            "short answer"
        ]):

            return 100, (
                "The assessment directly measures written "
                "communication."
            )

        if any(term in qtype_text for term in [
            "oral presentation",
            "speaking",
            "viva",
            "debate"
        ]):

            return 25, (
                "The CLO focuses on writing, but the assessment "
                "mainly measures oral performance."
            )

        return 55, (
            "The question provides only partial evidence of "
            "the writing CLO."
        )

    # -----------------------------------------------------
    # READING CLO
    # -----------------------------------------------------

    reading_clo = contains_any(
        clo_text,
        [
            "reading",
            "read",
            "comprehension",
            "interpret text"
        ]
    )

    if reading_clo:

        if any(term in qtype_text for term in [
            "reading",
            "comprehension",
            "short answer",
            "analysis",
            "case study"
        ]):

            return 100, (
                "The assessment directly measures reading/"
                "comprehension."
            )

        return 45, (
            "The assessment provides limited evidence of "
            "reading ability."
        )

    # -----------------------------------------------------
    # LISTENING CLO
    # -----------------------------------------------------

    listening_clo = contains_any(
        clo_text,
        [
            "listening",
            "listen",
            "understand spoken",
            "listening skills"
        ]
    )

    if listening_clo:

        if any(term in qtype_text for term in [
            "listening",
            "audio",
            "oral comprehension"
        ]):

            return 100, (
                "The assessment directly measures listening."
            )

        return 30, (
            "The CLO focuses on listening, but the assessment "
            "does not directly measure listening."
        )

    # -----------------------------------------------------
    # GENERAL CLO
    # -----------------------------------------------------

    clo_keywords = set(
        re.findall(
            r"\b[a-z]{4,}\b",
            clo_text
        )
    )

    question_keywords = set(
        re.findall(
            r"\b[a-z]{4,}\b",
            q_text
        )
    )

    common = clo_keywords.intersection(question_keywords)

    if len(common) >= 4:
        return 85, (
            "The question shows strong evidence of the "
            "selected CLO."
        )

    if len(common) >= 2:
        return 70, (
            "The question shows reasonable evidence of "
            "the selected CLO."
        )

    if len(common) >= 1:
        return 55, (
            "The question shows partial evidence of "
            "the selected CLO."
        )

    return 35, (
        "The question does not clearly demonstrate "
        "the selected CLO."
    )


# =========================================================
# PLO ALIGNMENT
# =========================================================

def check_plo_alignment(clo, plo, question, qtype):

    if not plo or not question:
        return 0, "PLO or question is missing."

    plo_text = clean_text(plo)
    q_text = clean_text(question)
    qtype_text = clean_text(qtype)

    # -----------------------------------------------------
    # ORAL COMMUNICATION PLO
    # -----------------------------------------------------

    oral_plo = contains_any(
        plo_text,
        [
            "oral communication",
            "oral",
            "speaking",
            "spoken communication",
            "communicate orally",
            "presentation",
            "communication skills",
            "oral skills"
        ]
    )

    if oral_plo:

        oral_types = [
            "oral presentation",
            "speaking",
            "viva",
            "debate",
            "discussion",
            "oral question"
        ]

        written_types = [
            "essay",
            "written",
            "short answer",
            "mcq",
            "problem solving"
        ]

        if any(term in qtype_text for term in oral_types):

            oral_action = [
                "speak",
                "present",
                "oral",
                "viva",
                "debate",
                "discuss verbally",
                "give a presentation",
                "deliver a presentation",
                "explain orally"
            ]

            if any(term in q_text for term in oral_action):

                return 100, (
                    "The assessment directly provides evidence "
                    "of oral communication."
                )

            return 90, (
                "The question type supports oral communication, "
                "but the wording could make the oral task clearer."
            )

        if any(term in qtype_text for term in written_types):

            return 25, (
                "The PLO focuses on oral communication, while "
                "this assessment is primarily written."
            )

        return 35, (
            "The assessment does not clearly demonstrate "
            "oral communication."
        )

    # -----------------------------------------------------
    # WRITTEN COMMUNICATION PLO
    # -----------------------------------------------------

    written_plo = contains_any(
        plo_text,
        [
            "written communication",
            "writing",
            "written",
            "written skills"
        ]
    )

    if written_plo:

        if any(term in qtype_text for term in [
            "essay",
            "written",
            "short answer",
            "writing"
        ]):

            return 100, (
                "The assessment directly provides evidence "
                "of written communication."
            )

        if any(term in qtype_text for term in [
            "oral presentation",
            "speaking",
            "viva",
            "debate"
        ]):

            return 25, (
                "The PLO focuses on written communication, "
                "but this assessment is primarily oral."
            )

        return 50, (
            "The assessment provides partial evidence "
            "toward written communication."
        )

    # -----------------------------------------------------
    # GENERAL PLO
    # -----------------------------------------------------

    clo_words = set(
        re.findall(
            r"\b[a-z]{4,}\b",
            clean_text(clo)
        )
    )

    plo_words = set(
        re.findall(
            r"\b[a-z]{4,}\b",
            plo_text
        )
    )

    question_words = set(
        re.findall(
            r"\b[a-z]{4,}\b",
            q_text
        )
    )

    plo_question_overlap = plo_words.intersection(
        question_words
    )

    clo_plo_overlap = clo_words.intersection(
        plo_words
    )

    if (
        len(plo_question_overlap) >= 2
        and len(clo_plo_overlap) >= 1
    ):

        return 85, (
            "The assessment provides strong evidence "
            "toward the selected PLO."
        )

    if len(plo_question_overlap) >= 1:

        return 65, (
            "The assessment provides partial evidence "
            "toward the selected PLO."
        )

    return 40, (
        "The assessment does not clearly demonstrate "
        "the selected PLO."
    )


# =========================================================
# QUESTION TYPE CHECK
# =========================================================

def check_question_type(clo, question, qtype):

    if not question:
        return 0, "Question is missing."

    clo_text = clean_text(clo)
    qtype_text = clean_text(qtype)
    q_text = clean_text(question)

    speaking_clo = contains_any(
        clo_text,
        [
            "speaking",
            "oral",
            "presentation",
            "oral communication"
        ]
    )

    writing_clo = contains_any(
        clo_text,
        [
            "writing",
            "written",
            "essay"
        ]
    )

    if speaking_clo:

        if any(term in qtype_text for term in [
            "oral presentation",
            "speaking",
            "viva",
            "debate",
            "discussion"
        ]):

            return 100, (
                "Question type is appropriate for the speaking CLO."
            )

        return 30, (
            "The question type does not directly measure "
            "speaking."
        )

    if writing_clo:

        if any(term in qtype_text for term in [
            "essay",
            "written",
            "writing",
            "short answer"
        ]):

            return 100, (
                "Question type is appropriate for the writing CLO."
            )

        return 35, (
            "The question type does not directly measure "
            "writing."
        )

    return 100, (
        "Question type is acceptable for the selected CLO."
    )


# =========================================================
# DIFFICULTY
# =========================================================

def get_difficulty(bloom):

    if bloom in ["Remember", "Understand"]:
        return "Easy"

    if bloom in ["Apply", "Analyze"]:
        return "Moderate"

    if bloom in ["Evaluate", "Create"]:
        return "Challenging"

    return "Moderate"


# =========================================================
# MARK REVIEW
# =========================================================

def review_marks(marks, qtype, bloom):

    if marks <= 0:
        return "Please enter valid marks."

    if qtype == "MCQ":

        if marks > 2:
            return (
                "For an MCQ, consider whether the marks are "
                "appropriate for the expected response."
            )

        return "Marks appear reasonable for an MCQ."

    if qtype in [
        "Oral Presentation / Speaking",
        "Viva / Oral Question"
    ]:

        if marks < 3:
            return (
                "Very low marks may not provide enough evidence "
                "for an oral performance."
            )

        return (
            "Marks appear reasonable. Ensure the rubric covers "
            "the intended speaking skills."
        )

    if bloom in ["Evaluate", "Create"] and marks < 5:

        return (
            "Higher-order tasks may require enough marks to "
            "provide meaningful evidence."
        )

    return "Marks appear reasonable. Marks are advisory and do not reduce OBE alignment."


# =========================================================
# QUESTION GENERATOR
# =========================================================

def generate_question(
    topic,
    clo,
    plo,
    bloom,
    qtype,
    marks
):

    topic = topic.strip()
    clo = clo.strip()

    if not topic:
        topic = "the selected topic"

    if qtype == "Oral Presentation / Speaking":

        if bloom == "Evaluate":

            return (
                f"Do you think {topic} should be viewed as an "
                f"important issue in your field? Take a clear "
                f"position and explain your opinion in a "
                f"2–3 minute oral presentation. Support your "
                f"position with at least two relevant reasons "
                f"and examples."
            )

        if bloom == "Analyze":

            return (
                f"Give a short oral presentation analyzing "
                f"the major factors related to {topic}. "
                f"Explain the relationship between the factors "
                f"and support your explanation with relevant examples."
            )

        if bloom == "Apply":

            return (
                f"Give a short oral presentation demonstrating "
                f"how the principles of {topic} can be applied "
                f"in a real-world situation."
            )

        return (
            f"Give a {marks}-mark oral presentation explaining "
            f"the key concepts related to {topic}."
        )

    if qtype == "Viva / Oral Question":

        if bloom == "Evaluate":

            return (
                f"Do you think {topic} is effective in solving "
                f"a relevant problem? Give your position and "
                f"justify your answer with appropriate reasons."
            )

        if bloom == "Analyze":

            return (
                f"Explain the major factors related to {topic} "
                f"and analyze how they influence one another."
            )

        return (
            f"Explain {topic} verbally and provide an appropriate "
            f"example."
        )

    if qtype == "Debate / Discussion":

        if bloom == "Evaluate":

            return (
                f"Should {topic} be encouraged in your field? "
                f"Take a position and defend your view using "
                f"at least two relevant arguments."
            )

        return (
            f"Discuss the importance of {topic} and support "
            f"your views with relevant examples."
        )

    if qtype == "Essay / Written":

        if bloom == "Evaluate":

            return (
                f"Evaluate the significance of {topic}. "
                f"Present a clear position and support your "
                f"evaluation with relevant evidence and examples."
            )

        if bloom == "Analyze":

            return (
                f"Analyze {topic} by identifying its major "
                f"components, relationships, and implications."
            )

        if bloom == "Apply":

            return (
                f"Explain how the principles of {topic} can "
                f"be applied to a relevant real-world situation."
            )

        return (
            f"Write an organized response explaining the "
            f"important concepts related to {topic}."
        )

    if qtype == "Problem Solving":

        if bloom == "Analyze":

            return (
                f"Analyze the following problem related to "
                f"{topic}. Identify the relevant information, "
                f"show the required steps, and explain your conclusion."
            )

        if bloom == "Apply":

            return (
                f"Apply the relevant principles of {topic} "
                f"to solve the following problem. Show all "
                f"important steps."
            )

        return (
            f"Solve the following problem related to {topic} "
            f"and explain your answer."
        )

    if qtype == "Case Study":

        return (
            f"Read the following case related to {topic}. "
            f"Analyze the situation, identify the key issue, "
            f"and recommend an appropriate response."
        )

    if qtype == "Practical / Laboratory":

        return (
            f"Perform the required practical task related to "
            f"{topic}. Record the observations, apply the "
            f"relevant procedure, and explain the result."
        )

    if qtype == "Project / Task":

        return (
            f"Develop a practical task related to {topic}. "
            f"Explain your approach, implementation, and "
            f"expected outcome."
        )

    if qtype == "MCQ":

        return (
            f"Which of the following statements about "
            f"{topic} is correct?"
        )

    return (
        f"Explain the key concept of {topic} and provide "
        f"an appropriate example."
    )


# =========================================================
# ANSWER GENERATOR
# =========================================================

def generate_answer(
    topic,
    question,
    bloom,
    qtype
):

    # Special case: AI in exams
    if (
        "ai" in clean_text(question)
        and "exam" in clean_text(question)
        and bloom == "Evaluate"
    ):

        return (
            "Model Answer:\n\n"
            "AI may be allowed in exams under clearly defined "
            "conditions because it can support learning, "
            "research, and problem solving. However, unrestricted "
            "use may make it difficult to determine whether a "
            "student has independently achieved the intended "
            "learning outcomes. Therefore, a reasonable approach "
            "is to permit AI only when the assessment is designed "
            "to evaluate higher-order thinking, explanation, "
            "reflection, or application. Students should disclose "
            "how AI was used and remain responsible for the "
            "accuracy of their work."
        )

    if qtype in [
        "Oral Presentation / Speaking",
        "Viva / Oral Question",
        "Debate / Discussion"
    ]:

        return (
            "Recommended Answer:\n\n"
            "The student should clearly address the topic, "
            "present relevant ideas, provide appropriate "
            "reasons or evidence, and communicate the response "
            "in a logical and understandable manner."
        )

    return (
        "Recommended Answer:\n\n"
        "The response should accurately explain the relevant "
        "concepts, demonstrate understanding of the selected "
        "CLO, and provide appropriate evidence, examples, "
        "calculations, or reasoning where required."
    )


# =========================================================
# MARKING SCHEME
# =========================================================

def generate_marking_scheme(
    marks,
    qtype,
    bloom
):

    if qtype in [
        "Oral Presentation / Speaking",
        "Viva / Oral Question",
        "Debate / Discussion"
    ]:

        criteria = [
            ("Content and understanding", 20),
            ("Reasoning / analysis / supporting examples", 25),
            ("Organization and coherence", 20),
            ("Language and vocabulary", 15),
            ("Clarity, confidence and delivery", 20)
        ]

    elif bloom in ["Evaluate", "Create"]:

        criteria = [
            ("Understanding of the topic", 20),
            ("Analysis / reasoning", 25),
            ("Use of evidence or examples", 20),
            ("Organization and clarity", 20),
            ("Conclusion / judgment / originality", 15)
        ]

    elif qtype == "Problem Solving":

        criteria = [
            ("Correct method", 25),
            ("Application of relevant concepts", 25),
            ("Working / reasoning", 20),
            ("Accuracy of result", 20),
            ("Units / explanation", 10)
        ]

    else:

        criteria = [
            ("Understanding of content", 30),
            ("Accuracy", 25),
            ("Relevant explanation", 20),
            ("Examples / evidence", 15),
            ("Clarity", 10)
        ]

    rows = []

    for criterion, percentage in criteria:

        allocated_marks = marks * percentage / 100

        rows.append({
            "Criterion": criterion,
            "Marks": round(allocated_marks, 2),
            "Percentage": f"{percentage}%"
        })

    return pd.DataFrame(rows)


# =========================================================
# TWEAK QUESTION
# =========================================================

def tweak_question(question, mode):

    if not question:
        return ""

    if mode == "Make Easier":

        return (
            question
            + "\n\nUse simple language and provide clear instructions."
        )

    if mode == "Make Harder":

        return (
            question
            + "\n\nRequire the student to provide additional "
              "evidence, reasoning, or justification."
        )

    if mode == "More Analytical":

        return (
            question
            + "\n\nAnalyze the relationships, causes, differences, "
              "or implications involved in the response."
        )

    if mode == "More Application-Based":

        return (
            question
            + "\n\nApply the concept to a realistic or "
              "discipline-specific situation."
        )

    if mode == "More Critical Thinking":

        return (
            question
            + "\n\nEvaluate the available evidence and justify "
              "the conclusion."
        )

    if mode == "More Discipline-Specific":

        return (
            question
            + "\n\nUse appropriate terminology, concepts, "
              "and examples from the selected discipline."
        )

    return question


# =========================================================
# MAIN HEADER
# =========================================================

st.markdown(
    '<div class="main-title">🎓 OBE Assessment Studio</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Create, review and improve assessment questions using '
    'CLO, PLO, Bloom’s Taxonomy and assessment evidence.'
    '</div>',
    unsafe_allow_html=True
)

# =========================================================
# STEP 1 — COURSE
# =========================================================

st.markdown(
    '<div class="section-title">1. Course & Assessment Context</div>',
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)

with col1:

    course = st.text_input(
        "Course",
        placeholder="e.g., English I"
    )

with col2:

    topic = st.text_input(
        "Topic",
        placeholder="e.g., Oral Communication"
    )

with col3:

    marks = st.number_input(
        "Marks",
        min_value=1,
        max_value=100,
        value=5
    )

# =========================================================
# STEP 2 — CLO
# =========================================================

st.markdown(
    '<div class="section-title">2. Course Learning Outcome (CLO)</div>',
    unsafe_allow_html=True
)

clo = st.text_area(
    "Enter the CLO",
    placeholder=(
        "Example: Demonstrate the ability to communicate "
        "ideas clearly and confidently when speaking on "
        "a range of topics."
    ),
    height=110
)

# =========================================================
# STEP 3 — PLO
# =========================================================

st.markdown(
    '<div class="section-title">3. Program Learning Outcome (PLO)</div>',
    unsafe_allow_html=True
)

plo = st.text_area(
    "Enter the PLO",
    placeholder=(
        "Example: Demonstrate effective oral communication "
        "skills in academic and professional contexts."
    ),
    height=110
)

# =========================================================
# STEP 4 — BLOOM + TYPE
# =========================================================

st.markdown(
    '<div class="section-title">4. Assessment Design</div>',
    unsafe_allow_html=True
)

col1, col2 = st.columns(2)

with col1:

    bloom = st.selectbox(
        "Bloom's Taxonomy Level",
        BLOOM_LEVELS,
        index=4
    )

with col2:

    qtype = st.selectbox(
        "Question Type",
        QUESTION_TYPES
    )

# =========================================================
# QUESTION GENERATION
# =========================================================

st.markdown(
    '<div class="section-title">5. Assessment Question</div>',
    unsafe_allow_html=True
)

if st.button(
    "✨ GENERATE QUESTION",
    use_container_width=True
):

    if not clo:

        st.error("Please enter a CLO first.")

    elif not plo:

        st.error("Please enter a PLO first.")

    else:

        st.session_state.question = generate_question(
            topic,
            clo,
            plo,
            bloom,
            qtype,
            marks
        )

        st.session_state.answer = generate_answer(
            topic,
            st.session_state.question,
            bloom,
            qtype
        )

        st.session_state.marking_scheme = generate_marking_scheme(
            marks,
            qtype,
            bloom
        )

        st.session_state.checked = False
        st.session_state.approval = ""
        st.session_state.alignment_data = None

# =========================================================
# QUESTION EDITOR
# =========================================================

question = st.text_area(
    "Edit the question before checking alignment",
    value=st.session_state.question,
    height=180
)

st.session_state.question = question

# =========================================================
# TWEAK BUTTONS
# =========================================================

st.markdown("**Quick Question Tweaks**")

t1, t2, t3, t4, t5, t6 = st.columns(6)

tweak_options = [
    ("Make Easier", t1),
    ("Make Harder", t2),
    ("More Analytical", t3),
    ("More Application-Based", t4),
    ("More Critical Thinking", t5),
    ("More Discipline-Specific", t6)
]

for label, column in tweak_options:

    with column:

        if st.button(
            label,
            key=f"tweak_{label}",
            use_container_width=True
        ):

            st.session_state.question = tweak_question(
                st.session_state.question,
                label
            )

            st.rerun()

# =========================================================
# CHECK ALIGNMENT
# =========================================================

st.markdown(
    '<div class="section-title">6. OBE Alignment Check</div>',
    unsafe_allow_html=True
)

if st.button(
    "🔍 CHECK OBE ALIGNMENT",
    use_container_width=True
):

    if not clo:

        st.error("Please enter the CLO.")

    elif not plo:

        st.error("Please enter the PLO.")

    elif not question:

        st.error("Please enter or generate a question.")

    else:

        clo_score, clo_message = check_clo_alignment(
            clo,
            question,
            qtype
        )

        plo_score, plo_message = check_plo_alignment(
            clo,
            plo,
            question,
            qtype
        )

        bloom_score, bloom_message = check_bloom_alignment(
            bloom,
            question
        )

        type_score, type_message = check_question_type(
            clo,
            question,
            qtype
        )

        # IMPORTANT:
        # Marks and difficulty are NOT included.
        alignment_score = round(
            (
                clo_score
                + plo_score
                + bloom_score
                + type_score
            ) / 4,
            1
        )

        difficulty = get_difficulty(bloom)

        marks_message = review_marks(
            marks,
            qtype,
            bloom
        )

        st.session_state.alignment_data = {
            "CLO": clo_score,
            "PLO": plo_score,
            "Bloom": bloom_score,
            "Question Type": type_score,
            "Overall": alignment_score,
            "Difficulty": difficulty,
            "CLO Message": clo_message,
            "PLO Message": plo_message,
            "Bloom Message": bloom_message,
            "Type Message": type_message,
            "Marks Message": marks_message
        }

        st.session_state.checked = True

# =========================================================
# DISPLAY ALIGNMENT
# =========================================================

if st.session_state.checked:

    data = st.session_state.alignment_data

    st.markdown(
        '<div class="section-title">7. Alignment Result</div>',
        unsafe_allow_html=True
    )

    overall = data["Overall"]

    if overall >= 90:

        box_class = "good"
        result_text = "STRONG OBE ALIGNMENT"

    elif overall >= 75:

        box_class = "medium"
        result_text = "PARTIAL OBE ALIGNMENT"

    else:

        box_class = "low"
        result_text = "ALIGNMENT NEEDS REVISION"

    st.markdown(
        f"""
        <div class="score-box {box_class}">
            <div class="big-score">{overall}%</div>
            <strong>{result_text}</strong>
        </div>
        """,
        unsafe_allow_html=True
    )

    # -----------------------------------------------------
    # COMPONENT SCORES
    # -----------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "CLO Alignment",
            f"{data['CLO']}%"
        )

    with c2:

        st.metric(
            "PLO Alignment",
            f"{data['PLO']}%"
        )

    with c3:

        st.metric(
            "Bloom Alignment",
            f"{data['Bloom']}%"
        )

    with c4:

        st.metric(
            "Question Type",
            f"{data['Question Type']}%"
        )

    # -----------------------------------------------------
    # EXPLANATIONS
    # -----------------------------------------------------

    st.markdown(
        '<div class="section-title">Why did the tool give this score?</div>',
        unsafe_allow_html=True
    )

    st.info(
        f"**CLO:** {data['CLO']}% — {data['CLO Message']}"
    )

    st.info(
        f"**PLO:** {data['PLO']}% — {data['PLO Message']}"
    )

    st.info(
        f"**Bloom:** {data['Bloom']}% — {data['Bloom Message']}"
    )

    st.info(
        f"**Question Type:** {data['Question Type']}% — "
        f"{data['Type Message']}"
    )

    # -----------------------------------------------------
    # DIFFICULTY
    # -----------------------------------------------------

    st.markdown(
        '<div class="section-title">Difficulty</div>',
        unsafe_allow_html=True
    )

    difficulty = data["Difficulty"]

    if difficulty == "Easy":

        st.success(
            "🟢 Easy — mainly lower-order cognitive demand."
        )

    elif difficulty == "Moderate":

        st.info(
            "🟡 Moderate — requires application or analysis."
        )

    else:

        st.warning(
            "🟠 Challenging — requires evaluation or creation."
        )

    st.caption(
        "Important: Difficulty is reported separately and "
        "does not reduce the OBE alignment percentage."
    )

    # -----------------------------------------------------
    # MARKS
    # -----------------------------------------------------

    st.markdown(
        '<div class="section-title">Marks Review</div>',
        unsafe_allow_html=True
    )

    st.info(
        f"**{marks} marks:** {data['Marks Message']}"
    )

    st.caption(
        "Important: Marks are advisory and do not reduce "
        "the OBE alignment percentage."
    )

# =========================================================
# ANSWER
# =========================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">8. Recommended Answer</div>',
        unsafe_allow_html=True
    )

    answer = st.text_area(
        "Faculty can edit the recommended answer",
        value=st.session_state.answer,
        height=220,
        key="answer_editor"
    )

    st.session_state.answer = answer

# =========================================================
# MARKING SCHEME
# =========================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">9. Recommended Marking Scheme</div>',
        unsafe_allow_html=True
    )

    scheme = generate_marking_scheme(
        marks,
        qtype,
        bloom
    )

    st.session_state.marking_scheme = scheme

    st.dataframe(
        scheme,
        use_container_width=True,
        hide_index=True
    )

    total_marks = scheme["Marks"].sum()

    st.success(
        f"Total allocated marks: {round(total_marks, 2)} / {marks}"
    )

    st.caption(
        "Percentage represents the allocation of marks across "
        "criteria, not probability of correctness."
    )

# =========================================================
# FACULTY DECISION
# =========================================================

if st.session_state.checked:

    st.markdown(
        '<div class="section-title">10. Faculty Decision</div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "✅ APPROVE ASSESSMENT",
            use_container_width=True
        ):

            st.session_state.approval = "Approved"

    with col2:

        if st.button(
            "🔄 NEEDS REVISION",
            use_container_width=True
        ):

            st.session_state.approval = "Needs Revision"

    if st.session_state.approval == "Approved":

        st.success(
            "Assessment approved by faculty."
        )

    elif st.session_state.approval == "Needs Revision":

        st.warning(
            "Assessment marked for revision. Review the "
            "CLO/PLO alignment and question wording."
        )

# =========================================================
# SUMMARY
# =========================================================

if st.session_state.checked:

    data = st.session_state.alignment_data

    st.markdown(
        '<div class="section-title">11. Assessment Summary</div>',
        unsafe_allow_html=True
    )

    summary = pd.DataFrame([
        ["Course", course],
        ["Topic", topic],
        ["CLO", clo],
        ["PLO", plo],
        ["Bloom Level", bloom],
        ["Question Type", qtype],
        ["Marks", marks],
        ["Difficulty", data["Difficulty"]],
        ["CLO Alignment", f"{data['CLO']}%"],
        ["PLO Alignment", f"{data['PLO']}%"],
        ["Bloom Alignment", f"{data['Bloom']}%"],
        ["Question Type Alignment", f"{data['Question Type']}%"],
        ["Overall OBE Alignment", f"{data['Overall']}%"],
        ["Faculty Decision", st.session_state.approval or "Pending"]
    ], columns=["Item", "Value"])

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )

# =========================================================
# IMPORTANT EXAMPLE
# =========================================================

with st.expander("💡 Example: Speaking CLO vs Written Question"):

    st.markdown("""
### CLO
**Demonstrate the ability to communicate ideas clearly and confidently when speaking on a range of topics.**

### PLO
**Demonstrate effective oral communication skills in academic and professional contexts.**

### ❌ Poorly aligned question

**Question Type:** Essay / Written

> Write a 200-word paragraph explaining your opinion about AI.

This should **not** receive 100% CLO/PLO alignment because the student is demonstrating writing rather than speaking.

### ✅ Strongly aligned question

**Question Type:** Oral Presentation / Speaking

> Do you think the use of AI should be allowed in exams? Take a clear position and explain your opinion in a 2–3 minute oral presentation. Support your position with at least two relevant reasons and examples.

This directly requires the student to demonstrate speaking/oral communication.

### Important principle

**Selecting a CLO/PLO does not automatically make an assessment aligned.**

The tool checks:

**CLO → What should the student demonstrate?**

**PLO → What broader competency is being demonstrated?**

**Question → What does the student actually have to do?**

**Question Type → What skill is actually being assessed?**
""")

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "🎓 OBE Assessment Studio | Faculty remains in control of "
    "the final assessment decision."
)
