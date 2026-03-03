# zipper.py
"""Create zip archives."""

import logging
import os
import zipfile

log = logging.getLogger(__name__)


def make_zip(folder_path: str, zip_path: str) -> str:
    """
    Create zip of folder contents using ZIP_DEFLATED.
    Works even if folder is empty. Returns zip_path.
    """
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.isdir(folder_path):
            for root, _dirs, files in os.walk(folder_path):
                for f in files:
                    path = os.path.join(root, f)
                    arcname = os.path.relpath(path, folder_path)
                    zf.write(path, arcname)
                    file_count += 1
    size = os.path.getsize(zip_path)
    log.info("make_zip: %d files, %d bytes -> %s", file_count, size, zip_path)
    return zip_path
