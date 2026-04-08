"""
This is some kind of port to Python from VCMI (high praise for the project!)
https://github.com/vcmi/vcmi/blob/develop/lib/mapping/MapFormatH3M.cpp
"""

import base64
import collections
import gzip
import logging
import pathlib
from functools import cached_property

from map_processors.encoding import detect_map_encoding
from map_processors.enums import ColorEnum, MapType, ObjectType, QuestType, ResourceType, RewardType
from map_processors.exceptions import H3MapParserException
from map_processors.schemas import GameMapStructure

logger = logging.getLogger(__name__)


class MapParser:
    def __init__(
        self,
        filename: str | pathlib.Path,
        encoding: str | None = None,
        fallback_encoding: str | None = 'cp1251',
        *args,
        **kwargs,
    ) -> None:
        self.filename = filename
        self._cursor_position = 0
        self.data = collections.OrderedDict()
        self.map_type = None
        self.encoding = encoding
        self.fallback_encoding = fallback_encoding
        self.exception_count = 0

    @staticmethod
    def bytes_to_int(input_bytes: bytes) -> int:
        return int.from_bytes(input_bytes, byteorder='little')

    @staticmethod
    def bytes_to_int_signed(input_bytes: bytes) -> int:
        return int.from_bytes(input_bytes, byteorder='little', signed=True)

    def process_uint8(self) -> int:
        value = self.map_binary[self._cursor_position]
        self._cursor_position += 1
        return value

    def process_uint16(self) -> int:
        value = self.bytes_to_int(
            self.map_binary[self._cursor_position : self._cursor_position + 2],
        )
        self._cursor_position += 2
        return value

    def process_uint32(self) -> int:
        value = self.bytes_to_int(
            self.map_binary[self._cursor_position : self._cursor_position + 4],
        )
        self._cursor_position += 4
        return value

    def process_int8(self) -> int:
        unsigned = self.process_uint8()
        if unsigned >= 128:
            return unsigned - 256

        return unsigned

    def process_int16(self) -> int:
        value = self.bytes_to_int_signed(
            self.map_binary[self._cursor_position : self._cursor_position + 2],
        )
        self._cursor_position += 2
        return value

    def process_int32(self) -> int:
        value = self.bytes_to_int_signed(
            self.map_binary[self._cursor_position : self._cursor_position + 4],
        )
        self._cursor_position += 4
        return value

    def skip_n_bytes(self, n: int, quiet: bool = True) -> None:
        skipped = self.map_binary[self._cursor_position : self._cursor_position + n]
        if any(skipped) and not quiet:
            logger.warning(
                'Non-empty bytes skipped at offset %s: %s', self._cursor_position, skipped.hex(' ')
            )
        self._cursor_position += n

    def process_n_bytes(self, n: int) -> bytes:
        result = self.map_binary[self._cursor_position : self._cursor_position + n]
        self._cursor_position += n
        return result

    def process_n_bytes_to_mask(self, n: int) -> str:
        result = self.map_binary[self._cursor_position : self._cursor_position + n]
        self._cursor_position += n
        bits_quantity = n * 8
        return f'{int(result.hex(), base=16):0{bits_quantity}b}'

    def process_n_bytes_to_base64(self, n: int) -> str:
        result = self.map_binary[self._cursor_position : self._cursor_position + n]
        self._cursor_position += n
        return base64.b64encode(result).decode()

    def base_process_string(self) -> str:
        string_len = self.process_uint32()
        string_end = self._cursor_position + string_len
        try:
            string_from_map = self.map_binary[self._cursor_position : string_end].decode(
                self.encoding
            )
        except Exception:
            string_from_map = '<cut>'
            if self.exception_count >= 3:
                raise
            self.exception_count += 1

        self._cursor_position = string_end
        return string_from_map

    def process_string_to_bytes(self) -> bytes:
        string_len = self.process_uint32()
        string_end = self._cursor_position + string_len
        string_from_map = self.map_binary[self._cursor_position : string_end]
        self._cursor_position = string_end
        return string_from_map

    def process_string(self) -> str:
        return self.base_process_string()

    def process_def_string(self) -> str:
        return self.base_process_string()

    def process_coordinates(self) -> tuple:
        pos_x = self.process_uint8()
        pos_y = self.process_uint8()
        pos_z = self.process_uint8()
        return pos_x, pos_y, pos_z

    @cached_property
    def map_binary(self):
        with gzip.open(self.filename, 'rb') as f:
            return f.read()

    def reset_cursor_position(self):
        self._cursor_position = 0

    def detect_encoding_by_header(self):
        map_type = self.process_uint32()
        if map_type not in MapType:
            raise H3MapParserException('Unknown map type')

        self.skip_n_bytes(6)

        map_name = self.process_string_to_bytes()
        map_description = self.process_string_to_bytes()
        map_description = map_description.replace(
            b'This map is taken from the catalogue www.heroesportal.net', b''
        ).replace(b' ', b'')

        self.encoding = detect_map_encoding(
            map_name, map_description, fallback_encoding=self.fallback_encoding
        )

        self.reset_cursor_position()

    def read_header(self):
        self.data['header'] = {}

        self.data['header']['map_type'] = self.process_uint32()
        if self.data['header']['map_type'] == MapType.ROE.value:
            self.map_type = MapType.ROE
        elif self.data['header']['map_type'] == MapType.AB.value:
            self.map_type = MapType.AB
        elif self.data['header']['map_type'] == MapType.SOD.value:
            self.map_type = MapType.SOD
        else:
            raise H3MapParserException('Unknown map type')

        self.data['header']['are_any_players'] = bool(self.process_uint8())
        self.data['header']['height'] = self.data['header']['width'] = self.process_uint32()
        self.data['header']['has_underground'] = bool(self.process_uint8())

        self.data['header']['map_name'] = self.process_string()
        self.data['header']['map_description'] = self.process_string()
        self.data['header']['map_difficulty'] = self.process_uint8()

        self.data['header']['hero_level_limit'] = None
        if self.map_type != MapType.ROE:
            self.data['header']['hero_level_limit'] = self.process_uint8()

    def map_stats(self) -> dict:
        difficulty_names = {0: 'Easy', 1: 'Normal', 2: 'Hard', 3: 'Expert', 4: 'Impossible'}

        if 'header' not in self.data:
            self.data = collections.OrderedDict()
            self.read_header()
        header = self.data['header']

        size = header['width']
        return {
            'map_name': header['map_name'],
            'map_description': header['map_description'],
            'encoding': self.encoding,
            'map_type': MapType(header['map_type']).name,
            'size': f'{size}x{size}',
            'has_underground': header['has_underground'],
            'difficulty': difficulty_names.get(header['map_difficulty'], header['map_difficulty']),
        }

    def read_players_attributes(self):
        self.data['players_attributes'] = []

        for player_color in ('red', 'blue', 'brown', 'green', 'orange', 'purple', 'teal', 'pink'):
            player_info = {}
            player_info['can_human_play'] = bool(self.process_uint8())
            player_info['can_computer_play'] = bool(self.process_uint8())
            if not player_info['can_human_play'] and not player_info['can_computer_play']:
                if self.map_type >= MapType.SOD:
                    self.skip_n_bytes(13)
                elif self.map_type == MapType.AB:
                    self.skip_n_bytes(12)
                elif self.map_type == MapType.ROE:
                    self.skip_n_bytes(6)
                self.data['players_attributes'].append(player_info)
                continue

            player_info['computer_playstyle'] = self.process_uint8()
            if self.map_type >= MapType.SOD:
                player_info['are_factions_configured'] = self.process_uint8()
            if self.map_type == MapType.ROE:
                player_info['allowed_factions'] = self.process_uint8()
            else:
                player_info['allowed_factions'] = self.process_uint16()

            player_info['is_faction_random'] = bool(self.process_uint8())
            has_main_town = bool(self.process_uint8())
            player_info['generate_hero_at_main_town'] = None
            player_info['generate_hero'] = None
            player_info['town_coordinates'] = None
            if has_main_town:
                if self.map_type != MapType.ROE:
                    player_info['generate_hero_at_main_town'] = self.process_uint8()
                    player_info['generate_hero'] = self.process_uint8()
                else:
                    player_info['generate_hero_at_main_town'] = 1
                    player_info['generate_hero'] = 0
                player_info['town_coordinates'] = self.process_coordinates()

            player_info['has_random_hero'] = self.process_uint8()
            player_info['main_custom_hero_id'] = self.process_uint8()
            if player_info['main_custom_hero_id'] != 0xFF:
                player_info['main_custom_hero_portrait'] = self.process_uint8()
                player_info['main_custom_hero_name'] = self.process_string()

            if self.map_type != MapType.ROE:
                self.skip_n_bytes(1)  # unknown byte
                player_info['hero_count'] = self.process_uint8()
                self.skip_n_bytes(3)
                player_info['heroes'] = []
                for _ in range(player_info['hero_count']):
                    player_info['heroes'].append(
                        {
                            'hero_id': self.process_uint8(),
                            'hero_name': self.process_string(),
                        }
                    )

            self.data['players_attributes'].append(player_info)

    def read_victory_conditions(self):
        self.data['victory'] = {}

        self.data['victory']['special_victory_condition'] = self.process_uint8()
        if self.data['victory']['special_victory_condition'] == 0xFF:
            pass
        else:
            self.data['victory']['standard_win_available'] = self.process_uint8()
            self.data['victory']['applies_to_computer'] = self.process_uint8()
            if self.data['victory']['special_victory_condition'] == 0:
                self.data['victory']['acquire_artifact_code'] = self.process_uint8()
                if self.map_type != MapType.ROE:
                    self.skip_n_bytes(1)
            elif self.data['victory']['special_victory_condition'] == 1:
                self.data['victory']['unit_code'] = self.process_uint8()
                if self.map_type != MapType.ROE:
                    self.skip_n_bytes(1)
                self.data['victory']['unit_quantity'] = self.process_uint32()
            elif self.data['victory']['special_victory_condition'] == 2:
                self.data['victory']['resource_code'] = self.process_uint8()
                self.data['victory']['resource_quantity'] = self.process_uint32()
            elif self.data['victory']['special_victory_condition'] == 3:
                self.data['victory']['upgrade_town_coordinates'] = self.process_coordinates()
                self.data['victory']['hall_level'] = self.process_uint8()
                self.data['victory']['castle_level'] = self.process_uint8()
            elif self.data['victory']['special_victory_condition'] == 4:
                self.data['victory']['build_grail_town_coordinates'] = self.process_coordinates()
            elif self.data['victory']['special_victory_condition'] == 5:
                self.data['victory']['hero_coordinates'] = self.process_coordinates()
            elif self.data['victory']['special_victory_condition'] == 6:
                self.data['victory']['capture_town_coordinates'] = self.process_coordinates()
            elif self.data['victory']['special_victory_condition'] == 7:
                self.data['victory']['creature_coordinates'] = self.process_coordinates()
            elif self.data['victory']['special_victory_condition'] in (8, 9):
                pass
            elif self.data['victory']['special_victory_condition'] == 10:
                self.data['victory']['bring_artifact_code'] = self.process_uint8()
                self.data['victory']['bring_artifact_town_coordinates'] = self.process_coordinates()
            else:
                raise H3MapParserException('Unknown victory type')

    def read_loss_conditions(self):
        self.data['loss'] = {}

        self.data['loss']['special_loss_condition'] = self.process_uint8()
        if self.data['loss']['special_loss_condition'] == 0:
            self.data['loss']['loss_town_coordinates'] = self.process_coordinates()
        elif self.data['loss']['special_loss_condition'] == 1:
            self.data['loss']['loss_hero_coordinates'] = self.process_coordinates()
        elif self.data['loss']['special_loss_condition'] == 2:
            self.data['loss']['time_expires_in_days'] = self.process_uint16()
        elif self.data['loss']['special_loss_condition'] == 0xFF:
            pass
        else:
            raise H3MapParserException('Unknown loss type')

    def read_teams(self):
        self.data['teams'] = {}

        self.data['teams']['quantity'] = self.process_uint8()
        if self.data['teams']['quantity']:
            self.data['teams']['red_team_number'] = self.process_uint8()
            self.data['teams']['blue_team_number'] = self.process_uint8()
            self.data['teams']['brown_team_number'] = self.process_uint8()
            self.data['teams']['green_team_number'] = self.process_uint8()
            self.data['teams']['orange_team_number'] = self.process_uint8()
            self.data['teams']['purple_team_number'] = self.process_uint8()
            self.data['teams']['teal_team_number'] = self.process_uint8()
            self.data['teams']['pink_team_number'] = self.process_uint8()

    def read_heroes_info(self) -> None:
        if self.map_type == MapType.ROE:
            self.data['allowed_heroes_info'] = self.process_n_bytes_to_mask(16)
        else:
            self.data['allowed_heroes_info'] = self.process_n_bytes_to_mask(20)

        if self.map_type >= MapType.AB:
            placeholder_quantity = self.process_uint32()
            self.data['placeholder_heroes'] = [
                self.process_uint8() for _ in range(placeholder_quantity)
            ]

        if self.map_type >= MapType.SOD:
            configured_quantity = self.process_uint8()
            self.data['configured_heroes'] = []
            for _ in range(configured_quantity):
                self.data['configured_heroes'].append(
                    {
                        'id': self.process_uint8(),
                        'portrait': self.process_uint8(),
                        'name': self.process_string(),
                        'players_access': self.process_uint8(),
                    }
                )

        self.skip_n_bytes(31)  # unknown bytes

    def read_artifacts(self):
        if self.map_type == MapType.AB:
            self.data['artifacts'] = self.process_n_bytes_to_mask(17)
        elif self.map_type >= MapType.SOD:
            self.data['artifacts'] = self.process_n_bytes_to_mask(18)

    def read_spells(self):
        if self.map_type >= MapType.SOD:
            self.data['allowed_spells_bytes'] = self.process_n_bytes_to_mask(9)

    def read_abilities(self):
        if self.map_type >= MapType.SOD:
            self.data['allowed_hero_abilities_bytes'] = self.process_n_bytes_to_mask(4)

    def read_rumors(self):
        self.data['rumors'] = []
        rumors_quantity = self.process_uint32()
        for _ in range(rumors_quantity):
            rumor_name = self.process_string()
            rumor_text = self.process_string()
            self.data['rumors'].append(
                {
                    'name': rumor_name,
                    'text': rumor_text,
                }
            )

    def read_predefined_heroes(self):
        if self.map_type <= MapType.AB:
            return

        self.data['predefined_heroes'] = dict()
        for hero_id in range(156):
            self.data['predefined_heroes'][hero_id] = hero = dict()
            is_hero_configured = self.process_uint8()
            if not is_hero_configured:
                continue

            if self.process_uint8():
                hero['experience'] = self.process_uint32()
            if self.process_uint8():
                abilities_count = self.process_uint32()
                hero['abilities'] = []
                for _ in range(abilities_count):
                    hero['abilities'].append(
                        {
                            'id': self.process_uint8(),
                            'level': self.process_uint8(),
                        }
                    )
            self.load_hero_artifacts(hero)

            if self.process_uint8():
                hero['biography'] = self.process_string()

            hero['sex'] = self.process_uint8()

            if self.process_uint8():
                hero['spells'] = self.process_n_bytes_to_mask(9)

            if self.process_uint8():
                hero['primary_skills'] = {
                    'attack': self.process_uint8(),
                    'defence': self.process_uint8(),
                    'power': self.process_uint8(),
                    'knowledge': self.process_uint8(),
                }

    def load_hero_artifacts(self, to_hero: dict):
        if not self.process_uint8():
            return

        to_hero['artifacts'] = dict()
        slot_number = 0
        for slot_number in range(16):
            self.load_artifact_to_slot(to_hero, slot_number)

        if self.map_type >= MapType.SOD:
            # catapult
            self.load_artifact_to_slot(to_hero, slot_number)
            slot_number += 1

        # spellbook
        self.load_artifact_to_slot(to_hero, slot_number)
        slot_number += 1

        # misc 5
        self.load_artifact_to_slot(to_hero, slot_number)
        slot_number += 1

        backpack_start = 19
        backpack_quantity = self.process_uint16()
        for slot_number in range(backpack_start, backpack_start + backpack_quantity):
            self.load_artifact_to_slot(to_hero, slot_number)

    def load_artifact_to_slot(self, to_hero: dict, slot: int):
        if self.map_type == MapType.ROE:
            artifact_default = 0xFF
            artifact_id = self.process_uint8()
        else:
            artifact_default = 0xFFFF
            artifact_id = self.process_uint16()

        if artifact_id == artifact_default:
            return

        to_hero['artifacts'][slot] = artifact_id

    def read_terrain(self):
        self.data['terrain'] = {
            'surface': [],
            'underground': [],
        }
        for level in ('surface', 'underground'):
            if level == 'underground' and not self.data['header']['has_underground']:
                break
            for x in range(self.data['header']['width']):
                for y in range(self.data['header']['height']):
                    self.data['terrain'][level].append(
                        {
                            'terrain_type': self.process_uint8(),
                            'view': self.process_uint8(),
                            'river_type': self.process_uint8(),
                            'river_flow': self.process_uint8(),
                            'road_type': self.process_uint8(),
                            'road_flow': self.process_uint8(),
                            'flip_bits': self.process_uint8(),
                        }
                    )

    def read_def_info(self):
        self.data['def'] = []
        def_quantity = self.process_uint32()
        for def_obj_number in range(def_quantity):
            self.data['def'].append(
                {
                    'sprite_filename': self.process_def_string(),
                    'unpassable_tiles': self.process_n_bytes_to_mask(6),
                    'active_tiles': self.process_n_bytes_to_mask(6),
                    'allowed_terrain': self.process_uint16(),
                    'terrain_group': self.process_uint16(),
                    'object_class': self.process_uint32(),  # id
                    'object_number': self.process_uint32(),  # sub_id
                    'object_group': self.process_uint8(),
                    'z_index': self.process_uint8(),
                    'unknown_base64': self.process_n_bytes_to_base64(16),
                }
            )

    def read_creature_set(self, quantity) -> list:
        max_id = 0xFF if self.map_type == MapType.ROE else 0xFFFF
        creatures = []
        for _ in range(quantity):
            if self.map_type >= MapType.AB:
                creature_id = self.process_uint16()
            else:
                creature_id = self.process_uint8()
            creatures_quantity = self.process_uint16()
            if creature_id == max_id:
                continue
            creatures.append(
                {
                    'id': creature_id,
                    'quantity': creatures_quantity,
                }
            )

        return creatures

    def read_message_and_guards(self) -> tuple:
        has_message = self.process_uint8()
        message = None
        guards = None
        if has_message:
            message = self.process_string()

            has_guards = self.process_uint8()
            if has_guards:
                guards = self.read_creature_set(7)
            self.skip_n_bytes(4)

        return message, guards

    def read_resources(self) -> dict[str, int]:
        return {
            'wood': self.process_int32(),
            'mercury': self.process_int32(),
            'ore': self.process_int32(),
            'sulfur': self.process_int32(),
            'crystal': self.process_int32(),
            'gems': self.process_int32(),
            'gold': self.process_int32(),
        }

    def read_hero(self):
        hero = dict()

        if self.map_type >= MapType.AB:
            hero['id'] = self.process_uint32()
        hero['owner'] = self.process_uint8()
        hero['hero_sub_id'] = self.process_uint8()

        has_name = self.process_uint8()
        if has_name:
            hero['name'] = self.process_string()

        if self.map_type >= MapType.SOD:
            has_exp = self.process_uint8()
            if has_exp:
                hero['experience'] = self.process_uint32()
        else:
            hero['experience'] = self.process_uint32()

        has_portrait = self.process_uint8()
        if has_portrait:
            hero['portrait'] = self.process_uint8()

        has_abilities = self.process_uint8()
        if has_abilities:
            abilities_quantity = self.process_uint32()
            hero['abilities'] = [
                {
                    'id': self.process_uint8(),
                    'level': self.process_uint8(),
                }
                for _ in range(abilities_quantity)
            ]

        has_creatures = self.process_uint8()
        if has_creatures:
            hero['creatures'] = self.read_creature_set(7)

        hero['formation'] = self.process_uint8()

        self.load_hero_artifacts(hero)

        hero['patrol_radius'] = self.process_uint8()

        if self.map_type >= MapType.AB:
            has_biography = self.process_uint8()
            if has_biography:
                hero['biography'] = self.process_string()
            hero['sex'] = self.process_uint8()

        if self.map_type >= MapType.SOD:
            has_custom_spells = self.process_uint8()
            if has_custom_spells:
                hero['custom_spells'] = self.process_n_bytes_to_mask(9)
        elif self.map_type == MapType.AB:
            hero['custom_spells'] = self.process_n_bytes_to_mask(8)

        if self.map_type >= MapType.SOD:
            has_custom_primary_skills = self.process_uint8()
            if has_custom_primary_skills:
                hero['custom_primary_skills'] = {
                    'attack': self.process_uint8(),
                    'defence': self.process_uint8(),
                    'power': self.process_uint8(),
                    'knowledge': self.process_uint8(),
                }

        self.skip_n_bytes(16)

        return hero

    def read_quest(self) -> dict:
        quest = dict()
        mission_type = QuestType(self.process_uint8())
        if mission_type == QuestType.EMPTY:
            pass
        elif mission_type == QuestType.ACHIEVE_LEVEL:
            quest['level'] = self.process_uint32()
        elif mission_type == QuestType.DEFEAT_HERO:
            quest['hero_object_id'] = self.process_uint32()
        elif mission_type == QuestType.DEFEAT_MONSTER:
            quest['monster_object_id'] = self.process_uint32()
        elif mission_type == QuestType.ACHIEVE_PRIMARY_SKILL_LEVEL:
            quest['primary_skills'] = {
                'attack': self.process_uint8(),
                'defence': self.process_uint8(),
                'power': self.process_uint8(),
                'knowledge': self.process_uint8(),
            }
        elif mission_type == QuestType.BRING_ARTEFACT:
            artifact_quantity = self.process_uint8()
            quest['artifacts'] = [self.process_uint16() for _ in range(artifact_quantity)]
        elif mission_type == QuestType.BRING_CREATURES:
            creatures_types = self.process_uint8()
            quest['creatures'] = [
                {'id': self.process_uint16(), 'quantity': self.process_uint16()}
                for _ in range(creatures_types)
            ]
        elif mission_type == QuestType.BRING_RESOURCES:
            quest['resources'] = self.read_resources()
        elif mission_type == QuestType.BE_SPECIFIC_HERO:
            quest['hero_object_id'] = self.process_uint8()
        elif mission_type == QuestType.BE_SPECIFIC_COLOR:
            quest['color'] = ColorEnum(self.process_uint8()).name.lower()

        if mission_type != QuestType.EMPTY:
            quest['limit'] = self.process_uint32()

            quest['first_visit_text'] = self.process_string()
            quest['next_visit_text'] = self.process_string()
            quest['completed_text'] = self.process_string()

        quest['mission_type'] = mission_type.name.lower()

        return quest

    def read_town(self) -> dict:
        town = dict()
        if self.map_type >= MapType.AB:
            town['id'] = self.process_uint32()
        town['owner'] = ColorEnum(self.process_uint8()).name.lower()
        if self.process_uint8():
            town['name'] = self.process_string()
        if self.process_uint8():
            town['garrison'] = self.read_creature_set(7)
        town['formation'] = self.process_uint8()

        has_custom_buildings = self.process_uint8()
        if has_custom_buildings:
            town['built_buildings'] = self.process_n_bytes_to_mask(6)
            town['forbidden_buildings'] = self.process_n_bytes_to_mask(6)
        else:
            town['has_fort'] = bool(self.process_uint8())

        if self.map_type >= MapType.AB:
            town['obligatory_spells'] = self.process_n_bytes_to_mask(9)
        town['possible_spells'] = self.process_n_bytes_to_mask(9)

        events_quantity = self.process_uint32()
        town['events'] = []
        for _ in range(events_quantity):
            town['events'].append(
                {
                    'name': self.process_string(),
                    'message': self.process_string(),
                    'resources': self.read_resources(),
                    'players': self.process_n_bytes_to_mask(1),
                    'is_human_affected': bool(self.process_uint8())
                    if self.map_type >= MapType.SOD
                    else True,
                    'is_computer_affected': bool(self.process_uint8()),
                    'first_occurrence': self.process_uint16(),
                    'next_occurrence': self.process_uint8(),
                    'unknown': self.process_n_bytes_to_base64(17),
                    'new_buildings': self.process_n_bytes_to_mask(6),
                    'new_creatures_quantities': [self.process_uint16() for _ in range(7)],
                    'unknown2': self.process_n_bytes_to_base64(4),
                }
            )
        if self.map_type >= MapType.SOD:
            town['alignment'] = self.process_uint8()
        self.skip_n_bytes(3)

        return town

    def read_objects(self):
        self.data['objects'] = []
        objects_quantity = self.process_uint32()
        for _ in range(objects_quantity):
            object_coordinates = self.process_coordinates()
            object_number = self.process_uint32()
            self.skip_n_bytes(5)  # unknown
            object_class = self.data['def'][object_number]['object_class']
            object_subclass = self.data['def'][object_number]['object_number']
            map_object = {}
            if object_class == ObjectType.EVENT.value:
                message, guards = self.read_message_and_guards()
                experience = self.process_uint32()
                mana_diff = self.process_int32()
                morale = self.process_int8()
                luck = self.process_int8()
                resources = self.read_resources()
                primary_skills = {
                    'attack': self.process_uint8(),
                    'defence': self.process_uint8(),
                    'power': self.process_uint8(),
                    'knowledge': self.process_uint8(),
                }
                abilities_quantity = self.process_uint8()
                abilities = [
                    {
                        'id': self.process_uint8(),
                        'level': self.process_uint8(),
                    }
                    for _ in range(abilities_quantity)
                ]
                artifacts_quantity = self.process_uint8()
                if self.map_type == MapType.ROE:
                    artifacts = [self.process_uint8() for _ in range(artifacts_quantity)]
                else:
                    artifacts = [self.process_uint16() for _ in range(artifacts_quantity)]
                spells_quantity = self.process_uint8()
                spells = [self.process_uint8() for _ in range(spells_quantity)]
                creatures_quantity = self.process_uint8()
                creatures = self.read_creature_set(creatures_quantity)

                self.skip_n_bytes(8)

                available_for_color = self.process_n_bytes_to_mask(1)
                can_computer_activate = bool(self.process_uint8())
                remove_after_visit = bool(self.process_uint8())

                self.skip_n_bytes(4)
                map_object = {
                    'message': message,
                    'guards': guards,
                    'experience': experience,
                    'mana_diff': mana_diff,
                    'morale': morale,
                    'luck': luck,
                    'resources': resources,
                    'primary_skills': primary_skills,
                    'abilities': abilities,
                    'artifacts': artifacts,
                    'spells': spells,
                    'creatures': creatures,
                    'available_for_color': available_for_color,
                    'can_computer_activate': can_computer_activate,
                    'remove_after_visit': remove_after_visit,
                }

            elif object_class in (ObjectType.SIGN.value, ObjectType.OCEAN_BOTTLE.value):
                map_object = {'message': self.process_string()}
                self.skip_n_bytes(4)

            elif object_class in (
                ObjectType.HERO.value,
                ObjectType.RANDOM_HERO.value,
                ObjectType.PRISON.value,
            ):
                map_object = self.read_hero()
            elif object_class in (
                ObjectType.MONSTER.value,
                ObjectType.RANDOM_MONSTER.value,
                ObjectType.RANDOM_MONSTER_L1.value,
                ObjectType.RANDOM_MONSTER_L2.value,
                ObjectType.RANDOM_MONSTER_L3.value,
                ObjectType.RANDOM_MONSTER_L4.value,
                ObjectType.RANDOM_MONSTER_L5.value,
                ObjectType.RANDOM_MONSTER_L6.value,
                ObjectType.RANDOM_MONSTER_L7.value,
            ):
                monster = dict()

                if self.map_type >= MapType.AB:
                    monster['id'] = self.process_uint32()

                monster['quantity'] = self.process_uint16()

                monster['character'] = self.process_uint8()

                has_message = self.process_uint8()
                if has_message:
                    monster['message'] = self.process_string()
                    monster['resources'] = self.read_resources()

                    if self.map_type == MapType.ROE:
                        monster['artifact_id'] = self.process_uint8()
                    else:
                        monster['artifact_id'] = self.process_uint16()

                monster['mood'] = self.process_uint8()
                monster['not_growing'] = bool(self.process_uint8())
                map_object = monster

                self.skip_n_bytes(2)

            elif object_class == ObjectType.SEER_HUT.value:
                quest = dict()
                if self.map_type >= MapType.AB:
                    quest = self.read_quest()
                else:
                    quest['mission_type'] = QuestType(5).name.lower()
                    quest['artifacts'] = [self.process_uint8()]

                if quest['mission_type']:
                    reward: dict = {'type': RewardType(self.process_uint8())}
                    if reward['type'] == RewardType.EXPERIENCE:
                        reward['experience'] = self.process_uint32()
                    elif reward['type'] == RewardType.MANA_POINTS:
                        reward['mana_points'] = self.process_uint32()
                    elif reward['type'] == RewardType.MORALE_BONUS:
                        reward['morale'] = self.process_int8()
                    elif reward['type'] == RewardType.LUCK_BONUS:
                        reward['luck'] = self.process_int8()
                    elif reward['type'] == RewardType.RESOURCES:
                        reward['resource_type'] = ResourceType(self.process_uint8()).name.lower()
                        reward['resource_quantity'] = self.process_uint32()
                    elif reward['type'] == RewardType.PRIMARY_SKILL:
                        reward['skill_id'] = self.process_uint8()
                        reward['skill_increase'] = self.process_uint8()
                    elif reward['type'] == RewardType.ABILITY:
                        reward['ability_id'] = self.process_uint8()
                        reward['ability_increase'] = self.process_uint8()
                    elif reward['type'] == RewardType.ARTIFACT:
                        if self.map_type == MapType.ROE:
                            reward['artifact_id'] = self.process_uint8()
                        else:
                            reward['artifact_id'] = self.process_uint16()
                    elif reward['type'] == RewardType.SPELL:
                        reward['spell_id'] = self.process_uint8()
                    elif reward['type'] == RewardType.CREATURE:
                        if self.map_type == MapType.ROE:
                            reward['creature_id'] = self.process_uint8()
                            reward['creature_quantity'] = self.process_uint16()
                        else:
                            reward['creature_id'] = self.process_uint16()
                            reward['creature_quantity'] = self.process_uint16()
                    reward['type'] = reward['type'].name.lower()
                    quest['reward'] = reward

                    self.skip_n_bytes(2)

                else:
                    self.skip_n_bytes(3)
                map_object = quest

            elif object_class == ObjectType.WITCH_HUT.value:
                if self.map_type >= MapType.AB:
                    map_object['ability_bits'] = f'{self.process_uint32():032b}'

            elif object_class == ObjectType.SCHOLAR.value:
                map_object['bonus_type'] = self.process_uint8()
                map_object['bonus_id'] = self.process_uint8()
                self.skip_n_bytes(6)

            elif object_class in (
                ObjectType.GARRISON_HORIZONTAL.value,
                ObjectType.GARRISON_VERTICAL.value,
            ):
                map_object['owner'] = ColorEnum(self.process_uint8()).name.lower()
                self.skip_n_bytes(3)
                map_object['creatures'] = self.read_creature_set(7)
                if self.map_type >= MapType.AB:
                    map_object['is_removable'] = self.process_uint8()
                else:
                    map_object['is_removable'] = 1
                self.skip_n_bytes(8)

            elif object_class == ObjectType.SPELL_SCROLL.value:
                map_object['message'], map_object['guards'] = self.read_message_and_guards()
                map_object['spell_id'] = self.process_uint32()

            elif object_class == ObjectType.ARTIFACT.value:
                map_object['message'], map_object['guards'] = self.read_message_and_guards()
                map_object['artifact_id'] = self.data['def'][object_number]['object_number']

            elif object_class in (
                ObjectType.RANDOM_ART.value,
                ObjectType.RANDOM_TREASURE_ART.value,
                ObjectType.RANDOM_MINOR_ART.value,
                ObjectType.RANDOM_MAJOR_ART.value,
                ObjectType.RANDOM_RELIC_ART.value,
            ):
                map_object['message'], map_object['guards'] = self.read_message_and_guards()
                if object_class == ObjectType.RANDOM_TREASURE_ART.value:
                    map_object['level'] = '1'
                if object_class == ObjectType.RANDOM_MINOR_ART.value:
                    map_object['level'] = '2'
                if object_class == ObjectType.RANDOM_MAJOR_ART.value:
                    map_object['level'] = '3'
                if object_class == ObjectType.RANDOM_RELIC_ART.value:
                    map_object['level'] = '4'
                if object_class == ObjectType.RANDOM_ART.value:
                    map_object['level'] = 'any'

            elif object_class in (ObjectType.RESOURCE.value, ObjectType.RANDOM_RESOURCE.value):
                map_object['message'], map_object['guards'] = self.read_message_and_guards()
                map_object['quantity'] = self.process_uint32()
                if object_class == ObjectType.RESOURCE.value:
                    map_object['resource_type'] = ResourceType(object_subclass).name.lower()
                self.skip_n_bytes(4)

            elif object_class in (ObjectType.TOWN.value, ObjectType.RANDOM_TOWN.value):
                map_object = self.read_town()

            elif object_class == ObjectType.ABANDONED_MINE.value or (
                object_class == ObjectType.MINE.value and object_subclass == 7
            ):
                map_object['possible_resources'] = self.process_n_bytes_to_mask(1)
                self.skip_n_bytes(3)

            elif object_class == ObjectType.MINE.value:
                map_object['owner'] = ColorEnum(self.process_uint8()).name.lower()
                self.skip_n_bytes(3)

            elif object_class in (
                ObjectType.CREATURE_GENERATOR1.value,
                ObjectType.CREATURE_GENERATOR2.value,
                ObjectType.CREATURE_GENERATOR3.value,
                ObjectType.CREATURE_GENERATOR4.value,
            ):
                map_object['owner'] = ColorEnum(self.process_uint8()).name.lower()
                self.skip_n_bytes(3)

            elif object_class in (
                ObjectType.SHRINE_OF_MAGIC_INCANTATION.value,
                ObjectType.SHRINE_OF_MAGIC_GESTURE.value,
                ObjectType.SHRINE_OF_MAGIC_THOUGHT.value,
            ):
                map_object['spell_id'] = self.process_uint8()
                self.skip_n_bytes(3)

            elif object_class == ObjectType.PANDORA_BOX.value:
                map_object['message'], map_object['guards'] = self.read_message_and_guards()
                map_object['experience'] = self.process_uint32()
                map_object['mana_diff'] = self.process_int32()
                map_object['morale_diff'] = self.process_int8()
                map_object['luck_diff'] = self.process_int8()
                map_object['resources'] = self.read_resources()
                map_object['primary_skills'] = {
                    'attack': self.process_uint8(),
                    'defence': self.process_uint8(),
                    'power': self.process_uint8(),
                    'knowledge': self.process_uint8(),
                }
                abilities_quantity = self.process_uint8()
                map_object['abilities'] = [
                    {
                        'id': self.process_uint8(),
                        'level': self.process_uint8(),
                    }
                    for _ in range(abilities_quantity)
                ]
                artifacts_quantity = self.process_uint8()
                if self.map_type == MapType.ROE:
                    map_object['artifacts'] = [
                        self.process_uint8() for _ in range(artifacts_quantity)
                    ]
                else:
                    map_object['artifacts'] = [
                        self.process_uint16() for _ in range(artifacts_quantity)
                    ]
                spells_quantity = self.process_uint8()
                map_object['spells'] = [self.process_uint8() for _ in range(spells_quantity)]
                creatures_quantity = self.process_uint8()
                map_object['creatures'] = self.read_creature_set(creatures_quantity)
                self.skip_n_bytes(8)

            elif object_class == ObjectType.GRAIL.value:
                map_object['radius'] = self.process_uint32()

            elif object_class == ObjectType.RANDOM_DWELLING.value:
                map_object['owner'] = ColorEnum(self.process_uint32()).name.lower()
                map_object['castle_id'] = self.process_uint32()
                if not map_object['castle_id']:
                    map_object['castles'] = (self.process_uint8(), self.process_uint8())
                map_object['min_lvl'] = self.process_uint8()
                map_object['max_lvl'] = self.process_uint8()

            elif object_class == ObjectType.RANDOM_DWELLING_LVL.value:
                map_object['owner'] = ColorEnum(self.process_uint32()).name.lower()
                map_object['castle_id'] = self.process_uint32()
                if not map_object['castle_id']:
                    map_object['castles'] = (self.process_uint8(), self.process_uint8())

            elif object_class == ObjectType.RANDOM_DWELLING_FACTION.value:
                map_object['owner'] = ColorEnum(self.process_uint32()).name.lower()
                map_object['min_lvl'] = self.process_uint8()
                map_object['max_lvl'] = self.process_uint8()

            elif object_class == ObjectType.QUEST_GUARD.value:
                map_object = self.read_quest()

            elif object_class == ObjectType.SHIPYARD.value:
                map_object['owner'] = ColorEnum(self.process_uint32()).name.lower()

            elif object_class == ObjectType.HERO_PLACEHOLDER.value:
                map_object['owner'] = ColorEnum(self.process_uint8()).name.lower()
                map_object['hero_id'] = self.process_uint8()
                if map_object['hero_id'] == 0xFF:
                    map_object['power'] = self.process_uint8()

            elif object_class == ObjectType.LIGHTHOUSE.value:
                map_object['owner'] = ColorEnum(self.process_uint32()).name.lower()

            map_object.update(
                {
                    'object_class': (
                        ObjectType(object_class).name.lower()
                        if object_class in ObjectType
                        else str(object_class)
                    ),
                    'object_subclass': object_subclass,
                    'coordinates': object_coordinates,
                }
            )
            self.data['objects'].append(map_object)

    def read_events(self):
        self.data['events'] = []
        events_quantity = self.process_uint32()
        for _ in range(events_quantity):
            self.data['events'].append(
                {
                    'name': self.process_string(),
                    'message': self.process_string(),
                    'resources': self.read_resources(),
                    'players': self.process_n_bytes_to_mask(1),
                    'is_human_affected': (
                        bool(self.process_uint8()) if self.map_type >= MapType.SOD else True
                    ),
                    'is_computer_affected': bool(self.process_uint8()),
                    'first_occurrence': self.process_uint16(),
                    'next_occurrence': self.process_uint8(),
                    'unknown': self.process_n_bytes_to_base64(17),
                }
            )

    def get_structured_data(self) -> GameMapStructure | None:
        self.data = collections.OrderedDict()
        if not self.encoding:
            self.detect_encoding_by_header()

        self.read_header()
        self.read_players_attributes()
        self.read_victory_conditions()
        self.read_loss_conditions()
        self.read_teams()
        self.read_heroes_info()
        self.read_artifacts()
        self.read_spells()
        self.read_abilities()
        self.read_rumors()
        self.read_predefined_heroes()
        self.read_terrain()
        self.read_def_info()
        try:
            self.read_objects()
        except IndexError as e:
            logger.error(
                'Failed to parse objects in %s at offset %s', self.filename, self._cursor_position
            )
            raise H3MapParserException(
                f'Failed to parse objects in {self.filename} at offset {self._cursor_position}'
            ) from e
        self.read_events()

        return GameMapStructure.model_validate(self.data)
