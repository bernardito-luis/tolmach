Heroes 3 map translation tool
-----------------------------

### Development setup

1. Create a virtual environment: `python -m venv .venv` (or other way you prefer)
2. Activate it: `source .venv/bin/activate` (on Linux/macOS) or `.venv\Scripts\activate` (on Windows)
3. Install dependencies: `pip install -r requirements.txt`
4. Set up pre-commit hooks: `pre-commit install`

Now `ruff` will run automatically on every commit to lint and format your code.

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
