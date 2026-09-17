# ========================================================
# CLO-BY-CLO ANALYSIS
# ========================================================

st.divider()

st.header("🎯 CLO-by-CLO Analysis")

st.write(
    "Select one CLO to view its numerical alignment, "
    "questions, graphical representation, and improvement suggestions."
)

# --------------------------------------------------------
# SELECT ONE CLO
# --------------------------------------------------------

clo_options = [
    clo["code"]
    for clo in clos
]

selected_clo_code = st.selectbox(
    "Select CLO to analyze",
    clo_options,
    key="selected_clo"
)

selected_clo = next(
    (
        clo
        for clo in clos
        if clo["code"] == selected_clo_code
    ),
    None
)

# --------------------------------------------------------
# QUESTIONS FOR SELECTED CLO
# --------------------------------------------------------

clo_questions = results_df[
    results_df["Best CLO"] == selected_clo_code
].copy()

# --------------------------------------------------------
# CLO SCORE
# --------------------------------------------------------

if len(clo_questions) > 0:

    clo_alignment = clo_questions[
        "CLO Alignment %"
    ].mean()

    clo_coverage = (
        len(clo_questions)
        /
        len(results_df)
    ) * 100

else:

    clo_alignment = 0
    clo_coverage = 0


# --------------------------------------------------------
# CLO INFORMATION
# --------------------------------------------------------

st.subheader(
    f"{selected_clo_code}"
)

st.info(
    f"**CLO Description:** {selected_clo['text']}"
)

# --------------------------------------------------------
# CLO NUMERICAL SUMMARY
# --------------------------------------------------------

c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "CLO Alignment",
        f"{clo_alignment:.1f}%"
    )

with c2:

    st.metric(
        "Questions Mapped",
        len(clo_questions)
    )

with c3:

    st.metric(
        "Quiz Coverage",
        f"{clo_coverage:.1f}%"
    )

# --------------------------------------------------------
# ALIGNMENT STATUS
# --------------------------------------------------------

if clo_alignment >= 70:

    st.success(
        f"{selected_clo_code} has strong quiz alignment "
        f"({clo_alignment:.1f}%)."
    )

elif clo_alignment >= 50:

    st.warning(
        f"{selected_clo_code} has moderate alignment "
        f"({clo_alignment:.1f}%). Some questions may need refinement."
    )

else:

    st.error(
        f"{selected_clo_code} has weak alignment "
        f"({clo_alignment:.1f}%). Revision is recommended."
    )

# --------------------------------------------------------
# CLO GRAPH
# --------------------------------------------------------

st.subheader(
    "📊 CLO Alignment Graph"
)

if len(clo_questions) > 0:

    graph_data = clo_questions[
        [
            "Question No.",
            "CLO Alignment %"
        ]
    ].copy()

    graph_data["Question"] = (
        "Q"
        +
        graph_data[
            "Question No."
        ].astype(str)
    )

    graph_data = graph_data[
        [
            "Question",
            "CLO Alignment %"
        ]
    ].set_index(
        "Question"
    )

    st.bar_chart(
        graph_data,
        use_container_width=True
    )

else:

    st.warning(
        "No question is currently mapped to this CLO."
    )

# --------------------------------------------------------
# QUESTIONS FOR THIS CLO
# --------------------------------------------------------

st.subheader(
    f"📝 Questions Assessing {selected_clo_code}"
)

if len(clo_questions) > 0:

    question_display = clo_questions[
        [
            "Question No.",
            "Question",
            "Intended Bloom",
            "Detected Bloom",
            "Bloom Alignment %",
            "CLO Alignment %",
            "Best PLO",
            "PLO Alignment %"
        ]
    ]

    st.dataframe(
        question_display,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        f"No question has been mapped to {selected_clo_code}. "
        "Add or revise a question that directly assesses this CLO."
    )

# --------------------------------------------------------
# CLO IMPROVEMENT SUGGESTIONS
# --------------------------------------------------------

st.subheader(
    f"💡 Suggestions for Improving {selected_clo_code}"
)

clo_suggestions = []

if len(clo_questions) == 0:

    clo_suggestions.append(
        f"Add at least one question that directly assesses "
        f"the knowledge or skill described in {selected_clo_code}."
    )

else:

    if clo_alignment < 50:

        clo_suggestions.append(
            f"The current alignment is only {clo_alignment:.1f}%. "
            f"Rewrite the questions so that their content and "
            f"required student action directly reflect the CLO."
        )

    elif clo_alignment < 70:

        clo_suggestions.append(
            f"The alignment is {clo_alignment:.1f}%. "
            f"Strengthen the wording of the questions so the "
            f"relationship with {selected_clo_code} is more explicit."
        )

    else:

        clo_suggestions.append(
            f"The alignment is strong at {clo_alignment:.1f}%. "
            f"Maintain the direct connection between the questions "
            f"and {selected_clo_code}."
        )

    if clo_coverage < 20:

        clo_suggestions.append(
            f"Only {clo_coverage:.1f}% of the quiz questions "
            f"currently contribute to this CLO. Consider increasing "
            f"assessment coverage if this CLO is an important "
            f"course outcome."
        )

# --------------------------------------------------------
# BLOOM SUGGESTION FOR THIS CLO
# --------------------------------------------------------

if len(clo_questions) > 0:

    weak_bloom_questions = clo_questions[
        clo_questions[
            "Bloom Alignment %"
        ] < 65
    ]

    if len(weak_bloom_questions) > 0:

        question_numbers = ", ".join(
            [
                f"Q{int(q)}"
                for q in weak_bloom_questions[
                    "Question No."
                ]
            ]
        )

        clo_suggestions.append(
            f"Questions {question_numbers} do not strongly "
            f"match the intended Bloom level of {intended_bloom}. "
            f"Revise their cognitive demand and action verbs."
        )

# --------------------------------------------------------
# WEAK CLO QUESTIONS
# --------------------------------------------------------

if len(clo_questions) > 0:

    weak_clo_questions = clo_questions[
        clo_questions[
            "CLO Alignment %"
        ] < 50
    ]

    if len(weak_clo_questions) > 0:

        numbers = ", ".join(
            [
                f"Q{int(q)}"
                for q in weak_clo_questions[
                    "Question No."
                ]
            ]
        )

        clo_suggestions.append(
            f"Priority revision: {numbers} have CLO alignment "
            f"below 50%. Review these questions first."
        )

# --------------------------------------------------------
# DISPLAY SUGGESTIONS
# --------------------------------------------------------

for suggestion in clo_suggestions:

    st.info(
        "💡 " + suggestion
    )

# --------------------------------------------------------
# CLO QUESTION DETAILS
# --------------------------------------------------------

if len(clo_questions) > 0:

    st.subheader(
        "🔎 Detailed CLO Question Review"
    )

    for _, row in clo_questions.iterrows():

        with st.expander(
            f"Question {int(row['Question No.'])}"
        ):

            st.write(
                f"**Question:** {row['Question']}"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "CLO Alignment",
                    f"{row['CLO Alignment %']:.1f}%"
                )

            with c2:

                st.metric(
                    "Bloom Alignment",
                    f"{row['Bloom Alignment %']:.1f}%"
                )

            with c3:

                st.metric(
                    "PLO Alignment",
                    f"{row['PLO Alignment %']:.1f}%"
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
                f"**Mapped PLO:** "
                f"{row['Best PLO']}"
            )

            if row["CLO Alignment %"] < 50:

                st.warning(
                    f"Revise this question to make its connection "
                    f"with {selected_clo_code} more explicit."
                )

            if row["Bloom Alignment %"] < 65:

                st.warning(
                    f"Revise the cognitive demand so the question "
                    f"better targets {intended_bloom}."
                )

            if row["PLO Alignment %"] < 50:

                st.warning(
                    f"Review whether this question provides clear "
                    f"evidence for {row['Best PLO']}."
                )

            if (
                row["CLO Alignment %"] >= 70
                and row["Bloom Alignment %"] >= 100
            ):

                st.success(
                    "This question provides strong alignment "
                    "with the selected CLO and intended Bloom level."
                )
