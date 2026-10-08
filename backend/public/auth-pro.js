/**
 * Neo Drug — Auth & CapCut Pro-Style Subscription Management Module
 * =================================================================
 * Provides global authentication, official Google Sign-In (Gmail & One Tap),
 * PRO paywall modal, WhatsApp activation (01070142811), promo redemption,
 * and top-bar status pill injection across all pages.
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
  const DEFAULT_GOOGLE_CLIENT_ID = '1096005273682-ved543vk8uj22r0185dsapd5qvkfo8te.apps.googleusercontent.com';

  window.authPro = {
    getUser() {
      return currentUser;
    },

    isPro() {
      return !!(currentUser && currentUser.is_pro);
    },

    async init() {
      // 1. Immediately load cached user from localStorage for zero-delay persistence across all pages
      currentUser = window.api.getCachedUser();
      this.injectHeaderWidget();
      this.injectModal();
      this.updateUserUI(currentUser);
      this.loadGoogleSDK();

      // 2. Asynchronously verify and refresh profile from backend if token exists
      if (window.api.getAuthToken()) {
        try {
          const fresh = await window.api.getMe();
          if (fresh) {
            currentUser = fresh;
            this.updateUserUI(currentUser);
          }
        } catch (e) {
          console.warn('Could not refresh user profile:', e);
        }
      }
    },

    loadGoogleSDK() {
      if (document.getElementById('googleGsiScript')) return;
      const script = document.createElement('script');
      script.id = 'googleGsiScript';
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = () => {
        this.initGoogleGSI();
      };
      document.head.appendChild(script);
    },

    initGoogleGSI() {
      if (!window.google || !window.google.accounts || !window.google.accounts.id) return;

      try {
        const clientId = window.GOOGLE_CLIENT_ID || DEFAULT_GOOGLE_CLIENT_ID;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) => {
            if (response && response.credential) {
              this.handleGoogleCredential(response.credential);
            }
          },
          auto_select: false,
          cancel_on_tap_outside: true
        });

        // Render button if container exists
        const btnContainer = document.getElementById('googleGsiButtonContainer');
        if (btnContainer) {
          btnContainer.innerHTML = '';
          window.google.accounts.id.renderButton(btnContainer, {
            theme: 'outline',
            size: 'large',
            type: 'standard',
            text: 'signin_with',
            shape: 'pill',
            logo_alignment: 'left',
            width: 320,
            locale: 'ar'
          });
        }

        // Show Google One Tap if not logged in
        if (!currentUser || !currentUser.email || currentUser.email === 'guest@neodrug.app') {
          setTimeout(() => {
            try { window.google.accounts.id.prompt(); } catch (e) {}
          }, 1500);
        }
      } catch (err) {
        console.warn('Google GSI initialization notice:', err);
      }
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
          btn.innerHTML = `<span>✨ ترقية لـ PRO 👑</span>`;
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
            <p style="font-size:12px; color:#64748b; line-height:1.5; margin-bottom:14px;">
              أدخل كود الهدية أو كود الاشتراك الذي حصلت عليه لتنشيط باقة Neo PRO فوراً:
            </p>

            <div style="margin-bottom:14px;">
              <input type="text" id="promoCodeInput" placeholder="أدخل كود التفعيل الترويجي هنا..." style="width:100%; padding:11px 14px; border:1.5px solid var(--border); border-radius:12px; font-family:var(--font-mono); font-size:14px; font-weight:700; text-transform:uppercase; outline:none; box-sizing:border-box;">
            </div>

            <div id="redeemMsg" style="font-size:12px; font-weight:600; margin-bottom:12px; display:none;"></div>

            <button id="redeemSubmitBtn" class="btn-pro-cta" onclick="window.authPro.submitRedeem()">
              تفعيل كود PRO الآن 🚀
            </button>

            <div style="text-align:center; margin-top:16px;">
              <a href="javascript:void(0)" onclick="window.authPro.openWhatsAppActivation()" style="font-size:12.5px; color:#16a34a; font-weight:700; text-decoration:none; display:inline-flex; align-items:center; gap:6px;">
                <span>💬</span> ليس لديك كود؟ اطلب اشتراكك عبر واتساب (${DISPLAY_PHONE})
              </a>
            </div>
          </div>

          <!-- Tab 3: Account (Login & Register & Google Auth) -->
          <div id="tabContentAuth" class="pro-tab-content" style="display:none; padding: 20px;">
            <div id="userLoggedInView" style="display:none; text-align:right; padding: 4px 0;">
              <div style="background:var(--surface-subtle); border:1.5px solid var(--border); border-radius:18px; padding:18px; margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom:1px solid #e2e8f0; padding-bottom:10px;">
                  <div style="font-size:14px; font-weight:800; color:#0f172a; display:flex; align-items:center; gap:6px;">
                    <span>👤</span> بيانات الحساب والاشتراك
                  </div>
                  <div id="userProfileBadge"></div>
                </div>

                <div style="font-size:13px; color:#475569; margin-bottom:8px;">
                  <strong>البريد الإلكتروني:</strong> <span id="userProfileEmail" style="font-family:var(--font-mono); font-weight:700; color:#0f172a;"></span>
                </div>
                <div style="font-size:13px; color:#475569; margin-bottom:8px;">
                  <strong>نوع الباقة:</strong> <span id="userProfileTier" style="font-weight:700;"></span>
                </div>
                <div style="font-size:13px; color:#475569; margin-bottom:10px;">
                  <strong>صلاحية الاشتراك:</strong> <span id="userProfileExpiry" style="font-weight:800; color:#0d9488;"></span>
                </div>

                <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:8px 12px; font-size:11.5px; color:#166534; line-height:1.5;">
                  ✓ حسابك مرتبط ويعمل على أي عدد من أجهزتك (الموبايل، التابلت، والكمبيوتر) في نفس الوقت بحرية تامة.
                </div>
              </div>

              <div style="display:flex; gap:8px;">
                <button class="btn btn-primary" style="flex:1; padding:10px; font-weight:700; font-size:13px;" onclick="window.authPro.openWhatsAppActivation()">
                  💬 تجديد / ترقية عبر واتساب
                </button>
                <button class="btn" style="background:#fee2e2; color:#ef4444; border:none; padding:10px 16px; border-radius:10px; font-weight:700; cursor:pointer;" onclick="window.authPro.logout()">
                  خروج ✕
                </button>
              </div>
            </div>

            <div id="userAuthFormView">
              <!-- Official Google Sign-In & One Tap Section -->
              <div style="margin-bottom:14px; text-align:center;">
                <div id="googleGsiButtonContainer" style="display:flex; justify-content:center; margin-bottom:8px;"></div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:10px 12px;">
                  <div style="display:flex; gap:6px;">
                    <input type="email" id="googleEmailInput" placeholder="أو اكتب بريدك Gmail للدخول الفوري..." style="flex:1; padding:7px 10px; border:1px solid #cbd5e1; border-radius:8px; font-size:12px; outline:none; box-sizing:border-box;" onkeypress="if(event.key==='Enter') window.authPro.signInWithGoogleInput()">
                    <button type="button" class="btn btn-primary" style="padding:7px 14px; font-size:12px; font-weight:700; border-radius:8px; white-space:nowrap;" onclick="window.authPro.signInWithGoogleInput()">
                      دخول سريع 🌐
                    </button>
                  </div>
                </div>
              </div>

              <div style="display:flex; align-items:center; gap:8px; margin-bottom:14px;">
                <div style="flex:1; height:1px; background:#e2e8f0;"></div>
                <span style="font-size:11px; color:#94a3b8; font-weight:600;">أو بالبريد وكلمة المرور</span>
                <div style="flex:1; height:1px; background:#e2e8f0;"></div>
              </div>

              <div style="display:flex; gap:8px; margin-bottom:14px; border-bottom:1px solid #e2e8f0; padding-bottom:8px;">
                <button id="authSubTabLogin" style="background:none; border:none; font-weight:700; font-size:13px; color:#0d9488; cursor:pointer;" onclick="window.authPro.setAuthMode('login')">تسجيل الدخول</button>
                <span style="color:#cbd5e1;">|</span>
                <button id="authSubTabRegister" style="background:none; border:none; font-weight:600; font-size:13px; color:#64748b; cursor:pointer;" onclick="window.authPro.setAuthMode('register')">إنشاء حساب جديد</button>
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
      if (tab === 'auth') {
        this.initGoogleGSI();
      }
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
            ? 'باقة المحترفين (Neo Drug PRO) 👑'
            : 'باقة مجانية (Free Tier) 🔒';
          document.getElementById('userProfileBadge').innerHTML = currentUser.is_pro
            ? '<span class="badge-pro">PRO ACTIVE</span>'
            : '<span class="badge-free">FREE</span>';
          document.getElementById('userProfileExpiry').textContent = currentUser.is_pro
            ? (currentUser.days_left > 1000 ? 'وصول دائم مدى الحياة ♾️' : `متبقي ${currentUser.days_left} يوم`)
            : 'مقفلة (تتطلب تفعيل الاشتراك)';
        } else {
          this.initGoogleGSI();
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

      // Check if logged in first; prompt login so PRO is permanently attached to user's real email
      if (!currentUser || !currentUser.email || currentUser.email === 'guest@neodrug.app') {
        msg.style.display = 'block';
        msg.style.color = '#d97706';
        msg.textContent = 'يرجى تسجيل الدخول أو إنشاء حسابك أولاً ليتم ربط باقة PRO بإيميلك الشخصي بشكل دائم.';
        setTimeout(() => this.openAuth('login'), 1200);
        return;
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

        if (res.user) {
          currentUser = res.user;
          this.updateUserUI(currentUser);
        } else {
          currentUser = await window.api.getMe();
          this.updateUserUI(currentUser);
        }

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

    async handleGoogleCredential(credential) {
      const msg = document.getElementById('authMsg');
      if (msg) {
        msg.style.display = 'block';
        msg.style.color = '#0284c7';
        msg.textContent = 'جاري تسجيل الدخول بحساب Google... ⏳';
      }

      try {
        const res = await window.api.googleAuth(credential);
        if (msg) {
          msg.style.color = '#15803d';
          msg.textContent = res.message || 'تم تسجيل الدخول بنجاح!';
        }

        if (res.user) {
          currentUser = res.user;
          this.updateUserUI(currentUser);
        } else {
          currentUser = await window.api.getMe();
          this.updateUserUI(currentUser);
        }

        setTimeout(() => {
          this.closeModal();
        }, 600);
      } catch (err) {
        if (msg) {
          msg.style.display = 'block';
          msg.style.color = 'var(--danger)';
          msg.textContent = err.message || 'فشل تسجيل الدخول بحساب Google.';
        }
      }
    },

    async signInWithGoogleInput() {
      const emailInput = document.getElementById('googleEmailInput');
      const emailClean = (emailInput?.value || '').trim().toLowerCase();
      if (!emailClean || !emailClean.includes('@')) {
        alert('يرجى كتابة بريد إلكتروني صحيح (Gmail).');
        return;
      }

      const msg = document.getElementById('authMsg');
      if (msg) {
        msg.style.display = 'block';
        msg.style.color = '#0284c7';
        msg.textContent = 'جاري تسجيل الدخول بحساب Google... ⏳';
      }

      try {
        const name = emailClean.split('@')[0];
        const res = await window.api.googleAuth(null, emailClean, name);

        if (msg) {
          msg.style.color = '#15803d';
          msg.textContent = res.message || 'تم تسجيل الدخول بنجاح!';
        }

        if (res.user) {
          currentUser = res.user;
          this.updateUserUI(currentUser);
        } else {
          currentUser = await window.api.getMe();
          this.updateUserUI(currentUser);
        }

        setTimeout(() => {
          this.closeModal();
        }, 600);
      } catch (err) {
        if (msg) {
          msg.style.display = 'block';
          msg.style.color = 'var(--danger)';
          msg.textContent = err.message || 'فشل تسجيل الدخول.';
        }
      }
    },

    async signInWithGooglePrompt() {
      // Try Google GSI prompt first
      if (window.google && window.google.accounts && window.google.accounts.id) {
        try {
          window.google.accounts.id.prompt();
          return;
        } catch (e) {}
      }

      // Fallback manual Gmail entry
      const email = prompt("أدخل بريدك الإلكتروني لحساب Google (Gmail):");
      if (!email || !email.trim()) return;

      const emailClean = email.trim().toLowerCase();
      if (!emailClean.includes("@")) {
        alert("يرجى إدخال بريد إلكتروني صحيح.");
        return;
      }

      const msg = document.getElementById('authMsg');
      if (msg) {
        msg.style.display = 'block';
        msg.style.color = '#0284c7';
        msg.textContent = 'جاري التحقق وتسجيل الدخول بحساب Google... ⏳';
      }

      try {
        const name = emailClean.split('@')[0];
        const res = await window.api.googleAuth(null, emailClean, name);

        if (msg) {
          msg.style.color = '#15803d';
          msg.textContent = res.message || 'تم تسجيل الدخول بنجاح!';
        }

        if (res.user) {
          currentUser = res.user;
          this.updateUserUI(currentUser);
        } else {
          currentUser = await window.api.getMe();
          this.updateUserUI(currentUser);
        }

        setTimeout(() => {
          this.closeModal();
        }, 700);

      } catch (err) {
        if (msg) {
          msg.style.display = 'block';
          msg.style.color = 'var(--danger)';
          msg.textContent = err.message || 'فشل تسجيل الدخول بحساب Google.';
        }
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
