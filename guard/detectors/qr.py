# guard/detectors/qr.py
import io, logging
from typing import List

import numpy as np
from PIL import Image, ImageOps
import zxingcpp
import discord

from ..config import Config

log = logging.getLogger("guard.detectors.qr")

def is_scannable_attachment(att: discord.Attachment, cfg: Config) -> bool:
    ct = (att.content_type or "").lower()
    if not ct.startswith("image/"):
        return False
    if cfg.qr_exclude_gif and ct == "image/gif":
        return False
    if ct in {"image/heic", "image/heif"}:
        return False
    if att.size and att.size > cfg.qr_max_bytes:
        return False
    return True

def _is_qr_format(fmt_obj) -> bool:
    name = getattr(fmt_obj, "name", str(fmt_obj))
    s = (name or "").replace(" ", "").lower()
    return s in {"qrcode", "microqrcode", "rmqrcode"} or s.endswith("qrcode")

def _pil_variants(img: Image.Image):
    img = img.convert("RGB")
    g = img.convert("L")
    variants = [
        img,
        ImageOps.invert(img),
        g,
        ImageOps.invert(g),
        ImageOps.autocontrast(g, cutoff=2),
        g.resize((max(1, g.width*2), max(1, g.height*2)), Image.NEAREST),
    ]
    for im in variants:
        yield im
        yield im.transpose(Image.ROTATE_90)
        yield im.transpose(Image.ROTATE_180)
        yield im.transpose(Image.ROTATE_270)

def _zxing_decode_pil(img: Image.Image) -> List[str]:
    texts = set()
    binarizers = [
        zxingcpp.Binarizer.LocalAverage,
        zxingcpp.Binarizer.GlobalHistogram,
        zxingcpp.Binarizer.FixedThreshold,
    ]
    for im in _pil_variants(img):
        arr = np.ascontiguousarray(np.array(im))
        for b in binarizers:
            results = zxingcpp.read_barcodes(
                arr, try_rotate=True, try_downscale=True, binarizer=b,
            )
            for r in results or []:
                if _is_qr_format(getattr(r, "format", "")) and getattr(r, "text", ""):
                    texts.add(r.text)
            if texts:
                break
        if texts:
            break
    return list(texts)

async def detect_qr_bytes(b: bytes) -> List[str]:
    try:
        img = Image.open(io.BytesIO(b))
        return _zxing_decode_pil(img)
    except Exception as e:
        log.warning("QR 디코딩 실패: %s", e)
        return []

def obfuscate(text: str) -> str:
    return (text or "").replace("http", "hxxp").replace(".", "[.]")
