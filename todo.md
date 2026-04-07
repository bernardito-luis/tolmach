# Tolmach — Task List

## Phase 1: H3M → JSON conversion (refinement)

### 1.1 (done) Generate OpenAPI spec from Pydantic models and serve via web page
- Use `GameMapStructure.model_json_schema()` to produce a JSON Schema
- Wrap it in a minimal OpenAPI 3.1 envelope (OpenAPI 3.1 uses JSON Schema natively)
- Serve an HTML page with Scalar/Redoc/Swagger UI that renders the schema
- Lightweight: no FastAPI needed — just a small script with `http.server` or similar
- Endpoint: `GET /` serves the docs page, `GET /openapi.json` serves the raw schema

### 1.2 (done) Output: `get_structured_data()` should return Pydantic models, not raw dicts
- `MapParser.get_structured_data()` currently builds `self.data` as `OrderedDict` of plain dicts
- Pydantic schemas already exist in `schemas.py` (`GameMapStructure` and children) but are never used by the parser
- Each `read_*` method should construct and return the corresponding Pydantic model instead of a dict
- `get_structured_data()` should return `GameMapStructure` instance
- This gives validation, typed access, and `.model_dump_json()` for free

### 1.3 (done) Serialization: `GameMapStructure` → JSON file
- Add a method (or standalone function) that takes a `GameMapStructure` and writes a human-readable JSON file
- Use `model_dump(mode='json', by_alias=True)` so the `def` field alias works correctly
- Ensure `Coordinates`, `Resources`, `PrimarySkills` etc. serialize cleanly (no Pydantic internals leaking)
- Decide on handling of `None` / default values: exclude or keep (probably `exclude_none=True` for readability)

### 1.4 Remove debug / hack code in `get_structured_data()`
- The `try/except IndexError` block (lines 1105-1116) that silently swallows parsing errors and writes to `strange_ab_maps.json` must go
- Replace with proper error handling — raise a clear `H3MapParserException` with context (filename, cursor position, object index)
- Remove leftover `print()` calls (e.g. `detect_encoding_by_header` line 153, `base_process_string` line 115)

### 1.5 (done) Remove/deprecate `map_structure.py`
- `map_structure.py` is a hand-written dict-based schema that duplicates `schemas.py`
- Once Pydantic models are the source of truth, this file is dead weight — delete it

### 1.6 (done) Ensure `enums.py` and `exceptions.py` live inside the package
- Currently `enums.py` and `exceptions.py` sit at the project root, outside `map_processors/`
- Move them into the package (e.g. `map_processors/enums.py`, `map_processors/exceptions.py`)
- Update imports in `base.py`

### 1.7 Clean up `MapParserWriter` and `MapTranslationFileGenerator` coupling
- `MapParserWriter` in `translations.py` overrides every `process_*` method just to also append bytes — fragile
- Consider: instead of dual-writing during parse, reconstruct binary from the Pydantic model (this becomes Phase 2)
- For now, mark `MapParserWriter` as deprecated or internal; the public API should be Pydantic-model-based

### 1.8 (done) Schema completeness audit
- Verify every object type parsed in `read_objects()` has a matching Pydantic schema in `schemas.py`
- Verify discriminator union `AllMapObjectSchemas` covers all `ObjectType` enum members that carry data
- Check field types match what the parser actually produces (e.g. `MapArtifact.artifact_id` is `int` in schema but parser takes it from `def` table — make sure this round-trips)

### 1.9 Test coverage for H3M → JSON
- Current tests: only one test (`test_write_output_file`) that tests a single Chinese map
- Add at least:
  - Unit test: parse a small SOD map → assert `GameMapStructure` validates successfully
  - Unit test: parse a ROE map (different code paths for artifact IDs, hero IDs, etc.)
  - Unit test: parse an AB map
  - Round-trip sanity: `parse → model_dump_json → model_validate_json` should not lose data
- Need sample .h3m files in `tests/fixtures/` (small maps, one per format)

### 1.10 Encoding handling
- `detect_encoding_by_header()` uses `chardet` with fallback to `cp1251` and a `MacCyrillic → cp1251` hack
- Document supported encodings
- Consider making encoding detection a separate utility function (testable independently)


### 1.11 TODOs from comments

#### 1.11.1 (done) `enums.py` — cleanup
- `EnumWithContainsCheck` metaclass — delete and just inherit from `IntEnum` (line 15)

#### 1.11.2 `map_processors/base.py` — parsing improvements
- `allowed_heroes_info` is typed as `str` — move to separate structure (line 340)
- `placeholder_heroes: [int, ...]` — unclear semantics, investigate (line 346)
- `skip_n_bytes()` — alert when skipped bytes are non-empty (line 83)
- `try/except Exception` — remove or rework broad exception catch; `print(self.map_binary[self._cursor_position : string_end], 'tried into', self.encoding)` (line 108)
- `computer_playstyle` — look for matching enum (line 219)
- Victory condition field — enum + rename to `special_victory_condition` (line 267)
- `special_loss_condition` — convert to enum (line 310-...)
- `red_team_number` — parse to bitmask? (line 328-...)
- Object reassembly question — can we continue parsing if assembly is unclear? (line 522)
- Primary skills reading — extract to `read_primary_skills()` method (line 645)
- `mana_diff` — check if `int32` should be unsigned (line 735)
- `bonus_type` — convert to enum (line 889)
- `bonus_id` — check if `uint8` is correct for spells (line 890-891)
- Mine/abandoned mine — analyze strange case;   # not owner for abandoned mine? (line 946)
- Hidden possibilities to check — investigate and document: # 1. town events occurrence: try strange numbers 8, 9, 10 (line 1116)

#### 1.11.3 `map_processors/translations.py` — cleanup
- Module-level `# TODO: remove?` — decide whether to keep or remove (line 6)

#### 1.11.3 `map_processors/schemas.py`
- `artifacts` is typed as `str` — likely blocked artifacts, clarify (line 624)


## Phase 2: JSON → H3M (binary writer)

> Depends on Phase 1 being done — Pydantic models are the interchange format.

### 2.1 Design the binary writer architecture
- Create `MapWriter` class that takes a `GameMapStructure` and writes `.h3m` (gzipped)
- Mirror the structure of `MapParser.get_structured_data()` — one `write_*` method per section
- Primitive writers: `write_uint8`, `write_uint16`, `write_uint32`, `write_string`, `write_n_bytes`, etc.

### 2.2 Implement section writers
- `write_header()`
- `write_players_attributes()`
- `write_victory_conditions()`
- `write_loss_conditions()`
- `write_teams()`
- `write_heroes_info()`
- `write_artifacts()`, `write_spells()`, `write_abilities()`
- `write_rumors()`
- `write_predefined_heroes()`
- `write_terrain()`
- `write_def_info()`
- `write_objects()` — most complex, needs per-object-type serialization
- `write_events()`

### 2.3 Round-trip test: H3M → JSON → H3M → byte-compare
- Parse an .h3m → get `GameMapStructure` → write back to .h3m → compare binary output byte-for-byte with original
- This is the ultimate correctness test
- Start with simple maps (no objects) and progressively add complexity

### 2.4 Handle `skip_n_bytes` / unknown data
- Parser currently uses `skip_n_bytes()` to jump over unknown/padding bytes
- These bytes are lost — the writer can't reproduce them
- Options: (a) store unknown bytes as base64 in the model, (b) use known padding values (usually `0x00`)
- Audit every `skip_n_bytes` call and decide which approach to use


## Phase 3: Translation feature refinement

### 3.1 Translation based on Pydantic model `Translatable` markers
- `Translatable` marker class exists in schemas but is unused at runtime
- Build a function that walks a `GameMapStructure`, finds all `Annotated[str, Translatable()]` fields, and extracts translatable strings with their path (e.g. `header.map_name`, `objects[3].message`)
- Replace `MapTranslationFileGenerator` with this approach

### 3.2 Apply translations to model
- Given a `GameMapStructure` and a translation dict, produce a new `GameMapStructure` with translated strings
- Combined with Phase 2 writer, this replaces `MapSimpleTranslator`


## Phase 4: Package & publish to PyPI

### 4.1 Project structure for packaging
- `pyproject.toml` already has basic metadata — extend with:
  - `license`, `authors`, `urls`, `classifiers`, `keywords`
  - Entry point / CLI (optional, e.g. `tolmach convert map.h3m`)
- Move `pre-commit` and `ruff` from `dependencies` to `dev` dependency group (they are dev tools, not runtime deps)

### 4.2 Public API surface
- Define what's exported from `map_processors.__init__.py` (currently empty)
- Consider renaming package from `map_processors` to `tolmach` for consistency with PyPI name

### 4.3 CI/CD
- GitHub Actions: lint, test, publish on tag
- Test matrix: Python 3.13+

### 4.4 Documentation
- README: update with Pydantic-model-based usage examples
- Docstrings for public API


### 5 Review map archive
- Faeries.h3m
- A Matter of Honor.h3m
- A Hard Journey.h3m (wrong coding)
- Taiji.h3m (wrong coding)
