// The same frontend is served from Vercel, from the local desktop server, and from
// a Capacitor WebView. Resolve the API base for each environment.
const API_BASE = (function () {
  const explicit = (window.NEO_API_BASE || localStorage.getItem("NEO_API_BASE") || "").trim();
  if (explicit) return explicit.replace(/\/+$/, "");

  const protocol = window.location.protocol;
  const host = window.location.hostname;
  const isCapacitor = protocol === "capacitor:" || protocol === "file:" || !!window.Capacitor;

  if (isCapacitor) return "https://neo-drug.vercel.app/api";
  if (host === "localhost" || host === "127.0.0.1") return "/api";
  return "/api";
})();

const IS_LOCAL_DESKTOP =
  !window.Capacitor &&
  ["http:", "https:"].includes(window.location.protocol) &&
  ["localhost", "127.0.0.1"].includes(window.location.hostname);

// Canonical host. Google Sign-In only works on origins registered in Google Cloud
// Console, so preview *deployment* hosts (neo-drug-<hash>-nemo24.vercel.app) must
// redirect to the canonical domain. Add ?preview=1 to stay on a preview build.
const CANONICAL_HOST = "neo-drug.vercel.app";
(function redirectPreviewHosts() {
  try {
    if (window.Capacitor || !/^https?:$/.test(window.location.protocol)) return;
    const host = window.location.hostname;
    if (host === CANONICAL_HOST) return;
    const isPreviewDeployment = /^neo-drug[a-z0-9.-]*\.vercel\.app$/i.test(host);
    if (!isPreviewDeployment) return;
    if (new URLSearchParams(window.location.search).get("preview") === "1") return;
    window.location.replace(
      "https://" + CANONICAL_HOST + window.location.pathname + window.location.search + window.location.hash
    );
  } catch (e) { /* ignore */ }
})();

window.api = {
  getAuthToken() {
    return localStorage.getItem("NEO_AUTH_TOKEN") || "";
  },

  setAuthToken(token, user = null) {
    if (token) {
      localStorage.setItem("NEO_AUTH_TOKEN", token);
      if (user) {
        localStorage.setItem("NEO_USER_PROFILE", JSON.stringify(user));
      }
    } else {
      localStorage.removeItem("NEO_AUTH_TOKEN");
      localStorage.removeItem("NEO_USER_PROFILE");
    }
  },

  getCachedUser() {
    try {
      const u = localStorage.getItem("NEO_USER_PROFILE");
      return u ? JSON.parse(u) : null;
    } catch (e) {
      return null;
    }
  },

  getAuthHeaders() {
    const headers = { "Content-Type": "application/json" };
    const token = this.getAuthToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const apiKey = localStorage.getItem('GEMINI_API_KEY') || "";
    if (apiKey) {
      headers["x-gemini-key"] = apiKey;
      headers["x-api-key"] = apiKey;
    }
    return headers;
  },

  // One-time cleanup: remove legacy third-party provider keys from the browser.
  cleanupLegacyKeys() {
    try {
      ["GROQ_API_KEY", "GROQ_KEY", "OPENROUTER_API_KEY", "OPENROUTER_KEY", "API_KEY", "GEMINI_KEY"].forEach(k => {
        if (k === "GEMINI_API_KEY") return;
        localStorage.removeItem(k);
      });
    } catch (e) { /* ignore */ }
  },

  async register(email, password, username = "") {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, username })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "فشل إنشاء الحساب");
    if (data.token) this.setAuthToken(data.token, data.user);
    return data;
  },

  async login(email, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "فشل تسجيل الدخول");
    if (data.token) this.setAuthToken(data.token, data.user);
    return data;
  },

  async googleAuth(credential) {
    const res = await fetch(`${API_BASE}/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "فشل تسجيل الدخول بحساب Google");
    if (data.token) this.setAuthToken(data.token, data.user);
    return data;
  },

  async exchangeCloudToken(token) {
    if (!token) return null;
    try {
      const res = await fetch(`${API_BASE}/auth/exchange`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token })
      });
      if (!res.ok) return null;
      const data = await res.json();
      if (data.token) this.setAuthToken(data.token, data.user);
      return data;
    } catch (e) {
      return null;
    }
  },

  async getMe() {
    const token = this.getAuthToken();
    if (!token) return null;

    try {
      let res = await fetch(`${API_BASE}/auth/me`, {
        headers: this.getAuthHeaders()
      });

      // A desktop build may hold a token issued by the cloud deployment. Exchange it
      // for a local token through the server (never trust the token payload locally).
      if (res.status === 401 && IS_LOCAL_DESKTOP) {
        const exchanged = await this.exchangeCloudToken(token);
        if (exchanged && exchanged.user) return exchanged.user;
      }

      if (!res.ok) {
        if (res.status === 401) {
          this.setAuthToken(null);
        }
        return null;
      }
      const profile = await res.json();

      if (profile && profile.email && profile.email !== 'guest@neodrug.app') {
        localStorage.setItem("NEO_USER_PROFILE", JSON.stringify(profile));
      }
      return profile;
    } catch (e) {
      console.warn("Error fetching user profile:", e);
      return this.getCachedUser();
    }
  },

  async redeemPromo(code) {
    const res = await fetch(`${API_BASE}/promo/redeem`, {
      method: "POST",
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ code: (code || "").trim() })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "فشل تفعيل الكود الترويجي");
    if (data.token) {
      this.setAuthToken(data.token);
    }
    return data;
  },

  logout() {
    this.setAuthToken(null);
    if (window.authPro && typeof window.authPro.updateUserUI === "function") {
      window.authPro.updateUserUI(null);
    }
  },

  async getBridgeConfig() {
    // The desktop shell (pywebview) hands us a one-time state and the local bridge URL.
    try {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.get_bridge_config) {
        const config = await window.pywebview.api.get_bridge_config();
        if (config && config.state && config.base) return config;
      }
    } catch (e) {}
    return { state: "", base: "" };
  },

  async checkDesktopBridge(state, base = "") {
    if (!state) return null;
    const root = String(base || "").replace(/\/+$/, "");
    if (!root) return null;
    try {
      const res = await fetch(`${root}/api/auth/desktop-bridge-poll?state=${encodeURIComponent(state)}`);
      if (res.ok) {
        const data = await res.json();
        return data.token || null;
      }
    } catch (e) {}
    return null;
  },

  async getDrugs(q = "", cls = "all", form = "all", page = 1, size = 50) {
    const params = new URLSearchParams();
    if (q) params.append("q", q);
    if (cls) params.append("cls", cls);
    if (form) params.append("form", form);
    params.append("page", page);
    params.append("size", size);

    try {
      const res = await fetch(`${API_BASE}/drugs?${params.toString()}`, {
        headers: this.getAuthHeaders()
      });
      if (!res.ok) throw new Error("Network response was not ok");
      return await res.json();
    } catch (e) {
      console.error("API Error fetching drugs:", e);
      return { items: [], total: 0 };
    }
  },

  async getDrugDetail(tradeName) {
    try {
      const res = await fetch(`${API_BASE}/drugs/${encodeURIComponent(tradeName)}`, {
        headers: this.getAuthHeaders()
      });
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
        headers: this.getAuthHeaders(),
        body: JSON.stringify({ drugs: drugsArray })
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn("Backend interaction check offline, running client-side clinical engine:", e);
    }

    // Client-side offline fallback interaction engine
    const text = drugsArray.join(" ").toLowerCase();
    const alerts = [];
    const has = (...terms) => terms.some(t => text.includes(t.toLowerCase()));

    const isNsaid = has("ibuprofen", "brufen", "diclofenac", "cataflam", "voltaren", "ketoprofen", "ketofan", "naproxen", "piroxicam");
    const isAspirin = has("aspirin", "acetylsalicylic", "asposid", "jusprin", "ezacard");
    const isWarfarin = has("warfarin", "marevan", "xarelto", "eliquis");
    const isNitrate = has("nitrate", "nitroglycerin", "monomak", "effox");
    const isPde5 = has("sildenafil", "viagra", "tadalafil", "cialis");
    const isBeta = has("bisoprolol", "concor", "atenolol", "metoprolol");
    const isCcb = has("verapamil", "isoptin", "diltiazem");
    const isStatin = has("atorvastatin", "lipitor", "simvastatin", "crestor");
    const isMacrolide = has("clarithromycin", "klacid", "erythromycin");

    if (isNsaid && isWarfarin) {
      alerts.push("🛑 **تعارض شديد وخطير (مضادات التخثر + NSAID):** يضاعف خطر النزيف الهضمي الحاد وقرح المعدة.");
    }
    if (isNsaid && isAspirin) {
      alerts.push("🛑 **تعارض شديد (Aspirin + NSAID):** زيادة حادة في احتمالية النزيف المعدي وتثبيط مفعول الأسبرين الوقائي.");
    }
    if (isNitrate && isPde5) {
      alerts.push("🛑 **تعارض مميت (Nitrates + أدوية الضعف الجنسي):** هبوط دوراني حاد وقاتل في ضغط الدم. يمنع الجمع بينهما.");
    }
    if (isBeta && isCcb) {
      alerts.push("🛑 **تعارض قلبي حرج (Beta-blocker + Verapamil):** خطر هبوط شديد في نبضات القلب وإحصار قلبي.");
    }
    if (isStatin && isMacrolide) {
      alerts.push("⚠️ **تحذير شديد (Statins + Macrolides):** خطر انحلال العضلات المخططة وتضرر الكلى.");
    }

    return {
      alerts: alerts,
      ai_report: null,
      drugs: drugsArray.map(d => ({ input: d, trade: d, generic: d, form: "", cls: "عام" }))
    };
  },

  async chat(message, imagesInput = null, history = []) {
    let imagesList = [];
    let prescriptionImg = null;
    let labImg = null;

    if (Array.isArray(imagesInput)) {
      imagesList = imagesInput.filter(Boolean);
    } else if (imagesInput && typeof imagesInput === "object") {
      if (imagesInput.prescription) prescriptionImg = imagesInput.prescription;
      if (imagesInput.lab) labImg = imagesInput.lab;
      if (imagesInput.images && Array.isArray(imagesInput.images)) {
        imagesList = imagesInput.images.filter(Boolean);
      } else {
        imagesList = [prescriptionImg, labImg].filter(Boolean);
      }
    } else if (typeof imagesInput === "string" && imagesInput.trim()) {
      imagesList = [imagesInput.trim()];
    }

    const isDual = imagesList.length >= 2 || (prescriptionImg && labImg);

    // 1. Try calling the backend /api/chat with full multi-turn conversation memory and Auth Token
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: this.getAuthHeaders(),
        body: JSON.stringify({
          message: message || "",
          image_base64: imagesList[0] || null,
          images: imagesList,
          prescription_image: prescriptionImg,
          lab_image: labImg,
          history: history || []
        })
      });

      if (res.status === 403) {
        const errorData = await res.json();
        // Trigger CapCut Pro style paywall modal
        if (window.authPro && typeof window.authPro.openPaywall === "function") {
          window.authPro.openPaywall(errorData.detail?.feature || (isDual ? "dual_ocr" : "limit"), errorData.detail?.message);
        }
        return {
          text: `👑 **ميزة حصرية لـ Neo PRO:**\n${errorData.detail?.message || "لقد استنفدت الحد اليومي المجاني. قم بالترقية لـ PRO للاستخدام غير المحدود."}\n\n✨ [اضغط هنا للترقية وتفعيل باقة PRO مجاناً بالكود الترويجي](#pro)`,
          isTruncated: false
        };
      }

      if (res.ok) {
        const data = await res.json();
        if (data.reply) {
          return { text: data.reply, isTruncated: false };
        }
      }
    } catch (e) {
      console.warn("Backend chat failed, falling back to direct Gemini inference:", e);
    }

    // 2. Direct Gemini REST fallback (works only if the user provides their own key)
    const geminiKey = (localStorage.getItem("GEMINI_API_KEY") || "").trim();
    if (geminiKey) {
      try {
        const systemPrompt = isDual
          ? "أنت استشاري الصيدلة الإكلينيكية وتعديل الجرعات الدوائية لتطبيق Neo Drug. قم بفحص صورة الروشتة وصورة التحليل معاً: 1- استخراج الأدوية والجرعات من الروشتة. 2- قراءة وتفسير نتائج التحاليل المخبرية. 3- تقييم دقة الجرعات والتنبيه الصريح في حال وجود خطأ في الجرعة المكتوبة بناءً على وظائف الكلى أو الكبد أو السكر أو السيولة مع تحديد الجرعة الصحيحة المعدلة (Dose Adjustment) والبدائل الآمنة للمريض."
          : "أنت المساعد الطبي والذكاء الاصطناعي الإكلينيكي المعتمد لتطبيق Neo Drug (دليل الأدوية المصري). قدم استشارات صيدلانية دقيقة وموثوقة، واشرح دواعي الاستعمال والجرعات والبدائل المتاحة في السوق المصري، ونبه دائماً على ضرورة استشارة الطبيب في الحالات الطارئة.";

        const contents = [];
        if (history && history.length > 0) {
          history.slice(-6).forEach(h => {
            const text = typeof h.content === "string" ? h.content : JSON.stringify(h.content);
            if (text) {
              contents.push({ role: h.role === "model" || h.role === "assistant" ? "model" : "user", parts: [{ text }] });
            }
          });
        }

        const parts = [{ text: message || (isDual ? "يرجى مطابقة الروشتة مع التحليل وتدقيق الجرعات وتعديل أي جرعة خاطئة" : "يرجى قراءة هذه الصورة واستخراج الأدوية والجرعات") }];
        imagesList.forEach(img => {
          parts.push({ inline_data: { mime_type: "image/jpeg", data: img.startsWith("data:") ? img.split(",")[1] : img } });
        });
        contents.push({ role: "user", parts });

        const geminiRes = await fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=" + encodeURIComponent(geminiKey), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            system_instruction: { parts: [{ text: systemPrompt }] },
            contents: contents,
            generationConfig: { maxOutputTokens: isDual ? 2000 : 1500, temperature: 0.4 }
          })
        });

        if (geminiRes.ok) {
          const geminiData = await geminiRes.json();
          const cand = geminiData.candidates?.[0]?.content?.parts;
          const reply = cand ? cand.map(p => p.text || "").join("").trim() : "";
          if (reply) {
            return { text: reply, isTruncated: false };
          }
        }
      } catch (err) {
        console.warn("Direct Gemini API failed:", err);
      }
    }

    // 3. Clinical fallback
    return {
      text: isDual
        ? "🩺 **نتائج المطابقة الإكلينيكية وتعديل الجرعة:**\n• ينبغي مراجعة الطبيب المعالج فوراً لضبط جرعات الأدوية بناءً على وظائف الكلى والكبد الظاهرة في التحليل.\n• بعض الأدوية كالمضادات الحيوية ومسكنات NSAIDs تتطلب تخفيض الجرعة إلى النصف أو استبدالها عند انخفاض كفاءة الكلى (eGFR).\n• يرجى إعادة الفحص بعد استقرار الحالة."
        : `🩺 **استشارة إكلينيكية (Neo Drug AI):**\nبناءً على استفسارك عن "${message}":\n• يرجى مراجعة الصيدلي أو الطبيب المعالج للتحقق من الجرعة المناسبة لحالتك.\n• يمكنك البحث عن الدواء وبدائله ومادته الفعالة في صفحة "الأدوية".\n• للتأكد من سلامة تناول الأدوية معاً، يمكنك استخدام صفحة "التعارضات".`,
      isTruncated: false
    };
  }
};

// Run the legacy-key cleanup once on script load.
if (typeof window.api.cleanupLegacyKeys === "function") {
  window.api.cleanupLegacyKeys();
}
