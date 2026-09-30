# apps/core/storage.py
from cloudinary_storage.storage import MediaCloudinaryStorage

class SeekSafeCloudinaryStorage(MediaCloudinaryStorage):
    def _upload(self, name, content):
        if hasattr(content, "seek"):
            content.seek(0)
        return super()._upload(name, content)