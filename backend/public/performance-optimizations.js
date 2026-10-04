/**
 * Neo Drug Performance Optimizations
 * ====================================
 * تحسينات الأداء لتطبيق Neo Drug
 */

(function() {
  'use strict';

  // Debounce function
  window.debounce = function(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  };

  // Throttle function
  window.throttle = function(func, limit) {
    let inThrottle;
    return function(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  };

  // Create search index
  window.createSearchIndex = function(drugs) {
    return { count: drugs.length };
  };

  // Optimized filter
  window.optimizedFilter = function(drugs, searchIndex, query, classFilter, formFilter) {
    const q = (query || '').toLowerCase().trim();
    const cls = classFilter === 'all' ? '' : classFilter;
    const frm = formFilter === 'all' ? '' : formFilter;

    return drugs.filter(d => {
      const matchCls = !cls || d.cls === cls;
      const matchForm = !frm || (d.form && d.form.toLowerCase().includes(frm.toLowerCase()));
      const matchQ = !q ||
        (d.tradeEn && d.tradeEn.toLowerCase().includes(q)) ||
        (d.genericEn && d.genericEn.toLowerCase().includes(q)) ||
        (d.genericAr && d.genericAr.includes(q)) ||
        (d.alternates && d.alternates.some(a => a.toLowerCase().includes(q)));

      return matchCls && matchForm && matchQ;
    });
  };

  // Build DOM Fragment for drug cards
  window.buildDrugCardFragment = function(drugs, startIdx, onClickCallback) {
    const fragment = document.createDocumentFragment();

    drugs.forEach((drug, idx) => {
      const card = document.createElement('a');
      card.href = `detail?name=${encodeURIComponent(drug.trade_en)}`;
      card.className = 'drug-card';

      const icon = document.createElement('div');
      icon.className = 'drug-icon';
      icon.textContent = '💊';

      const meta = document.createElement('div');
      meta.className = 'drug-meta';

      const tradeName = document.createElement('div');
      tradeName.className = 'drug-trade-name';
      tradeName.textContent = drug.trade_en || '';

      const genericName = document.createElement('div');
      genericName.className = 'drug-generic-name';
      genericName.textContent = (drug.generic_en || '') + (drug.generic_ar ? ' • ' + drug.generic_ar : '') + (drug.strength ? ' • ' + drug.strength : '');

      meta.appendChild(tradeName);
      meta.appendChild(genericName);

      const badge = document.createElement('div');
      badge.className = 'drug-badge';
      badge.textContent = drug.form_ar || drug.form || '';

      card.appendChild(icon);
      card.appendChild(meta);
      card.appendChild(badge);

      fragment.appendChild(card);
    });

    return fragment;
  };

  console.log('✅ Performance optimizations loaded');
})();
