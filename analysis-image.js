// analysis-image.js v10 — gemini-3.8-flash only
const GEMINI_KEY = "AQ.Ab8RN6KajEtMzidGZDVDHmbaHs8R6cA_IeV-81bmCX5MdoBAig";
const resultBox  = document.getElementById('analysis-result');

async function callGemini(parts, attempt = 0) {
  if (attempt >= 4) throw new Error('الخادم مشغول، حاول بعد دقيقة.');
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key=${GEMINI_KEY}`;
  const res  = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contents: [{ parts }] })
  });
  const data = await res.json();
  if (data.error) {
    const msg = data.error.message || '';
    if (msg.includes('high demand') || msg.includes('overloaded') || res.status === 503 || res.status === 429) {
      resultBox.textContent = `⏳ الخادم مشغول، محاولة ${attempt + 2} من 4...`;
      await new Promise(r => setTimeout(r, 4000));
      return callGemini(parts, attempt + 1);
    }
    throw new Error(msg);
  }
  return data.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || 'لم يتم الحصول على نتيجة.';
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('analysis-run');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const fileInput = document.getElementById('analysis-file');
    if (!fileInput.files[0]) { alert('اختر صورة أولاً'); return; }
    resultBox.textContent = '⏳ جاري تحليل الصورة...';
    const reader = new FileReader();
    reader.onload = async () => {
      const imgData  = reader.result;
      const base64   = imgData.split(',')[1];
      const mimeType = imgData.split(';')[0].split(':')[1] || 'image/jpeg';
      const question = document.getElementById('analysis-question').value.trim()
        || 'اقرأ الروشتة الطبية بدقة، حدد التخصص الطبي للطبيب، استخرج أسماء الأدوية المكتوبة، واقترح بدائل متاحة في السوق المصري لكل دواء.';
      try {
        const result = await callGemini([
          { text: question },
          { inlineData: { mimeType, data: base64 } }
        ]);
        resultBox.textContent = result;
      } catch (e) {
        resultBox.textContent = 'خطأ: ' + e.message;
      }
    };
    reader.readAsDataURL(fileInput.files[0]);
  });
});
