
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import supabase

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "Invalid request."
        }), 400

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    mobile = data.get("mobile", "").strip()
    password = data.get("password", "")

    if not name or not email or not mobile or not password:
        return jsonify({
            "status": "error",
            "message": "All fields are required."
        }), 400

    try:
        # Check whether this email is already registered.
        existing = (
            supabase.table("citizen_users")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if existing.data:
            return jsonify({
                "status": "error",
                "message": "An account with this email already exists."
            }), 409

        # Store the password as a secure hash, never as plain text.
        password_hash = generate_password_hash(password)

        supabase.table("citizen_users").insert({
            "name": name,
            "email": email,
            "mobile": mobile,
            "password_hash": password_hash
        }).execute()

        return jsonify({
            "status": "success",
            "message": "Account created successfully!"
        }), 201

    except Exception as error:
        print("Citizen signup error:", repr(error))
        return jsonify({
            "status": "error",
            "message": "Registration failed. Please try again."
        }), 500


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "Invalid request."
        }), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "status": "error",
            "message": "Email and password are required."
        }), 400

    try:
        result = (
            supabase.table("citizen_users")
            .select("name, email, mobile, password_hash")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if not result.data:
            return jsonify({
                "status": "error",
                "message": "Account not found. Please sign up first."
            }), 404

        user = result.data[0]

        if not check_password_hash(user["password_hash"], password):
            return jsonify({
                "status": "error",
                "message": "Incorrect password."
            }), 401

        return jsonify({
            "status": "success",
            "message": "Login successful!",
            "name": user["name"],
            "email": user["email"],
            "mobile": user["mobile"]
        }), 200

    except Exception as error:
        print("Citizen login error:", repr(error))
        return jsonify({
            "status": "error",
            "message": "Login failed. Please try again."
        }), 500
