import pathlib

import pytest

from map_processors.base import MapParser
from map_processors.schemas import (
    GameMapStructure,
    Header,
    Loss,
    Teams,
    Terrain,
    Victory,
)
from map_processors.writer import MapWriter

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope='session')
def test_map_path() -> pathlib.Path:
    return PROJECT_ROOT / '6424.h3m'


def _parse(path: pathlib.Path):
    parser = MapParser(str(path))
    structure = parser.get_structured_data()
    return structure, parser.encoding


@pytest.fixture(scope='session')
def test_map(test_map_path):
    structure, encoding = _parse(test_map_path)
    return structure, encoding


@pytest.fixture
def writer():
    structure = GameMapStructure(
        header=Header(
            map_type=28,
            are_any_players=True,
            height=36,
            width=36,
            has_underground=False,
            map_name='',
            map_description='',
            map_difficulty=0,
            hero_level_limit=0,
        ),
        victory=Victory(special_victory_condition=0xFF),
        loss=Loss(special_loss_condition=0xFF),
        teams=Teams(quantity=0),
        allowed_heroes_info='0' * 160,
        terrain=Terrain(),
    )
    return MapWriter(structure, encoding='cp1251')
