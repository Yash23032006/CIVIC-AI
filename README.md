CivicAI – Citizen Development Intelligence

CivicAI is a web-based civic issue reporting and intelligence platform designed to help citizens report local problems and track their requests.

Features

Citizen registration and login

Civic issue reporting

Location-based issue reporting

English voice-based issue input

AI-assisted rule-based issue classification

Severity analysis

Priority score calculation

Dashboard with civic report statistics

City-based civic intelligence

Citizen request tracking through My Reports

Report ID and request status

7 Core Modules

Citizen Registration & Login

Civic Issue Reporting

AI Issue Classification

Severity & Priority Analysis

Location-Based Civic Intelligence

Citizen Request Management & Tracking

Voice-Based Issue Reporting

Technology Stack

Frontend

HTML5

CSS3

JavaScript

Backend

Python

Flask

Flask-CORS

REST API

AI / Intelligence

Rule-based AI-assisted classification

Severity analysis

Priority scoring

Location-based analysis

Data Storage

JSON

CSV

Voice Input

Web Speech API

English Speech Recognition

Project Structure

CivicAI/
│
├── backend.py
├── requirements.txt
├── README.md
├── .gitignore
├── users.json
├── citizen_requests.csv
│
└── frontend/
    ├── index.html
    ├── dashboard.html
    ├── login.html
    ├── signup.html
    ├── script.js
    └── style.css

How to Run

1. Clone the repository

git clone <YOUR-GITHUB-REPOSITORY-URL>
cd CivicAI

2. Create a virtual environment

Windows:

python -m venv venv
venv\Scripts\activate

3. Install dependencies

pip install -r requirements.txt

4. Run the backend

python backend.py

5. Open the application

Open:

http://127.0.0.1:5000

How It Works

A citizen creates an account or logs in.

The citizen describes a civic problem.

The problem can be entered using text or English voice input.

The system identifies the issue category.

The system analyzes the severity.

A priority score is calculated.

The report is stored with its location, category, severity, priority and status.

Citizens can view their submitted reports through My Reports.

The dashboard provides overall and city-based civic insights.

Note

The current prototype uses rule-based AI-assisted classification, severity analysis and priority scoring. It is intended as a working prototype for civic issue reporting and digital governance.

Project

CivicAI – Citizen Development Intelligence

Track: AI for Digital Public Infrastructure & Governance