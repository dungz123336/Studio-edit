#!/usr/bin/env python3
"""Kiểm CHỮ KÝ SỐ (Ed25519) — khoá công khai của người bán nằm sẵn ở đây.

- KHOA_CAP_NHAT: kiểm gói cập nhật thật sự do người bán đóng (máy chủ bị chiếm cũng không giả được).
- KHOA_KICH_HOAT: kiểm thẻ kích hoạt do máy chủ / người bán cấp.
Khoá bí mật tương ứng KHÔNG BAO GIỜ nằm trong skill (xem quan_ly_ma.py).
"""
import base64, json

KHOA_CAP_NHAT = "853W8n6ELPKLPHNh-6trcWhuHVGckKYSo3eBZiT6gU0"   # dòng Studio
KHOA_KICH_HOAT = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtDX_-K6iAzlaetDaOpyf0Dmfa6BRcMrwdNEEFZ0dsEgEW3bnpvjom4g8ioiUCxWH02y_LyU4xWmNWn6jLRBeorqPQYq2-lXLNX7Hc3Bnm8Mb8Efl8b66mR221YSC6POX83aUMPM7G4DMWSNz-HS0dsiqyXeoCOsIUVDhnyniA-TREza55Genn9p_Mnnv-WwoTwGNctxWEl-BOTgWCxrJf_FmdH0s0vghayoOY9wPXMZrnzr18O3kpXoni4G2UkZTvKUL5wAsctwtieDnFRlELBlZcr_c7R1fJZFdUAHY71Zs1bdJqFnZLRNmEwLfFZhFpL-DHSF_KqjH7mkkSPhjLQIDAQAB"


def _b(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def kiem(khoa_b64, du_lieu: bytes, chu_ky: str) -> bool:
    """khoá 32 byte = Ed25519 (bản cập nhật, ký ở máy người bán) · khoá dài = RSA DER (thẻ kích hoạt, website ký bằng OpenSSL)"""
    if not khoa_b64 or not chu_ky:
        return False
    try:
        k = _b(khoa_b64)
        if len(k) == 32:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            Ed25519PublicKey.from_public_bytes(k).verify(_b(chu_ky), du_lieu)
        else:
            from cryptography.hazmat.primitives.serialization import load_der_public_key
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives import hashes
            load_der_public_key(k).verify(_b(chu_ky), du_lieu, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def chuan(obj) -> bytes:
    """dạng byte cố định của một dict để ký/kiểm (thứ tự khoá, không khoảng trắng)"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def dong_goi_the(noi_dung: dict, ham_ky) -> str:
    """thẻ = base64(noi_dung).chu_ky"""
    b = chuan(noi_dung)
    return base64.urlsafe_b64encode(b).decode().rstrip("=") + "." + ham_ky(b)


def mo_the(the: str):
    """→ dict nội dung nếu chữ ký đúng, None nếu sai"""
    try:
        a, c = the.strip().split(".")
        b = _b(a)
        return json.loads(b) if kiem(KHOA_KICH_HOAT, b, c) else None
    except Exception:
        return None
