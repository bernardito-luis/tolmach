import base64
import gzip
import logging
import pathlib

from map_processors.enums import (
    ColorEnum,
    ComputerPlaystyleEnum,
    MapType,
    QuestType,
    ResourceType,
    RewardType,
)
from map_processors.exceptions import H3MapWriterException
from map_processors.schemas import GameMapStructure, PredefinedHeroNonConfigured

logger = logging.getLogger(__name__)


class MapWriter:
    def __init__(
        self,
        structure: GameMapStructure,
        encoding: str = 'cp1251',
        fallback_encoding: str | None = 'cp1251',
    ) -> None:
        self.structure = structure
        self.encoding = encoding
        self.fallback_encoding = fallback_encoding
        self._buffer = bytearray()

        map_type_value = structure.header.map_type
        if map_type_value == MapType.ROE.value:
            self.map_type = MapType.ROE
        elif map_type_value == MapType.AB.value:
            self.map_type = MapType.AB
        elif map_type_value == MapType.SOD.value:
            self.map_type = MapType.SOD
        else:
            raise H3MapWriterException(f'Unknown map type: {map_type_value}')

    def write_uint8(self, value: int) -> None:
        self._buffer += value.to_bytes(1, 'little')

    def write_uint16(self, value: int) -> None:
        self._buffer += value.to_bytes(2, 'little')

    def write_uint32(self, value: int) -> None:
        self._buffer += value.to_bytes(4, 'little')

    def write_int8(self, value: int) -> None:
        self._buffer += value.to_bytes(1, 'little', signed=True)

    def write_int16(self, value: int) -> None:
        self._buffer += value.to_bytes(2, 'little', signed=True)

    def write_int32(self, value: int) -> None:
        self._buffer += value.to_bytes(4, 'little', signed=True)

    def write_padding(self, n: int) -> None:
        self._buffer += b'\x00' * n

    def write_n_bytes(self, data: bytes) -> None:
        self._buffer += data

    def write_mask_string(self, mask: str, n: int) -> None:
        if len(mask) != n * 8:
            raise H3MapWriterException(
                f'Mask length {len(mask)} does not match expected {n * 8} bits'
            )
        self._buffer += int(mask, 2).to_bytes(n, 'big')

    def write_base64_bytes(self, b64: str, expected_n: int) -> None:
        decoded = base64.b64decode(b64)
        if len(decoded) != expected_n:
            raise H3MapWriterException(
                f'Base64 length {len(decoded)} does not match expected {expected_n}'
            )
        self._buffer += decoded

    def _write_unknown(self, value: str | None, n: int) -> None:
        if value is None:
            self.write_padding(n)
        else:
            self.write_base64_bytes(value, n)

    def _write_unknown_variable(self, value: str | None, n: int) -> None:
        if value is None:
            self.write_padding(n)
            return
        decoded = base64.b64decode(value)
        if len(decoded) != n:
            logger.warning('Unknown-bytes length %d does not match expected %d', len(decoded), n)
        self._buffer += decoded

    def write_string(self, value: str) -> None:
        try:
            encoded = value.encode(self.encoding)
        except UnicodeEncodeError:
            if self.fallback_encoding and self.fallback_encoding != self.encoding:
                encoded = value.encode(self.fallback_encoding)
            else:
                raise
        self.write_uint32(len(encoded))
        self._buffer += encoded

    def write_coordinates(self, coordinates: tuple[int, int, int]) -> None:
        x, y, z = coordinates
        self.write_uint8(x)
        self.write_uint8(y)
        self.write_uint8(z)

    def write_header(self) -> None:
        header = self.structure.header
        self.write_uint32(header.map_type)
        self.write_uint8(int(header.are_any_players))
        self.write_uint32(header.width)
        self.write_uint8(int(header.has_underground))
        self.write_string(header.map_name)
        self.write_string(header.map_description)
        self.write_uint8(header.map_difficulty)
        if self.map_type != MapType.ROE:
            self.write_uint8(header.hero_level_limit)

    def write_players_attributes(self) -> None:
        for player in self.structure.players_attributes:
            self.write_uint8(int(player.can_human_play))
            self.write_uint8(int(player.can_computer_play))
            if not player.can_human_play and not player.can_computer_play:
                if self.map_type >= MapType.SOD:
                    self._write_unknown(player.inactive_unknown, 13)
                elif self.map_type == MapType.AB:
                    self._write_unknown(player.inactive_unknown, 12)
                else:
                    self._write_unknown(player.inactive_unknown, 6)
                continue

            self.write_uint8(_playstyle_to_value(player.computer_playstyle))
            if self.map_type >= MapType.SOD:
                self.write_uint8(player.are_factions_configured)
            if self.map_type == MapType.ROE:
                self.write_uint8(player.allowed_factions)
            else:
                self.write_uint16(player.allowed_factions)

            self.write_uint8(int(player.is_faction_random))

            has_main_town = player.town_coordinates is not None
            self.write_uint8(int(has_main_town))
            if has_main_town:
                if self.map_type != MapType.ROE:
                    self.write_uint8(player.generate_hero_at_main_town)
                    self.write_uint8(player.generate_hero)
                self.write_coordinates(player.town_coordinates)

            self.write_uint8(player.has_random_hero)
            self.write_uint8(player.main_custom_hero_id)
            if player.main_custom_hero_id != 0xFF:
                self.write_uint8(player.main_custom_hero_portrait)
                self.write_string(player.main_custom_hero_name)

            if self.map_type != MapType.ROE:
                self._write_unknown(player.hero_section_prefix, 1)
                self.write_uint8(player.hero_count)
                self._write_unknown(player.hero_section_suffix, 3)
                for hero in player.heroes or []:
                    self.write_uint8(hero.hero_id)
                    self.write_string(hero.hero_name)

    def write_victory_conditions(self) -> None:
        victory = self.structure.victory
        cond = victory.special_victory_condition
        self.write_uint8(cond)
        if cond == 0xFF:
            return

        self.write_uint8(victory.standard_win_available)
        self.write_uint8(victory.applies_to_computer)

        if cond == 0:
            self.write_uint8(victory.acquire_artifact_code)
            if self.map_type != MapType.ROE:
                self._write_unknown(victory.acquire_artifact_unknown, 1)
        elif cond == 1:
            self.write_uint8(victory.unit_code)
            if self.map_type != MapType.ROE:
                self._write_unknown(victory.unit_unknown, 1)
            self.write_uint32(victory.unit_quantity)
        elif cond == 2:
            self.write_uint8(victory.resource_code)
            self.write_uint32(victory.resource_quantity)
        elif cond == 3:
            self.write_coordinates(victory.upgrade_town_coordinates)
            self.write_uint8(victory.hall_level)
            self.write_uint8(victory.castle_level)
        elif cond == 4:
            self.write_coordinates(victory.build_grail_town_coordinates)
        elif cond == 5:
            self.write_coordinates(victory.hero_coordinates)
        elif cond == 6:
            self.write_coordinates(victory.capture_town_coordinates)
        elif cond == 7:
            self.write_coordinates(victory.creature_coordinates)
        elif cond in (8, 9):
            pass
        elif cond == 10:
            self.write_uint8(victory.bring_artifact_code)
            self.write_coordinates(victory.bring_artifact_town_coordinates)
        else:
            raise H3MapWriterException(f'Unknown victory type: {cond}')

    def write_loss_conditions(self) -> None:
        loss = self.structure.loss
        cond = loss.special_loss_condition
        self.write_uint8(cond)
        if cond == 0:
            self.write_coordinates(loss.loss_town_coordinates)
        elif cond == 1:
            self.write_coordinates(loss.loss_hero_coordinates)
        elif cond == 2:
            self.write_uint16(loss.time_expires_in_days)
        elif cond == 0xFF:
            pass
        else:
            raise H3MapWriterException(f'Unknown loss type: {cond}')

    def write_teams(self) -> None:
        teams = self.structure.teams
        self.write_uint8(teams.quantity)
        if teams.quantity:
            self.write_uint8(teams.red_team_number)
            self.write_uint8(teams.blue_team_number)
            self.write_uint8(teams.brown_team_number)
            self.write_uint8(teams.green_team_number)
            self.write_uint8(teams.orange_team_number)
            self.write_uint8(teams.purple_team_number)
            self.write_uint8(teams.teal_team_number)
            self.write_uint8(teams.pink_team_number)

    def write_heroes_info(self) -> None:
        if self.map_type == MapType.ROE:
            self.write_mask_string(self.structure.allowed_heroes_info, 16)
        else:
            self.write_mask_string(self.structure.allowed_heroes_info, 20)

        if self.map_type >= MapType.AB:
            self.write_uint32(len(self.structure.placeholder_heroes))
            for hero_id in self.structure.placeholder_heroes:
                self.write_uint8(hero_id)

        if self.map_type >= MapType.SOD:
            self.write_uint8(len(self.structure.configured_heroes))
            for hero in self.structure.configured_heroes:
                self.write_uint8(hero.id)
                self.write_uint8(hero.portrait)
                self.write_string(hero.name)
                self.write_uint8(hero.players_access)

        self._write_unknown(self.structure.heroes_info_unknown, 31)

    def write_artifacts(self) -> None:
        if self.map_type == MapType.AB:
            self.write_mask_string(self.structure.artifacts, 17)
        elif self.map_type >= MapType.SOD:
            self.write_mask_string(self.structure.artifacts, 18)

    def write_spells(self) -> None:
        if self.map_type >= MapType.SOD:
            self.write_mask_string(self.structure.allowed_spells_bytes, 9)

    def write_abilities(self) -> None:
        if self.map_type >= MapType.SOD:
            self.write_mask_string(self.structure.allowed_hero_abilities_bytes, 4)

    def write_rumors(self) -> None:
        self.write_uint32(len(self.structure.rumors))
        for rumor in self.structure.rumors:
            self.write_string(rumor.name)
            self.write_string(rumor.text)

    def write_predefined_heroes(self) -> None:
        if self.map_type <= MapType.AB:
            return

        for hero_id in range(156):
            hero = self.structure.predefined_heroes.get(hero_id)
            is_configured = hero is not None and not _is_empty_predefined(hero)
            self.write_uint8(int(is_configured))
            if not is_configured:
                continue

            has_experience = hero.experience is not None
            self.write_uint8(int(has_experience))
            if has_experience:
                self.write_uint32(hero.experience)

            has_abilities = hero.abilities is not None
            self.write_uint8(int(has_abilities))
            if has_abilities:
                self.write_uint32(len(hero.abilities))
                for ability in hero.abilities:
                    self.write_uint8(ability.id)
                    self.write_uint8(ability.level)

            self._write_hero_artifacts(hero.artifacts)

            has_biography = hero.biography is not None
            self.write_uint8(int(has_biography))
            if has_biography:
                self.write_string(hero.biography)

            self.write_uint8(hero.sex)

            has_spells = hero.spells is not None
            self.write_uint8(int(has_spells))
            if has_spells:
                self.write_mask_string(hero.spells, 9)

            has_primary_skills = hero.primary_skills is not None
            self.write_uint8(int(has_primary_skills))
            if has_primary_skills:
                self._write_primary_skills(hero.primary_skills)

    def write_terrain(self) -> None:
        for tile in self.structure.terrain.surface:
            self._write_terrain_tile(tile)
        if self.structure.header.has_underground:
            for tile in self.structure.terrain.underground:
                self._write_terrain_tile(tile)

    def _write_terrain_tile(self, tile) -> None:
        self.write_uint8(tile.terrain_type)
        self.write_uint8(tile.view)
        self.write_uint8(tile.river_type)
        self.write_uint8(tile.river_flow)
        self.write_uint8(tile.road_type)
        self.write_uint8(tile.road_flow)
        self.write_uint8(tile.flip_bits)

    def write_def_info(self) -> None:
        self.write_uint32(len(self.structure.def_objects))
        for def_obj in self.structure.def_objects:
            self.write_string(def_obj.sprite_filename)
            self.write_mask_string(def_obj.unpassable_tiles, 6)
            self.write_mask_string(def_obj.active_tiles, 6)
            self.write_uint16(def_obj.allowed_terrain)
            self.write_uint16(def_obj.terrain_group)
            self.write_uint32(def_obj.object_class)
            self.write_uint32(def_obj.object_number)
            self.write_uint8(def_obj.object_group)
            self.write_uint8(def_obj.z_index)
            self.write_base64_bytes(def_obj.unknown_base64, 16)

    def write_objects(self) -> None:
        self.write_uint32(len(self.structure.objects))
        for obj in self.structure.objects:
            self.write_coordinates(obj.coordinates)
            self.write_uint32(obj.object_number)
            self._write_unknown(obj.pre_body_unknown, 5)
            self._dispatch_object_body(obj)

    def _dispatch_object_body(self, obj) -> None:
        oc = obj.object_class
        if oc == 'event':
            self._write_event(obj)
        elif oc in ('sign', 'ocean_bottle'):
            self._write_sign(obj)
        elif oc in ('hero', 'random_hero', 'prison'):
            self._write_hero_object(obj)
        elif oc in (
            'monster',
            'random_monster',
            'random_monster_l1',
            'random_monster_l2',
            'random_monster_l3',
            'random_monster_l4',
            'random_monster_l5',
            'random_monster_l6',
            'random_monster_l7',
        ):
            self._write_monster(obj)
        elif oc == 'seer_hut':
            self._write_seer_hut(obj)
        elif oc == 'witch_hut':
            self._write_witch_hut(obj)
        elif oc == 'scholar':
            self._write_scholar(obj)
        elif oc in ('garrison_horizontal', 'garrison_vertical'):
            self._write_garrison(obj)
        elif oc == 'spell_scroll':
            self._write_spell_scroll(obj)
        elif oc == 'artifact':
            self._write_artifact(obj)
        elif oc in (
            'random_art',
            'random_treasure_art',
            'random_minor_art',
            'random_major_art',
            'random_relic_art',
        ):
            self._write_random_artifact(obj)
        elif oc in ('resource', 'random_resource'):
            self._write_resource(obj)
        elif oc in ('town', 'random_town'):
            self._write_town_object(obj)
        elif oc == 'abandoned_mine':
            self._write_abandoned_mine(obj)
        elif oc == 'mine':
            self._write_mine(obj)
        elif oc in (
            'creature_generator1',
            'creature_generator2',
            'creature_generator3',
            'creature_generator4',
        ):
            self._write_creature_generator(obj)
        elif oc in (
            'shrine_of_magic_incantation',
            'shrine_of_magic_gesture',
            'shrine_of_magic_thought',
        ):
            self._write_shrine(obj)
        elif oc == 'pandora_box':
            self._write_pandora_box(obj)
        elif oc == 'grail':
            self._write_grail(obj)
        elif oc == 'random_dwelling':
            self._write_random_dwelling(obj)
        elif oc == 'random_dwelling_lvl':
            self._write_random_dwelling_lvl(obj)
        elif oc == 'random_dwelling_faction':
            self._write_random_dwelling_faction(obj)
        elif oc == 'quest_guard':
            self._write_quest_guard(obj)
        elif oc == 'shipyard':
            self._write_shipyard(obj)
        elif oc == 'hero_placeholder':
            self._write_hero_placeholder(obj)
        elif oc == 'lighthouse':
            self._write_lighthouse(obj)

    def _write_event(self, obj) -> None:
        self._write_message_and_guards(obj.message, obj.guards, obj.message_unknown)
        self.write_uint32(obj.experience)
        self.write_int32(obj.mana_diff)
        self.write_int8(obj.morale)
        self.write_int8(obj.luck)
        self._write_resources(obj.resources)
        self._write_primary_skills(obj.primary_skills)
        self.write_uint8(len(obj.abilities))
        for ability in obj.abilities:
            self.write_uint8(ability.id)
            self.write_uint8(ability.level)
        self.write_uint8(len(obj.artifacts))
        for art_id in obj.artifacts:
            if self.map_type == MapType.ROE:
                self.write_uint8(art_id)
            else:
                self.write_uint16(art_id)
        self.write_uint8(len(obj.spells))
        for spell_id in obj.spells:
            self.write_uint8(spell_id)
        self.write_uint8(len(obj.creatures))
        self._write_creature_set_inline(obj.creatures)

        self._write_unknown(obj.unknown_mid, 8)
        self.write_mask_string(obj.available_for_color, 1)
        self.write_uint8(int(obj.can_computer_activate))
        self.write_uint8(int(obj.remove_after_visit))
        self._write_unknown(obj.unknown_tail, 4)

    def _write_sign(self, obj) -> None:
        self.write_string(obj.message)
        self._write_unknown(obj.message_tail, 4)

    def _write_hero_object(self, obj) -> None:
        if self.map_type >= MapType.AB:
            self.write_uint32(obj.id)
        self.write_uint8(obj.owner)
        self.write_uint8(obj.hero_sub_id)

        has_name = obj.name is not None
        self.write_uint8(int(has_name))
        if has_name:
            self.write_string(obj.name)

        if self.map_type >= MapType.SOD:
            has_exp = obj.experience is not None
            self.write_uint8(int(has_exp))
            if has_exp:
                self.write_uint32(obj.experience)
        else:
            self.write_uint32(obj.experience or 0)

        has_portrait = obj.portrait is not None
        self.write_uint8(int(has_portrait))
        if has_portrait:
            self.write_uint8(obj.portrait)

        has_abilities = obj.abilities is not None
        self.write_uint8(int(has_abilities))
        if has_abilities:
            self.write_uint32(len(obj.abilities))
            for ability in obj.abilities:
                self.write_uint8(ability.id)
                self.write_uint8(ability.level)

        has_creatures = obj.creatures is not None
        self.write_uint8(int(has_creatures))
        if has_creatures:
            self._write_creature_set_fixed(obj.creatures, 7)

        self.write_uint8(obj.formation)

        self._write_hero_artifacts(obj.artifacts)

        self.write_uint8(obj.patrol_radius)

        if self.map_type >= MapType.AB:
            has_biography = obj.biography is not None
            self.write_uint8(int(has_biography))
            if has_biography:
                self.write_string(obj.biography)
            self.write_uint8(obj.sex if obj.sex is not None else 0xFF)

        if self.map_type >= MapType.SOD:
            has_custom_spells = obj.custom_spells is not None
            self.write_uint8(int(has_custom_spells))
            if has_custom_spells:
                self.write_mask_string(obj.custom_spells, 9)
        elif self.map_type == MapType.AB:
            self.write_mask_string(obj.custom_spells, 8)

        if self.map_type >= MapType.SOD:
            has_custom_primary_skills = obj.custom_primary_skills is not None
            self.write_uint8(int(has_custom_primary_skills))
            if has_custom_primary_skills:
                self._write_primary_skills(obj.custom_primary_skills)

        self._write_unknown(obj.unknown_tail, 16)

    def _write_monster(self, obj) -> None:
        if self.map_type >= MapType.AB:
            self.write_uint32(obj.id)
        self.write_uint16(obj.quantity)
        self.write_uint8(obj.character)

        has_message = obj.message is not None
        self.write_uint8(int(has_message))
        if has_message:
            self.write_string(obj.message)
            self._write_resources(obj.resources)
            if self.map_type == MapType.ROE:
                self.write_uint8(obj.artifact_id)
            else:
                self.write_uint16(obj.artifact_id)

        self.write_uint8(obj.mood)
        self.write_uint8(int(obj.not_growing))
        self._write_unknown(obj.unknown_tail, 2)

    def _write_seer_hut(self, obj) -> None:
        if self.map_type >= MapType.AB:
            self._write_quest(obj)
        else:
            # ROE: artifact-bring quest with single uint8
            artifacts = obj.artifacts or []
            self.write_uint8(artifacts[0] if artifacts else 0)

        if obj.mission_type:
            reward = obj.reward
            reward_type_enum = RewardType[reward.type.upper()]
            self.write_uint8(reward_type_enum.value)
            if reward_type_enum == RewardType.EXPERIENCE:
                self.write_uint32(reward.experience)
            elif reward_type_enum == RewardType.MANA_POINTS:
                self.write_uint32(reward.mana_points)
            elif reward_type_enum == RewardType.MORALE_BONUS:
                self.write_int8(reward.morale)
            elif reward_type_enum == RewardType.LUCK_BONUS:
                self.write_int8(reward.luck)
            elif reward_type_enum == RewardType.RESOURCES:
                self.write_uint8(ResourceType[reward.resource_type.upper()].value)
                self.write_uint32(reward.resource_quantity)
            elif reward_type_enum == RewardType.PRIMARY_SKILL:
                self.write_uint8(reward.skill_id)
                self.write_uint8(reward.skill_increase)
            elif reward_type_enum == RewardType.ABILITY:
                self.write_uint8(reward.ability_id)
                self.write_uint8(reward.ability_increase)
            elif reward_type_enum == RewardType.ARTIFACT:
                if self.map_type == MapType.ROE:
                    self.write_uint8(reward.artifact_id)
                else:
                    self.write_uint16(reward.artifact_id)
            elif reward_type_enum == RewardType.SPELL:
                self.write_uint8(reward.spell_id)
            elif reward_type_enum == RewardType.CREATURE:
                if self.map_type == MapType.ROE:
                    self.write_uint8(reward.creature_id)
                    self.write_uint16(reward.creature_quantity)
                else:
                    self.write_uint16(reward.creature_id)
                    self.write_uint16(reward.creature_quantity)
            self._write_unknown_variable(obj.unknown_tail, 2)
        else:
            self._write_unknown_variable(obj.unknown_tail, 3)

    def _write_witch_hut(self, obj) -> None:
        if self.map_type >= MapType.AB:
            self.write_uint32(int(obj.ability_bits, 2))

    def _write_scholar(self, obj) -> None:
        self.write_uint8(obj.bonus_type)
        self.write_uint8(obj.bonus_id)
        self._write_unknown(obj.unknown_tail, 6)

    def _write_garrison(self, obj) -> None:
        self.write_uint8(ColorEnum[obj.owner.upper()].value)
        self._write_unknown(obj.unknown_mid, 3)
        self._write_creature_set_fixed(obj.creatures, 7)
        if self.map_type >= MapType.AB:
            self.write_uint8(obj.is_removable)
        self._write_unknown(obj.unknown_tail, 8)

    def _write_spell_scroll(self, obj) -> None:
        self._write_message_and_guards(obj.message, obj.guards, obj.message_unknown)
        self.write_uint32(obj.spell_id)

    def _write_artifact(self, obj) -> None:
        self._write_message_and_guards(obj.message, obj.guards, obj.message_unknown)

    def _write_random_artifact(self, obj) -> None:
        self._write_message_and_guards(obj.message, obj.guards, obj.message_unknown)

    def _write_resource(self, obj) -> None:
        self._write_message_and_guards(obj.message, obj.guards, obj.message_unknown)
        self.write_uint32(obj.quantity)
        self._write_unknown(obj.unknown_tail, 4)

    def _write_town_object(self, obj) -> None:
        if self.map_type >= MapType.AB:
            self.write_uint32(obj.id)
        self.write_uint8(ColorEnum[obj.owner.upper()].value)

        has_name = obj.name is not None
        self.write_uint8(int(has_name))
        if has_name:
            self.write_string(obj.name)

        has_garrison = obj.garrison is not None
        self.write_uint8(int(has_garrison))
        if has_garrison:
            self._write_creature_set_fixed(obj.garrison, 7)

        self.write_uint8(obj.formation)

        has_custom_buildings = obj.built_buildings is not None
        self.write_uint8(int(has_custom_buildings))
        if has_custom_buildings:
            self.write_mask_string(obj.built_buildings, 6)
            self.write_mask_string(obj.forbidden_buildings, 6)
        else:
            self.write_uint8(int(obj.has_fort))

        if self.map_type >= MapType.AB:
            self.write_mask_string(obj.obligatory_spells, 9)
        self.write_mask_string(obj.possible_spells, 9)

        self.write_uint32(len(obj.events))
        for event in obj.events:
            self.write_string(event.name)
            self.write_string(event.message)
            self._write_resources(event.resources)
            self.write_mask_string(event.players, 1)
            if self.map_type >= MapType.SOD:
                self.write_uint8(int(event.is_human_affected))
            self.write_uint8(int(event.is_computer_affected))
            self.write_uint16(event.first_occurrence)
            self.write_uint8(event.next_occurrence)
            self.write_base64_bytes(event.unknown, 17)
            self.write_mask_string(event.new_buildings, 6)
            for q in event.new_creatures_quantities:
                self.write_uint16(q)
            self.write_base64_bytes(event.unknown2, 4)

        if self.map_type >= MapType.SOD:
            self.write_uint8(obj.alignment)
        self._write_unknown(obj.unknown_tail, 3)

    def _write_abandoned_mine(self, obj) -> None:
        self.write_mask_string(obj.possible_resources, 1)
        self._write_unknown(obj.unknown_tail, 3)

    def _write_mine(self, obj) -> None:
        if obj.object_subclass == 7:
            self.write_mask_string(obj.possible_resources, 1)
            self._write_unknown(obj.unknown_tail, 3)
        else:
            self.write_uint8(ColorEnum[obj.owner.upper()].value)
            self._write_unknown(obj.unknown_tail, 3)

    def _write_creature_generator(self, obj) -> None:
        self.write_uint8(ColorEnum[obj.owner.upper()].value)
        self._write_unknown(obj.unknown_tail, 3)

    def _write_shrine(self, obj) -> None:
        self.write_uint8(obj.spell_id)
        self._write_unknown(obj.unknown_tail, 3)

    def _write_pandora_box(self, obj) -> None:
        self._write_message_and_guards(obj.message, obj.guards, obj.message_unknown)
        self.write_uint32(obj.experience)
        self.write_int32(obj.mana_diff)
        self.write_int8(obj.morale_diff)
        self.write_int8(obj.luck_diff)
        self._write_resources(obj.resources)
        self._write_primary_skills(obj.primary_skills)
        self.write_uint8(len(obj.abilities))
        for ability in obj.abilities:
            self.write_uint8(ability.id)
            self.write_uint8(ability.level)
        self.write_uint8(len(obj.artifacts))
        for art_id in obj.artifacts:
            if self.map_type == MapType.ROE:
                self.write_uint8(art_id)
            else:
                self.write_uint16(art_id)
        self.write_uint8(len(obj.spells))
        for spell_id in obj.spells:
            self.write_uint8(spell_id)
        self.write_uint8(len(obj.creatures))
        self._write_creature_set_inline(obj.creatures)
        self._write_unknown(obj.unknown_tail, 8)

    def _write_grail(self, obj) -> None:
        self.write_uint32(obj.radius)

    def _write_random_dwelling(self, obj) -> None:
        self.write_uint32(ColorEnum[obj.owner.upper()].value)
        self.write_uint32(obj.castle_id)
        if not obj.castle_id:
            self.write_uint8(obj.castles[0])
            self.write_uint8(obj.castles[1])
        self.write_uint8(obj.min_lvl)
        self.write_uint8(obj.max_lvl)

    def _write_random_dwelling_lvl(self, obj) -> None:
        self.write_uint32(ColorEnum[obj.owner.upper()].value)
        self.write_uint32(obj.castle_id)
        if not obj.castle_id:
            self.write_uint8(obj.castles[0])
            self.write_uint8(obj.castles[1])

    def _write_random_dwelling_faction(self, obj) -> None:
        self.write_uint32(ColorEnum[obj.owner.upper()].value)
        self.write_uint8(obj.min_lvl)
        self.write_uint8(obj.max_lvl)

    def _write_quest_guard(self, obj) -> None:
        self._write_quest(obj)

    def _write_shipyard(self, obj) -> None:
        self.write_uint32(ColorEnum[obj.owner.upper()].value)

    def _write_hero_placeholder(self, obj) -> None:
        self.write_uint8(ColorEnum[obj.owner.upper()].value)
        self.write_uint8(obj.hero_id)
        if obj.hero_id == 0xFF:
            self.write_uint8(obj.power)

    def _write_lighthouse(self, obj) -> None:
        self.write_uint32(ColorEnum[obj.owner.upper()].value)

    def _write_resources(self, resources) -> None:
        if resources is None:
            for _ in range(7):
                self.write_int32(0)
            return
        self.write_int32(resources.wood)
        self.write_int32(resources.mercury)
        self.write_int32(resources.ore)
        self.write_int32(resources.sulfur)
        self.write_int32(resources.crystal)
        self.write_int32(resources.gems)
        self.write_int32(resources.gold)

    def _write_primary_skills(self, skills) -> None:
        if skills is None:
            self.write_padding(4)
            return
        if isinstance(skills, dict):
            self.write_uint8(skills['attack'])
            self.write_uint8(skills['defence'])
            self.write_uint8(skills['power'])
            self.write_uint8(skills['knowledge'])
        else:
            self.write_uint8(skills.attack)
            self.write_uint8(skills.defence)
            self.write_uint8(skills.power)
            self.write_uint8(skills.knowledge)

    def _write_creature_set_inline(self, creatures) -> None:
        for creature in creatures:
            if self.map_type >= MapType.AB:
                self.write_uint16(creature.id)
            else:
                self.write_uint8(creature.id)
            self.write_uint16(creature.quantity)

    def _write_creature_set_fixed(self, creatures, slot_count: int) -> None:
        creatures = list(creatures)
        empty_id = 0xFFFF if self.map_type >= MapType.AB else 0xFF
        for i in range(slot_count):
            if i < len(creatures):
                creature = creatures[i]
                if self.map_type >= MapType.AB:
                    self.write_uint16(creature.id)
                else:
                    self.write_uint8(creature.id)
                self.write_uint16(creature.quantity)
            else:
                if self.map_type >= MapType.AB:
                    self.write_uint16(empty_id)
                else:
                    self.write_uint8(empty_id)
                self.write_uint16(0)

    def _write_message_and_guards(self, message, guards, message_unknown=None) -> None:
        has_message = message is not None
        self.write_uint8(int(has_message))
        if has_message:
            self.write_string(message)
            has_guards = guards is not None
            self.write_uint8(int(has_guards))
            if has_guards:
                self._write_creature_set_fixed(guards, 7)
            self._write_unknown(message_unknown, 4)

    def _write_hero_artifacts(self, artifacts) -> None:
        has_artifacts = artifacts is not None
        self.write_uint8(int(has_artifacts))
        if not has_artifacts:
            return

        # Slot layout (matches parser's corrected numbering in `base.py::load_hero_artifacts`):
        # SOD:    0..15 equipment, 16 catapult, 17 spellbook, 18 misc5, 19+ backpack
        # ROE/AB: 0..15 equipment, 16 spellbook, 17 misc5, 18+ backpack
        for slot in range(16):
            self._write_artifact_slot(artifacts.get(slot))

        next_slot = 16
        if self.map_type >= MapType.SOD:
            self._write_artifact_slot(artifacts.get(next_slot))  # catapult
            next_slot += 1
        self._write_artifact_slot(artifacts.get(next_slot))  # spellbook
        next_slot += 1
        self._write_artifact_slot(artifacts.get(next_slot))  # misc5
        next_slot += 1

        backpack_start = next_slot
        backpack_slots = sorted(s for s in artifacts.keys() if s >= backpack_start)
        backpack_quantity = (backpack_slots[-1] - backpack_start + 1) if backpack_slots else 0
        self.write_uint16(backpack_quantity)
        for slot in range(backpack_start, backpack_start + backpack_quantity):
            self._write_artifact_slot(artifacts.get(slot))

    def _write_artifact_slot(self, artifact_id) -> None:
        if self.map_type == MapType.ROE:
            empty_id = 0xFF
            if artifact_id is None:
                self.write_uint8(empty_id)
            else:
                self.write_uint8(artifact_id)
        else:
            empty_id = 0xFFFF
            if artifact_id is None:
                self.write_uint16(empty_id)
            else:
                self.write_uint16(artifact_id)

    def _write_quest(self, obj) -> None:
        mission_name = obj.mission_type.upper()
        mission_type = QuestType[mission_name]
        self.write_uint8(mission_type.value)

        if mission_type == QuestType.EMPTY:
            return
        elif mission_type == QuestType.ACHIEVE_LEVEL:
            self.write_uint32(obj.level)
        elif mission_type == QuestType.DEFEAT_HERO:
            self.write_uint32(obj.hero_object_id)
        elif mission_type == QuestType.DEFEAT_MONSTER:
            self.write_uint32(obj.monster_object_id)
        elif mission_type == QuestType.ACHIEVE_PRIMARY_SKILL_LEVEL:
            self._write_primary_skills(obj.primary_skills)
        elif mission_type == QuestType.BRING_ARTEFACT:
            self.write_uint8(len(obj.artifacts))
            for art_id in obj.artifacts:
                self.write_uint16(art_id)
        elif mission_type == QuestType.BRING_CREATURES:
            self.write_uint8(len(obj.creatures))
            for c in obj.creatures:
                self.write_uint16(c.id)
                self.write_uint16(c.quantity)
        elif mission_type == QuestType.BRING_RESOURCES:
            self._write_resources(obj.resources)
        elif mission_type == QuestType.BE_SPECIFIC_HERO:
            self.write_uint8(obj.hero_object_id)
        elif mission_type == QuestType.BE_SPECIFIC_COLOR:
            self.write_uint8(ColorEnum[obj.color.upper()].value)

        self.write_uint32(obj.limit)
        self.write_string(obj.first_visit_text)
        self.write_string(obj.next_visit_text)
        self.write_string(obj.completed_text)

    def write_events(self) -> None:
        self.write_uint32(len(self.structure.events))
        for event in self.structure.events:
            self.write_string(event.name)
            self.write_string(event.message)
            self._write_resources(event.resources)
            self.write_mask_string(event.players, 1)
            if self.map_type >= MapType.SOD:
                self.write_uint8(int(event.is_human_affected))
            self.write_uint8(int(event.is_computer_affected))
            self.write_uint16(event.first_occurrence)
            self.write_uint8(event.next_occurrence)
            self.write_base64_bytes(event.unknown, 17)

    def write(self) -> bytes:
        self._buffer = bytearray()
        self.write_header()
        self.write_players_attributes()
        self.write_victory_conditions()
        self.write_loss_conditions()
        self.write_teams()
        self.write_heroes_info()
        self.write_artifacts()
        self.write_spells()
        self.write_abilities()
        self.write_rumors()
        self.write_predefined_heroes()
        self.write_terrain()
        self.write_def_info()
        self.write_objects()
        self.write_events()
        if self.structure.trailing_unknown:
            self._buffer += base64.b64decode(self.structure.trailing_unknown)
        return bytes(self._buffer)

    def write_to_file(self, path: str | pathlib.Path) -> None:
        data = self.write()
        with gzip.open(path, 'wb') as f:
            f.write(data)


def _playstyle_to_value(name: str | None) -> int:
    if name is None:
        return 0xFF
    return ComputerPlaystyleEnum[name.upper()].value & 0xFF


def _is_empty_predefined(hero) -> bool:
    return isinstance(hero, PredefinedHeroNonConfigured)
