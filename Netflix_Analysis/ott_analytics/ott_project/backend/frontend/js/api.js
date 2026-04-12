/* api.js — All backend calls */

const API_BASE = "http://localhost:5000/api";

const api = {
  async get(endpoint) {
    const res = await fetch(`${API_BASE}${endpoint}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async post(endpoint, body) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    return res.json();
  },

  stats: () => api.get("/stats"),
  health: () => api.get("/health"),
  featureImportance: () => api.get("/feature-importance"),
  search: (q, limit = 10) => api.get(`/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  titles: (page = 1, perPage = 20, type = "", country = "") =>
    api.get(`/titles?page=${page}&per_page=${perPage}${type ? `&type=${type}` : ""}${country ? `&country=${country}` : ""}`),
  recommend: (title, n = 10, contentType = null) =>
    api.post("/recommend", { title, n, content_type: contentType }),
  predictType: (data) => api.post("/predict/type", data),
  predictRating: (data) => api.post("/predict/rating", data),
  predictGenre: (data) => api.post("/predict/genre", data),
};
