"""Secure image upload helpers."""

import os
import uuid

from werkzeug.utils import secure_filename

from config import Config

MAGIC_SIGNATURES = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "webp": (b"RIFF",),
    "gif": (b"GIF87a", b"GIF89a"),
}


class UploadError(Exception):
    """Raised when an uploaded file fails validation."""


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_image(file_storage) -> str:
    filename = file_storage.filename or ""
    extension = _extension(filename)
    if extension not in Config.ALLOWED_IMAGE_EXTENSIONS:
        raise UploadError(f"Unsupported file type: {filename or 'unnamed file'}")
    if (file_storage.mimetype or "").lower() not in Config.ALLOWED_IMAGE_MIME_TYPES:
        raise UploadError(f"Unsupported image MIME type: {filename}")

    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size == 0:
        raise UploadError(f"Empty file: {filename}")
    if size > Config.MAX_UPLOAD_BYTES:
        raise UploadError(f"Image exceeds the {Config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit: {filename}")

    header = stream.read(12)
    stream.seek(0)
    if extension == "webp":
        if header[:4] != b"RIFF" or header[8:12] != b"WEBP":
            raise UploadError(f"Invalid WebP image: {filename}")
    elif not any(header.startswith(signature) for signature in MAGIC_SIGNATURES.get(extension, ())):
        raise UploadError(f"File content does not match its image type: {filename}")
    return extension


def save_images(file_storages, upload_folder=None, limit=4):
    """Validate and save images. Returns (relative_path, original_name) tuples."""
    folder = upload_folder or Config.UPLOAD_FOLDER
    os.makedirs(folder, exist_ok=True)
    saved = []
    for storage in file_storages:
        if not storage or not storage.filename:
            continue
        if len(saved) >= limit:
            raise UploadError(f"Maximum {limit} images per complaint.")
        extension = validate_image(storage)
        original = secure_filename(storage.filename)[:200] or f"image.{extension}"
        new_name = f"{uuid.uuid4().hex}.{extension}"
        storage.save(os.path.join(folder, new_name))
        saved.append((f"uploads/complaints/{new_name}", original))
    return saved
