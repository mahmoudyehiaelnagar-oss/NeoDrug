/**
 * Neo Drug — Creative Interactive Background & Molecular Canvas
 * محرك الخلفية الإبداعية المتفاعلة وجزيئات الأدوية ثلاثية الأبعاد
 */

(function () {
  'use strict';

  function initCreativeBackground() {
    if (document.getElementById('creative-canvas')) return;

    // 1. إنشاء طبقة الأورورا السديمية المتدفقة
    const bgLayer = document.createElement('div');
    bgLayer.className = 'creative-bg-layer';
    bgLayer.innerHTML = `
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    `;
    document.body.prepend(bgLayer);

    // 2. شبكة الماتريكس النقطية الطبية
    const gridOverlay = document.createElement('div');
    gridOverlay.className = 'creative-grid-overlay';
    document.body.prepend(gridOverlay);

    // 3. كانفاس الجزيئات التفاعلية
    const canvas = document.createElement('canvas');
    canvas.id = 'creative-canvas';
    document.body.prepend(canvas);

    // 4. تشغيل محرك الجزيئات
    setupMolecularEngine(canvas);
  }

  function setupMolecularEngine(canvas) {
    const ctx = canvas.getContext('2d');
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    let mouse = { x: -1000, y: -1000, radius: 150 };

    window.addEventListener('resize', () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    }, { passive: true });

    window.addEventListener('mousemove', (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    }, { passive: true });

    window.addEventListener('mouseleave', () => {
      mouse.x = -1000;
      mouse.y = -1000;
    }, { passive: true });

    // ألوان طبية زمردية ونيون متوهجة
    const colors = [
      'rgba(45, 212, 191, 0.95)', // Bright Teal
      'rgba(6, 182, 212, 0.95)',  // Cyan
      'rgba(52, 211, 153, 0.95)', // Bright Emerald
      'rgba(56, 189, 248, 0.90)', // Sky Blue
      'rgba(167, 139, 250, 0.85)' // Purple
    ];

    const particleCount = Math.min(Math.floor((width * height) / 28000), 38);
    const particles = [];

    class MolecularNode {
      constructor() {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.radius = Math.random() * 2.8 + 1.8;
        this.baseRadius = this.radius;
        this.color = colors[Math.floor(Math.random() * colors.length)];
        this.vx = (Math.random() - 0.5) * 0.7;
        this.vy = (Math.random() - 0.5) * 0.7;
        this.isSpecial = Math.random() > 0.80;
        this.pulse = Math.random() * Math.PI;
      }

      update() {
        this.x += this.vx;
        this.y += this.vy;

        if (this.x < 0) this.x = width;
        if (this.x > width) this.x = 0;
        if (this.y < 0) this.y = height;
        if (this.y > height) this.y = 0;

        const dx = mouse.x - this.x;
        const dy = mouse.y - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < mouse.radius) {
          const force = (mouse.radius - dist) / mouse.radius;
          const angle = Math.atan2(dy, dx);
          this.x -= Math.cos(angle) * force * 2.5;
          this.y -= Math.sin(angle) * force * 2.5;
          this.radius = this.baseRadius * (1 + force * 1.0);
        } else {
          this.radius = this.baseRadius;
        }

        this.pulse += 0.04;
      }

      draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = this.color;
        ctx.shadowColor = this.color;
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.shadowBlur = 0;

        if (this.isSpecial) {
          ctx.beginPath();
          const ringR = this.radius * (2.2 + Math.sin(this.pulse) * 0.4);
          ctx.arc(this.x, this.y, ringR, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(45, 212, 191, 0.5)';
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }
      }
    }

    for (let i = 0; i < particleCount; i++) {
      particles.push(new MolecularNode());
    }

    let isRunning = true;
    let animationFrameId = null;

    function render() {
      if (!isRunning) return;

      ctx.clearRect(0, 0, width, height);

      // رسم الروابط الكيميائية
      const maxDist = 140;
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const p1 = particles[i];
          const p2 = particles[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < maxDist) {
            const alpha = (1 - dist / maxDist) * 0.45;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(45, 212, 191, ${alpha})`;
            ctx.lineWidth = 1.2;
            ctx.stroke();
          }
        }
      }

      for (let i = 0; i < particles.length; i++) {
        particles[i].update();
        particles[i].draw();
      }

      animationFrameId = requestAnimationFrame(render);
    }

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        isRunning = false;
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
      } else {
        isRunning = true;
        render();
      }
    });

    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCreativeBackground);
  } else {
    initCreativeBackground();
  }
})();
