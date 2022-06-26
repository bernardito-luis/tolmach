"""
This is some kind of port to Python from VCMI (high praise for the project!)
https://github.com/vcmi/vcmi/blob/develop/lib/mapping/MapFormatH3M.cpp
"""

import collections
import gzip

from enums import MapType, ObjectType, RewardType
from exceptions import H3MapParserException


class MapParser:
    def __init__(self, filename: str, encoding='cp1251', *args, **kwargs) -> None:
        self.filename = filename
        self.map_binary = b''
        self._cursor_position = 0
        self.data = collections.OrderedDict()
        self.map_type = None
        self.encoding = encoding

    @staticmethod
    def bytes_to_int(input_bytes: bytes) -> int:
        return int.from_bytes(input_bytes, byteorder='little')

    def process_uint8(self) -> int:
        value = self.map_binary[self._cursor_position]
        self._cursor_position += 1
        return value

    def process_uint16(self) -> int:
        value = self.bytes_to_int(
            self.map_binary[self._cursor_position:self._cursor_position + 2]
        )
        self._cursor_position += 2
        return value

    def process_uint32(self) -> int:
        value = self.bytes_to_int(
            self.map_binary[self._cursor_position:self._cursor_position + 4]
        )
        self._cursor_position += 4
        return value

    def process_n_bytes(self, n: int) -> bytes:
        result = self.map_binary[self._cursor_position:self._cursor_position + n]
        self._cursor_position += n
        return result

    def base_process_string(self) -> str:
        string_len = self.process_uint32()
        string_end = self._cursor_position + string_len
        string_from_map = self.map_binary[self._cursor_position:string_end].decode(self.encoding)
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

    def read_map_file(self):
        with gzip.open(self.filename, 'rb') as f:
            self.map_binary = f.read()

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

    def read_players_attributes(self):
        self.data['players_attributes'] = []

        for player_color in ('red', 'blue', 'brown', 'green', 'orange', 'purple', 'teal', 'pink'):
            player_info = {}
            player_info['can_human_play'] = bool(self.process_uint8())
            player_info['can_computer_play'] = bool(self.process_uint8())
            if not player_info['can_human_play'] and not player_info['can_computer_play']:
                if self.map_type >= MapType.SOD:
                    self.process_n_bytes(13)
                elif self.map_type == MapType.AB:
                    self.process_n_bytes(12)
                elif self.map_type == MapType.ROE:
                    self.process_n_bytes(6)
                self.data['players_attributes'].append(player_info)
                continue

            player_info['computer_playstyle'] = self.process_uint8()
            if self.map_type >= MapType.SOD:
                player_info['are_factions_configured'] = self.process_uint8()
            if self.map_type == MapType.ROE:
                player_info['allowed_factions'] = self.process_uint8()
            else:
                player_info['allowed_factions'] = self.process_uint16()

            player_info['is_faction_random'] = self.process_uint8()
            has_main_town = bool(self.process_uint8())
            player_info['generate_hero_at_main_town'] = None
            player_info['generate_hero'] = None
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
            if player_info['main_custom_hero_id'] != 0xff:
                player_info['main_custom_hero_portrait'] = self.process_uint8()
                player_info['main_custom_hero_name'] = self.process_string()

            if self.map_type != MapType.ROE:
                self.process_n_bytes(1)  # unknown byte
                player_info['hero_count'] = self.process_uint8()
                self.process_n_bytes(3)
                player_info['heroes'] = []
                for _ in range(player_info['hero_count']):
                    player_info['heroes'].append({
                        'hero_id': self.process_uint8(),
                        'hero_name': self.process_string(),
                    })

            self.data['players_attributes'].append(player_info)

    def read_victory_conditions(self):
        self.data['victory'] = {}

        self.data['victory']['victory_condition'] = self.process_uint8()
        if self.data['victory']['victory_condition'] == 0xff:
            pass
        else:
            self.data['victory']['standard_win_available'] = self.process_uint8()
            self.data['victory']['applies_to_computer'] = self.process_uint8()
            if self.data['victory']['victory_condition'] == 0:
                self.data['victory']['artifact_code'] = self.process_uint8()
                if self.map_type != MapType.ROE:
                    self.process_n_bytes(1)
            elif self.data['victory']['victory_condition'] == 1:
                self.data['victory']['unit_code'] = self.process_uint8()
                if self.map_type != MapType.ROE:
                    self.process_n_bytes(1)
                self.data['victory']['victory_quantity'] = self.process_uint32()
            elif self.data['victory']['victory_condition'] == 2:
                self.data['victory']['resource_code'] = self.process_uint8()
                self.data['victory']['victory_quantity'] = self.process_uint32()
            elif self.data['victory']['victory_condition'] == 3:
                self.data['victory']['victory_town_coordinates'] = self.process_coordinates()
                self.data['victory']['hall_level'] = self.process_uint8()
                self.data['victory']['castle_level'] = self.process_uint8()
            elif self.data['victory']['victory_condition'] in (4, 6):
                self.data['victory']['victory_town_coordinates'] = self.process_coordinates()
            elif self.data['victory']['victory_condition'] == 5:
                self.data['victory']['victory_hero_coordinates'] = self.process_coordinates()
            elif self.data['victory']['victory_condition'] == 7:
                self.data['victory']['victory_creature_coordinates'] = self.process_coordinates()
            elif self.data['victory']['victory_condition'] in (8, 9):
                pass
            elif self.data['victory']['victory_condition'] == 10:
                self.data['victory']['artifact_code'] = self.process_uint8()
                self.data['victory']['victory_creature_coordinates'] = self.process_coordinates()
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
        elif self.data['loss']['special_loss_condition'] == 0xff:
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
            self.data['allowed_heroes_info'] = self.process_n_bytes(16)
        else:
            self.data['allowed_heroes_info'] = self.process_n_bytes(20)

        if self.map_type >= MapType.AB:
            placeholder_quantity = self.process_uint32()
            self.data['placeholder_heroes'] = [
                self.process_uint8() for _ in range(placeholder_quantity)
            ]

        if self.map_type >= MapType.SOD:
            configured_quantity = self.process_uint8()
            self.data['configured_heroes'] = []
            for _ in range(configured_quantity):
                self.data['configured_heroes'].append({
                    'id': self.process_uint8(),
                    'portrait': self.process_uint8(),
                    'name': self.process_string(),
                    'players_access': self.process_uint8(),
                })

        self.process_n_bytes(31)  # unknown bytes

    def read_artifacts(self):
        if self.map_type == MapType.AB:
            self.data['artifacts_bytes'] = self.process_n_bytes(17)
        elif self.map_type >= MapType.SOD:
            self.data['artifacts_bytes'] = self.process_n_bytes(18)

    def read_spells(self):
        if self.map_type >= MapType.SOD:
            self.data['allowed_spells_bytes'] = self.process_n_bytes(9)

    def read_abilities(self):
        if self.map_type >= MapType.SOD:
            self.data['allowed_hero_abilities_bytes'] = self.process_n_bytes(4)

    def read_rumors(self):
        self.data['rumors'] = []
        rumors_quantity = self.process_uint32()
        for _ in range(rumors_quantity):
            rumor_name = self.process_string()
            rumor_text = self.process_string()
            self.data['rumors'].append({
                'name': rumor_name,
                'text': rumor_text,
            })

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
                    hero['abilities'].append({
                        'id': self.process_uint8(),
                        'level': self.process_uint8(),
                    })
            self.load_hero_artifacts(hero)

            if self.process_uint8():
                hero['biography'] = self.process_string()

            hero['sex'] = self.process_uint8()

            if self.process_uint8():
                hero['spells'] = self.process_n_bytes(9)

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
            artifact_default = 0xff
            artifact_id = self.process_uint8()
        else:
            artifact_default = 0xffff
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
                    self.data['terrain'][level].append({
                        'terrain_type': self.process_uint8(),
                        'view': self.process_uint8(),
                        'river_type': self.process_uint8(),
                        'river_flow': self.process_uint8(),
                        'road_type': self.process_uint8(),
                        'road_flow': self.process_uint8(),
                        'flip_bits': self.process_uint8(),
                    })

    def read_def_info(self):
        self.data['def'] = []
        def_quantity = self.process_uint32()
        for def_obj_number in range(def_quantity):
            self.data['def'].append({
                'sprite_filename': self.process_def_string(),
                'unpassable_tiles': self.process_n_bytes(6),
                'active_tiles': self.process_n_bytes(6),
                'allowed_terrain': self.process_uint16(),
                'terrain_group': self.process_uint16(),
                'object_class': self.process_uint32(),  # id
                'object_number': self.process_uint32(),  # sub_id
                'object_group': self.process_uint8(),
                'z_index': self.process_uint8(),
                'unknown': self.process_n_bytes(16),
            })

    def read_creature_set(self, quantity) -> list:
        max_id = 0xff if self.map_type == MapType.ROE else 0xffff
        creatures = []
        for _ in range(quantity):
            if self.map_type >= MapType.AB:
                creature_id = self.process_uint16()
            else:
                creature_id = self.process_uint8()
            creatures_quantity = self.process_uint16()
            if creature_id == max_id:
                continue
            creatures.append((creature_id, creatures_quantity))

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
            self.process_n_bytes(4)

        return message, guards

    def read_resources(self):
        return [
            self.process_uint32() for _ in range(7)
        ]

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
                (self.process_uint8(), self.process_uint8())
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
                hero['custom_spells'] = self.process_n_bytes(9)
        elif self.map_type == MapType.AB:
            hero['custom_spells'] = self.process_uint8()

        if self.map_type >= MapType.SOD:
            has_custom_primary_skills = self.process_uint8()
            if has_custom_primary_skills:
                hero['custom_primary_skills'] = [
                    self.process_uint8() for _ in range(4)
                ]

        self.process_n_bytes(16)

        return hero

    def read_quest(self) -> dict:
        quest = dict()
        quest['mission_type'] = self.process_uint8()
        if quest['mission_type'] == 0:
            return quest
        elif quest['mission_type'] in (1, 3, 4):
            quest['goal'] = self.process_uint32()
        elif quest['mission_type'] == 2:
            quest['primary_stats'] = [self.process_uint8() for _ in range(4)]
        elif quest['mission_type'] == 5:
            artifact_quantity = self.process_uint8()
            quest['artifacts'] = [self.process_uint16() for _ in range(artifact_quantity)]
        elif quest['mission_type'] == 6:
            creatures_types = self.process_uint8()
            quest['creatures'] = [
                {'type': self.process_uint16(), 'quantity': self.process_uint16()}
                for _ in range(creatures_types)
            ]
        elif quest['mission_type'] == 7:
            quest['resources'] = [self.process_uint32() for _ in range(7)]
        elif quest['mission_type'] in (8, 9):
            quest['goal'] = self.process_uint8()

        quest['limit'] = self.process_uint32()

        quest['first_visit_text'] = self.process_string()
        quest['next_visit_text'] = self.process_string()
        quest['completed_text'] = self.process_string()

        return quest

    def read_town(self) -> dict:
        town = dict()
        if self.map_type >= MapType.AB:
            town['id'] = self.process_uint32()
        town['owner'] = self.process_uint8()
        if self.process_uint8():
            town['name'] = self.process_string()
        if self.process_uint8():
            town['garrison'] = self.read_creature_set(7)
        town['formation'] = self.process_uint8()

        has_custom_buildings = self.process_uint8()
        if has_custom_buildings:
            town['built_buildings'] = self.process_n_bytes(6)
            town['forbidden_buildings'] = self.process_n_bytes(6)
        else:
            town['has_fort'] = self.process_uint8()

        if self.map_type >= MapType.AB:
            town['obligatory_spells'] = [self.process_uint8() for _ in range(9)]
        town['possible_spells'] = [self.process_uint8() for _ in range(9)]

        events_quantity = self.process_uint32()
        town['events'] = []
        for _ in range(events_quantity):
            town['events'].append({
                'name': self.process_string(),
                'message': self.process_string(),
                'resources': self.read_resources(),
                'players': self.process_uint8(),
                'human_affected': self.process_uint8() if self.map_type >= MapType.SOD else True,
                'computer_affected': self.process_uint8(),
                'first_occurrence': self.process_uint16(),
                'next_occurrence': self.process_uint8(),
                'unknown': self.process_n_bytes(17),
                'new_buildings': self.process_n_bytes(6),
                'new_creatures_quantities': [self.process_uint16() for _ in range(7)],
                'unknown2': self.process_n_bytes(4),
            })
        if self.map_type >= MapType.SOD:
            town['alignment'] = self.process_uint8()
        self.process_n_bytes(3)

        return town

    def read_objects(self):
        self.data['objects'] = []
        objects_quantity = self.process_uint32()
        for _ in range(objects_quantity):
            object_coordinates = self.process_coordinates()
            object_number = self.process_uint32()
            self.process_n_bytes(5)  # unknown
            object_class = self.data['def'][object_number]['object_class']
            map_object = {}
            if object_class == ObjectType.EVENT.value:
                message, guards = self.read_message_and_guards()
                experience = self.process_uint32()
                mana_diff = self.process_uint32()
                morale = self.process_uint8()
                luck = self.process_uint8()
                resources = self.read_resources()
                primary_skills = [self.process_uint8() for _ in range(4)]
                abilities_quantity = self.process_uint8()
                abilities = [
                    (self.process_uint8(), self.process_uint8())
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

                self.process_n_bytes(8)

                available_for_color = self.process_uint8()
                can_computer_activate = self.process_uint8()
                remove_after_visit = self.process_uint8()

                self.process_n_bytes(4)
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
                self.process_n_bytes(4)

            elif object_class in (
                ObjectType.HERO.value, ObjectType.RANDOM_HERO.value, ObjectType.PRISON.value,
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
                monster['not_growing'] = self.process_uint8()
                map_object = monster

                self.process_n_bytes(2)

            elif object_class == ObjectType.SEER_HUT.value:
                quest = dict()
                if self.map_type >= MapType.AB:
                    quest = self.read_quest()
                else:
                    quest['mission_type'] = 5
                    quest['artifacts'] = [self.process_uint8()]

                if quest['mission_type']:
                    quest['reward_type'] = self.process_uint8()
                    if quest['reward_type'] == RewardType.EXPERIENCE.value:
                        quest['reward_experience'] = self.process_uint32()
                    elif quest['reward_type'] == RewardType.MANA_POINTS.value:
                        quest['reward_mana_points'] = self.process_uint32()
                    elif quest['reward_type'] == RewardType.MORALE_BONUS.value:
                        quest['reward_morale'] = self.process_uint8()
                    elif quest['reward_type'] == RewardType.LUCK_BONUS.value:
                        quest['reward_luck'] = self.process_uint8()
                    elif quest['reward_type'] == RewardType.RESOURCES.value:
                        quest['reward_resource_id'] = self.process_uint8()
                        quest['reward_resource_quantity'] = self.process_uint32()
                    elif quest['reward_type'] == RewardType.PRIMARY_SKILL.value:
                        quest['reward_skill_id'] = self.process_uint8()
                        quest['reward_skill_increase'] = self.process_uint8()
                    elif quest['reward_type'] == RewardType.ABILITY.value:
                        quest['reward_ability_id'] = self.process_uint8()
                        quest['reward_ability_increase'] = self.process_uint8()
                    elif quest['reward_type'] == RewardType.ARTIFACT.value:
                        if self.map_type == MapType.ROE:
                            quest['reward_artifact_id'] = self.process_uint8()
                        else:
                            quest['reward_artifact_id'] = self.process_uint16()
                    elif quest['reward_type'] == RewardType.SPELL.value:
                        quest['reward_spell'] = self.process_uint8()
                    elif quest['reward_type'] == RewardType.CREATURE.value:
                        if self.map_type == MapType.ROE:
                            quest['reward_creature_id'] = self.process_uint8()
                            quest['reward_creature_quantity'] = self.process_uint16()
                        else:
                            quest['reward_creature_id'] = self.process_uint16()
                            quest['reward_creature_quantity'] = self.process_uint16()

                    self.process_n_bytes(2)

                else:
                    self.process_n_bytes(3)
                map_object = quest

            elif object_class == ObjectType.WITCH_HUT.value:
                if self.map_type >= MapType.AB:
                    map_object['ability_bits'] = self.process_n_bytes(4)

            elif object_class == ObjectType.SCHOLAR.value:
                map_object['bonus_type'] = self.process_uint8()
                map_object['bonus_id'] = self.process_uint8()
                self.process_n_bytes(6)

            elif object_class in (ObjectType.GARRISON.value, ObjectType.GARRISON2.value):
                map_object['owner'] = self.process_uint8()
                self.process_n_bytes(3)
                map_object['creatures'] = self.read_creature_set(7)
                if self.map_type >= MapType.AB:
                    map_object['is_removable'] = self.process_uint8()
                else:
                    map_object['is_removable'] = 1
                self.process_n_bytes(8)

            elif object_class in (
                ObjectType.ARTIFACT.value,
                ObjectType.RANDOM_ART.value,
                ObjectType.RANDOM_TREASURE_ART.value,
                ObjectType.RANDOM_MINOR_ART.value,
                ObjectType.RANDOM_MAJOR_ART.value,
                ObjectType.RANDOM_RELIC_ART.value,
                ObjectType.SPELL_SCROLL.value,
            ):
                map_object['message'], map_object['guards'] = self.read_message_and_guards()
                if object_class == ObjectType.SPELL_SCROLL.value:
                    map_object['spell_id'] = self.process_uint32()
                if object_class == ObjectType.ARTIFACT.value:
                    map_object['artifact_id'] = self.data['def'][object_number]['object_number']

            elif object_class in (ObjectType.RESOURCE.value, ObjectType.RANDOM_RESOURCE.value):
                map_object['message'], map_object['guards'] = self.read_message_and_guards()
                map_object['quantity'] = self.process_uint32()
                self.process_n_bytes(4)

            elif object_class in (ObjectType.TOWN.value, ObjectType.RANDOM_TOWN.value):
                map_object = self.read_town()

            elif object_class in (
                ObjectType.MINE.value,
                ObjectType.ABANDONED_MINE.value,
                ObjectType.CREATURE_GENERATOR1.value,
                ObjectType.CREATURE_GENERATOR2.value,
                ObjectType.CREATURE_GENERATOR3.value,
                ObjectType.CREATURE_GENERATOR4.value,
            ):
                map_object['owner'] = self.process_uint8()
                self.process_n_bytes(3)

            elif object_class in (
                ObjectType.SHRINE_OF_MAGIC_INCANTATION.value,
                ObjectType.SHRINE_OF_MAGIC_GESTURE.value,
                ObjectType.SHRINE_OF_MAGIC_THOUGHT.value,
            ):
                map_object['spell_id'] = self.process_uint8()
                self.process_n_bytes(3)

            elif object_class == ObjectType.PANDORAS_BOX.value:
                map_object['message'], map_object['guards'] = self.read_message_and_guards()
                map_object['experience'] = self.process_uint32()
                map_object['mana_diff'] = self.process_uint32()
                map_object['morale_diff'] = self.process_uint8()
                map_object['luck_diff'] = self.process_uint8()
                map_object['resources'] = self.read_resources()
                map_object['primary_skills'] = [self.process_uint8() for _ in range(4)]
                abilities_quantity = self.process_uint8()
                map_object['abilities'] = [
                    (self.process_uint8(), self.process_uint8())
                    for _ in range(abilities_quantity)
                ]
                artifacts_quantity = self.process_uint8()
                if self.map_type == MapType.ROE:
                    map_object['artifacts'] = [self.process_uint8() for _ in range(artifacts_quantity)]
                else:
                    map_object['artifacts'] = [self.process_uint16() for _ in range(artifacts_quantity)]
                spells_quantity = self.process_uint8()
                map_object['spells'] = [self.process_uint8() for _ in range(spells_quantity)]
                creatures_quantity = self.process_uint8()
                map_object['creatures'] = self.read_creature_set(creatures_quantity)
                self.process_n_bytes(8)

            elif object_class == ObjectType.GRAIL.value:
                map_object['radius'] = self.process_uint32()

            elif object_class == ObjectType.RANDOM_DWELLING.value:
                map_object['owner'] = self.process_uint32()
                map_object['castle_id'] = self.process_uint32()
                if not map_object['castle_id']:
                    map_object['castles'] = (self.process_uint8(), self.process_uint8())
                map_object['min_lvl'] = self.process_uint8()
                map_object['max_lvl'] = self.process_uint8()

            elif object_class == ObjectType.RANDOM_DWELLING_LVL.value:
                map_object['owner'] = self.process_uint32()
                map_object['castle_id'] = self.process_uint32()
                if not map_object['castle_id']:
                    map_object['castles'] = (self.process_uint8(), self.process_uint8())

            elif object_class == ObjectType.RANDOM_DWELLING_FACTION.value:
                map_object['owner'] = self.process_uint32()
                map_object['min_lvl'] = self.process_uint8()
                map_object['max_lvl'] = self.process_uint8()

            elif object_class == ObjectType.QUEST_GUARD.value:
                map_object = self.read_quest()

            elif object_class == ObjectType.SHIPYARD.value:
                map_object['owner'] = self.process_uint32()

            elif object_class == ObjectType.HERO_PLACEHOLDER.value:
                map_object['owner'] = self.process_uint8()
                map_object['hero_id'] = self.process_uint8()
                if map_object['hero_id'] == 0xff:
                    map_object['power'] = self.process_uint8()

            elif object_class == ObjectType.LIGHTHOUSE.value:
                map_object['owner'] = self.process_uint32()

            self.data['objects'].append({
                'type': (
                    ObjectType(object_class).name if object_class in ObjectType
                    else object_class
                ),
                'coordinates': object_coordinates,
                'object': map_object,
            })

    def read_events(self):
        self.data['events'] = []
        events_quantity = self.process_uint32()
        for _ in range(events_quantity):
            self.data['events'].append({
                'name': self.process_string(),
                'message': self.process_string(),
                'resources': self.read_resources(),
                'players': self.process_uint8(),
                'human_affected': self.process_uint8() if self.map_type >= MapType.SOD else True,
                'computer_affected': self.process_uint8(),
                'first_occurrence': self.process_uint16(),
                'next_occurrence': self.process_uint8(),
            })
            self.process_n_bytes(17)

    def get_structured_data(self) -> dict:
        self.read_map_file()

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
        self.read_objects()
        self.read_events()

        return self.data

