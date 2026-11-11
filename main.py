import os
import io
import json
import base64
from typing import List, Optional
from fastapi import FastAPI, Request, File, UploadFile, Form, HTTPException, status
from fastapi.responses import HTMLResponse, Response, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from optimizer import smart_compress, get_image_info, create_zip_archive, convert_images_to_pdf, apply_watermark
from pillow_heif import register_heif_opener
register_heif_opener()
from blog_db import get_all_posts, get_post_by_slug, get_all_slugs_for_sitemap, insert_post, get_all_posts_admin, delete_post_by_id


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

# رمز عبور پنل مدیریت ادمین
ADMIN_PASS = "piccompressor2026"
AUTH_TOKEN = "GAPGPTMASKTOKEN23ybt7hhez7X0X"


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


# --- پنل مدیریت ادمین (سیستم فرم لاگین امن) ---

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ورود به پنل ادمین - پیک کامپرسور</title>
        <style>
            body { font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
            .box { background: #1e293b; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); width: 340px; text-align: center; }
            h2 { color: #0d9488; margin-top: 0; margin-bottom: 25px; font-size: 20px; }
            input { width: 100%; padding: 12px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; box-sizing: border-box; font-size: 14px; text-align: center; }
            input:focus { outline: none; border-color: #0d9488; }
            button { background: #0d9488; color: white; border: none; padding: 12px; font-size: 15px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; transition: 0.2s; }
            button:hover { background: #0f766e; }
        </style>
    </head>
    <body>
        <div class="box">
            <h2>🔐 ورود به پنل ادمین</h2>
            <form method="POST" action="/admin/login">
                <input type="password" name="password" required placeholder="رمز عبور ادمین را وارد کنید...">
                <button type="submit">ورود به پنل</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/admin/login")
def admin_login_submit(password: str = Form(...)):
    if password != ADMIN_PASS:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head><meta charset="UTF-8"><title>خطا</title><style>body{background:#0f172a;color:#fff;text-align:center;padding-top:60px;font-family:Tahoma;}a{color:#0d9488;text-decoration:none;font-weight:bold;}</style></head>
        <body>
            <h3 style="color:#ef4444;">❌ رمز عبور اشتباه است!</h3>
            <p><a href="/admin/login">بازگشت و تلاش مجدد</a></p>
        </body>
        </html>
        """, status_code=400)
    
    # پس از لاگین موفق، هدایت به صفحه لیست مقالات ادمین
    response = RedirectResponse(url="/admin/posts", status_code=303)
    response.set_cookie(key="admin_auth", value=AUTH_TOKEN, httponly=True, max_age=86400 * 7)
    return response


# --- صفحه لیست مقالات و مدیریت (حذف) ---

@app.get("/admin/posts", response_class=HTMLResponse)
def admin_posts_list(request: Request):
    auth_cookie = request.cookies.get("admin_auth")
    if auth_cookie != AUTH_TOKEN:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    posts = get_all_posts_admin()
    posts_html = ""
    for p in posts:
        posts_html += f"""
        <tr style="border-bottom: 1px solid #334155;">
            <td style="padding: 12px;">{p['title']}</td>
            <td style="padding: 12px; color: #94a3b8; font-size: 13px;">{p['created_at']}</td>
            <td style="padding: 12px; text-align: left;">
                <a href="/admin/delete/{p['id']}" onclick="return confirm('آیا از حذف این مقاله مطمئن هستید؟');" style="background: #ef4444; color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 13px;">حذف 🗑️</a>
            </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>مدیریت مقالات - پیک کامپرسور</title>
        <style>
            body {{ font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; padding: 30px 15px; margin: 0; }}
            .container {{ max-width: 800px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
            .top-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; }}
            h2 {{ color: #0d9488; margin: 0; }}
            .btn {{ background: #0d9488; color: white; text-decoration: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; font-size: 14px; }}
            .btn:hover {{ background: #0f766e; }}
            .logout {{ color: #ef4444; text-decoration: none; font-size: 14px; padding: 6px 12px; border: 1px solid #ef4444; border-radius: 6px; margin-right: 10px; }}
            .logout:hover {{ background: #ef4444; color: #fff; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ text-align: right; padding: 12px; background: #0f172a; color: #0d9488; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="top-bar">
                <h2>📚 مدیریت مقالات وبلاگ</h2>
                <div>
                    <a href="/admin/new-post" class="btn">➕ افزودن مقاله جدید</a>
                    <a href="/admin/logout" class="logout">خروج 🚪</a>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>عنوان مقاله</th>
                        <th>تاریخ ثبت</th>
                        <th style="text-align: left;">عملیات</th>
                    </tr>
                </thead>
                <tbody>
                    {posts_html if posts_html else '<tr><td colspan="3" style="text-align:center; padding:20px; color:#94a3b8;">هنوز مقاله‌ای ثبت نشده است.</td></tr>'}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """

@app.get("/admin/delete/{post_id}")
def admin_delete_post(request: Request, post_id: int):
    auth_cookie = request.cookies.get("admin_auth")
    if auth_cookie != AUTH_TOKEN:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    delete_post_by_id(post_id)
    return RedirectResponse(url="/admin/posts", status_code=303)


# --- صفحه افزودن مقاله جدید ---

@app.get("/admin/new-post", response_class=HTMLResponse)
def admin_new_post(request: Request):
    auth_cookie = request.cookies.get("admin_auth")
    if auth_cookie != AUTH_TOKEN:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>افزودن مقاله جدید - پیک کامپرسور</title>
        <style>
            body { font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; padding: 30px 15px; margin: 0; }
            .container { max-width: 720px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
            .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            h2 { color: #0d9488; margin: 0; }
            .back-btn { background: #334155; color: #fff; text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 14px; margin-left: 10px; }
            .back-btn:hover { background: #475569; }
            .logout { color: #ef4444; text-decoration: none; font-size: 14px; padding: 6px 12px; border: 1px solid #ef4444; border-radius: 6px; }
            .logout:hover { background: #ef4444; color: #fff; }
            label { display: block; margin-top: 15px; margin-bottom: 6px; font-weight: bold; font-size: 14px; }
            input, textarea { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; box-sizing: border-box; font-family: Tahoma, sans-serif; }
            input:focus, textarea:focus { outline: none; border-color: #0d9488; }
            textarea { height: 200px; resize: vertical; line-height: 1.6; }
            button { margin-top: 25px; background: #0d9488; color: white; border: none; padding: 13px; font-size: 16px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; }
            button:hover { background: #0f766e; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="top-bar">
                <h2>✍️ افزودن مقاله جدید به وبلاگ</h2>
                <div>
                    <a href="/admin/posts" class="back-btn">⬅️ بازگشت به لیست</a>
                    <a href="/admin/logout" class="logout">خروج 🚪</a>
                </div>
            </div>
            <form method="POST" action="/admin/new-post">
                <label>عنوان مقاله:</label>
                <input type="text" name="title" required placeholder="مثلاً: راهنمای کامل کاهش حجم عکس در وردپرس">

                <label>آدرس یکتا (Slug انگلیسی):</label>
                <input type="text" name="slug" required placeholder="مثلاً: compress-images-wordpress">

                <label>توضیحات کوتاه سئو (Meta Description):</label>
                <input type="text" name="meta_desc" required placeholder="یک یا دو جمله برای پیش‌نمایش در نتایج گوگل...">

                <label>کلمات کلیدی (با کاما جدا کنید):</label>
                <input type="text" name="keywords" placeholder="کاهش حجم عکس, آموزش وردپرس, وب پی">

                <label>زمان تقریبی مطالعه (به دقیقه):</label>
                <input type="number" name="reading_time" value="3" required>

                <label>متن مقاله (تگ‌های HTML مانند h2، p، ul مجاز است):</label>
                <textarea name="content" required placeholder="<h2>تیتر اول</h2><p>متن توضیحات...</p>"></textarea>

                <button type="submit">انتشار مقاله در وبلاگ 🚀</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/admin/new-post")
def admin_create_post(
    request: Request,
    title: str = Form(...),
    slug: str,
    meta_desc: str = Form(...),
    keywords: str = Form(""),
    reading_time: int = Form(3),
    content: str = Form(...)
):
    auth_cookie = request.cookies.get("admin_auth")
    if auth_cookie != AUTH_TOKEN:
        return RedirectResponse(url="/admin/login", status_code=303)

    success = insert_post(
        slug=slug.strip(),
        title=title.strip(),
        meta_desc=meta_desc.strip(),
        keywords=keywords.strip(),
        content=content.strip(),
        reading_time=reading_time,
        status="published"
    )
    
    if success:
        return RedirectResponse(url="/admin/posts", status_code=303)
    else:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head><meta charset="UTF-8"><title>خطا</title><style>body{background:#0f172a;color:#fff;text-align:center;padding-top:60px;font-family:Tahoma;}a{color:#0d9488;text-decoration:none;font-weight:bold;}</style></head>
        <body>
            <h3 style="color:#ef4444;">❌ خطا در ثبت مقاله: این Slug قبلاً ثبت شده است!</h3>
            <p><a href="/admin/new-post">بازگشت و تغییر Slug</a></p>
        </body>
        </html>
        """, status_code=400)

@app.get("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("admin_auth")
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
