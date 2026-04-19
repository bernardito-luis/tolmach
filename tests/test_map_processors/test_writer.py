import base64
import gzip
import pathlib

from map_processors.base import MapParser
from map_processors.schemas import OBJECT_CLASS_TO_TAG
from map_processors.writer import MapWriter


def test_write_uint32_round_trips_through_parser(writer):
    writer.write_uint32(0xDEADBEEF)
    parser = MapParser.__new__(MapParser)
    parser._cursor_position = 0
    parser.map_binary = bytes(writer._buffer)

    assert parser.process_uint32() == 0xDEADBEEF


def test_write_int32_round_trips_through_parser(writer):
    writer.write_int32(-12345)
    parser = MapParser.__new__(MapParser)
    parser._cursor_position = 0
    parser.map_binary = bytes(writer._buffer)

    assert parser.process_int32() == -12345


def test_write_mask_string_uses_big_endian_like_parser(writer):
    mask = '1000000000000001'
    writer.write_mask_string(mask, 2)
    parser = MapParser.__new__(MapParser)
    parser._cursor_position = 0
    parser.map_binary = bytes(writer._buffer)

    assert parser.process_n_bytes_to_mask(2) == mask


def test_write_string_round_trips_through_parser(writer):
    writer.write_string('hello')
    parser = MapParser.__new__(MapParser)
    parser._cursor_position = 0
    parser.map_binary = bytes(writer._buffer)
    parser.encoding = 'cp1251'

    assert parser.process_string() == 'hello'


def test_write_base64_bytes_round_trips_through_parser(writer):
    raw = bytes(range(16))
    writer.write_base64_bytes(base64.b64encode(raw).decode(), 16)
    parser = MapParser.__new__(MapParser)
    parser._cursor_position = 0
    parser.map_binary = bytes(writer._buffer)

    assert parser.process_n_bytes_to_base64(16) == base64.b64encode(raw).decode()


def test_write_witch_hut_ability_bits_uses_little_endian_uint32(writer):
    bits = '10000000000000000000000000000001'
    writer.write_uint32(int(bits, 2))
    parser = MapParser.__new__(MapParser)
    parser._cursor_position = 0
    parser.map_binary = bytes(writer._buffer)

    assert f'{parser.process_uint32():032b}' == bits


def test_all_object_class_tags_have_dispatch():
    expected_tags = set(OBJECT_CLASS_TO_TAG.keys())
    handled = {
        'event',
        'sign',
        'ocean_bottle',
        'hero',
        'random_hero',
        'prison',
        'monster',
        'random_monster',
        'random_monster_l1',
        'random_monster_l2',
        'random_monster_l3',
        'random_monster_l4',
        'random_monster_l5',
        'random_monster_l6',
        'random_monster_l7',
        'seer_hut',
        'witch_hut',
        'scholar',
        'garrison_horizontal',
        'garrison_vertical',
        'spell_scroll',
        'artifact',
        'random_art',
        'random_treasure_art',
        'random_minor_art',
        'random_major_art',
        'random_relic_art',
        'resource',
        'random_resource',
        'town',
        'random_town',
        'mine',
        'abandoned_mine',
        'creature_generator1',
        'creature_generator2',
        'creature_generator3',
        'creature_generator4',
        'shrine_of_magic_incantation',
        'shrine_of_magic_gesture',
        'shrine_of_magic_thought',
        'pandora_box',
        'grail',
        'random_dwelling',
        'random_dwelling_lvl',
        'random_dwelling_faction',
        'quest_guard',
        'shipyard',
        'hero_placeholder',
        'lighthouse',
    }

    missing = expected_tags - handled

    assert not missing, f'Missing dispatch entries: {missing}'


def _round_trip(original, encoding, tmp_path: pathlib.Path):
    """Write structure → re-parse, return restored structure."""
    writer = MapWriter(original, encoding=encoding)
    out_path = tmp_path / 'roundtrip.h3m'
    writer.write_to_file(str(out_path))

    restored_parser = MapParser(str(out_path), encoding=encoding)
    return restored_parser.get_structured_data()


def test_round_trip_test_map_model_equality(test_map, tmp_path):
    original, encoding = test_map

    restored = _round_trip(original, encoding, tmp_path)

    assert restored.header == original.header
    assert restored.players_attributes == original.players_attributes
    assert restored.victory == original.victory
    assert restored.loss == original.loss
    assert restored.teams == original.teams
    assert restored.allowed_heroes_info == original.allowed_heroes_info
    assert restored.placeholder_heroes == original.placeholder_heroes
    assert restored.configured_heroes == original.configured_heroes
    assert restored.artifacts == original.artifacts
    assert restored.allowed_spells_bytes == original.allowed_spells_bytes
    assert restored.allowed_hero_abilities_bytes == original.allowed_hero_abilities_bytes
    assert restored.rumors == original.rumors
    assert restored.predefined_heroes == original.predefined_heroes
    assert restored.terrain == original.terrain
    assert restored.def_objects == original.def_objects
    assert restored.objects == original.objects
    assert restored.events == original.events


def _read_decompressed(path: pathlib.Path) -> bytes:
    with gzip.open(path, 'rb') as f:
        return f.read()


def test_byte_for_byte_round_trip_chinese_map(test_map, test_map_path, tmp_path):
    original, encoding = test_map
    parser = MapParser(str(test_map_path))
    parser.get_structured_data()

    w = MapWriter(original, encoding=encoding)
    out = tmp_path / 'roundtrip.h3m'
    w.write_to_file(str(out))

    assert _read_decompressed(out) == _read_decompressed(test_map_path)


def test_heroes_info_unknown_populated(test_map):
    original, _ = test_map

    assert original.heroes_info_unknown is not None
    assert len(base64.b64decode(original.heroes_info_unknown)) == 31


def test_pre_body_unknown_populated_on_objects(test_map):
    original, _ = test_map

    assert original.objects, 'map has no objects to test against'
    assert original.objects[0].pre_body_unknown is not None
    assert len(base64.b64decode(original.objects[0].pre_body_unknown)) == 5
    assert original.objects[-1].pre_body_unknown is not None
    assert len(base64.b64decode(original.objects[-1].pre_body_unknown)) == 5


def test_unknown_fallback_emits_zero_padding(writer):
    writer._write_unknown(None, 5)

    assert bytes(writer._buffer) == b'\x00' * 5
