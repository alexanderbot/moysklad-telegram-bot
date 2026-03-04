import base64
import logging
from cryptography.fernet import Fernet
import os

logger = logging.getLogger(__name__)

# Импортируем конфигурацию
try:
    from config import config
except ImportError:
    class SimpleConfig:
        ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    config = SimpleConfig()


class SecurityManager:
    """Менеджер безопасности для шифрования данных"""

    def __init__(self, encryption_key: str = None):
        self.encryption_key = encryption_key or config.ENCRYPTION_KEY
        logger.info("SecurityManager: initializing...")
        self.fernet = self._init_fernet()

    def _init_fernet(self):
        """Инициализация Fernet с ключом"""
        try:
            if not self.encryption_key:
                logger.error("Encryption key is missing")
                return self._generate_new_key()

            if len(self.encryption_key) != 44:
                logger.warning("Invalid encryption key length: %d (expected 44)", len(self.encryption_key))
                return self._generate_new_key()

            try:
                key = base64.urlsafe_b64decode(self.encryption_key)

                if len(key) != 32:
                    logger.error("Decoded key is not 32 bytes: %d", len(key))
                    return self._generate_new_key()

                fernet = Fernet(self.encryption_key.encode())
                logger.info("Fernet initialized successfully")
                return fernet

            except Exception as decode_error:
                logger.error("Key decoding failed: %s", decode_error)
                return self._generate_new_key()

        except Exception as e:
            logger.error("Encryption initialization failed: %s", e)
            return self._generate_new_key()

    def _generate_new_key(self):
        """Генерация нового ключа шифрования"""
        logger.warning("Generating new temporary encryption key — save it to .env as ENCRYPTION_KEY")
        key = Fernet.generate_key()
        self.encryption_key = key.decode()
        return Fernet(key)

    def encrypt(self, data: str) -> str:
        """Шифрование данных"""
        if not data:
            logger.warning("Empty data passed to encrypt()")
            return ""

        try:
            encrypted = self.fernet.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error("Encryption failed: %s", e)
            raise ValueError("Failed to encrypt data") from e

    def decrypt(self, encrypted_data: str) -> str:
        """Расшифровка данных"""
        if not encrypted_data:
            logger.warning("Empty data passed to decrypt()")
            return ""

        try:
            decrypted = self.fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error("Decryption failed (%s): %s", type(e).__name__, e)
            return ""

    def hash_phone(self, phone_number: str) -> str:
        """Хеширование номера телефона"""
        import hashlib
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        salt = os.getenv("HASH_SALT", "moysklad_bot_salt")
        return hashlib.sha256(f"{clean_phone}{salt}".encode()).hexdigest()


# Создаем глобальный экземпляр
security = SecurityManager()