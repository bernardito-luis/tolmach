"""
Encoding detection for H3M map files.

Supported encodings (detected via chardet):
- Windows-1251 (cp1251) - Cyrillic maps
- Windows-1252 (cp1252) - European latin languages
- GB18030 - Chinese maps
- MacCyrillic - treated as cp1251 (chardet sometimes misidentifies cp1251 as MacCyrillic)
- Any other encoding chardet detects with high confidence
"""

import chardet

ENCODING_ALIASES: dict[str, str] = {
    'MacCyrillic': 'cp1251',
}

LOW_CONFIDENCE_ENCODINGS: dict[str, float] = {
    'GB18030': 0.2,
    'Windows-1251': 0.2,
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.85


def detect_map_encoding(
    map_name: bytes,
    map_description: bytes,
    *,
    fallback_encoding: str | None = 'cp1251',
) -> str | None:
    map_name_coding = detect_encoding(map_name, confidence_threshold=0.9)
    map_description_coding = detect_encoding(
        map_description, confidence_threshold=DEFAULT_CONFIDENCE_THRESHOLD
    )

    encoding = map_description_coding or map_name_coding or fallback_encoding
    return ENCODING_ALIASES.get(encoding, encoding) if encoding else None


def detect_encoding(unknown_bytes: bytes, *, confidence_threshold: float) -> str | None:
    if not unknown_bytes:
        return None

    result = chardet.detect(unknown_bytes, prefer_superset=True)
    detected_encoding: str | None = result['encoding']
    confidence: float = result['confidence']

    if confidence >= confidence_threshold:
        return detected_encoding

    if detected_encoding and confidence >= LOW_CONFIDENCE_ENCODINGS.get(
        detected_encoding, DEFAULT_CONFIDENCE_THRESHOLD
    ):
        return detected_encoding

    return None
