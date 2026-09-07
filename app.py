# =========================================================
# API SERVER
# Wraps main.py's register_complete_farm() as a web endpoint
# so the frontend can call it over HTTP.
# =========================================================

from flask import Flask, request, jsonify
from flask_cors import CORS

from main import register_complete_farm
from database import create_database


app = Flask(__name__)

# Allows the frontend (running on a different port/domain
# during development) to call this API.
CORS(app)


# =========================================================
# STARTUP: MAKE SURE DATABASE EXISTS
# =========================================================

create_database()


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/api/health", methods=["GET"])
def health_check():

    return jsonify({
        "status": "OK",
        "message": "Smart Farming Assistant API is running"
    })


# =========================================================
# REGISTER FARM
# =========================================================

@app.route("/api/register", methods=["POST"])
def register_farm_endpoint():

    data = request.get_json(silent=True)

    if data is None:

        return jsonify({
            "status": "ERROR",
            "error": "Request body must be JSON."
        }), 400


    # -----------------------------------------------------
    # REQUIRED FIELDS CHECK
    # -----------------------------------------------------

    required_fields = [
        "name",
        "phone_number",
        "language",
        "latitude",
        "longitude",
        "sowing_date",
        "device_id"
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in data
    ]

    if missing_fields:

        return jsonify({
            "status": "ERROR",
            "error": f"Missing required fields: {', '.join(missing_fields)}"
        }), 400


    # -----------------------------------------------------
    # OPTIONAL FIELD
    # -----------------------------------------------------

    selected_season = data.get("selected_season")


    # -----------------------------------------------------
    # CALL BACKEND LOGIC
    # -----------------------------------------------------

    try:

        result = register_complete_farm(
            name=data["name"],
            phone_number=data["phone_number"],
            language=data["language"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            sowing_date=data["sowing_date"],
            device_id=data["device_id"],
            selected_season=selected_season
        )

        # -------------------------------------------------
        # SEASON SELECTION REQUIRED
        # (not an error — this is a valid intermediate step)
        # -------------------------------------------------

        if result["status"] == "SEASON_SELECTION_REQUIRED":

            return jsonify(result), 200

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        return jsonify(result), 201


    # -----------------------------------------------------
    # VALIDATION / BUSINESS-LOGIC ERRORS
    # Examples: bad name, invalid phone, unsupported state,
    # sowing date outside any configured season.
    # -----------------------------------------------------

    except ValueError as error:

        return jsonify({
            "status": "ERROR",
            "error": str(error)
        }), 400


    # -----------------------------------------------------
    # LOCATION LOOKUP FAILURES
    # (e.g. reverse geocoding service unreachable)
    # -----------------------------------------------------

    except ConnectionError as error:

        return jsonify({
            "status": "ERROR",
            "error": f"Location service unavailable: {error}"
        }), 503


    # -----------------------------------------------------
    # ANYTHING UNEXPECTED
    # -----------------------------------------------------

    except Exception as error:

        return jsonify({
            "status": "ERROR",
            "error": f"Unexpected server error: {error}"
        }), 500


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    # debug=True auto-reloads on code changes during development.
    # Turn this off before any real deployment.
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )