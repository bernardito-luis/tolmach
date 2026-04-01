from map_processors.translations import MapTranslationFileGenerator


def test_write_output_file():
    # parser = MapTranslationFileGenerator('6424УўРЫґ«.h3m', output_filename='6424.json', encoding='gb18030')
    parser = MapTranslationFileGenerator(
        '6424.h3m',
        output_filename='6424.json',
    )

    parser.get_structured_data()

    assert parser.data['header']['map_name'] == '6424英雄传'
    assert len(parser.data['players_attributes']) == 8
    assert len(parser.data['configured_heroes']) == 124
    assert len(parser.data['rumors']) == 0
    assert len(parser.data['predefined_heroes']) == 156
    assert len(parser.data['terrain']['surface']) == 20736
    assert len(parser.data['terrain']['underground']) == 20736
    assert len(parser.data['def']) == 965
    assert len(parser.data['objects']) == 17401
    assert len(parser.data['events']) == 11
