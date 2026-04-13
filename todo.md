# Tolmach — Task List

## Phase 1: H3M → JSON conversion (refinement)

(done)


### 1.11 TODOs from comments

#### 1.11.1 (done) `enums.py` — cleanup
- `EnumWithContainsCheck` metaclass — delete and just inherit from `IntEnum` (line 15)

#### 1.11.2 `map_processors/base.py` — parsing improvements
- `allowed_heroes_info` is typed as `str` — move to separate structure (line 340)
- (done) `placeholder_heroes: [int, ...]` — unclear semantics, investigate (line 354), just an array containing hero_id's for objects of class 'hero_placeholder', seems to be useless
- (done) `skip_n_bytes()` — alert when skipped bytes are non-empty (line 83)
- (done) `try/except Exception` — remove or rework broad exception catch; `print(self.map_binary[self._cursor_position : string_end], 'tried into', self.encoding)` (line 108)
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

### 4.3 Add typer checker
- For example ty
- Fix type checker inspections

### 4.4 CI/CD
- GitHub Actions: lint, test, publish on tag
- Test matrix: Python 3.13+

### 4.5 Documentation
- README: update with Pydantic-model-based usage examples
- Docstrings for public API


### 5 Review map archive
- Faeries.h3m
- A Matter of Honor.h3m
- A Hard Journey.h3m (wrong coding)
- Taiji.h3m (wrong coding)
