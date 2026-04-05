"""
Flask REST API — Netflix & Amazon Prime Content Analysis
Run:
    pip install -r requirements.txt
    python train_models.py      # first-time only
    python app.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback, os

from ml_models import (
    load_and_clean, compute_stats,
    ContentRecommender, ContentTypeClassifier,
    RatingPredictor, GenreClassifier,
)

app = Flask(__name__)
CORS(app)

DATA_PATH  = "final_dataset.csv"
MODELS_DIR = "models"
_cache: dict = {}

def get_model(name: str):
    if name not in _cache:
        paths = {
            "recommender":      f"{MODELS_DIR}/recommender.pkl",
            "type_classifier":  f"{MODELS_DIR}/type_classifier.pkl",
            "rating_predictor": f"{MODELS_DIR}/rating_predictor.pkl",
            "genre_classifier": f"{MODELS_DIR}/genre_classifier.pkl",
        }
        loaders = {
            "recommender":      ContentRecommender.load,
            "type_classifier":  ContentTypeClassifier.load,
            "rating_predictor": RatingPredictor.load,
            "genre_classifier": GenreClassifier.load,
        }
        path = paths[name]
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Model not found: {path}. Run `python train_models.py` first.")
        _cache[name] = loaders[name](path)
    return _cache[name]

def err(msg, code=400):
    return jsonify({"error": msg}), code

# ── Health ──────────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "OTT ML API running"})

# ── Dashboard Stats ─────────────────────────────────────────────────────────
@app.route("/api/stats", methods=["GET"])
def stats():
    try:
        return jsonify({"success": True, "data": compute_stats(DATA_PATH)})
    except Exception as e:
        return err(str(e), 500)

# ── Recommend ───────────────────────────────────────────────────────────────
@app.route("/api/recommend", methods=["POST"])
def recommend():
    body = request.get_json(silent=True) or {}
    title = body.get("title", "").strip()
    if not title:
        return err("'title' is required")
    try:
        rec = get_model("recommender")
        results = rec.recommend(title, n=int(body.get("n", 10)),
                                content_type=body.get("content_type"))
        if not results:
            return jsonify({"success": False,
                            "message": f"No content found for '{title}'"}), 404
        return jsonify({"success": True, "query": title,
                        "count": len(results), "recommendations": results})
    except Exception as e:
        traceback.print_exc(); return err(str(e), 500)

# ── Predict Content Type ─────────────────────────────────────────────────────
@app.route("/api/predict/type", methods=["POST"])
def predict_type():
    body = request.get_json(silent=True) or {}
    for k in ["country", "rating", "genre", "release_year"]:
        if k not in body: return err(f"Missing: {k}")
    try:
        tc = get_model("type_classifier")
        result = tc.predict(body["country"], body["rating"], body["genre"],
                            int(body["release_year"]),
                            int(body.get("year_added", 2022)),
                            int(body.get("month_added", 6)),
                            float(body.get("duration_num", 90)))
        return jsonify({"success": True, "result": result})
    except Exception as e:
        traceback.print_exc(); return err(str(e), 500)

# ── Predict Rating ───────────────────────────────────────────────────────────
@app.route("/api/predict/rating", methods=["POST"])
def predict_rating():
    body = request.get_json(silent=True) or {}
    for k in ["description", "content_type", "country", "genre", "release_year"]:
        if k not in body: return err(f"Missing: {k}")
    try:
        rp = get_model("rating_predictor")
        result = rp.predict(body["description"], body["content_type"],
                            body["country"], body["genre"],
                            int(body["release_year"]),
                            float(body.get("duration_num", 90)))
        return jsonify({"success": True, "result": result})
    except Exception as e:
        traceback.print_exc(); return err(str(e), 500)

# ── Predict Genre ────────────────────────────────────────────────────────────
@app.route("/api/predict/genre", methods=["POST"])
def predict_genre():
    body = request.get_json(silent=True) or {}
    if not body.get("description"): return err("'description' is required")
    try:
        gc = get_model("genre_classifier")
        result = gc.predict(body.get("title", ""), body["description"],
                            float(body.get("threshold", 0.3)))
        return jsonify({"success": True, "result": result})
    except Exception as e:
        traceback.print_exc(); return err(str(e), 500)

# ── Feature Importance ───────────────────────────────────────────────────────
@app.route("/api/feature-importance", methods=["GET"])
def feature_importance():
    try:
        tc = get_model("type_classifier")
        return jsonify({"success": True, "feature_importance": tc.feature_importance()})
    except Exception as e:
        return err(str(e), 500)

# ── Search ───────────────────────────────────────────────────────────────────
@app.route("/api/search", methods=["GET"])
def search():
    q = request.args.get("q", "").strip()
    limit = int(request.args.get("limit", 10))
    if not q: return err("'q' is required")
    try:
        df = load_and_clean(DATA_PATH)
        mask = df["title"].str.lower().str.contains(q.lower(), na=False)
        cols = ["title","type","listed_in","country","release_year","rating","duration","description"]
        results = df[mask][cols].head(limit)
        return jsonify({"success": True, "query": q, "count": len(results),
                        "results": results.fillna("Unknown").to_dict(orient="records")})
    except Exception as e:
        return err(str(e), 500)

# ── Titles (paginated) ───────────────────────────────────────────────────────
@app.route("/api/titles", methods=["GET"])
def titles():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    ctype = request.args.get("type")
    country = request.args.get("country")
    try:
        df = load_and_clean(DATA_PATH)
        if ctype:    df = df[df["type"] == ctype]
        if country:  df = df[df["country"].str.contains(country, case=False, na=False)]
        total = len(df)
        subset = df.iloc[(page-1)*per_page : page*per_page]
        cols = ["show_id","title","type","listed_in","country","release_year","rating","duration"]
        return jsonify({"success": True, "page": page, "per_page": per_page,
                        "total": total, "pages": (total+per_page-1)//per_page,
                        "titles": subset[cols].fillna("Unknown").to_dict(orient="records")})
    except Exception as e:
        return err(str(e), 500)

if __name__ == "__main__":
    print("🚀 OTT ML API → http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
