from map_processors.encoding import detect_map_encoding


def test_detect_encoding_cyrillic_text():
    name = 'Карта'.encode('cp1251')
    description = 'Описание карты для тестирования'.encode('cp1251')
    expected_encoding = 'Windows-1251'

    encoding = detect_map_encoding(name, description)

    assert encoding == expected_encoding


def test_detect_encoding_chinese_text():
    name = '6424英雄传'.encode('gb18030')
    description = '这是一个中文地图描述'.encode('gb18030')
    expected_encoding = 'GB18030'

    encoding = detect_map_encoding(name, description)

    assert encoding == expected_encoding


def test_detect_encoding_ascii_text():
    name = b'Simple Map'
    description = b'A simple description'
    expected_encoding = 'Windows-1252'

    encoding = detect_map_encoding(name, description, fallback_encoding='cp1251')

    assert encoding == expected_encoding


def test_detect_encoding_empty_bytes_uses_fallback():
    expected_encoding = 'cp1251'
    encoding = detect_map_encoding(b'', b'', fallback_encoding=expected_encoding)

    assert encoding == expected_encoding


def test_detect_encoding_no_fallback_returns_none():
    encoding = detect_map_encoding(b'', b'', fallback_encoding=None)

    assert encoding is None


def test_detect_encoding_mac_cyrillic_remapped_to_cp1251():
    encoding = detect_map_encoding(b'', b'', fallback_encoding='MacCyrillic')
    expected_encoding = 'cp1251'

    assert encoding == expected_encoding


def test_detect_encoding_prefers_description_over_name():
    name = b'Simple Name'
    description = 'Длинное описание карты на русском языке для теста'.encode('cp1251')
    expected_encoding = 'Windows-1251'

    encoding = detect_map_encoding(name, description, fallback_encoding=None)

    assert encoding == expected_encoding
