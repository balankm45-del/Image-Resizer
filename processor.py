import os
import tempfile
from io import BytesIO

from PIL import Image, ImageOps


def get_image_metadata(file_path):
    """
    Retrieves the width, height, and file size of an image using Pillow.
    """
    try:
        with Image.open(file_path) as img:
            img = ImageOps.exif_transpose(img)
            width, height = img.size
            size_bytes = os.path.getsize(file_path)
            return {
                "width": width,
                "height": height,
                "size_bytes": size_bytes,
            }
    except Exception as exc:
        print(f"Error reading metadata for {file_path}: {exc}")
    return None


def _parse_size(image, resize_mode, width, height, percentage, keep_aspect):
    original_width, original_height = image.size

    if resize_mode == "percentage":
        try:
            pct = int(percentage)
            if pct < 1 or pct > 1000:
                pct = 100
        except Exception:
            pct = 100
        return max(1, int(round(original_width * pct / 100))), max(1, int(round(original_height * pct / 100)))

    width_value = int(width) if str(width).strip() else None
    height_value = int(height) if str(height).strip() else None

    if width_value is None and height_value is None:
        return original_width, original_height

    if keep_aspect:
        if width_value is not None and height_value is not None:
            scale = min(width_value / original_width, height_value / original_height)
            target_width = max(1, int(round(original_width * scale)))
            target_height = max(1, int(round(original_height * scale)))
        elif width_value is not None:
            target_width = width_value
            target_height = max(1, int(round(original_height * width_value / original_width)))
        else:
            target_height = height_value
            target_width = max(1, int(round(original_width * height_value / original_height)))
    else:
        target_width = width_value if width_value is not None else original_width
        target_height = height_value if height_value is not None else original_height

    return max(1, target_width), max(1, target_height)


def process_image(input_bytes, filename, resize_mode, width, height, percentage, keep_aspect, format_ext, quality):
    """
    Processes the input image bytes using Pillow.
    Returns (output_bytes, output_filename, resized_width, resized_height, output_size).
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        _, ext = os.path.splitext(filename.lower())
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".png"

        input_path = os.path.join(temp_dir, f"input{ext}")
        with open(input_path, "wb") as f:
            f.write(input_bytes)

        original_meta = get_image_metadata(input_path)
        if not original_meta:
            raise ValueError("Failed to identify uploaded image. Please ensure it is a valid JPG, PNG, or WEBP.")

        target_ext = format_ext.lower().strip()
        if target_ext not in ["jpg", "jpeg", "png", "webp"]:
            target_ext = "png"

        try:
            q = int(quality)
            if q < 1 or q > 100:
                q = 80
        except Exception:
            q = 80

        try:
            with Image.open(input_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode in {"RGBA", "LA", "P"}:
                    img = img.convert("RGBA")
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                target_width, target_height = _parse_size(img, resize_mode, width, height, percentage, keep_aspect)
                resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

                if target_ext in ["jpg", "jpeg"]:
                    if resized.mode in {"RGBA", "LA", "P"}:
                        background = Image.new("RGB", resized.size, "white")
                        background.paste(resized.convert("RGBA"), (0, 0), resized.convert("RGBA"))
                        resized = background
                    else:
                        resized = resized.convert("RGB")

                    output = BytesIO()
                    resized.save(output, format="JPEG", quality=q, optimize=True)
                    output_bytes = output.getvalue()
                    output_format = "jpeg"
                elif target_ext == "webp":
                    output = BytesIO()
                    resized.save(output, format="WEBP", quality=q, lossless=False)
                    output_bytes = output.getvalue()
                    output_format = "webp"
                else:
                    output = BytesIO()
                    resized.save(output, format="PNG", optimize=True)
                    output_bytes = output.getvalue()
                    output_format = "png"

                output_width, output_height = resized.size
        except Exception as exc:
            raise ValueError(f"Image processing failed: {exc}") from exc

        base, _ = os.path.splitext(filename)
        safe_base = "".join(c for c in base if c.isalnum() or c in ("-", "_")).strip()
        if not safe_base:
            safe_base = "resized"
        download_filename = f"resized_{safe_base}.{output_format}"

        return output_bytes, download_filename, output_width, output_height, len(output_bytes)
