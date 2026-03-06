<div align="center">
  <h1>🎯 GATE Score Calculator</h1>
  <p><strong>A full-stack, automated response sheet analyzer that accurately parses, compares, and calculates GATE applicant scores against official answer keys in real-time.</strong></p>
  
  <p>
    <a href="https://gate-predictor.onrender.com/"><strong>🔴 Live Demo</strong></a> •
    <a href="#about-the-project">About</a> •
    <a href="#key-features">Features</a> •
    <a href="#technical-architecture">Architecture</a> •
    <a href="#getting-started">Setup</a>
  </p>
</div>

---

## 💡 About the Project

The **GATE Score Calculator** addresses the stressful post-exam period for thousands of engineering graduates. Instead of manually cross-referencing hundreds of questions across multiple response sheets and official PDFs, this application automates the entire process. 

Users simply paste the URL to their official GATE response sheet. The system instantly parses their answers, matches them against a digitized community-sourced answer key, and calculates their exact score (accounting for MCQ negative marking, complex MSQ evaluations, and NAT range parsing).

Built as a robust backend-heavy application, it successfully transforms unstructured PDFs and complex HTML DOMs into a clean, instantaneous UI.

## ✨ Key Features

- **Real-Time HTML Parsing:** Uses `BeautifulSoup` to navigate and reverse-engineer the structure of official GATE Response Sheets live from the provided URL.
- **Complex Scoring Engine:** Handles dynamic scoring logics natively. Accurately evaluates:
  - **MCQs:** Applies $1/3$ or $2/3$ negative marking based on the question weight.
  - **MSQs:** Enforces all-or-nothing multiple selection logic without partial marking penalties.
  - **NATs:** Parses numerical ranges (e.g., `0.25 to 0.28`) and correctly evaluates the user's float responses.
  - **MTA (Marks to All):** Captures anomalies automatically and assigns free marks.
- **Automated Answer Key Extraction:** Instead of manual schema creation, the system extracts data tables from official answer-key PDFs using `pdfplumber`, normalizing "Subject", "Shift", and "Session" anomalies.
- **Community Contribution Portal:** A built-in staging environment where students can upload missing official keys. These are sent into a sandbox for admin verification via email tokens before going live to the public.
- **Detailed Analytics Dashboard:** Breaks down the user's score into "Total Attempts", "Correct", "Wrong", and "Unattempted", alongside an itemized table showing exactly where marks were lost.

## 🛠️ Technical Architecture

### 🧰 Tech Stack
- **Backend:** Python, Flask, Flask-CORS
- **Data Parsing:** BeautifulSoup4, PDFPlumber, Regex Pattern Matching
- **Frontend:** HTML5, Vanilla JavaScript, CSS3 (Custom Glassmorphism UI)
- **External Services:** Supabase Storage (for cloud object storage), Waitress/Gunicorn (for production WSGI)
- **Deployment:** Render (with custom keep-alive daemon to prevent cold starts).
- **Email Gateway:** SMTPLib for async admin alerts and one-click token approvals.

### ⚙️ System Design
1. **The Parsing Layer:** Response Sheets are fetched via standard HTTP requests spoofed with standard User-Agents. We identify the Question ID via image `src` and regex patterns on the backend, mapping them perfectly to the schema.
2. **The Schema Engine:** Schemas are stored securely in JSON. When navigating different branches (CS, DA, EC), dynamic object mapping assigns Official Keys independently for every question matrix.
3. **The Data Storage Pivot:** Includes an abstraction layer `StorageService`. When running locally, schemas stay safely in `--/data`. However, setting `STORAGE_TYPE=supabase` shifts the entire app to cloud-buckets instantly.
4. **Resiliency:** Implemented internal daemon keep-alive threads to fight hosting cold-starts dynamically without resorting to external cron-jobs.

---

## 🚀 Getting Started

If you wish to run the project locally on your machine instead of using the [Live Version](https://gate-predictor.onrender.com/):

### 1. Clone the repository
```bash
git clone https://github.com/iamshrisawant/GATE_Predictor.git
cd GATE_Predictor
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
SECRET_KEY=your_secret_key
# Used for community paper contributions
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_app_password
# Admin access
ADMIN_PIN=GATE2025
# To enable background KEEP-ALIVE (optional)
# SELF_URL=http://localhost:5000 
```

### 4. Run the Application
```bash
python run.py
```
* **Local App URL:** `http://localhost:5000`
* **Local Dashboard:** `http://localhost:5000/dashboard`

---

## 📈 Status

**Production Deployed.** 
Currently live at [gate-predictor.onrender.com](https://gate-predictor.onrender.com/). Equipped to process GATE CS, DA, and EC schemas among others, adaptable for multiple years seamlessly utilizing the robust PDF extraction engine.

---

<div align="center">
  <p>Built by <strong><a href="https://github.com/iamshrisawant">Shriswarup Sawant</a></strong> as a showcase of robust data parsing and full-stack API architecture.</p>
</div>
