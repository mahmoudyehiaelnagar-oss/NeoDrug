// analysis-image.js v12 - Optimized Image Compression + Gemini AI Analysis
let GEMINI_KEY = localStorage.getItem("GEMINI_KEY");

// ضغط وتصغير الصورة تلقائياً لسرعة الرفع والاستجابة الفورية
function compressImage(file, maxDimension = 2048, quality = 0.92) {
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

async function callAI(promptText, dataUrl) {
  const url = '/api/chat';

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      message: promptText,
      image_base64: dataUrl,
      images: [dataUrl]
    })
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }

  const data = await res.json();
  return data.reply || 'لم يتم استخراج معلومات من الروشتة.';
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

      const result = await callAI(question, `data:${mimeType};base64,${base64}`);

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
