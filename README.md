# 🧮 AI-Powered Symbolic Math Solver API

A production-style **symbolic mathematics reasoning engine** built with  
**FastAPI** and **SymPy**, designed to deliver structured, step-by-step
solutions for advanced mathematical expressions.

This project combines **symbolic computation**, **rule-based reasoning**, and
**backend API engineering** to simulate how an AI-powered math assistant works internally.

---

## 🚀 Why This Project Matters

Most math APIs return only final answers.  
This engine goes further — it explains the reasoning.

It:

- Classifies expressions intelligently
- Applies symbolic rules manually (e.g., Product Rule: f'g + fg')
- Generates structured intermediate steps
- Measures execution performance
- Exposes everything through a production-ready REST API

This is not just a calculator — it’s a reasoning engine.

---

## ✨ Core Features

- 🔍 Intelligent expression classification (derivatives, simplification, solving)
- 📘 Structured step-by-step symbolic reasoning
- 🧠 Manual Product Rule implementation (f'g + fg)
- ⚡ High-performance FastAPI backend
- 📊 Execution time tracking (performance aware design)
- 🔐 Secure expression parsing (safe evaluation)
- 🧱 Clean modular architecture
- 🐳 Docker-ready for deployment
- 📑 Auto-generated interactive API docs (Swagger UI)

---

## 🏗️ Architecture Overview

```
math_solver/
│
├── api.py              # FastAPI routes & request handling
├── engine.py           # Core symbolic reasoning engine
├── models.py           # Step & response models (Pydantic)
├── static/             # Optional frontend assets
├── requirements.txt
├── Dockerfile
└── README.md
```

### Architectural Design Principles

- Separation of concerns
- Modular symbolic engine
- Structured response models
- Production-oriented API design
- Scalable backend foundation

---

## 🛠️ Tech Stack

- Python 3.10+
- FastAPI
- SymPy
- Uvicorn
- Pydantic
- Docker

---

## 📡 API Endpoints

### 🔹 Health Check

**GET /health**

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

### 🔹 Solve Mathematical Expression

**POST /solve**

Request:

```json
{
  "expression": "x^2 * sin(x)"
}
```

Response:

```json
{
  "type": "derivative",
  "steps": [
    "Step 1: Identify f(x) and g(x)",
    "Step 2: Compute f'(x)",
    "Step 3: Compute g'(x)",
    "Step 4: Apply product rule",
    "Step 5: Simplify result"
  ],
  "final_answer": "2*x*sin(x) + x^2*cos(x)",
  "execution_time_ms": 12
}
```

---

## 🔐 Security & Safety

Symbolic parsing is handled carefully to prevent unsafe evaluation:

- Controlled parsing using `parse_expr`
- Restricted allowed symbols
- Structured error handling
- No arbitrary code execution
- Input validation safeguards

Designed with backend security best practices in mind.

---

## ▶️ Running Locally

### 1️⃣ Clone the repository

```
git clone https://github.com/yourusername/math-solver.git
cd math-solver
```

### 2️⃣ Install dependencies

```
pip install -r requirements.txt
```

### 3️⃣ Start the server

```
uvicorn api:app --reload
```

Server runs at:

```
http://127.0.0.1:8000
```

Interactive API documentation:

```
http://127.0.0.1:8000/docs
```

---

## 🐳 Docker Deployment

Build image:

```
docker build -t math-solver .
```

Run container:

```
docker run -p 8000:8000 math-solver
```

---

## 📈 Engineering Goals Behind This Project

- Implement rule-based symbolic reasoning
- Understand how CAS (Computer Algebra Systems) work internally
- Build scalable backend APIs
- Apply modular architecture principles
- Strengthen production-ready Python backend skills
- Bridge AI reasoning with backend engineering

---

## 🌟 Future Enhancements

- Support for integrals
- Multi-variable calculus
- LaTeX output formatting
- Expression tree visualization
- Rate limiting & authentication
- Frontend interface for live solving
- Deployment to cloud (AWS / GCP / Azure)

---

## 👩‍💻 Author

**Hasini**  
B.Tech CSE (AI/ML)  
 

---

⭐ If you find this project interesting, feel free to give it a star!
