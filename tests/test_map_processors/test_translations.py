from map_processors.base import MapParser
from map_processors.schemas import GameMapStructure
from map_processors.translations import MapTranslationFileGenerator


def test_write_output_file():
    parser = MapTranslationFileGenerator(
        '6424.h3m',
        output_filename='6424.json',
    )

    result = parser.get_structured_data()

    assert isinstance(result, GameMapStructure)
    assert result.header.map_name == '6424英雄传'
    assert len(result.players_attributes) == 8
    assert len(result.configured_heroes) == 124
    assert len(result.rumors) == 0
    assert len(result.predefined_heroes) == 156
    assert len(result.terrain.surface) == 20736
    assert len(result.terrain.underground) == 20736
    assert len(result.def_objects) == 965
    assert len(result.objects) == 17401
    assert len(result.events) == 11


def test_round_trip_json():
    parser = MapParser('6424.h3m')
    original = parser.get_structured_data()
    json_str = original.model_dump_json(by_alias=True, exclude_none=True)

    restored = GameMapStructure.model_validate_json(json_str)

    assert restored.header == original.header
    assert restored.players_attributes == original.players_attributes
    assert restored.victory == original.victory
    assert restored.loss == original.loss
    assert restored.teams == original.teams
    assert restored.configured_heroes == original.configured_heroes
    assert restored.rumors == original.rumors
    assert restored.predefined_heroes == original.predefined_heroes
    assert restored.terrain == original.terrain
    assert restored.def_objects == original.def_objects
    assert restored.objects == original.objects
    assert restored.events == original.events
