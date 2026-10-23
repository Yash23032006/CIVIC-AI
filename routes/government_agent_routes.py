
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import supabase
from datetime import datetime

government_agent_bp = Blueprint("government_agent", __name__)


@government_agent_bp.route("/api/government-agent/signup", methods=["POST"])
def government_agent_signup():
    data = request.get_json(silent=True) or {}

    full_name = str(data.get("full_name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    department = str(data.get("department", "")).strip()
    employee_id = str(data.get("employee_id", "")).strip()
    password = data.get("password", "")

    if not all([full_name, email, department, employee_id, password]):
        return jsonify({
            "status": "error",
            "message": "All fields are required."
        }), 400

    if not isinstance(password, str) or len(password) < 8:
        return jsonify({
            "status": "error",
            "message": "Password must be at least 8 characters long."
        }), 400

    try:
        existing = (
            supabase.table("government_agents")
            .select("id")
            .or_(f"email.eq.{email},employee_id.eq.{employee_id}")
            .limit(1)
            .execute()
        )

        if existing.data:
            return jsonify({
                "status": "error",
                "message": "Email or employee ID is already registered."
            }), 409

        result = supabase.table("government_agents").insert({
            "full_name": full_name,
            "email": email,
            "department": department,
            "employee_id": employee_id,
            "password_hash": generate_password_hash(password),
            "status": "pending"
        }).execute()

        if not result.data:
            return jsonify({
                "status": "error",
                "message": "Registration could not be completed."
            }), 500

        return jsonify({
            "status": "success",
            "message": "Registration submitted. Please wait for administrator approval."
        }), 201

    except Exception:
        # Keep database details and credentials out of the response.
        return jsonify({
            "status": "error",
            "message": "Registration failed. Please try again."
        }), 500


@government_agent_bp.route("/api/government-agent/login", methods=["POST"])
def government_agent_login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not email or not isinstance(password, str) or not password:
        return jsonify({
            "status": "error",
            "message": "Email and password are required."
        }), 400

    try:
        result = (
            supabase.table("government_agents")
            .select(
                "id, full_name, email, department, employee_id, "
                "password_hash, status","latitude","longitude"
            )
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if not result.data:
            return jsonify({
                "status": "error",
                "message": "Invalid email or password."
            }), 401

        agent = result.data[0]

        if not check_password_hash(agent["password_hash"], password):
            return jsonify({
                "status": "error",
                "message": "Invalid email or password."
            }), 401

        if agent["status"] != "approved":
            return jsonify({
                "status": "error",
                "message": (
                    "Your account is pending approval."
                    if agent["status"] == "pending"
                    else "Your account has not been approved."
                )
            }), 403

        return jsonify({
            "status": "success",
            "message": "Login successful.",
            "agent": {
                "id": agent["id"],
                "full_name": agent["full_name"],
                "email": agent["email"],
                "department": agent["department"],
                "employee_id": agent["employee_id"]
            }
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Login failed. Please try again."
        }), 500

# Government agent: view and search all citizen reports
REPORTS_TABLE = "citizen_requests"
EVIDENCE_BUCKET = "civic-evidence"


def _oldest_first(reports):
    """Sort reports by created_at, oldest first."""
    def sort_key(report):
        created_at = report.get("created_at")

        if not created_at:
            return datetime.min

        try:
            parsed = datetime.fromisoformat(
                str(created_at).replace("Z", "+00:00")
            )
            # Normalize timezone-aware values for safe comparison.
            return parsed.replace(tzinfo=None)
        except (ValueError, TypeError):
            return datetime.min

    return sorted(reports, key=sort_key)


def _add_photo_urls(report):
    """
    Keep all original database columns and add a view_url
    to each evidence photo.
    """
    report = dict(report)
    photos = report.get("evidence_photos") or []

    # Support JSON stored either as a list or as a JSON string.
    if isinstance(photos, str):
        import json
        try:
            photos = json.loads(photos)
        except (ValueError, TypeError):
            photos = []

    if not isinstance(photos, list):
        photos = []

    updated_photos = []

    for photo in photos:
        if isinstance(photo, str):
            photo = {"path": photo}
        elif isinstance(photo, dict):
            photo = dict(photo)
        else:
            continue

        path = photo.get("path")

        if path:
            try:
                signed = (
                    supabase.storage
                    .from_(EVIDENCE_BUCKET)
                    .create_signed_url(path, 3600)
                )

                # Supabase SDK response formats can vary by version.
                if isinstance(signed, dict):
                    photo["view_url"] = (
                        signed.get("signedURL")
                        or signed.get("signedUrl")
                        or signed.get("signed_url")
                    )
                else:
                    photo["view_url"] = None

            except Exception as error:
                print("Photo URL generation failed:", repr(error))
                photo["view_url"] = None
        else:
            photo["view_url"] = None

        updated_photos.append(photo)

    report["evidence_photos"] = updated_photos
    return report


@government_agent_bp.route(
    "/api/government-agent/reports",
    methods=["GET"]
)
def government_agent_reports():
    """
    Query parameters:
      city    - filter by city/location (partial match)
      problem - search complaint description (partial match)

    Returns all columns, oldest report first, with photo view URLs.
    """
    city = request.args.get("city", "").strip().casefold()
    problem = request.args.get("problem", "").strip().casefold()

    try:
        response = (
            supabase.table(REPORTS_TABLE)
            .select("*")
            .execute()
        )

        reports = response.data or []

        # Search city/location and problem text.
        if city:
            reports = [
                report for report in reports
                if city in str(report.get("location") or "").casefold()
            ]

        if problem:
            reports = [
                report for report in reports
                if problem in str(report.get("problem") or "").casefold()
            ]

        reports = _oldest_first(reports)

        # Generate viewable links for evidence photos.
        reports = [_add_photo_urls(report) for report in reports]

        return jsonify({
            "status": "success",
            "total_reports": len(reports),
            "sort": "oldest_first",
            "reports": reports
        }), 200

    except Exception as error:
        print("Government agent reports error:", repr(error))
        return jsonify({
            "status": "error",
            "message": "Unable to load government reports."
        }), 500
