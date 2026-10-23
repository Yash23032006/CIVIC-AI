
import json
import os
import re

from services.issue_analysis import (
    classify_issue,
    analyze_severity,
    calculate_priority,
)


def _fallback_assessment(problem):
    """Use existing local analysis if Gemini is unavailable."""
    category = classify_issue(problem)
    severity = analyze_severity(problem)

    return {
        "category": category,
        "severity": severity,
        "priority_score": calculate_priority(category, severity),
        "confidence": None,
        "explanation": (
            "AI assessment was unavailable. "
            "This result uses the existing local keyword rules."
        ),
        "evidence_findings": [],
        "photo_analysis_available": False,
        "assessment_method": "local_fallback",
    }


def _extract_json(response_text):
    """Parse a JSON object, including one wrapped in code fences."""
    text = (response_text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    result = json.loads(text)

    if not isinstance(result, dict):
        raise ValueError("AI response must be a JSON object.")

    return result


def assess_issue(problem, language="English", location=None, photos=None):
    """
    Assess a citizen complaint using Gemini.

    photos: optional list of dictionaries:
        {"data": bytes, "mime_type": "image/jpeg"}

    This function never receives or sends the citizen's email address.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        return _fallback_assessment(problem)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are an assistant helping triage public-service complaints.

Complaint language: {language}
Complaint text:
{problem}

Approximate reported location:
{location or "Not provided"}

Assess the reported civic issue. Use photos only as supporting evidence.
Do not claim that a photo proves the report is genuine, identifies a person,
or verifies an exact location. If evidence is unclear, say so.

Choose one category from:
Road & Transport, Water & Sanitation, Waste Management, Electricity,
Healthcare, Education, Environment, Other.

Choose severity: Low, Medium, or High.
Recommend a priority score from 0 to 100 based on public-service urgency.
Give a short explanation and list observable findings from the photos.
Do not invent facts that are not present in the text or images.
Treat emergencies as requiring prompt human review.

Return ONLY a JSON object with this schema:
{{
  "category": "one allowed category",
  "severity": "Low, Medium, or High",
  "priority_score": 0,
  "confidence": 0.0,
  "explanation": "brief reason",
  "evidence_findings": ["observable finding"],
  "photo_analysis_available": true
}}

Confidence must be a number from 0 to 1 and is an estimate, not a
calibrated probability. If there are no photos, set
photo_analysis_available to false and evidence_findings to [].
"""

        contents = [prompt]

        for photo in (photos or [])[:4]:
            image_data = photo.get("data")
            mime_type = photo.get("mime_type", "")

            if not image_data:
                continue

            if mime_type not in (
                "image/jpeg",
                "image/png",
                "image/webp",
            ):
                continue

            contents.append(
                types.Part.from_bytes(
                    data=image_data,
                    mime_type=mime_type,
                )
            )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        result = _extract_json(response.text)

        allowed_categories = {
            "Road & Transport",
            "Water & Sanitation",
            "Waste Management",
            "Electricity",
            "Healthcare",
            "Education",
            "Environment",
            "Other",
        }

        category = result.get("category")
        severity = result.get("severity")
        score = result.get("priority_score")
        confidence = result.get("confidence")

        if category not in allowed_categories:
            raise ValueError("Invalid category returned by AI.")

        if severity not in {"Low", "Medium", "High"}:
            raise ValueError("Invalid severity returned by AI.")

        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("Invalid priority score returned by AI.")

        if not 0 <= score <= 100:
            raise ValueError("Priority score is out of range.")

        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            raise ValueError("Invalid confidence returned by AI.")

        findings = result.get("evidence_findings", [])

        if not isinstance(findings, list):
            findings = []

        return {
            "category": category,
            "severity": severity,
            "priority_score": round(score),
            "confidence": round(confidence, 2),
            "explanation": str(result.get("explanation", ""))[:1000],
            "evidence_findings": [
                str(item)[:300] for item in findings[:10]
            ],
            "photo_analysis_available": (
                bool(photos)
                and result.get("photo_analysis_available") is True
            ),
            "assessment_method": "gemini",
        }

    except Exception:
        # Keep report submission available if the provider fails.
        return _fallback_assessment(problem)