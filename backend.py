from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from config import FRONTEND_DIR
from routes.auth_routes import auth_bp
from routes.report_routes import reports_bp
from routes.government_agent_routes import government_agent_bp

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 21 * 1024 * 1024
CORS(app)

app.register_blueprint(auth_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(government_agent_bp)

@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "login.html")

@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)

@app.route("/api/status")
def status():
    return jsonify({
        "status": "success",
        "message": "CivicAI Backend is running!"
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader = False)