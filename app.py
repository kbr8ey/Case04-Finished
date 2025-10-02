from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission, StoredSurveyRecord
from storage import append_json_line
import hashlib

app = Flask(__name__)

@app.get("/ping")
def ping():
    return jsonify({"message": "API is alive"}), 200

def sha256_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "invalid_json", "detail": "Body must be application/json"}), 400

    user_agent = request.headers.get("User-Agent")
    if "user_agent" not in payload:
        payload["user_agent"] = user_agent

    try:
        submission = SurveySubmission(**payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": ve.errors()}), 422

    if not submission.submission_id:
        now_utc = datetime.now(timezone.utc)
        timestamp_str = now_utc.strftime("%Y%m%d%H")
        submission_id = sha256_hash(submission.email + timestamp_str)
    else:
        submission_id = submission.submission_id

    # Hash sensitive fields for storage
    hashed_email = sha256_hash(submission.email)
    hashed_age = sha256_hash(str(submission.age))

    record = StoredSurveyRecord(
        name=submission.name,
        email=hashed_email,
        age=hashed_age,
        consent=submission.consent,
        rating=submission.rating,
        comments=submission.comments,
        user_agent=submission.user_agent,
        submission_id=submission_id,
        received_at=datetime.now(timezone.utc),
        ip=request.headers.get("X-Forwarded-For", request.remote_addr or "")
    )

    append_json_line(record.dict())
    return jsonify({"status": "ok"}), 201

if __name__ == "__main__":
    app.run(port=5000, debug=True)
