from flask import Flask, request, render_template
import fitz  # PyMuPDF
from analyse_pdf import analyse_resume_gemini
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def extract_text_from_resume(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        resume_file = request.files["resume"]
        job_description = request.form["job_description"]

        if resume_file.filename.endswith(".pdf"):
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], resume_file.filename)
            resume_file.save(pdf_path)

            resume_content = extract_text_from_resume(pdf_path)
            result = analyse_resume_gemini(resume_content, job_description)

            return render_template("index.html", result=result)

    return render_template("index.html", result=None)


if __name__ == "__main__":
    app.run(debug=True)
