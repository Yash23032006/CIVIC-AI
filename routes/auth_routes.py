from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from services.user_service import load_users, save_users

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid request."}), 400

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    mobile = data.get("mobile", "").strip()
    password = data.get("password", "")

    if not name or not email or not mobile or not password:
        return jsonify({"status": "error", "message": "All fields are required."}), 400

    users = load_users()
    for user in users:
        if user["email"] == email:
            return jsonify({
                "status": "error",
                "message": "An account with this email already exists."
            }), 409

    users.append({
        "name": name,
        "email": email,
        "mobile": mobile,
        "password": generate_password_hash(password)
    })
    save_users(users)
    return jsonify({"status": "success", "message": "Account created successfully!"}), 201


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid request."}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    for user in load_users():
        if user["email"] == email:
            if check_password_hash(user["password"], password):
                return jsonify({
                    "status": "success",
                    "message": "Login successful!",
                    "name": user["name"],
                    "email": user["email"],
                    "mobile": user["mobile"]
                }), 200
            return jsonify({"status": "error", "message": "Incorrect password."}), 401

    return jsonify({
        "status": "error",
        "message": "Account not found. Please sign up first."
    }), 404
