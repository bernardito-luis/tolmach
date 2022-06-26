Heroes 3 map translation tool
-----------------------------

### Usage:

- Generate file with translations from map `map.h3m`
```python
from map_processors.translations import MapTranslationFileGenerator

parser = MapTranslationFileGenerator('D:\\Heroes 3\\Maps\\map.h3m')
parser.write_output_file()
```
- Open `D:\Heroes 3\Maps\map_translations.json` and fill the translations

- Translate map `map.h3m`
```python
from map_processors.translations import MapSimpleTranslator

translator = MapSimpleTranslator('D:\\Heroes 3\\Maps\\map.h3m')
translator.write_output_file()
```
see code for more details
