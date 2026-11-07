# پیک کامپرسور | کاهش حجم هوشمند تصویر

پروژه‌ای آماده استقرار برای فشرده‌سازی، تبدیل فرمت و تغییر اندازه تصاویر با **FastAPI، Pillow، Jinja2 و Vanilla JavaScript**.

## قابلیت‌ها

- فشرده‌سازی JPEG، PNG و WebP با انتخاب کیفیت
- حالت خودکار برای انتخاب فرمت مناسب
- حفظ شفافیت PNG و تصحیح جهت EXIF
- تغییر اندازه با تعیین حداکثر عرض/ارتفاع
- پردازش تکی و دسته‌ای و دانلود ZIP
- رابط فارسی، RTL، واکنش‌گرا و دارک/لایت
- صفحات حریم خصوصی، شرایط، sitemap و robots
- پردازش در حافظه و بدون ذخیره‌سازی دائمی فایل‌ها

## اجرای محلی با Python

پیش‌نیاز: Python 3.11 یا جدیدتر.

```bash
cd piccompressor
python3 -m venv .venv
source .venv/bin/activate       # ویندوز: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000
```

سپس آدرس `http://localhost:8000` را باز کنید.

## استقرار با Docker Compose

```bash
cp .env.example .env
# مقدار SITE_URL را با دامنه واقعی جایگزین کنید
docker compose up -d --build
docker compose logs -f
```

برای محیط عملیاتی بهتر است اپلیکیشن پشت Nginx یا Caddy و HTTPS قرار گیرد. محدودیت فعلی هر فایل ۳۰ مگابایت است؛ در صورت نیاز می‌توانید آن را در `main.py` تغییر دهید.

## نصب SSL رایگان با Certbot و Nginx در Ubuntu

ابتدا رکورد DNS نوع A دامنه را به IP سرور وصل کنید، سپس:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

نمونه کانفیگ `/etc/nginx/sites-available/piccompressor`:

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    client_max_body_size 35M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

فعال‌سازی و دریافت گواهی:

```bash
sudo ln -s /etc/nginx/sites-available/piccompressor /etc/nginx/sites-enabled/piccompressor
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d example.com -d www.example.com
sudo certbot renew --dry-run
```

دامنه واقعی را جایگزین `example.com` کنید و در `.env` نیز `SITE_URL=https://example.com` قرار دهید.

## ثبت در Google Search Console

1. وارد [Google Search Console](https://search.google.com/search-console) شوید.
2. یک Property از نوع Domain یا URL prefix اضافه کنید.
3. برای Domain، رکورد TXT تأییدشده گوگل را در DNS قرار دهید؛ برای URL prefix می‌توانید فایل HTML یا متاتگ را استفاده کنید.
4. پس از تأیید، از بخش **Sitemaps** آدرس `https://example.com/sitemap.xml` را ثبت کنید.
5. در URL Inspection صفحه اصلی را بررسی و درخواست Indexing بدهید.
6. در صورت تغییر دامنه یا پروتکل، مقدار `SITE_URL`، لینک canonical و sitemap را بررسی کنید.

## بررسی سلامت سرویس

- `GET /` صفحه اصلی
- `GET /privacy` و `GET /terms`
- `GET /robots.txt` و `GET /sitemap.xml`
- `POST /api/compress` فشرده‌سازی تکی
- `POST /api/compress-batch` فشرده‌سازی دسته‌ای
- `POST /api/download-zip` ساخت ZIP خروجی

## نکات امنیتی و عملیاتی

- در محیط واقعی `--reload` استفاده نکنید.
- دامنه و HTTPS را فعال کنید و برای Nginx مقدار `client_max_body_size` را هماهنگ تنظیم کنید.
- برای کنترل سوءاستفاده، در صورت عمومی شدن سرویس rate limit، لاگ‌گذاری و محدودیت تعداد فایل اضافه کنید.
- تصاویر ناسالم یا فرمت‌های ناشناخته باید با پاسخ خطا مدیریت شوند؛ Pillow ورودی را اعتبارسنجی می‌کند.

## مجوز

این پروژه به عنوان قالب آماده توسعه و استقرار ارائه شده است. قبل از استفاده تجاری، سیاست حریم خصوصی و متن شرایط را متناسب با کسب‌وکار خود بازبینی کنید.
