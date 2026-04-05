"""
Netflix & Amazon Prime - ML Models
Includes: Content Recommender, Rating Predictor, Genre Classifier
"""

import pandas as pd
import numpy as np
import pickle
import os
import warnings
warnings.filterwarnings("ignore")

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MultiLabelBinarizer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.metrics import (
    accuracy_score, classification_report,
    confusion_matrix, f1_score
)
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

# ─────────────────────────────────────────────
# 1.  DATA LOADING & CLEANING
# ─────────────────────────────────────────────

def load_and_clean(path: str = "final_dataset.csv") -> pd.DataFrame:
    df = pd.read_csv(path)

    # Fill missing values
    df["director"]   = df["director"].fillna("Unknown")
    df["cast"]       = df["cast"].fillna("Unknown")
    df["country"]    = df["country"].fillna("Unknown")
    df["rating"]     = df["rating"].fillna(df["rating"].mode()[0])
    df["duration"]   = df["duration"].fillna("Unknown")
    df["date_added"] = df["date_added"].fillna("Unknown")

    # Extract numeric duration
    df["duration_num"] = df["duration"].str.extract(r"(\d+)").astype(float)

    # Parse date_added
    df["date_added_parsed"] = pd.to_datetime(df["date_added"], errors="coerce")
    df["year_added"]  = df["date_added_parsed"].dt.year.fillna(0).astype(int)
    df["month_added"] = df["date_added_parsed"].dt.month.fillna(0).astype(int)

    # Genre list from listed_in
    df["genre_list"] = df["listed_in"].str.split(", ")

    # Primary genre (first in list)
    df["primary_genre"] = df["genre_list"].apply(lambda x: x[0] if isinstance(x, list) else "Unknown")

    # Combined text feature for recommendations
    df["combined_text"] = (
        df["title"].fillna("") + " " +
        df["description"].fillna("") + " " +
        df["listed_in"].fillna("") + " " +
        df["director"].fillna("") + " " +
        df["cast"].fillna("")
    )

    # Binary type flag
    df["is_movie"] = (df["type"] == "Movie").astype(int)

    return df.reset_index(drop=True)


# ─────────────────────────────────────────────
# 2.  CONTENT-BASED RECOMMENDER  (TF-IDF + Cosine Sim)
# ─────────────────────────────────────────────

class ContentRecommender:
    """
    Content-based filtering using TF-IDF on combined text features.
    Returns top-N similar titles to a given title.
    """

    def __init__(self, max_features: int = 5000, ngram_range=(1, 2)):
        self.tfidf   = TfidfVectorizer(max_features=max_features,
                                       ngram_range=ngram_range,
                                       stop_words="english")
        self.sim_matrix = None
        self.df         = None

    def fit(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        tfidf_matrix    = self.tfidf.fit_transform(df["combined_text"])
        self.sim_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)
        print(f"[Recommender] TF-IDF matrix: {tfidf_matrix.shape}")
        return self

    def recommend(self, title: str, n: int = 10,
                  content_type: str = None) -> list[dict]:
        matches = self.df[self.df["title"].str.lower() == title.lower()]
        if matches.empty:
            # Partial match fallback
            matches = self.df[self.df["title"].str.lower().str.contains(
                title.lower(), na=False)]
        if matches.empty:
            return []

        idx  = matches.index[0]
        sims = list(enumerate(self.sim_matrix[idx]))
        sims = sorted(sims, key=lambda x: x[1], reverse=True)[1:]   # drop self

        results = []
        for i, score in sims:
            row = self.df.iloc[i]
            if content_type and row["type"] != content_type:
                continue
            results.append({
                "title":        row["title"],
                "type":         row["type"],
                "genre":        row["listed_in"],
                "country":      row["country"],
                "release_year": int(row["release_year"]),
                "rating":       row["rating"],
                "similarity":   round(float(score), 4),
            })
            if len(results) >= n:
                break
        return results

    def save(self, path: str = "models/recommender.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        print(f"[Recommender] Saved → {path}")

    @staticmethod
    def load(path: str = "models/recommender.pkl"):
        with open(path, "rb") as f:
            return pickle.load(f)


# ─────────────────────────────────────────────
# 3.  CONTENT-TYPE CLASSIFIER  (Movie vs TV Show)
# ─────────────────────────────────────────────

class ContentTypeClassifier:
    """
    Predicts whether content is a Movie or TV Show given
    features like genre, country, duration, rating, year.
    """

    def __init__(self):
        self.model      = None
        self.le_country = LabelEncoder()
        self.le_rating  = LabelEncoder()
        self.le_genre   = LabelEncoder()
        self.feature_cols = None

    def _encode(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        d = df.copy()
        if fit:
            d["country_enc"] = self.le_country.fit_transform(d["country"])
            d["rating_enc"]  = self.le_rating.fit_transform(d["rating"])
            d["genre_enc"]   = self.le_genre.fit_transform(d["primary_genre"])
        else:
            def safe_transform(le, col):
                known = set(le.classes_)
                return col.apply(lambda x: le.transform([x])[0]
                                 if x in known else -1)
            d["country_enc"] = safe_transform(self.le_country, d["country"])
            d["rating_enc"]  = safe_transform(self.le_rating,  d["rating"])
            d["genre_enc"]   = safe_transform(self.le_genre,   d["primary_genre"])
        return d

    def fit(self, df: pd.DataFrame):
        d = self._encode(df, fit=True)
        self.feature_cols = [
            "country_enc", "rating_enc", "genre_enc",
            "release_year", "year_added", "month_added", "duration_num"
        ]
        X = d[self.feature_cols].fillna(-1)
        y = d["is_movie"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)

        self.model = GradientBoostingClassifier(
            n_estimators=200, max_depth=5,
            learning_rate=0.1, random_state=42
        )
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        print("\n[ContentTypeClassifier] Evaluation:")
        print(f"  Accuracy : {accuracy_score(y_test, y_pred):.4f}")
        print(f"  F1 Score : {f1_score(y_test, y_pred):.4f}")
        print(classification_report(y_test, y_pred,
                                    target_names=["TV Show", "Movie"]))
        return self

    def predict(self, country: str, rating: str, genre: str,
                release_year: int, year_added: int = 2022,
                month_added: int = 6, duration_num: float = 90.0) -> dict:
        row = pd.DataFrame([{
            "country": country, "rating": rating,
            "primary_genre": genre,
            "release_year": release_year,
            "year_added": year_added, "month_added": month_added,
            "duration_num": duration_num,
        }])
        row = self._encode(row, fit=False)
        X   = row[self.feature_cols].fillna(-1)
        pred  = self.model.predict(X)[0]
        proba = self.model.predict_proba(X)[0]
        label = "Movie" if pred == 1 else "TV Show"
        return {
            "prediction":   label,
            "confidence":   round(float(max(proba)), 4),
            "movie_prob":   round(float(proba[1]), 4),
            "tvshow_prob":  round(float(proba[0]), 4),
        }

    def feature_importance(self) -> dict:
        imp = self.model.feature_importances_
        return dict(sorted(zip(self.feature_cols, imp.tolist()),
                            key=lambda x: -x[1]))

    def save(self, path: str = "models/type_classifier.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        print(f"[ContentTypeClassifier] Saved → {path}")

    @staticmethod
    def load(path: str = "models/type_classifier.pkl"):
        with open(path, "rb") as f:
            return pickle.load(f)


# ─────────────────────────────────────────────
# 4.  RATING PREDICTOR  (Multi-class)
# ─────────────────────────────────────────────

class RatingPredictor:
    """
    Predicts content maturity rating (TV-MA, PG-13, R …)
    from type, genre, country, and release year.
    """

    TOP_RATINGS = ["TV-MA", "TV-14", "TV-PG", "R", "PG-13",
                   "TV-Y7", "TV-Y", "PG", "TV-G"]

    def __init__(self):
        self.pipeline  = None
        self.le_rating  = LabelEncoder()
        self.le_country = LabelEncoder()
        self.le_genre   = LabelEncoder()
        self.tfidf      = TfidfVectorizer(max_features=500, stop_words="english")

    def _prepare(self, df: pd.DataFrame, fit: bool = False) -> np.ndarray:
        d = df.copy()
        d = d[d["rating"].isin(self.TOP_RATINGS)].copy()

        if fit:
            d["country_enc"] = self.le_country.fit_transform(d["country"])
            d["genre_enc"]   = self.le_genre.fit_transform(d["primary_genre"])
            text_feat        = self.tfidf.fit_transform(d["description"]).toarray()
        else:
            known_c = set(self.le_country.classes_)
            known_g = set(self.le_genre.classes_)
            d["country_enc"] = d["country"].apply(
                lambda x: self.le_country.transform([x])[0] if x in known_c else -1)
            d["genre_enc"]   = d["primary_genre"].apply(
                lambda x: self.le_genre.transform([x])[0] if x in known_g else -1)
            text_feat        = self.tfidf.transform(d["description"]).toarray()

        num_feat = d[["is_movie", "country_enc", "genre_enc",
                      "release_year", "duration_num"]].fillna(-1).values
        return d, np.hstack([num_feat, text_feat])

    def fit(self, df: pd.DataFrame):
        d, X = self._prepare(df, fit=True)
        y    = self.le_rating.fit_transform(d["rating"])

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)

        self.pipeline = LogisticRegression(
            max_iter=1000, C=1.0, random_state=42, solver="lbfgs"
        )
        self.pipeline.fit(X_train, y_train)

        y_pred = self.pipeline.predict(X_test)
        print("\n[RatingPredictor] Evaluation:")
        print(f"  Accuracy : {accuracy_score(y_test, y_pred):.4f}")
        print(f"  F1 Macro : {f1_score(y_test, y_pred, average='macro'):.4f}")
        return self

    def predict(self, description: str, content_type: str,
                country: str, genre: str,
                release_year: int, duration_num: float = 90.0) -> dict:
        row = pd.DataFrame([{
            "description":   description,
            "is_movie":      1 if content_type == "Movie" else 0,
            "country":       country,
            "primary_genre": genre,
            "release_year":  release_year,
            "duration_num":  duration_num,
            "rating":        self.TOP_RATINGS[0],   # placeholder – not used in pred
        }])
        _, X  = self._prepare(row, fit=False)
        pred  = self.pipeline.predict(X)[0]
        proba = self.pipeline.predict_proba(X)[0]
        label = self.le_rating.inverse_transform([pred])[0]
        top3  = sorted(zip(self.le_rating.classes_,
                           self.le_rating.inverse_transform(range(len(proba))),
                           proba.tolist()),
                       key=lambda x: -x[2])[:3]
        return {
            "predicted_rating": label,
            "confidence":       round(float(max(proba)), 4),
            "top3": [{"rating": r, "probability": round(p, 4)}
                     for _, r, p in top3],
        }

    def save(self, path: str = "models/rating_predictor.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        print(f"[RatingPredictor] Saved → {path}")

    @staticmethod
    def load(path: str = "models/rating_predictor.pkl"):
        with open(path, "rb") as f:
            return pickle.load(f)


# ─────────────────────────────────────────────
# 5.  GENRE CLASSIFIER  (Multi-label)
# ─────────────────────────────────────────────

class GenreClassifier:
    """
    Multi-label classification: predicts genres from title + description.
    Uses TF-IDF + OneVsRest LogisticRegression.
    """

    MIN_SUPPORT = 100   # only genres with ≥ this many samples

    def __init__(self):
        self.tfidf   = TfidfVectorizer(max_features=3000,
                                       ngram_range=(1, 2),
                                       stop_words="english")
        self.mlb     = MultiLabelBinarizer()
        self.model   = OneVsRestClassifier(
            LogisticRegression(max_iter=500, C=1.0, random_state=42))
        self.valid_genres: list[str] = []

    def _get_text(self, df: pd.DataFrame) -> list[str]:
        return (df["title"].fillna("") + " " +
                df["description"].fillna("")).tolist()

    def fit(self, df: pd.DataFrame):
        # Find genres with sufficient support
        from collections import Counter
        genre_counts: Counter = Counter()
        for lst in df["genre_list"]:
            if isinstance(lst, list):
                genre_counts.update(lst)
        self.valid_genres = [g for g, c in genre_counts.items()
                             if c >= self.MIN_SUPPORT]

        # Filter genre lists to valid only
        df = df.copy()
        df["genre_filtered"] = df["genre_list"].apply(
            lambda lst: [g for g in lst if g in self.valid_genres]
            if isinstance(lst, list) else [])
        df = df[df["genre_filtered"].apply(len) > 0]

        X = self.tfidf.fit_transform(self._get_text(df))
        y = self.mlb.fit_transform(df["genre_filtered"])

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        print("\n[GenreClassifier] Evaluation:")
        print(f"  F1 Micro : {f1_score(y_test, y_pred, average='micro'):.4f}")
        print(f"  F1 Macro : {f1_score(y_test, y_pred, average='macro'):.4f}")
        return self

    def predict(self, title: str, description: str,
                threshold: float = 0.3) -> dict:
        text   = [title + " " + description]
        X      = self.tfidf.transform(text)
        proba  = self.model.predict_proba(X)[0]
        genres = [
            {"genre": g, "probability": round(float(p), 4)}
            for g, p in sorted(zip(self.mlb.classes_, proba),
                                key=lambda x: -x[1])
            if p >= threshold
        ]
        return {"predicted_genres": genres}

    def save(self, path: str = "models/genre_classifier.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        print(f"[GenreClassifier] Saved → {path}")

    @staticmethod
    def load(path: str = "models/genre_classifier.pkl"):
        with open(path, "rb") as f:
            return pickle.load(f)


# ─────────────────────────────────────────────
# 6.  TRAIN & SAVE ALL MODELS
# ─────────────────────────────────────────────

def train_all(data_path: str = "final_dataset.csv"):
    print("=" * 60)
    print("  Training all models")
    print("=" * 60)

    df = load_and_clean(data_path)
    print(f"\nDataset loaded: {df.shape[0]:,} rows | {df.shape[1]} columns")

    # 1. Recommender
    print("\n--- Content Recommender ---")
    rec = ContentRecommender(max_features=5000)
    rec.fit(df)
    rec.save("models/recommender.pkl")

    # 2. Type Classifier
    print("\n--- Content Type Classifier ---")
    tc = ContentTypeClassifier()
    tc.fit(df)
    tc.save("models/type_classifier.pkl")

    # 3. Rating Predictor
    print("\n--- Rating Predictor ---")
    rp = RatingPredictor()
    rp.fit(df)
    rp.save("models/rating_predictor.pkl")

    # 4. Genre Classifier
    print("\n--- Genre Classifier ---")
    gc = GenreClassifier()
    gc.fit(df)
    gc.save("models/genre_classifier.pkl")

    print("\n✓ All models trained and saved to ./models/")
    return rec, tc, rp, gc


# ─────────────────────────────────────────────
# 7.  EDA STATS  (used by the backend)
# ─────────────────────────────────────────────

def compute_stats(data_path: str = "final_dataset.csv") -> dict:
    df = load_and_clean(data_path)

    # Genre frequency
    from collections import Counter
    genre_counter: Counter = Counter()
    for lst in df["genre_list"]:
        if isinstance(lst, list):
            genre_counter.update(lst)

    # Yearly content count
    yearly = (df.groupby("release_year")
                .size().reset_index(name="count")
                .query("release_year >= 2000")
                .sort_values("release_year"))

    # Country top 10
    country_top = (df["country"]
                   .str.split(", ").explode()
                   .value_counts().head(10).to_dict())

    # Platform breakdown (all Netflix here; extend for Amazon if col exists)
    type_dist = df["type"].value_counts().to_dict()

    return {
        "total_titles":    int(len(df)),
        "total_movies":    int(type_dist.get("Movie", 0)),
        "total_tvshows":   int(type_dist.get("TV Show", 0)),
        "total_countries": int(df["country"].nunique()),
        "total_genres":    int(len(genre_counter)),
        "type_distribution": type_dist,
        "top_genres":     dict(genre_counter.most_common(10)),
        "yearly_growth":  yearly.set_index("release_year")["count"].to_dict(),
        "top_countries":  country_top,
        "top_ratings":    df["rating"].value_counts().head(10).to_dict(),
    }


if __name__ == "__main__":
    train_all("final_dataset.csv")
