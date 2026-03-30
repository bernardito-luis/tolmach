from typing import Annotated, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, conint

# TODO: move to custom types
TextField = str
AnotherTextField = str

UPPER_LIMIT_1_BYTE = 255
UPPER_LIMIT_2_BYTES = 65535
UPPER_LIMIT_4_BYTES = 4294967295
UPPER_LIMIT_SIGNED_1_BYTE = 127
UPPER_LIMIT_SIGNED_2_BYTES = 32767
UPPER_LIMIT_SIGNED_4_BYTES = 2147483647
LOWER_LIMIT_SIGNED_1_BYTE = -128
LOWER_LIMIT_SIGNED_2_BYTES = -32768
LOWER_LIMIT_SIGNED_4_BYTES = -2147483648


class Empty(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Coordinates(BaseModel):
    x: int
    y: int
    z: int

    @classmethod
    def from_tuple(cls, coords: Tuple[int, int, int]) -> 'Coordinates':
        return cls(x=coords[0], y=coords[1], z=coords[2])


class Resources(BaseModel):
    wood: int = 0
    mercury: int = 0
    ore: int = 0
    sulfur: int = 0
    crystal: int = 0
    gems: int = 0
    gold: int = 0


class PrimarySkills(BaseModel):
    attack: int = 0
    defence: int = 0
    power: int = 0
    knowledge: int = 0


class Ability(BaseModel):
    id: int
    level: int


class Creature(BaseModel):
    id: int
    quantity: int


class Guard(BaseModel):
    id: int
    quantity: int


# Header Schema
class Header(BaseModel):
    map_type: conint(ge=0, le=UPPER_LIMIT_1_BYTE)
    are_any_players: bool
    height: int
    width: int
    has_underground: bool
    map_name: str
    map_description: Annotated[str, Tag('translatable')]
    map_difficulty: int
    hero_level_limit: Optional[int] = None


# Player-related Schemas
class Hero(BaseModel):
    hero_id: int
    hero_name: str


class PlayerAttributes(BaseModel):
    can_human_play: bool
    can_computer_play: bool
    computer_playstyle: Optional[int] = None
    are_factions_configured: Optional[int] = None
    allowed_factions: Optional[int] = None
    is_faction_random: Optional[int] = None
    generate_hero_at_main_town: Optional[int] = None
    generate_hero: Optional[int] = None
    town_coordinates: Optional[Tuple[int, int, int]] = None
    has_random_hero: Optional[int] = None
    main_custom_hero_id: Optional[int] = None
    main_custom_hero_portrait: Optional[int] = None
    main_custom_hero_name: Optional[str] = None
    hero_count: Optional[int] = None
    heroes: Optional[List[Hero]] = None


# Victory and Loss Conditions
class Victory(BaseModel):
    special_victory_condition: int
    standard_win_available: Optional[int] = None
    applies_to_computer: Optional[int] = None
    acquire_artifact_code: Optional[int] = None
    unit_code: Optional[int] = None
    unit_quantity: Optional[int] = None
    resource_code: Optional[int] = None
    resource_quantity: Optional[int] = None
    upgrade_town_coordinates: Optional[Tuple[int, int, int]] = None
    hall_level: Optional[int] = None
    castle_level: Optional[int] = None
    build_grail_town_coordinates: Optional[Tuple[int, int, int]] = None
    hero_coordinates: Optional[Tuple[int, int, int]] = None
    capture_town_coordinates: Optional[Tuple[int, int, int]] = None
    creature_coordinates: Optional[Tuple[int, int, int]] = None
    bring_artifact_code: Optional[int] = None
    bring_artifact_town_coordinates: Optional[Tuple[int, int, int]] = None


class Loss(BaseModel):
    special_loss_condition: int
    loss_town_coordinates: Optional[Tuple[int, int, int]] = None
    loss_hero_coordinates: Optional[Tuple[int, int, int]] = None
    time_expires_in_days: Optional[int] = None


# Team Configuration
class Teams(BaseModel):
    quantity: int
    red_team_number: int | None = None
    blue_team_number: int | None = None
    brown_team_number: int | None = None
    green_team_number: int | None = None
    orange_team_number: int | None = None
    purple_team_number: int | None = None
    teal_team_number: int | None = None
    pink_team_number: int | None = None


# Hero Configuration
class ConfiguredHero(BaseModel):
    id: int
    portrait: int
    name: str
    players_access: int


class PredefinedHero(BaseModel):
    experience: Optional[int] = None
    abilities: List[Ability] = []
    artifacts: Dict[int, int] = {}
    biography: Optional[str] = None
    sex: int
    spells: Optional[str] = None
    primary_skills: Optional[PrimarySkills] = None


class PredefinedHeroNonConfigured(Empty):
    pass


# Rumors
class Rumor(BaseModel):
    name: str
    text: str


# Terrain
class TerrainTile(BaseModel):
    terrain_type: int
    view: int
    river_type: int
    river_flow: int
    road_type: int
    road_flow: int
    flip_bits: int


class Terrain(BaseModel):
    surface: List[TerrainTile] = []
    underground: List[TerrainTile] = []


# Definition Files
class DefFile(BaseModel):
    sprite_filename: str
    unpassable_tiles: str
    active_tiles: str
    allowed_terrain: int
    terrain_group: int
    object_class: int
    object_number: int
    object_group: int
    z_index: int
    unknown_base64: str


# class Mine(BaseModel):
#     owner: str
#
#
# class AbandonedMine(BaseModel):
#     possible_resources: str


# Main Object Schema
class MapObject(BaseModel):
    object_class: str
    object_subclass: int
    coordinates: Tuple[int, int, int]


class MapEvent(MapObject):
    object_class: Literal['event']
    message: str | None = None
    guards: List[Guard] | None = None
    experience: int
    mana_diff: int
    morale: int
    luck: int
    resources: Resources = Resources()
    primary_skills: PrimarySkills = PrimarySkills()
    abilities: List[Ability] = []
    artifacts: List[int] = []
    spells: List[int] = []
    creatures: List[Creature] = []
    available_for_color: str
    can_computer_activate: bool
    remove_after_visit: bool

    # TODO
    # def model_dump(
    #     self,
    #     *,
    #     mode: Literal['json', 'python'] | str = 'python',
    #     include: IncEx | None = None,
    #     exclude: IncEx | None = None,
    #     context: Any | None = None,
    #     by_alias: bool | None = None,
    #     exclude_unset: bool = False,
    #     exclude_defaults: bool = False,
    #     exclude_none: bool = False,
    #     round_trip: bool = False,
    #     warnings: bool | Literal['none', 'warn', 'error'] = True,
    #     fallback: Callable[[Any], Any] | None = None,
    #     serialize_as_any: bool = False,
    # ) -> dict[str, Any]:


class MapSign(MapObject):
    object_class: Literal['sign']
    message: str


class MapOceanBottle(MapObject):
    object_class: Literal['ocean_bottle']
    message: str


class MapHero(MapObject):
    object_class: Literal['hero', 'random_hero', 'prison']
    id: Optional[int] = None
    owner: int
    hero_sub_id: int
    name: str | None = None
    experience: int | None = None
    portrait: int | None = None
    abilities: List[Ability] | None = None
    creatures: List[Creature] | None = None
    formation: int
    artifacts: Dict[int, int] | None = None
    patrol_radius: int
    biography: str | None = None
    sex: int | None = None
    custom_spells: str | None = None
    custom_primary_skills: PrimarySkills | None = None


class MapMonster(MapObject):
    object_class: Literal[
        'monster',
        'random_monster',
        'random_monster_l1',
        'random_monster_l2',
        'random_monster_l3',
        'random_monster_l4',
        'random_monster_l5',
        'random_monster_l6',
        'random_monster_l7',
    ]
    id: int | None = None
    quantity: int
    character: int
    message: str | None = None
    resources: Resources | None = None
    artifact_id: int | None = None
    mood: int
    not_growing: bool


class Reward(BaseModel):
    type: str
    experience: Optional[int] = None
    mana_points: Optional[int] = None
    morale: Optional[int] = None
    luck: Optional[int] = None
    resource_type: Optional[str] = None
    resource_quantity: Optional[int] = None
    skill_id: Optional[int] = None
    skill_increase: Optional[int] = None
    artifact_id: Optional[int] = None
    spell_id: Optional[int] = None
    creature_id: Optional[int] = None
    creature_quantity: Optional[int] = None


class MapSeerHut(MapObject):
    object_class: Literal['seer_hut']
    mission_type: str
    level: int | None = None
    hero_object_id: int | None = None
    monster_object_id: int | None = None
    primary_skills: dict | None = None
    artifacts: list[int] | None = None
    creatures: list[Creature] | None = None
    resources: Resources | None = None
    color: str | None = None
    limit: int | None = None
    first_visit_text: str | None = None
    next_visit_text: str | None = None
    completed_text: str | None = None
    reward: Reward | None = None


class MapWitchHut(MapObject):
    object_class: Literal['witch_hut']
    ability_bits: Optional[str] = None


class MapScholar(MapObject):
    object_class: Literal['scholar']
    bonus_type: int
    bonus_id: int


class MapGarrison(MapObject):
    object_class: Literal['garrison_horizontal', 'garrison_vertical']
    owner: str
    creatures: List[Creature] = []
    is_removable: int


class MessageAndGuards(MapObject):
    message: str | None = None
    guards: List[Guard] | None = None


class MapSpellScroll(MessageAndGuards):
    object_class: Literal['spell_scroll']
    spell_id: int


class MapArtifact(MessageAndGuards):
    object_class: Literal['artifact']
    artifact_id: int


class MapRandomArtifact(MessageAndGuards):
    object_class: Literal[
        'random_art',
        'random_treasure_art',
        'random_minor_art',
        'random_major_art',
        'random_relic_art',
    ]
    level: str


class MapResource(MessageAndGuards):
    object_class: Literal['resource']
    resource_type: str
    quantity: int


class MapRandomResource(MessageAndGuards):
    object_class: Literal['random_resource']
    quantity: int


class TownEvent(BaseModel):
    name: str
    message: str
    resources: Resources = Resources()
    players: str
    is_human_affected: bool
    is_computer_affected: bool
    first_occurrence: int
    next_occurrence: int
    unknown: str
    new_buildings: str
    new_creatures_quantities: List[int] = []
    unknown2: str


class MapTown(MapObject):
    object_class: Literal['town', 'random_town']
    id: int | None = None
    owner: str
    name: str | None = None
    garrison: List[Creature] | None = None
    formation: int
    built_buildings: str | None = None
    forbidden_buildings: str | None = None
    has_fort: bool | None = None
    obligatory_spells: str | None = None
    possible_spells: str
    events: List[TownEvent] = []
    alignment: int | None = None


class MapMineAbandonedMine(MapObject):
    object_class: Literal['mine', 'abandoned_mine']
    possible_resources: str | None = None
    owner: str | None = None


class MapCreatureGenerator(MapObject):
    object_class: Literal[
        'creature_generator1', 'creature_generator2', 'creature_generator3', 'creature_generator4'
    ]
    owner: str


class MapShrineOfMagic(MapObject):
    object_class: Literal[
        'shrine_of_magic_incantation', 'shrine_of_magic_gesture', 'shrine_of_magic_thought'
    ]
    spell_id: int


class MapPandoraBox(MapObject):
    object_class: Literal['pandora_box']
    message: str | None = None
    guards: List[Guard] | None = None
    experience: int
    mana_diff: int
    morale_diff: int
    luck_diff: int
    resources: Resources = Resources()
    primary_skills: PrimarySkills = PrimarySkills()
    abilities: List[Ability]
    artifacts: List[int]
    spells: List[int]
    creatures: List[Creature]


class MapGrail(MapObject):
    object_class: Literal['grail']
    radius: int


class MapRandomDwelling(MapObject):
    object_class: Literal['random_dwelling']
    owner: str
    castle_id: int
    castles: Tuple[int, int] | None = None
    min_lvl: int
    max_lvl: int


class MapRandomDwellingLvl(MapObject):
    object_class: Literal['random_dwelling_lvl']
    owner: str
    castle_id: int
    castles: Tuple[int, int] | None = None


class MapRandomDwellingFaction(MapObject):
    object_class: Literal['random_dwelling_faction']
    owner: str
    min_lvl: int
    max_lvl: int


class MapQuestGuard(MapObject):
    object_class: Literal['quest_guard']
    mission_type: str
    level: int
    hero_object_id: int
    monster_object_id: int
    primary_skills: PrimarySkills = PrimarySkills()
    artifacts: List[int] = []
    creatures: List[Creature] = []
    resources: Resources = Resources()
    color: str
    limit: int
    first_visit_text: str
    next_visit_text: str
    completed_text: str


class MapShipyard(MapObject):
    object_class: Literal['shipyard']
    owner: str


class MapHeroPlaceholder(MapObject):
    object_class: Literal['hero_placeholder']
    owner: str
    hero_id: int
    power: int | None = None


class MapLighthouse(MapObject):
    object_class: Literal['lighthouse']
    owner: str


class MapTimedEvent(BaseModel):
    name: str
    message: str
    resources: Resources = Resources()
    players: str
    is_human_affected: bool
    is_computer_affected: bool
    first_occurrence: int
    next_occurrence: int
    unknown: str


AllMapObjectSchemas = Union[
    Annotated[MapEvent, Tag('event')],
    Annotated[MapSign, Tag('sign')],
    Annotated[MapOceanBottle, Tag('ocean_bottle')],
    Annotated[MapHero, Tag('hero')],
    Annotated[MapMonster, Tag('monster')],
    Annotated[MapSeerHut, Tag('seer_hut')],
    Annotated[MapWitchHut, Tag('witch_hut')],
    Annotated[MapScholar, Tag('scholar')],
    Annotated[MapSpellScroll, Tag('spell_scroll')],
    Annotated[MapArtifact, Tag('artifact')],
    Annotated[MapRandomArtifact, Tag('random_artifact')],
    Annotated[MapResource, Tag('resource')],
    Annotated[MapRandomResource, Tag('random_resource')],
    Annotated[MapTown, Tag('town')],
    Annotated[MapMineAbandonedMine, Tag('mine')],
    Annotated[MapMineAbandonedMine, Tag('abandoned_mine')],
    Annotated[MapCreatureGenerator, Tag('creature_generator')],
    Annotated[MapShrineOfMagic, Tag('shrine_of_magic')],
    Annotated[MapPandoraBox, Tag('pandora_box')],
    Annotated[MapGrail, Tag('grail')],
    Annotated[MapRandomDwelling, Tag('random_dwelling')],
    Annotated[MapRandomDwellingLvl, Tag('random_dwelling_lvl')],
    Annotated[MapRandomDwellingFaction, Tag('random_dwelling_faction')],
    Annotated[MapShipyard, Tag('shipyard')],
    Annotated[MapHeroPlaceholder, Tag('hero_place_holder')],
    Annotated[MapLighthouse, Tag('lighthouse')],
    Annotated[MapObject, Tag('general_map_object')],
]


def map_object_discriminator(value) -> str:
    object_class = value.get('object_class')
    if object_class in (
        'event',
        'sign',
        'ocean_bottle',
        'hero',
        'monster',
        'seer_hut',
        'witch_hut',
        'scholar',
        'spell_scroll',
        'artifact',
        'random_artifact',
        'resource',
        'random_resource',
        'town',
        'mine',
        'abandoned_mine',
        'creature_generator',
        'shrine_of_magic',
        'pandora_box',
        'grail',
        'random_dwelling',
        'random_dwelling_lvl',
        'random_dwelling_faction',
        'shipyard',
        'hero_place_holder',
        'lighthouse',
        'general_map_object',
    ):
        return object_class
    return 'general_map_object'


# Main Structure Schema
class GameMapStructure(BaseModel):
    header: Header
    players_attributes: List[PlayerAttributes] = []
    victory: Victory
    loss: Loss
    teams: Teams
    allowed_heroes_info: str
    placeholder_heroes: List[int] = []
    configured_heroes: List[ConfiguredHero] = []
    artifacts: Optional[str] = None
    allowed_spells_bytes: Optional[str] = None
    allowed_hero_abilities_bytes: Optional[str] = None
    rumors_quantity: int
    rumors: List[Rumor] = []
    predefined_heroes: Dict[int, PredefinedHero | PredefinedHeroNonConfigured] = {}
    terrain: Terrain
    def_objects: List[DefFile] = Field(alias='def', default=[])
    objects: list[
        Annotated[AllMapObjectSchemas, Field(discriminator=Discriminator(map_object_discriminator))]
    ] = []
    events: List[MapTimedEvent] = []

    class Config:
        validate_by_name = True

    def __str__(self):
        return f'HMM3 map structure for "{self.header.map_name}"'

    __repr__ = __str__
