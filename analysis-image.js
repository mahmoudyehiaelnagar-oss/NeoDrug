// analysis-image.js v12 - Optimized Image Compression + Gemini AI Analysis
const GEMINI_KEY = "AQ.Ab8RN6KajEtMzidGZDVDHmbaHs8R6cA_IeV-81bmCX5MdoBAig";

// ضغط وتصغير الصورة تلقائياً لسرعة الرفع والاستجابة الفورية
function compressImage(file, maxDimension = 1024, quality = 0.8) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = reject;
    reader.onload = (e) => {
      const img = new Image();
      img.onerror = reject;
      img.onload = () => {
        let width = img.width;
        let height = img.height;

        if (width > maxDimension || height > maxDimension) {
          if (width > height) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          } else {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        const dataUrl = canvas.toDataURL('image/jpeg', quality);
        const base64 = dataUrl.split(',')[1];
        resolve({ mimeType: 'image/jpeg', base64 });
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

async function callGemini(parts, attempt = 0) {
  if (attempt >= 3) throw new Error('الخادم مشغول حالياً، برجاء إعادة المحاولة بعد ثوانٍ.');
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key=${GEMINI_KEY}`;
  
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 35000);

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contents: [{ parts }] }),
      signal: ctrl.signal
    });
    clearTimeout(timer);

    const data = await res.json();
    if (data.error) {
      const msg = data.error.message || '';
      if (msg.includes('high demand') || msg.includes('overloaded') || res.status === 503 || res.status === 429) {
        return null;
      }
      throw new Error(msg);
    }
    return data.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || 'لم يتم استخراج معلومات من الروشتة.';
  } catch (e) {
    clearTimeout(timer);
    if (e.name === 'AbortError') return null;
    throw e;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('analysis-run');
  const resultBox = document.getElementById('analysis-result');
  if (!btn || !resultBox) return;

  btn.addEventListener('click', async () => {
    const fileInput = document.getElementById('analysis-file');
    if (!fileInput.files[0]) {
      alert('يرجى اختيار صورة الروشتة أولاً');
      return;
    }

    resultBox.textContent = '⚡ جاري ضغط ومعالجة الصورة لتسريع التحليل...';
    btn.disabled = true;

    try {
      const file = fileInput.files[0];
      const { mimeType, base64 } = await compressImage(file);

      const question = document.getElementById('analysis-question').value.trim()
        || 'اقرأ الروشتة الطبية بدقة، حدد التخصص الطبي للطبيب، استخرج أسماء الأدوية المكتوبة، واقترح بدائل متاحة في السوق المصري لكل دواء.';

      const parts = [
        { text: question },
        { inlineData: { mimeType, data: base64 } }
      ];

      resultBox.textContent = '🚀 جاري إرسال الصورة لـ Gemini 3.8 Flash وقراءة الروشتة...';

      let result = null;
      for (let attempt = 0; attempt < 3; attempt++) {
        if (attempt > 0) {
          resultBox.textContent = `⏳ الخادم يستجيب ببطء، جاري المحاولة السريعة (${attempt + 1}/3)...`;
          await new Promise(r => setTimeout(r, 2000));
        }
        result = await callGemini(parts, attempt);
        if (result !== null) break;
      }

      if (result === null) {
        resultBox.textContent = '⚠️ استغرق الطلب وقتاً أطول من المتوقع، اضغط على زر "تحليل الصورة" للمحاولة مجدداً.';
      } else {
        resultBox.textContent = result;
      }
    } catch (e) {
      resultBox.textContent = 'خطأ: ' + e.message;
    } finally {
      btn.disabled = false;
    }
  });
});
