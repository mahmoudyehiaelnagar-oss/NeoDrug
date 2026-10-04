const API_BASE = "/api";

window.api = {
  async getDrugs(q = "", cls = "all", form = "all", page = 1, size = 50) {
    const params = new URLSearchParams();
    if (q) params.append("q", q);
    if (cls) params.append("cls", cls);
    if (form) params.append("form", form);
    params.append("page", page);
    params.append("size", size);

    try {
      const res = await fetch(`${API_BASE}/drugs?${params.toString()}`);
      if (!res.ok) throw new Error("Network response was not ok");
      return await res.json();
    } catch (e) {
      console.error("API Error fetching drugs:", e);
      return { items: [], total: 0 };
    }
  },

  async getDrugDetail(tradeName) {
    try {
      const res = await fetch(`${API_BASE}/drugs/${encodeURIComponent(tradeName)}`);
      if (!res.ok) throw new Error("Drug not found");
      return await res.json();
    } catch (e) {
      console.error("API Error fetching drug detail:", e);
      return null;
    }
  },

  async checkInteractions(drugsArray) {
    try {
      const res = await fetch(`${API_BASE}/check_interaction`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ drugs: drugsArray })
      });
      if (!res.ok) throw new Error("Interaction check failed");
      return await res.json();
    } catch (e) {
      console.error("API Error checking interactions:", e);
      return { alerts: [] };
    }
  }
};
