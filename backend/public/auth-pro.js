/**
 * Neo Drug — Auth & CapCut Pro-Style Subscription Management Module
 * =================================================================
 * Provides global authentication, PRO paywall modal, WhatsApp activation (01070142811),
 * promo redemption, and top-bar status pill injection across all pages.
 */

(function() {
  'use strict';

  let currentUser = null;
  let activeTab = 'upgrade'; // 'upgrade', 'redeem', 'auth'
  let authMode = 'login'; // 'login', 'register'
  let selectedPlan = {
    name: 'الباقة السنوية (499 ج.م / سنة - وفّر 45%)',
    price: '499 ج.م',
    period: 'سنوياً'
  };

  const WHATSAPP_PHONE = '201070142811';
  const DISPLAY_PHONE = '01070142811';

  window.authPro = {
    getUser() {
      return currentUser;
    },

    isPro() {
      return !!(currentUser && currentUser.is_pro);
    },

    async init() {
      try {
        currentUser = await window.api.getMe();
      } catch (e) {
        console.warn('Could not fetch user profile:', e);
      }
      this.injectHeaderWidget();
      this.injectModal();
      this.updateUserUI(currentUser);
    },

    injectHeaderWidget() {
      const appbars = document.querySelectorAll('.appbar');
      appbars.forEach(bar => {
        if (bar.querySelector('.auth-pro-widget')) return;

        const widget = document.createElement('div');
        widget.className = 'auth-pro-widget';
        widget.style.cssText = 'display:flex; align-items:center; gap:8px; margin-right:auto;';

        const btn = document.createElement('button');
        btn.id = 'headerProBtn';
        btn.className = 'pro-badge-pill pro-badge-free';
        btn.innerHTML = '<span>✨ ترقية لـ PRO</span>';
        btn.onclick = (e) => {
          e.preventDefault();
          this.openPaywall();
        };

        const userMenuBtn = document.createElement('button');
        userMenuBtn.id = 'headerUserBtn';
        userMenuBtn.style.cssText = 'background:var(--surface-subtle); border:1px solid var(--border); border-radius:10px; padding:6px 10px; font-size:12px; font-weight:700; color:var(--fg); cursor:pointer; display:flex; align-items:center; gap:6px;';
        userMenuBtn.innerHTML = '<span>👤 حسابي</span>';
        userMenuBtn.onclick = (e) => {
          e.preventDefault();
          if (currentUser && currentUser.email && currentUser.email !== 'guest@neodrug.app') {
            this.openPaywall('auth');
          } else {
            this.openAuth('login');
          }
        };

        widget.appendChild(btn);
        widget.appendChild(userMenuBtn);
        bar.appendChild(widget);
      });
    },

    updateUserUI(user) {
      currentUser = user;
      const proBtns = document.querySelectorAll('#headerProBtn');
      const userBtns = document.querySelectorAll('#headerUserBtn');

      proBtns.forEach(btn => {
        if (user && user.is_pro) {
          btn.className = 'pro-badge-pill pro-badge-active';
          btn.innerHTML = `<span>👑 عضو PRO (${user.days_left > 1000 ? 'دائم ♾️' : user.days_left + ' يوم'})</span>`;
        } else {
          btn.className = 'pro-badge-pill pro-badge-free';
          const remaining = Math.max(0, (user?.ai_queries_limit || 5) - (user?.ai_queries_used || 0));
          btn.innerHTML = `<span>✨ ترقية PRO <small style="opacity:0.85">(${remaining} متبقي)</small></span>`;
        }
      });

      userBtns.forEach(btn => {
        if (user && user.email && user.email !== 'guest@neodrug.app') {
          btn.innerHTML = `<span>👤 ${user.username || user.email.split('@')[0]}</span>`;
        } else {
          btn.innerHTML = '<span>🔐 تسجيل الدخول</span>';
        }
      });
    },

    injectModal() {
      if (document.getElementById('proModalBackdrop')) return;

      const backdrop = document.createElement('div');
      backdrop.id = 'proModalBackdrop';
      backdrop.className = 'pro-modal-backdrop';

      backdrop.innerHTML = `
        <div class="pro-modal-card">
          <button class="pro-modal-close" onclick="window.authPro.closeModal()">✕</button>

          <!-- Banner Header -->
          <div class="pro-modal-header">
            <div class="pro-modal-title">👑 Neo Drug PRO</div>
            <div class="pro-modal-subtitle">الميزات الإكلينيكية الكاملة والذكاء الاصطناعي اللامحدود للأطباء والصيادلة</div>
          </div>

          <!-- Tabs Navigation -->
          <div class="pro-nav-tabs">
            <button class="pro-nav-tab active" id="tabBtnUpgrade" onclick="window.authPro.switchTab('upgrade')">✨ الباقات والترقية</button>
            <button class="pro-nav-tab" id="tabBtnRedeem" onclick="window.authPro.switchTab('redeem')">🎁 كود ترويجي</button>
            <button class="pro-nav-tab" id="tabBtnAuth" onclick="window.authPro.switchTab('auth')">🔐 الحساب</button>
          </div>

          <!-- Tab 1: Upgrade Plans & WhatsApp Activation -->
          <div id="tabContentUpgrade" class="pro-tab-content">
            <div class="pro-plans-grid">
              <div class="pro-plan-card selected" onclick="window.authPro.selectPlan(this, 'الباقة السنوية (499 ج.م / سنة - وفّر 45%)', '499 ج.م', 'سنوياً')">
                <span class="pro-plan-tag">الأكثر طلباً 🔥</span>
                <div class="pro-plan-name">الباقة السنوية</div>
                <div class="pro-plan-price">499 ج.م</div>
                <div class="pro-plan-cycle">سنوياً (وفّر 45%)</div>
              </div>
              <div class="pro-plan-card" onclick="window.authPro.selectPlan(this, 'الباقة الشهرية (69 ج.م / شهر)', '69 ج.م', 'شهرياً')">
                <div class="pro-plan-name">الباقة الشهرية</div>
                <div class="pro-plan-price">69 ج.م</div>
                <div class="pro-plan-cycle">شهرياً (مرن)</div>
              </div>
            </div>

            <div class="pro-features-list">
              <div class="pro-feature-item">
                <span class="pro-feature-name">📄 قراءة وتحليل الروشتات (OCR)</span>
                <span class="pro-feature-val pro-highlight">غير محدود 👑</span>
              </div>
              <div class="pro-feature-item">
                <span class="pro-feature-name">🧪 مطابقة الروشتة مع التحاليل وتدقيق الجرعات</span>
                <span class="pro-feature-val pro-highlight">متاح بالكامل ⚡</span>
              </div>
              <div class="pro-feature-item">
                <span class="pro-feature-name">🤖 استشارات المساعد الإكلينيكي AI</span>
                <span class="pro-feature-val pro-highlight">غير محدود (Turbo)</span>
              </div>
              <div class="pro-feature-item">
                <span class="pro-feature-name">💊 دليل الأدوية والبدائل (9,325 دواء)</span>
                <span class="pro-feature-val">مجاني للجميع ✓</span>
              </div>
            </div>

            <div style="padding: 0 20px 20px;">
              <!-- WhatsApp Activation CTA Button -->
              <button class="btn-pro-cta" style="background: linear-gradient(135deg, #16a34a, #15803d, #0d9488) !important; box-shadow: 0 4px 18px rgba(22, 163, 74, 0.45) !important;" onclick="window.authPro.openWhatsAppActivation()">
                💬 تفعيل الاشتراك عبر واتساب (${DISPLAY_PHONE})
              </button>

              <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; font-size:12px;">
                <span style="color:#64748b;">طرق الدفع: فودافون كاش • إنستاباي InstaPay</span>
                <a href="javascript:void(0)" onclick="window.authPro.switchTab('redeem')" style="color:#0284c7; font-weight:700; text-decoration:none;">معي كود ترويجي 🎁</a>
              </div>
            </div>
          </div>

          <!-- Tab 2: Promo / Gift Code Redemption -->
          <div id="tabContentRedeem" class="pro-tab-content" style="display:none; padding: 20px;">
            <div style="font-size:13.5px; font-weight:700; margin-bottom:6px; color:#0f172a;">هل تمتلك كود تفعيل ترويجي؟ 🎁</div>
            <p style="font-size:12px; color:#64748b; line-height:1.5; margin-bottom:12px;">
              أدخل كود الهدية أو كود التفعيل لتنشيط اشتراك Neo PRO مجاناً وفوراً:
            </p>

            <div style="margin-bottom:10px;">
              <input type="text" id="promoCodeInput" placeholder="أدخل الكود هنا (مثال: NEOPRO)..." style="width:100%; padding:10px 14px; border:1.5px solid var(--border); border-radius:12px; font-family:var(--font-mono); font-size:14px; font-weight:700; text-transform:uppercase; outline:none; box-sizing:border-box;">
            </div>

            <div style="font-size:11.5px; color:#64748b; margin-bottom:4px;">أكواد سريعة للتجربة:</div>
            <div class="promo-chips-row">
              <span class="promo-chip" onclick="window.authPro.fillPromo('NEOPRO')">⚡ NEOPRO (30 يوم)</span>
              <span class="promo-chip" onclick="window.authPro.fillPromo('VIP2026')">👑 VIP2026 (90 يوم)</span>
              <span class="promo-chip" onclick="window.authPro.fillPromo('PHARMA2026')">🩺 PHARMA2026 (سنة)</span>
            </div>

            <div id="redeemMsg" style="font-size:12px; font-weight:600; margin-bottom:12px; display:none;"></div>

            <button id="redeemSubmitBtn" class="btn-pro-cta" onclick="window.authPro.submitRedeem()">
              تفعيل كود PRO الآن 🚀
            </button>

            <div style="text-align:center; margin-top:14px;">
              <a href="javascript:void(0)" onclick="window.authPro.openWhatsAppActivation()" style="font-size:12px; color:#16a34a; font-weight:700; text-decoration:none;">
                💬 اطلب كود تفعيل خاص عبر واتساب (${DISPLAY_PHONE})
              </a>
            </div>
          </div>

          <!-- Tab 3: Account (Login & Register) -->
          <div id="tabContentAuth" class="pro-tab-content" style="display:none; padding: 20px;">
            <div id="userLoggedInView" style="display:none; text-align:center; padding: 10px 0;">
              <div style="font-size:36px; margin-bottom:8px;">👤</div>
              <div id="userProfileEmail" style="font-weight:700; font-size:15px; margin-bottom:4px;"></div>
              <div id="userProfileTier" style="font-size:12px; color:#0d9488; font-weight:700; margin-bottom:16px;"></div>

              <div style="margin-bottom:16px;">
                <button class="btn btn-primary" style="padding:8px 16px; font-size:12.5px; margin-left:6px;" onclick="window.authPro.openWhatsAppActivation()">
                  💬 تواصل مع الإدارة عبر واتساب
                </button>
                <button class="btn" style="background:#fee2e2; color:#ef4444; border:none; padding:8px 16px; border-radius:10px; font-weight:700; cursor:pointer;" onclick="window.authPro.logout()">
                  تسجيل الخروج ✕
                </button>
              </div>
            </div>

            <div id="userAuthFormView">
              <div style="display:flex; gap:8px; margin-bottom:16px; border-bottom:1px solid #e2e8f0; padding-bottom:8px;">
                <button id="authSubTabLogin" style="background:none; border:none; font-weight:700; font-size:13.5px; color:#0d9488; cursor:pointer;" onclick="window.authPro.setAuthMode('login')">تسجيل الدخول</button>
                <span style="color:#cbd5e1;">|</span>
                <button id="authSubTabRegister" style="background:none; border:none; font-weight:600; font-size:13.5px; color:#64748b; cursor:pointer;" onclick="window.authPro.setAuthMode('register')">إنشاء حساب جديد</button>
              </div>

              <div style="margin-bottom:10px;">
                <label style="display:block; font-size:11.5px; font-weight:700; color:#475569; margin-bottom:4px;">البريد الإلكتروني:</label>
                <input type="email" id="authEmailInput" placeholder="name@example.com" style="width:100%; padding:9px 12px; border:1px solid var(--border); border-radius:10px; font-size:13px; outline:none; box-sizing:border-box;">
              </div>

              <div style="margin-bottom:14px;">
                <label style="display:block; font-size:11.5px; font-weight:700; color:#475569; margin-bottom:4px;">كلمة المرور:</label>
                <input type="password" id="authPasswordInput" placeholder="••••••••" style="width:100%; padding:9px 12px; border:1px solid var(--border); border-radius:10px; font-size:13px; outline:none; box-sizing:border-box;">
              </div>

              <div id="authMsg" style="font-size:12px; font-weight:600; margin-bottom:12px; display:none;"></div>

              <button id="authSubmitBtn" class="btn btn-primary" style="width:100%; padding:10px; font-weight:700;" onclick="window.authPro.submitAuth()">
                دخول 🔐
              </button>
            </div>
          </div>

        </div>
      `;

      document.body.appendChild(backdrop);
    },

    openPaywall(tab = 'upgrade', customMsg = '') {
      const backdrop = document.getElementById('proModalBackdrop');
      if (!backdrop) return;
      this.switchTab(tab);
      backdrop.classList.add('active');
    },

    openRedeem() {
      this.openPaywall('redeem');
    },

    openAuth(mode = 'login') {
      this.openPaywall('auth');
      this.setAuthMode(mode);
    },

    closeModal() {
      const backdrop = document.getElementById('proModalBackdrop');
      if (backdrop) backdrop.classList.remove('active');
    },

    switchTab(tabName) {
      activeTab = tabName;
      ['Upgrade', 'Redeem', 'Auth'].forEach(t => {
        const btn = document.getElementById(`tabBtn${t}`);
        const content = document.getElementById(`tabContent${t}`);
        if (btn) btn.classList.toggle('active', t.toLowerCase() === tabName);
        if (content) content.style.display = (t.toLowerCase() === tabName) ? 'block' : 'none';
      });

      if (tabName === 'auth') {
        const loggedIn = currentUser && currentUser.email && currentUser.email !== 'guest@neodrug.app';
        document.getElementById('userLoggedInView').style.display = loggedIn ? 'block' : 'none';
        document.getElementById('userAuthFormView').style.display = loggedIn ? 'none' : 'block';
        if (loggedIn) {
          document.getElementById('userProfileEmail').textContent = currentUser.email;
          document.getElementById('userProfileTier').textContent = currentUser.is_pro
            ? `👑 عضوية PRO مفعلة (${currentUser.days_left > 1000 ? 'مدى الحياة ♾️' : currentUser.days_left + ' يوم متبقي'})`
            : 'باقة مجانية (Free Tier)';
        }
      }
    },

    selectPlan(cardEl, planName, price, period) {
      document.querySelectorAll('.pro-plan-card').forEach(c => c.classList.remove('selected'));
      cardEl.classList.add('selected');
      selectedPlan = { name: planName, price, period };
    },

    openWhatsAppActivation() {
      const email = (currentUser && currentUser.email && currentUser.email !== 'guest@neodrug.app')
        ? currentUser.email
        : 'أرغب في تسجيل حساب جديد وتفعيله';

      const text = `مرحباً دكتور محمود،\nأرغب في تفعيل اشتراك باقة Neo Drug PRO 👑✨\n\n• الباقة المختارة: ${selectedPlan.name}\n• البريد الإلكتروني: ${email}\n• طريقة التحويل المفضلة: فودافون كاش / إنستاباي InstaPay\n\nبرجاء إرسال تفاصيل التحويل وكود التفعيل الخاص بي. شكراً جزيلاً!`;

      const whatsappUrl = `https://wa.me/${WHATSAPP_PHONE}?text=${encodeURIComponent(text)}`;
      window.open(whatsappUrl, '_blank');
    },

    fillPromo(code) {
      const input = document.getElementById('promoCodeInput');
      if (input) {
        input.value = code;
        input.focus();
      }
    },

    async submitRedeem() {
      const input = document.getElementById('promoCodeInput');
      const msg = document.getElementById('redeemMsg');
      const btn = document.getElementById('redeemSubmitBtn');
      const code = (input?.value || '').trim();

      if (!code) {
        msg.style.display = 'block';
        msg.style.color = 'var(--danger)';
        msg.textContent = 'يرجى إدخال كود التفعيل أولاً.';
        return;
      }

      // Check if logged in first; if not, auto register an account
      if (!currentUser || !currentUser.email || currentUser.email === 'guest@neodrug.app') {
        try {
          msg.style.display = 'block';
          msg.style.color = '#0284c7';
          msg.textContent = 'جاري تجهيز حسابك وتفعيل الكود...';
          const guestEmail = `user_${Math.random().toString(36).substring(2, 8)}@neodrug.app`;
          await window.api.register(guestEmail, 'NeoDrug2026!');
        } catch (e) {
          // continue
        }
      }

      btn.disabled = true;
      btn.textContent = '⏳ جاري التفعيل...';

      try {
        const res = await window.api.redeemPromo(code);
        msg.style.display = 'block';
        msg.style.color = '#15803d';
        msg.textContent = `🎉 ${res.message}`;

        currentUser = await window.api.getMe();
        this.updateUserUI(currentUser);

        setTimeout(() => {
          this.closeModal();
          alert('🎉 تم تفعيل باقة Neo PRO بنجاح! جميع الميزات الإكلينيكية أصبحت متاحة الآن بلا حدود.');
        }, 1200);

      } catch (err) {
        msg.style.display = 'block';
        msg.style.color = 'var(--danger)';
        msg.textContent = err.message || 'كود غير صالح أو منتهي.';
      } finally {
        btn.disabled = false;
        btn.textContent = 'تفعيل كود PRO الآن 🚀';
      }
    },

    setAuthMode(mode) {
      authMode = mode;
      const loginTab = document.getElementById('authSubTabLogin');
      const regTab = document.getElementById('authSubTabRegister');
      const submitBtn = document.getElementById('authSubmitBtn');

      if (mode === 'login') {
        loginTab.style.color = '#0d9488';
        loginTab.style.fontWeight = '700';
        regTab.style.color = '#64748b';
        regTab.style.fontWeight = '600';
        submitBtn.textContent = 'تسجيل الدخول 🔐';
      } else {
        regTab.style.color = '#0d9488';
        regTab.style.fontWeight = '700';
        loginTab.style.color = '#64748b';
        loginTab.style.fontWeight = '600';
        submitBtn.textContent = 'إنشاء حساب جديد ✨';
      }
    },

    async submitAuth() {
      const email = document.getElementById('authEmailInput')?.value.trim();
      const password = document.getElementById('authPasswordInput')?.value.trim();
      const msg = document.getElementById('authMsg');
      const btn = document.getElementById('authSubmitBtn');

      if (!email || !password) {
        msg.style.display = 'block';
        msg.style.color = 'var(--danger)';
        msg.textContent = 'يرجى إدخال البريد الإلكتروني وكلمة المرور.';
        return;
      }

      btn.disabled = true;
      btn.textContent = '⏳ جاري المعالجة...';

      try {
        let res;
        if (authMode === 'register') {
          res = await window.api.register(email, password);
        } else {
          res = await window.api.login(email, password);
        }

        msg.style.display = 'block';
        msg.style.color = '#15803d';
        msg.textContent = res.message || 'تمت العملية بنجاح!';

        currentUser = await window.api.getMe();
        this.updateUserUI(currentUser);

        setTimeout(() => {
          this.closeModal();
        }, 800);

      } catch (err) {
        msg.style.display = 'block';
        msg.style.color = 'var(--danger)';
        msg.textContent = err.message || 'حدث خطأ أثناء العملية.';
      } finally {
        btn.disabled = false;
        btn.textContent = authMode === 'login' ? 'تسجيل الدخول 🔐' : 'إنشاء حساب جديد ✨';
      }
    },

    logout() {
      window.api.logout();
      currentUser = null;
      this.updateUserUI(null);
      this.switchTab('auth');
    }
  };

  // Auto initialize on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => window.authPro.init());
  } else {
    window.authPro.init();
  }
})();
