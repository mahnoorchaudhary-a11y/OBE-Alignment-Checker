# 🎯 OBE Assessment Studio

**OBE Assessment Studio** is an AI-powered assessment design tool that helps teachers create, refine, and check assessment questions according to **CLOs, PLOs, Bloom’s Taxonomy, question type, and marks**.

## 🚀 What It Does

Teachers select:

**Course → CLO → PLO → Bloom’s Level → Question Type → Marks**

The AI then generates an assessment question that the teacher can **review and tweak before accepting**.

## ⭐ Key Features

### 🤖 AI Question Generator

Generate questions based on:

* CLO
* PLO
* Bloom's Level
* Question Type
* Marks

### ⚙️ Tweak This Question

Teachers can modify an AI-generated question using simple controls:

* 🎯 More closely aligned with CLO
* 🔗 Strengthen PLO connection
* 🧠 Change Bloom's Level
* Make easier
* Make harder
* Make more analytical
* Make more application-based
* Make more critical-thinking based
* Make discipline-specific
* Change question type
* 🔄 Regenerate

### 🔍 Check OBE Alignment

The tool evaluates the generated question and provides a simple report:

| Alignment Check | Result               |
| --------------- | -------------------- |
| CLO Alignment   | ✅ Strong             |
| PLO Alignment   | ✅ Strong             |
| Bloom's Level   | ⚠️ Needs Improvement |
| Marks           | ✅ Appropriate        |
| Difficulty      | ✅ Appropriate        |

## 👩‍🏫 Designed for Teachers

The goal is not to replace the teacher. **AI generates suggestions, while the teacher remains in control.**

Teachers can modify, regenerate, review, and approve every question.

## 🛠️ Suggested Technology

* **Python**
* **Streamlit**
* **OpenAI API / Gemini API**
* **Pandas**
* **Plotly** (optional)

## 📁 Basic Project Structure

```text
OBE-Assessment-Studio/
│
├── app.py
├── README.md
├── requirements.txt
└── .env
```

## ▶️ Run the App

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
streamlit run app.py
```

## 🎯 Main Goal

**Generate → Tweak → Check → Approve**

OBE Assessment Studio makes assessment design more **aligned, transparent, flexible, and teacher-controlled**.
