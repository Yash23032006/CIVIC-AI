from datetime import datetime
from flask import Blueprint, request, jsonify
from config import supabase
from services.ai_assessment import assess_issue
from services.report_identity import generate_unique_report_id, find_duplicate_report
import json
import uuid

reports_bp = Blueprint("reports", __name__)
TABLE_NAME = "citizen_requests"


STORAGE_BUCKET = "civic-evidence"
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PHOTOS = 4

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _read_optional_float(value, field_name):
    if value is None or str(value).strip() == "":
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number.")

    import math
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be a finite number.")

    return number


def _validate_image(data, content_type):
    if not data:
        raise ValueError("An uploaded photo is empty.")

    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("Each photo must be 5 MB or smaller.")

    # Verify file signatures instead of trusting the browser's MIME type.
    valid = (
        (content_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
        or (content_type == "image/png"
            and data.startswith(b"\x89PNG\r\n\x1a\n"))
        or (content_type == "image/webp"
            and data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    )

    if not valid:
        raise ValueError("Only valid JPEG, PNG, and WebP images are allowed.")


def _upload_evidence(files, report_id):
    if len(files) > MAX_PHOTOS:
        raise ValueError(f"You can upload up to {MAX_PHOTOS} photos.")

    uploaded_paths = []
    evidence = []

    try:
        for photo in files:
            if not photo or not photo.filename:
                continue

            content_type = (photo.mimetype or "").lower()
            if content_type not in ALLOWED_IMAGE_TYPES:
                raise ValueError("Only JPEG, PNG, and WebP photos are allowed.")

            data = photo.read(MAX_PHOTO_BYTES + 1)
            _validate_image(data, content_type)

            path = f"reports/{report_id}/{uuid.uuid4().hex}{ALLOWED_IMAGE_TYPES[content_type]}"

            supabase.storage.from_(STORAGE_BUCKET).upload(
                path,
                data,
                {
                    "content-type": content_type,
                    "upsert": "false",
                },
            )

            uploaded_paths.append(path)
            evidence.append({
                "path": path,
                "content_type": content_type,
                "size_bytes": len(data),
            })

        return evidence, uploaded_paths

    except Exception:
        if uploaded_paths:
            try:
                supabase.storage.from_(STORAGE_BUCKET).remove(uploaded_paths)
            except Exception as cleanup_error:
                print("Evidence cleanup error:", repr(cleanup_error))
        raise


def get_supabase_reports():
    response = supabase.table(TABLE_NAME).select("*").execute()
    return response.data or []


def _sort_reports_newest_first(reports):
    def sort_key(row):
        value = row.get("created_at")

        if not value:
            return datetime.min

        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

            # Make timezone-aware and naive values comparable.
            return parsed.replace(tzinfo=None)

        except (ValueError, TypeError):
            return datetime.min

    return sorted(reports, key=sort_key, reverse=True)




@reports_bp.route("/api/report", methods=["POST"])
def submit_report():
    uploaded_paths = []
    report_inserted = False

    try:
        if request.is_json:
            data = request.get_json(silent=True) or {}
            photo_files = []
        else:
            data = request.form
            photo_files = request.files.getlist("evidence_photos")

        problem = str(data.get("problem") or "").strip()
        language = str(data.get("language") or "").strip()
        location = str(data.get("location") or "").strip()
        citizen_email = str(
            data.get("citizen_email") or ""
        ).strip().lower()

        if not problem or not location or not citizen_email:
            return jsonify({
                "status": "error",
                "message": "STEP 2 FAILED: Required fields missing."
            }), 400

        # Optional GPS values.
        try:
            latitude = _read_optional_float(
                data.get("latitude"), "latitude"
            )
            longitude = _read_optional_float(
                data.get("longitude"), "longitude"
            )
            gps_accuracy = _read_optional_float(
                data.get("gps_accuracy_m"), "gps_accuracy_m"
            )
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error)
            }), 400

        if (latitude is None) != (longitude is None):
            return jsonify({
                "status": "error",
                "message": "Latitude and longitude must be provided together."
            }), 400

        if latitude is not None and not (-90 <= latitude <= 90):
            return jsonify({
                "status": "error",
                "message": "Latitude must be between -90 and 90."
            }), 400

        if longitude is not None and not (-180 <= longitude <= 180):
            return jsonify({
                "status": "error",
                "message": "Longitude must be between -180 and 180."
            }), 400

        if gps_accuracy is not None and gps_accuracy < 0:
            return jsonify({
                "status": "error",
                "message": "GPS accuracy cannot be negative."
            }), 400

        if len(photo_files) > MAX_PHOTOS:
            return jsonify({
                "status": "error",
                "message": f"You can upload up to {MAX_PHOTOS} photos."
            }), 400

        # Validate photos before creating the report.
        # This checks size and image signature without uploading yet.
        validated_photos = []
        for photo in photo_files:
            if not photo or not photo.filename:
                continue

            content_type = (photo.mimetype or "").lower()
            if content_type not in ALLOWED_IMAGE_TYPES:
                return jsonify({
                    "status": "error",
                    "message": "Only JPEG, PNG, and WebP photos are allowed."
                }), 400

            raw = photo.read(MAX_PHOTO_BYTES + 1)
            try:
                _validate_image(raw, content_type)
            except ValueError as error:
                return jsonify({
                    "status": "error",
                    "message": str(error)
                }), 400

            validated_photos.append((raw, content_type))

        duplicate = find_duplicate_report(problem, location)
        if duplicate:
            return jsonify({
                "status": "error",
                "code": "DUPLICATE_REPORT",
                "message": (
                    "A similar complaint is already registered "
                    "at this location."
                ),
                "existing_report_id": duplicate.get("id"),
                "existing_status": duplicate.get("status"),
                "similarity_score": duplicate.get("similarity_score"),
                "matched_problem": duplicate.get("problem"),
                "duplicate_reason": duplicate.get("duplicate_reason")
            }), 409

        assessment_photos = [
            {"data": raw, "mime_type": content_type}
            for raw, content_type in validated_photos
        ]

        assessment = assess_issue(
            problem=problem,
            language=language or "English",
            location=None,
            photos=assessment_photos,
        )

        category = assessment["category"]
        severity = assessment["severity"]
        priority_score = assessment["priority_score"]


        duplicate = find_duplicate_report(problem, location)
        if duplicate:
            return jsonify({
                "status": "error",
                "code": "DUPLICATE_REPORT",
                "message": (
                    "A similar complaint is already registered "
                    "at this location."
                ),
                "existing_report_id": duplicate.get("id"),
                "existing_status": duplicate.get("status"),
                "similarity_score": duplicate.get("similarity_score"),
                "matched_problem": duplicate.get("problem"),
                "duplicate_reason": duplicate.get("duplicate_reason")
            }), 409

        next_id = generate_unique_report_id(location)
        created_at = datetime.now().astimezone().isoformat()

        # Upload optional evidence after validation and duplicate checks.
        evidence = []
        for raw, content_type in validated_photos:
            path = (
                f"reports/{next_id}/"
                f"{uuid.uuid4().hex}{ALLOWED_IMAGE_TYPES[content_type]}"
            )
            supabase.storage.from_(STORAGE_BUCKET).upload(
                path,
                raw,
                {"content-type": content_type, "upsert": "false"},
            )
            uploaded_paths.append(path)
            evidence.append({
                "path": path,
                "content_type": content_type,
                "size_bytes": len(raw),
            })

        record = {
            "id": next_id,
            "problem": problem,
            "language": language,
            "location": location,
            "category": category,
            "severity": severity,
            "priority_score": priority_score,
            "ai_assessment": assessment,
            "status": "Pending",
            "created_at": created_at,
            "citizen_email": citizen_email,
            "latitude": latitude,
            "longitude": longitude,
            "gps_accuracy_m": gps_accuracy,
            "evidence_photos": evidence,
        }

        supabase.table(TABLE_NAME).insert(record).execute()
        report_inserted = True

        return jsonify({
            "status": "success",
            "message": "Civic issue submitted successfully!",
            "id": next_id,
            "category": category,
            "severity": severity,
            "location": location,
            "priority_score": priority_score,
            "latitude": latitude,
            "longitude": longitude,
            "gps_accuracy_m": gps_accuracy,
            "evidence_count": len(evidence),
            "assessment": assessment,
            "assessment_method": assessment["assessment_method"],
            "confidence": assessment["confidence"],
            "explanation": assessment["explanation"],
        }), 201

    except Exception as error:
        print("REPORT ERROR:", repr(error))

        # Avoid leaving orphaned photos if database insertion fails.
        if uploaded_paths and not report_inserted:
            try:
                supabase.storage.from_(STORAGE_BUCKET).remove(uploaded_paths)
            except Exception as cleanup_error:
                print("Evidence cleanup error:", repr(cleanup_error))

        return jsonify({
            "status": "error",
            "message": "Unable to submit the report. Please try again."
        }), 500


def _is_high_priority(value):
    """Return True only when priority_score is numeric and at least 80."""
    try:
        return float(value) >= 80
    except (TypeError, ValueError):
        # Bad/missing stored scores must not prevent reports from loading.
        return False


@reports_bp.route("/api/reports", methods=["GET"])
def get_reports():
    try:
        reports = get_supabase_reports()
        total_reports = len(reports)
        pending = sum(1 for r in reports if (r.get("status") or "").lower() == "pending")
        resolved = sum(1 for r in reports if (r.get("status") or "").lower() == "resolved")
        in_progress = sum(1 for r in reports if (r.get("status") or "").lower() == "in progress")
        high_priority = sum(1 for r in reports if _is_high_priority(r.get("priority_score")))
        reports = _sort_reports_newest_first(reports)

        return jsonify({
            "status": "success",
            "total_reports": total_reports,
            "pending": pending,
            "in_progress": in_progress,
            "resolved": resolved,
            "high_priority": high_priority,
            "reports": reports[:5]
        }), 200
    except Exception as error:
        import traceback

        print("\n========== DASHBOARD REPORT ERROR ==========")
        traceback.print_exc()
        print("============================================\n")

        return jsonify({
            "status": "error",
            "message": "Unable to load civic reports. Check the backend terminal."
        }), 500

@reports_bp.route("/api/my-reports", methods=["GET"])
def get_my_reports():
    citizen_email = request.args.get("citizen_email", "").strip().lower()
    if not citizen_email:
        return jsonify({"status": "error", "message": "Citizen email is required."}), 400

    try:
        response = (
            supabase.table(TABLE_NAME).select("*")
            .eq("citizen_email", citizen_email).execute()
        )
        reports = _sort_reports_newest_first(response.data or [])
        return jsonify({
            "status": "success",
            "citizen_email": citizen_email,
            "total_reports": len(reports),
            "reports": reports
        }), 200
    except Exception as error:
        print("Supabase my-reports error:", error)
        return jsonify({"status": "error", "message": "Unable to load your reports."}), 500


@reports_bp.route("/api/reports/city", methods=["GET"])
def get_reports_by_city():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"status": "error", "message": "City name is required."}), 400

    try:
        all_reports = get_supabase_reports()
        reports = [
            r for r in all_reports
            if (r.get("location") or "").strip().lower() == city.lower()
        ]
        total_reports = len(reports)
        high_priority = sum(1 for r in reports if _is_high_priority(r.get("priority_score")))
        pending = sum(1 for r in reports if (r.get("status") or "").lower() == "pending")
        resolved = sum(1 for r in reports if (r.get("status") or "").lower() == "resolved")
        in_progress = sum(1 for r in reports if (r.get("status") or "").lower() == "in progress")

        category_counts = {}
        for report in reports:
            category = report.get("category")
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1
        top_category = max(category_counts, key=category_counts.get) if category_counts else "No data"

        reports = _sort_reports_newest_first(reports)
        return jsonify({
            "status": "success",
            "city": city,
            "total_reports": total_reports,
            "high_priority": high_priority,
            "pending": pending,
            "in_progress": in_progress,
            "resolved": resolved,
            "top_category": top_category,
            "reports": reports
        }), 200
    except Exception as error:
        print("Supabase city reports error:", error)
        return jsonify({"status": "error", "message": "Unable to load city reports."}), 500


@reports_bp.route("/api/report/<report_id>", methods=["GET"])
def track_report(report_id):
    try:
        response = (
            supabase.table(TABLE_NAME).select("*")
            .eq("id", str(report_id)).execute()
        )
        reports = response.data or []
        if not reports:
            return jsonify({"status": "error", "message": "Report ID not found."}), 404
        return jsonify({"status": "success", "report": reports[0]}), 200
    except Exception as error:
        print("Supabase track report error:", error)
        return jsonify({"status": "error", "message": "Unable to track report."}), 500
