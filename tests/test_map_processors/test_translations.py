from map_processors.translations import MapTranslationFileGenerator


def test_write_output_file():
    # parser = MapTranslationFileGenerator('6424УўРЫґ«.h3m', output_filename='6424.json', encoding='gb18030')
    parser = MapTranslationFileGenerator(
        '/home/maxb/.wine/drive_c/Games/LC_Heroes3/Heroes UNLEASHED/Maps/6424.h3m',
        output_filename='6424.json',
        encoding='gb18030',
    )

    parser.get_structured_data()

    assert parser.data['header']['map_name'] == '6424英雄传'
