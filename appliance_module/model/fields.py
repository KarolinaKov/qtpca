from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def _fernet() -> Fernet:
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode()
                   if isinstance(settings.FIELD_ENCRYPTION_KEY, str)
                   else settings.FIELD_ENCRYPTION_KEY)


class EncryptedCharField(models.BinaryField):
    """Ulozeny obsah je v DB vzdy jen sifrovany blob, klic zna jen aplikace."""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return _fernet().decrypt(bytes(value)).decode()

    def to_python(self, value):
        if isinstance(value, str) or value is None:
            return value
        return _fernet().decrypt(bytes(value)).decode()

    def get_prep_value(self, value):
        if value is None:
            return value
        return _fernet().encrypt(str(value).encode())