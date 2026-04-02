from map_processors.schemas import GameMapStructure
from map_processors.translations import MapTranslationFileGenerator


def test_write_output_file():
    # parser = MapTranslationFileGenerator('6424УўРЫґ«.h3m', output_filename='6424.json', encoding='gb18030')
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
