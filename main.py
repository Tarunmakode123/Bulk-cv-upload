from flask import Flask, request, render_template, redirect, url_for
import fitz  # PyMuPDF
from analyse_pdf import analyse_resume_gemini
import os
import uuid
import re
import json
import csv
import io
from flask import jsonify, send_file

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Safety limits
# Max total request size (in bytes) to avoid very large uploads
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB
# Max number of resumes allowed per upload (tunable)
MAX_FILES_PER_REQUEST = 50

# KPIs shown above each category table to explain scoring basis
KPIS = [
    "Keyword match against the job description (required skills)",
    "Years of relevant experience and seniority level",
    "Role-specific achievements and measurable impact",
    "Education, certifications, and domain knowledge",
    "Overall clarity, formatting and readability of the resume"
]


def extract_text_from_resume(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text


def normalize_extracted_text(raw: str) -> str:
    """Clean and normalize PDF-extracted text.

    Goals:
    - Drop repeated header/footer lines (short lines that repeat many times)
    - Remove page-number boilerplate (e.g., "Page 1 of 2", "1/3")
    - Fix hyphenated line breaks ("experi-\nence" -> "experience")
    - Reflow hard line breaks inside paragraphs
    """
    if not raw:
        return ""

    # Standardize newlines
    txt = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Split to lines and strip whitespace
    lines = [ln.strip() for ln in txt.split("\n")]

    # Remove obvious page markers and noise
    page_num_re = re.compile(r"^(?:page\s+\d+(?:\s*of\s*\d+)?)$|^(?:\d+\s*/\s*\d+)$", re.IGNORECASE)
    noise_tokens = {"curriculum vitae", "resume", "confidential"}

    filtered = []
    for ln in lines:
        if not ln:
            filtered.append(ln)
            continue
        if page_num_re.match(ln):
            continue
        if ln.lower() in noise_tokens:
            continue
        filtered.append(ln)

    # Identify repeated short lines (likely headers/footers) and drop them
    freq = {}
    for ln in filtered:
        if not ln:
            continue
        if len(ln) <= 60:  # short line candidates
            freq[ln] = freq.get(ln, 0) + 1
    common_repeat = {ln for ln, c in freq.items() if c >= 3}

    filtered2 = [ln for ln in filtered if ln not in common_repeat]

    # Fix hyphenated line breaks (word-\nword -> wordword) before reflow
    rejoined = "\n".join(filtered2)
    rejoined = re.sub(r"(\w)-\n(\w)", r"\1\2", rejoined)

    # Reflow paragraphs: split by blank lines, then join inner newlines with spaces
    paras = [p for p in rejoined.split("\n\n")]
    for i, p in enumerate(paras):
        # collapse multiple internal newlines to spaces
        body = " ".join([ln.strip() for ln in p.split("\n") if ln.strip()])
        # normalize excessive spaces
        body = re.sub(r"\s+", " ", body).strip()
        paras[i] = body

    cleaned = "\n\n".join([p for p in paras if p])
    return cleaned


# Helper to extract a numeric score from the model output (moved to module level so other endpoints can use it)
def parse_match_score(text):
    """Try several heuristics to extract a numeric match score (0-100).

    Handles formats like:
    - 'Match Score: 85/100'
    - 'Match Score: 85'
    - '85%'
    - 'score": 0.85' (JSON-like float)
    - '0.85' (decimal)
    Returns an int 0..100 or None if not found.
    """
    if not text:
        return None

    # 1) common X/100
    m = re.search(r"(\d{1,3})\s*/\s*100", text)
    if m:
        try:
            v = int(m.group(1))
            return max(0, min(100, v))
        except Exception:
            pass

    # 2) explicit 'Match Score' or 'Score' labels
    m = re.search(r"(?:Match\s*Score|Score)\s*[:\-]?\s*(\d{1,3})", text, re.IGNORECASE)
    if m:
        try:
            v = int(m.group(1))
            return max(0, min(100, v))
        except Exception:
            pass

    # 3) percentage like '85%'
    m = re.search(r"(\d{1,3})\s*%", text)
    if m:
        try:
            v = int(m.group(1))
            return max(0, min(100, v))
        except Exception:
            pass

    # 4) JSON-like or free-floating decimal scores e.g. 0.85 or "score": 0.85
    mlist = re.findall(r"\b(?:score\"?\s*[:=]\s*|score\s*[:=]\s*|\b)([01]?:?\d?\.\d+)\b", text, re.IGNORECASE)
    # fallback pattern: any float between 0 and 1 or 0-100
    if mlist:
        for token in mlist:
            try:
                f = float(token)
                if 0.0 <= f <= 1.0:
                    return int(round(f * 100))
                if 1.0 < f <= 100.0:
                    return int(round(f))
            except Exception:
                continue

    # 5) last resort: any 0-100 integer in the text that's likely a score
    m = re.search(r"\b(\d{1,3})\b", text)
    if m:
        try:
            v = int(m.group(1))
            if 0 <= v <= 100:
                return v
        except Exception:
            pass

    return None


@app.route("/analyze", methods=["GET", "POST"])
def analyze():
    if request.method == "POST":
        # Support multiple resume uploads named 'resumes'
        resume_files = request.files.getlist("resumes")
        job_description = request.form.get("job_description")

        # enforce max files per request
        real_files = [r for r in resume_files if r and r.filename]
        if len(real_files) == 0:
            return render_template("index.html", result=None, error="No resumes uploaded", kpis=KPIS)
        if len(real_files) > MAX_FILES_PER_REQUEST:
            return render_template("index.html", result=None, error=f"Please upload at most {MAX_FILES_PER_REQUEST} resumes per attempt.", kpis=KPIS)

        categorized = {"Best Fit": [], "Moderate Fit": [], "Low Fit": []}

        for f in real_files:
            # validate pdf extension
            if not f.filename.lower().endswith(".pdf"):
                categorized["Low Fit"].append({
                    "filename": f.filename,
                    "score": None,
                    "analysis": "Skipped: not a PDF file",
                })
                continue

            # save with a unique name to avoid collisions
            unique_name = f"{uuid.uuid4().hex}_{f.filename}"
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            f.save(pdf_path)

            try:
                # extract text and analyze
                resume_content = normalize_extracted_text(extract_text_from_resume(pdf_path))
                # remove the saved pdf early to avoid disk growth
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass

                try:
                    analysis_text = analyse_resume_gemini(resume_content, job_description)
                except Exception as e:
                    analysis_text = f"Error during analysis: {e}"

                score = parse_match_score(analysis_text)

                # categorize using thresholds
                if score is None:
                    bucket = "Low Fit"
                elif score >= 75:
                    bucket = "Best Fit"
                elif score >= 50:
                    bucket = "Moderate Fit"
                else:
                    bucket = "Low Fit"

                categorized[bucket].append({
                    "filename": f.filename,
                    "score": score,
                    "analysis": analysis_text,
                    # include extracted text so client can request a rerun without re-upload
                    "resume_text": resume_content,
                })
            finally:
                # cleanup uploaded file to avoid disk growth
                try:
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                except Exception:
                    pass

        # after processing all files, render results
        return render_template("index.html", result=categorized, kpis=KPIS, active='analyze')

    # GET -> show empty form
    return render_template("index.html", result=None, kpis=KPIS, active='analyze')


@app.route("/", methods=["GET"])
def index():
    # Redirect root to the analysis page (home page removed)
    return redirect(url_for('analyze'))


@app.route('/rerun', methods=['POST'])
def rerun():
    """Re-run analysis for a single resume. Expects JSON: { resume_text, job_description }
    Returns JSON: { analysis, score }
    """
    data = None
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()

    resume_text = data.get('resume_text')
    jd = data.get('job_description', '')
    if not resume_text:
        return jsonify({'error': 'missing resume_text'}), 400

    try:
        analysis = analyse_resume_gemini(resume_text, jd)
    except Exception as e:
        analysis = f"Error during analysis: {e}"

    score = parse_match_score(analysis)
    return jsonify({'analysis': analysis, 'score': score})


@app.route('/rerun_all', methods=['POST'])
def rerun_all():
    """Re-run analysis for a list of resumes. Expects JSON: { resumes: [{filename, resume_text}], job_description }
    Returns JSON: { results: [{filename, analysis, score}], summary... }
    """
    if not request.is_json:
        return jsonify({'error': 'expected JSON body'}), 400
    data = request.get_json()
    resumes = data.get('resumes', [])
    jd = data.get('job_description', '')
    results = []
    for item in resumes:
        txt = item.get('resume_text', '')
        filename = item.get('filename', 'unknown')
        try:
            analysis = analyse_resume_gemini(txt, jd)
        except Exception as e:
            analysis = f"Error during analysis: {e}"
        score = parse_match_score(analysis)
        results.append({'filename': filename, 'analysis': analysis, 'score': score})

    return jsonify({'results': results})


@app.route('/download/json', methods=['POST'])
def download_json():
    # Expect a form field 'results_json' or JSON body
    data = None
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.get('results_json')
        try:
            data = json.loads(data or '{}')
        except Exception:
            return jsonify({'error': 'invalid results_json'}), 400

    payload = json.dumps(data, indent=2, ensure_ascii=False)
    return send_file(io.BytesIO(payload.encode('utf-8')),
                     mimetype='application/json',
                     as_attachment=True,
                     download_name='results.json')


@app.route('/download/csv', methods=['POST'])
def download_csv():
    # Expect a form field 'results_json' or JSON body
    raw = None
    if request.is_json:
        raw = request.get_json()
    else:
        raw = request.form.get('results_json')
        try:
            raw = json.loads(raw or '{}')
        except Exception:
            return jsonify({'error': 'invalid results_json'}), 400

    # Normalize into rows: category, filename, score, analysis
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['category', 'filename', 'score', 'analysis'])
    for category, items in (raw or {}).items():
        for it in items:
            writer.writerow([category, it.get('filename'), it.get('score'), it.get('analysis')])

    return send_file(io.BytesIO(output.getvalue().encode('utf-8')),
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name='results.csv')


if __name__ == "__main__":
    app.run(debug=True)
