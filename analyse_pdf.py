from dotenv import load_dotenv
import os

# Try importing the Google generative client. If it's missing, we don't want
# the whole app to fail on import; instead provide a clear runtime error when
# someone attempts to use the analysis function.
try:
    import google.generativeai as genai
    _HAVE_GENAI = True
except Exception:
    genai = None
    _HAVE_GENAI = False

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

configuration = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}


DEFAULT_MODEL_NAME = "gemini-2.5-flash"

if _HAVE_GENAI:
    # Configure the client only when the package is available. If the API key
    # is missing the actual call will fail later; we keep configuration here.
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name=DEFAULT_MODEL_NAME,
        generation_config=configuration,
    )


def analyse_resume_gemini(resume_content, job_description):
    """Analyze a resume against a job description using the Gemini model.

    If the `google.generativeai` package is not installed this function
    raises a RuntimeError with a helpful message. This keeps import-time
    failures from crashing the Flask app.
    """

    if not _HAVE_GENAI:
        raise RuntimeError(
            "google.generativeai package is not installed. Install it with:\n"
            "python -m pip install google-generativeai"
        )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to a .env file or set the environment "
            "variable before running the app."
        )

    prompt = f"""
    You are a professional resume analyzer.

    Resume:
    {resume_content}

    Job Description:
    {job_description}

    Task:
    - Analyze the resume against the job description.
    - Give a match score out of 100.
    - Highlight missing skills or experiences.
    - Suggest improvements.

    Return the result in structured format:
    Match Score: XX/100
    Missing Skills:
    - ...
    Suggestions:
    - ...
    Summary:
    ...
    """

    try:
        response = model.generate_content(prompt)
    except Exception as e:
        # Common cause: model name is not available for this API version or
        # the model doesn't support generate_content. Try to list available
        # models and attempt a fallback to a compatible one.
        available_models = None
        try:
            available = genai.list_models()
            # available may be objects or strings like 'models/NAME'
            available_models = [getattr(m, "name", str(m)) for m in available]
        except Exception:
            available_models = None

        # Try automatic fallback: prefer models that contain 'flash' or 'gemini'
        if available_models:
            for full_name in available_models:
                # skip embedding or image-only models
                lname = full_name.lower()
                if "embedding" in lname or "imagen" in lname or "embedding-" in lname:
                    continue
                # strip leading 'models/' if present
                candidate = full_name.split("/")[-1]
                if candidate == DEFAULT_MODEL_NAME:
                    continue
                try:
                    candidate_model = genai.GenerativeModel(
                        model_name=candidate, generation_config=configuration
                    )
                    response = candidate_model.generate_content(prompt)
                    return getattr(response, "text", str(response))
                except Exception:
                    # try next candidate
                    continue

        msg = (
            f"Model '{DEFAULT_MODEL_NAME}' not found or not supported by generate_content.\n"
            f"Original error: {e}\n"
        )
        if available_models:
            msg += "Available models: " + ", ".join(available_models)
        else:
            msg += "Could not retrieve available models programmatically."

        raise RuntimeError(msg) from e

    # Different client versions may structure the response differently. We
    # try the common `.text` attribute and fall back to stringifying the
    # response if needed.
    return getattr(response, "text", str(response))