import base64
from cryptography.fernet import Fernet
import os

# Импортируем конфигурацию
try:
    from config import config
except ImportError:
    # Создаем минимальную конфигурацию, если config.py не найден
    class SimpleConfig:
        ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")


    config = SimpleConfig()


class SecurityManager:
    """Менеджер безопасности для шифрования данных"""

    def __init__(self, encryption_key: str = None):
        self.encryption_key = encryption_key or config.ENCRYPTION_KEY
        print(f"[SECURITY] Initialization with key: {self.encryption_key[:20]}...")
        self.fernet = self._init_fernet()

    def _init_fernet(self):
        """Инициализация Fernet с ключом"""
        try:
            print(f"[SECURITY] Initializing Fernet with key length {len(self.encryption_key)}")

            # Проверяем, является ли ключ валидным Fernet ключом
            if not self.encryption_key:
                print("[ERROR] Encryption key is missing")
                return self._generate_new_key()

            if len(self.encryption_key) != 44:
                print(f"[WARNING] Invalid key length: {len(self.encryption_key)} (should be 44)")
                return self._generate_new_key()

            # Декодируем ключ из base64
            try:
                key = base64.urlsafe_b64decode(self.encryption_key)
                print(f"[SUCCESS] Key decoded from base64, length: {len(key)} bytes")

                if len(key) != 32:
                    print(f"[ERROR] Decoded key is not 32 bytes: {len(key)}")
                    return self._generate_new_key()

                fernet = Fernet(self.encryption_key.encode())
                print("[SUCCESS] Fernet initialized successfully")
                return fernet

            except Exception as decode_error:
                print(f"[ERROR] Key decoding failed: {decode_error}")
                return self._generate_new_key()

        except Exception as e:
            print(f"[ERROR] Encryption initialization failed: {e}")
            return self._generate_new_key()

    def _generate_new_key(self):
        """Генерация нового ключа шифрования"""
        print("[SECURITY] Generating new encryption key...")
        key = Fernet.generate_key()
        self.encryption_key = key.decode()

        print(f"[INFO] New key (save to .env):")
        print(f"ENCRYPTION_KEY={self.encryption_key}")

        return Fernet(key)

    def encrypt(self, data: str) -> str:
        """Шифрование данных"""
        print(f"[ENCRYPT] Encrypting data of length {len(data)}")
        try:
            if not data:
                print("[WARNING] Empty data for encryption")
                return ""

            encrypted = self.fernet.encrypt(data.encode())
            result = encrypted.decode()
            print(f"[SUCCESS] Data encrypted, result: {result[:50]}...")
            return result

        except Exception as e:
            print(f"[ERROR] Encryption failed: {e}")
            return data

    def decrypt(self, encrypted_data: str) -> str:
        """Расшифровка данных"""

        try:
            if not encrypted_data:
                print("[WARNING] Empty data for decryption")
                return ""

            decrypted = self.fernet.decrypt(encrypted_data.encode())
            result = decrypted.decode()
            print(f"[SUCCESS] Data decrypted, result: {result[:50]}...")
            return result

        except Exception as e:
            print(f"[ERROR] Decryption failed: {e}")
            print(f"   Error type: {type(e).__name__}")
            return ""

    def hash_phone(self, phone_number: str) -> str:
        """Хеширование номера телефона"""
        import hashlib
        # Убираем все нецифровые символы
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        # Хешируем с солью
        salt = os.getenv("HASH_SALT", "moysklad_bot_salt")
        return hashlib.sha256(f"{clean_phone}{salt}".encode()).hexdigest()


# Создаем глобальный экземпляр
security = SecurityManager()