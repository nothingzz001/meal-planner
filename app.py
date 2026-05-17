"""
app.py — Flask backend for the Family Meal Planner

What this does:
  GET  /              → serves the meal planner web app
  GET  /api/plan      → returns the current week's plan as JSON
  POST /api/plan      → saves an updated plan (from web edits)
  POST /api/regenerate → generates a fresh plan, saves and returns it
  GET  /api/grocery   → returns the grocery list as JSON
  GET  /api/recipes   → returns all recipes from Ingredient.xlsx

The bot.py and app.py share the same current_plan.json file.
Any change made in the web planner is immediately visible in the bot, and vice versa.

Run locally:   python app.py
Run on Railway: auto-detected via Procfile
"""

import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from meals import load_recipes, generate_week, build_grocery, DAYS

# ── Setup ─────────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder="static")
CORS(app)  # allows the Vercel HTML to call this API

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

BASE_DIR  = os.path.dirname(__file__)
PLAN_FILE = os.path.join(BASE_DIR, "current_plan.json")

# ── Plan helpers ──────────────────────────────────────────────────────────────

def save_plan(plan: dict):
    """Save plan to JSON file — shared with bot.py"""
    with open(PLAN_FILE, "w") as f:
        json.dump(plan, f, indent=2)
    log.info("Plan saved")


def load_plan() -> dict | None:
    """Load saved plan, or None if not yet created"""
    if os.path.exists(PLAN_FILE):
        with open(PLAN_FILE) as f:
            return json.load(f)
    return None


def get_or_create_plan() -> dict:
    """Return saved plan or generate a fresh one"""
    plan = load_plan()
    if plan is None:
        recipes = load_recipes()
        plan = generate_week(recipes)
        save_plan(plan)
        log.info("Generated fresh plan on first load")
    return plan


def get_week_label() -> str:
    """Return 'Mon 11 May – Sun 17 May' for the current week"""
    today  = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%a %d %b").replace(" 0"," ") + " – " + sunday.strftime("%a %d %b").replace(" 0"," ")

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the meal planner HTML"""
    return send_from_directory(BASE_DIR, "meal_planner.html")


@app.route("/api/plan", methods=["GET"])
def api_get_plan():
    """Return the current week's plan as JSON"""
    plan = get_or_create_plan()
    return jsonify({
        "ok": True,
        "plan": plan,
        "week": get_week_label(),
    })


@app.route("/api/plan", methods=["POST"])
def api_save_plan():
    """
    Save an updated plan sent from the web planner.
    Body: { "plan": { ...full plan dict... } }
    """
    data = request.get_json()
    if not data or "plan" not in data:
        return jsonify({"ok": False, "error": "Missing plan"}), 400

    plan = data["plan"]

    # Basic validation — must have all 7 days
    for day in DAYS:
        if day not in plan:
            return jsonify({"ok": False, "error": f"Missing day: {day}"}), 400

    save_plan(plan)
    return jsonify({"ok": True, "message": "Plan saved"})


@app.route("/api/regenerate", methods=["POST"])
def api_regenerate():
    """Generate a fresh plan, save and return it"""
    recipes = load_recipes()
    plan    = generate_week(recipes)
    save_plan(plan)
    log.info("Plan regenerated via web")
    return jsonify({
        "ok":   True,
        "plan": plan,
        "week": get_week_label(),
    })


@app.route("/api/grocery", methods=["GET"])
def api_grocery():
    """Return grocery list split by Mon and Thu shops"""
    plan    = get_or_create_plan()
    grocery = build_grocery(plan)
    return jsonify({
        "ok":      True,
        "grocery": grocery,
        "week":    get_week_label(),
    })


@app.route("/api/recipes", methods=["GET"])
def api_recipes():
    """Return all recipes loaded from Ingredient.xlsx"""
    try:
        recipes = load_recipes()
        return jsonify({"ok": True, "recipes": recipes})
    except Exception as e:
        log.error(f"Failed to load recipes: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/health")
def health():
    """Health check for Railway"""
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log.info(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
