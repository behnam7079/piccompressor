import io
import os
import zipfile
from typing import Tuple, Dict, Any, Optional, List
from PIL import Image, ImageOps, ImageDraw, ImageFont

SUPPORTED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}

def get_image_info(image_bytes: bytes) -> Dict[str, Any]:
    with Image.open(io.BytesIO(image_bytes)) as img:
        fmt = (img.format or "JPEG").upper()
        if fmt == "JPEG":
            fmt = "JPG"
        return {
            "format": fmt,
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "size_bytes": len(image_bytes)
        }

def smart_compress(
    image_bytes: bytes,
    target_format: str = "AUTO",
    quality: int = 80,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    strip_exif: bool = True
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Optimizes and compresses an image intelligently based on format and settings.
    """
    original_size = len(image_bytes)
    with Image.open(io.BytesIO(image_bytes)) as img:
        # Correct orientation if EXIF present
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        orig_format = (img.format or "JPEG").upper()
        orig_w, orig_h = img.size

        # Determine target format
        normalized_target = target_format.upper().strip()
        if normalized_target == "AUTO":
            has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
            if has_alpha:
                save_format = "PNG"
                file_ext = "png"
            else:
                if orig_format in ("JPEG", "JPG"):
                    save_format = "JPEG"
                    file_ext = "jpg"
                elif orig_format == "WEBP":
                    save_format = "WEBP"
                    file_ext = "webp"
                else:
                    save_format = "JPEG"
                    file_ext = "jpg"
        elif normalized_target in ("JPG", "JPEG"):
            save_format = "JPEG"
            file_ext = "jpg"
        elif normalized_target == "PNG":
            save_format = "PNG"
            file_ext = "png"
        elif normalized_target == "WEBP":
            save_format = "WEBP"
            file_ext = "webp"
        else:
            save_format = "JPEG"
            file_ext = "jpg"

        # Resize if dimensions provided
        w, h = orig_w, orig_h
        if max_width and max_height:
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            w, h = img.size
        elif max_width and w > max_width:
            ratio = max_width / float(w)
            h = int(float(h) * ratio)
            img = img.resize((max_width, h), Image.Resampling.LANCZOS)
            w = max_width
        elif max_height and h > max_height:
            ratio = max_height / float(h)
            w = int(float(w) * ratio)
            img = img.resize((w, max_height), Image.Resampling.LANCZOS)
            h = max_height

        # Mode conversions (preventing black background on transparency)
        if save_format == "JPEG":
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
        elif save_format == "PNG":
            if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                img = img.convert("RGBA")
        elif save_format == "WEBP":
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "transparency" in img.info or img.mode in ("RGBA", "LA") else "RGB")

        # Save with optimization
        out_io = io.BytesIO()
        save_kwargs = {}

        if save_format == "JPEG":
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
            save_kwargs["progressive"] = True
            if not strip_exif and "exif" in img.info:
                save_kwargs["exif"] = img.info["exif"]
            img.save(out_io, format="JPEG", **save_kwargs)
        elif save_format == "PNG":
            save_kwargs["optimize"] = True
            if quality < 85:
                colors = max(32, int(256 * (quality / 100.0)))
                try:
                    quantized = img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
                    quantized.save(out_io, format="PNG", optimize=True, compress_level=9)
                except Exception:
                    img.save(out_io, format="PNG", **save_kwargs)
            else:
                img.save(out_io, format="PNG", compress_level=9, **save_kwargs)
        elif save_format == "WEBP":
            save_kwargs["quality"] = quality
            save_kwargs["method"] = 6
            if not strip_exif and "exif" in img.info:
                save_kwargs["exif"] = img.info["exif"]
            img.save(out_io, format="WEBP", **save_kwargs)

        compressed_bytes = out_io.getvalue()
        compressed_size = len(compressed_bytes)

        saved_bytes = max(0, original_size - compressed_size)
        saving_percentage = round((saved_bytes / original_size) * 100, 1) if original_size > 0 else 0

        metadata = {
            "original_size": original_size,
            "compressed_size": compressed_size,
            "saved_bytes": saved_bytes,
            "saving_percentage": saving_percentage,
            "original_dimensions": [orig_w, orig_h],
            "new_dimensions": [w, h],
            "format": file_ext
        }

        return compressed_bytes, metadata

def create_zip_archive(files_data: list) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for item in files_data:
            zip_file.writestr(item["name"], item["data"])
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def convert_images_to_pdf(image_files: List[bytes]) -> bytes:
    pil_images = []
    try:
        for f in image_files:
            img = Image.open(io.BytesIO(f))
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            
            # جلوگیری از پس‌زمینه سیاه برای تصاویر شفاف در PDF
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[3])
                pil_images.append(bg)
            elif img.mode != "RGB":
                pil_images.append(img.convert("RGB"))
            else:
                pil_images.append(img.copy())
            img.close()
        
        if not pil_images:
            return b""
            
        pdf_buffer = io.BytesIO()
        pil_images[0].save(
            pdf_buffer, 
            format="PDF", 
            save_all=True, 
            append_images=pil_images[1:]
        )
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    finally:
        for im in pil_images:
            try:
                im.close()
            except Exception:
                pass

def apply_watermark(image_bytes: bytes, text: str = "", logo_bytes: bytes = None, position: str = "bottom-right", opacity: int = 50) -> bytes:
    import bidi.algorithm
    import arabic_reshaper

    with Image.open(io.BytesIO(image_bytes)) as base_img:
        try:
            base_img = ImageOps.exif_transpose(base_img)
        except Exception:
            pass
        img = base_img.convert("RGBA")

    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    alpha = int((opacity / 100) * 255)

    if text:
        draw = ImageDraw.Draw(txt_layer)
        font_size = max(24, int(img.width * 0.04))
        
        # لیست فونت‌های لینوکس سرور + ویندوز لوکال + مسیر استاتیک پروژه
        font = None
        candidate_fonts = [
            os.path.join("static", "fonts", "Vazirmatn-Bold.ttf"),
            os.path.join("static", "fonts", "Vazirmatn-Regular.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "tahoma.ttf",
            "arial.ttf"
        ]
        for f_path in candidate_fonts:
            try:
                font = ImageFont.truetype(f_path, font_size)
                break
            except Exception:
                continue
        if not font:
            font = ImageFont.load_default()

        # فرمت‌بندی متن فارسی
        try:
            reshaped_text = arabic_reshaper.reshape(text)
            bidi_text = bidi.algorithm.get_display(reshaped_text)
        except Exception:
            bidi_text = text

        bbox = draw.textbbox((0, 0), bidi_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        pad = int(img.width * 0.03)
        if position == "center":
            pos = ((img.width - text_w) // 2, (img.height - text_h) // 2)
        elif position == "top-left":
            pos = (pad, pad)
        elif position == "top-right":
            pos = (img.width - text_w - pad, pad)
        elif position == "bottom-left":
            pos = (pad, img.height - text_h - pad)
        else:
            pos = (img.width - text_w - pad, img.height - text_h - pad)

        shadow_offset = max(1, int(font_size * 0.08))
        draw.text((pos[0] + shadow_offset, pos[1] + shadow_offset), bidi_text, fill=(0, 0, 0, int(alpha * 0.8)), font=font)
        draw.text(pos, bidi_text, fill=(255, 255, 255, alpha), font=font)

    if logo_bytes:
        try:
            with Image.open(io.BytesIO(logo_bytes)) as raw_logo:
                watermark_img = raw_logo.convert("RGBA")
            base_logo_w = int(img.width * 0.2)
            ratio = base_logo_w / float(watermark_img.width)
            base_logo_h = int(float(watermark_img.height) * ratio)
            watermark_img = watermark_img.resize((base_logo_w, base_logo_h), Image.Resampling.LANCZOS)
            
            w_alpha = watermark_img.split()[3].point(lambda p: int(p * (opacity / 100)))
            watermark_img.putalpha(w_alpha)

            pad = int(img.width * 0.03)
            if position == "center":
                pos = ((img.width - base_logo_w) // 2, (img.height - base_logo_h) // 2)
            elif position == "top-left":
                pos = (pad, pad)
            elif position == "top-right":
                pos = (img.width - base_logo_w - pad, pad)
            elif position == "bottom-left":
                pos = (pad, img.height - base_logo_h - pad)
            else:
                pos = (img.width - base_logo_w - pad, img.height - base_logo_h - pad)

            txt_layer.paste(watermark_img, pos, watermark_img)
        except Exception:
            pass

    watermarked = Image.alpha_composite(img, txt_layer)
    
    # پس‌زمینه سفید برای جلوگیری از سیاه شدن نواحی شفاف در JPG
    final_bg = Image.new("RGB", watermarked.size, (255, 255, 255))
    final_bg.paste(watermarked, mask=watermarked.split()[3])
    
    out = io.BytesIO()
    final_bg.save(out, format="JPEG", quality=92)
    return out.getvalue()
