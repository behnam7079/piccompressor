import os
import io
import json
import base64
from typing import List, Optional
from fastapi import FastAPI, Request, File, UploadFile, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, Response, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from optimizer import smart_compress, get_image_info, create_zip_archive, convert_images_to_pdf, apply_watermark
from pillow_heif import register_heif_opener
register_heif_opener()
from blog_db import get_all_posts, get_post_by_slug, get_all_slugs_for_sitemap, insert_post


app = FastAPI(
    title="پیک کامپرسور | کاهش حجم هوشمند تصویر آنلاین",
    description="ابزار رایگان و حرفه‌ای کاهش حجم و بهینه‌سازی تصاویر JPEG, PNG و WebP بدون افت کیفیت محسوس",
    version="1.0.0"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

SITE_URL = os.getenv("SITE_URL", "https://piccompressor.ir")
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

# تنظیمات امنیت پنل ادمین
security = HTTPBasic()
ADMIN_USER = "admin"
ADMIN_PASS = "piccompressor2026"  # می‌توانی این رمز عبور را به دلخواه عوض کنی

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != ADMIN_USER or credentials.password != ADMIN_PASS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور اشتباه است",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "site_url": SITE_URL,
            "page_title": "کاهش حجم تصویر آنلاین | بهینه‌ساز هوشمند عکس بدون افت کیفیت",
            "meta_desc": "سریع‌ترین و بهترین ابزار رایگان کاهش حجم عکس آنلاین. فشرده‌سازی هوشمند تصاویر JPG، PNG و WebP تا ۹۰٪ بدون افت کیفیت. تبدیل فرمت و تغییر اندازه عکس."
        }
    )

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="privacy.html",
        context={
            "site_url": SITE_URL,
            "page_title": "حریم خصوصی | پیک کامپرسور",
            "meta_desc": "سیاست حفظ حریم خصوصی کاربران در سرویس کاهش حجم عکس پیک کامپرسور."
        }
    )

@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="terms.html",
        context={
            "site_url": SITE_URL,
            "page_title": "قوانین و مقررات استفاده | پیک کامپرسور",
            "meta_desc": "شرایط و ضوابط استفاده از ابزارهای بهینه‌سازی و فشرده‌سازی تصویر پیک کامپرسور."
        }
    )

@app.get("/robots.txt", response_class=Response)
async def robots_txt():
    content = f"""User-agent: *
Allow: /
Sitemap: {SITE_URL}/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")

@app.get("/sitemap.xml", response_class=Response)
async def sitemap_xml():
    blog_urls = ""
    for post in get_all_slugs_for_sitemap():
        blog_urls += f"""
  <url>
    <loc>{SITE_URL}/blog/{post['slug']}</loc>
    <lastmod>{post['created_at']}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>"""

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{SITE_URL}/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{SITE_URL}/blog</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{SITE_URL}/privacy</loc>
    <changefreq>monthly</changefreq>
    <priority>0.3</priority>
  </url>
  <url>
    <loc>{SITE_URL}/terms</loc>
    <changefreq>monthly</changefreq>
    <priority>0.3</priority>
  </url>{blog_urls}
</urlset>"""
    return Response(content=xml_content, media_type="application/xml")


@app.post("/api/compress")
async def compress_single_image(
    file: UploadFile = File(...),
    quality: int = Form(80),
    format: str = Form("AUTO"),
    max_width: Optional[int] = Form(None),
    max_height: Optional[int] = Form(None),
    strip_exif: bool = Form(True)
):
    try:
        ext_check = os.path.splitext(file.filename)[1].lower()
        if ext_check not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="فرمت فایل مجاز نیست (فقط jpg, jpeg, png, webp).")

        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="فایل ارسالی خالی است.")
        
        if len(content) > 30 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="حجم فایل نباید بیشتر از ۳۰ مگابایت باشد.")

        compressed_data, metadata = smart_compress(
            content,
            target_format=format,
            quality=quality,
            max_width=max_width if max_width and max_width > 0 else None,
            max_height=max_height if max_height and max_height > 0 else None,
            strip_exif=strip_exif
        )

        base_name = os.path.splitext(file.filename)[0]
        ext = metadata["format"]
        out_filename = f"{base_name}-compressed.{ext}"

        mime_type = "jpeg" if ext in ("jpg", "jpeg") else ext
        b64_data = base64.b64encode(compressed_data).decode("utf-8")
        data_url = f"data:image/{mime_type};base64,{b64_data}"

        return JSONResponse({
            "success": True,
            "filename": out_filename,
            "original_filename": file.filename,
            "meta": metadata,
            "preview_url": data_url
        })
    except HTTPException as he:
        return JSONResponse(status_code=he.status_code, content={"success": False, "error": he.detail})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/compress-batch")
async def compress_batch_images(
    files: List[UploadFile] = File(...),
    quality: int = Form(80),
    format: str = Form("AUTO"),
    max_width: Optional[int] = Form(None),
    max_height: Optional[int] = Form(None),
    strip_exif: bool = Form(True)
):
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="هیچ فایلی ارسال نشده است.")

    results = []

    for file in files:
        try:
            ext_check = os.path.splitext(file.filename)[1].lower()
            if ext_check not in ALLOWED_EXTENSIONS:
                results.append({
                    "original_filename": file.filename,
                    "error": "فرمت فایل مجاز نیست (فقط jpg, jpeg, png, webp)"
                })
                continue

            content = await file.read()
            if len(content) == 0:
                continue

            compressed_data, metadata = smart_compress(
                content,
                target_format=format,
                quality=quality,
                max_width=max_width if max_width and max_width > 0 else None,
                max_height=max_height if max_height and max_height > 0 else None,
                strip_exif=strip_exif
            )

            base_name = os.path.splitext(file.filename)[0]
            ext = metadata["format"]
            out_filename = f"{base_name}-compressed.{ext}"

            mime_type = "jpeg" if ext in ("jpg", "jpeg") else ext
            b64_data = base64.b64encode(compressed_data).decode("utf-8")
            data_url = f"data:image/{mime_type};base64,{b64_data}"

            results.append({
                "original_filename": file.filename,
                "compressed_filename": out_filename,
                "meta": metadata,
                "preview_url": data_url
            })
        except Exception as e:
            results.append({
                "original_filename": file.filename,
                "error": str(e)
            })

    return JSONResponse({
        "success": True,
        "items": results,
        "total_processed": len(results)
    })

@app.post("/api/download-zip")
async def download_batch_zip(request: Request):
    try:
        body = await request.json()
        files = body.get("files", [])
        if not files:
            raise HTTPException(status_code=400, detail="فایلی برای دانلود یافت نشد.")

        zip_items = []
        for item in files:
            name = item["name"]
            data_b64 = item["data"].split(",")[-1]
            raw_bytes = base64.b64decode(data_b64)
            zip_items.append({"name": name, "data": raw_bytes})

        zip_bytes = create_zip_archive(zip_items)
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=compressed_images.zip"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/images-to-pdf")
async def images_to_pdf(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="هیچ فایلی ارسال نشده است.")

    image_bytes_list = []
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

    for file in files:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="فقط فرمت‌های jpg, jpeg, png و webp مجاز هستند.")
        content = await file.read()
        if content:
            image_bytes_list.append(content)

    if not image_bytes_list:
        raise HTTPException(status_code=400, detail="تصاویر ارسالی خالی هستند.")

    pdf_bytes = convert_images_to_pdf(image_bytes_list)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="converted.pdf"'}
    )

@app.post("/api/watermark")
async def add_watermark(
    file: UploadFile = File(...),
    text: str = Form(""),
    logo: Optional[UploadFile] = File(None),
    position: str = Form("bottom-right"),
    opacity: int = Form(50)
):
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="فایل اصلی خالی است.")

        logo_content = None
        if logo:
            logo_content = await logo.read()

        watermarked_bytes = apply_watermark(
            image_bytes=content,
            text=text,
            logo_bytes=logo_content,
            position=position,
            opacity=opacity
        )

        base_name = os.path.splitext(file.filename)[0]
        out_filename = f"{base_name}-watermarked.jpg"

        b64_data = base64.b64encode(watermarked_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64_data}"

        return JSONResponse({
            "success": True,
            "filename": out_filename,
            "preview_url": data_url
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


# --- روت‌های بخش وبلاگ ---

@app.get("/blog", response_class=HTMLResponse)
async def blog_list(request: Request):
    posts = get_all_posts(limit=30)
    return templates.TemplateResponse(
        request=request,
        name="blog.html",
        context={
            "site_url": SITE_URL,
            "posts": posts,
            "page_title": "وبلاگ و مقالات آموزشی کاهش حجم عکس | پیک کامپرسور",
            "meta_desc": "مجموعه مقالات تخصصی و کاربردی در زمینه کاهش حجم تصاویر، ترفندهای بهینه‌سازی فرمت‌های WebP و JPG، و افزایش سرعت سایت."
        }
    )

@app.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_detail(request: Request, slug: str):
    post = get_post_by_slug(slug)
    if not post:
        raise HTTPException(status_code=404, detail="مقاله مورد نظر یافت نشد.")
    return templates.TemplateResponse(
        request=request,
        name="post.html",
        context={
            "site_url": SITE_URL,
            "post": post,
            "page_title": f"{post['title']} | پیک کامپرسور",
            "meta_desc": post["meta_desc"],
            "keywords": post.get("keywords", "")
        }
    )


# --- پنل مدیریت ادمین برای ارسال مقاله ---

@app.get("/admin/new-post", response_class=HTMLResponse)
def admin_new_post(request: Request, user: str = Depends(verify_admin)):
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>افزودن مقاله جدید - پیک کامپرسور</title>
        <style>
            body { font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; padding: 40px; }
            .container { max-width: 700px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
            h2 { color: #0d9488; text-align: center; margin-bottom: 25px; }
            label { display: block; margin-top: 15px; margin-bottom: 5px; font-weight: bold; }
            input, textarea { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; box-sizing: border-box; }
            textarea { height: 180px; }
            button { margin-top: 25px; background: #0d9488; color: white; border: none; padding: 12px 20px; font-size: 16px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; }
            button:hover { background: #0f766e; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>✍️ افزودن مقاله جدید به وبلاگ</h2>
            <form method="POST" action="/admin/new-post">
                <label>عنوان مقاله:</label>
                <input type="text" name="title" required placeholder="مثلاً: راهنمای کاهش حجم عکس">

                <label>آدرس یکتا (Slug انگلیسی):</label>
                <input type="text" name="slug" required placeholder="مثلاً: compress-images-guide">

                <label>توضیحات کوتاه (Meta Description):</label>
                <input type="text" name="meta_desc" required placeholder="خلاصه‌ای برای سئو گوگل...">

                <label>کلمات کلیدی (با کاما جدا کنید):</label>
                <input type="text" name="keywords" placeholder="کاهش حجم, عکس, وب پی">

                <label>زمان مطالعه (عدد به دقیقه):</label>
                <input type="number" name="reading_time" value="3" required>

                <label>متن مقاله (کد HTML مجاز است):</label>
                <textarea name="content" required placeholder="<h2>عنوان تیتر</h2><p>متن مقاله...</p>"></textarea>

                <button type="submit">انتشار مقاله 🚀</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/admin/new-post")
def admin_create_post(
    title: str = Form(...),
    slug: str = Form(...),
    meta_desc: str = Form(...),
    keywords: str = Form(""),
    reading_time: int = Form(3),
    content: str = Form(...),
    user: str = Depends(verify_admin)
):
    success = insert_post(
        slug=slug,
        title=title,
        meta_desc=meta_desc,
        keywords=keywords,
        content=content,
        reading_time=reading_time,
        status="published"
    )
    
    if success:
        return RedirectResponse(url="/blog", status_code=303)
    else:
        return {"error": "خطا در ثبت مقاله. احتمالاً این Slug قبلاً استفاده شده است."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
