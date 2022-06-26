import json

from map_processors.base import MapParser


class MapParserWriter(MapParser):
    def __init__(
        self, filename: str, output_filename: str = None, encoding='cp1251', *args, **kwargs
    ) -> None:
        super().__init__(filename, *args, **kwargs)
        self.output_data_binary = []

        if not output_filename:
            output_filename, ext = filename.rsplit('.', maxsplit=1)
            self.output_filename = f'{output_filename}_output.{ext}'

    def process_uint8(self) -> int:
        value = self.map_binary[self._cursor_position]
        self._cursor_position += 1
        self.output_data_binary.append(value.to_bytes(1, 'little'))
        return value

    def process_uint16(self) -> int:
        value = self.bytes_to_int(
            self.map_binary[self._cursor_position:self._cursor_position + 2]
        )
        self.output_data_binary.append(
            self.map_binary[self._cursor_position:self._cursor_position + 2]
        )
        self._cursor_position += 2
        return value

    def process_uint32(self, write_same=True) -> int:
        value = self.bytes_to_int(
            self.map_binary[self._cursor_position:self._cursor_position + 4]
        )
        if write_same:
            self.output_data_binary.append(
                self.map_binary[self._cursor_position:self._cursor_position + 4]
            )
        self._cursor_position += 4
        return value

    def process_n_bytes(self, n: int) -> bytes:
        result = self.map_binary[self._cursor_position:self._cursor_position + n]
        self.output_data_binary.append(
            self.map_binary[self._cursor_position:self._cursor_position + n]
        )
        self._cursor_position += n
        return result

    def base_process_string(self) -> str:
        string_len = self.process_uint32()
        string_end = self._cursor_position + string_len
        string_from_map = self.map_binary[self._cursor_position:string_end].decode(self.encoding)
        self.output_data_binary.append(
            self.map_binary[self._cursor_position:string_end]
        )
        self._cursor_position = string_end
        return string_from_map

    def write_output_file(self):
        if not self.data:
            # along with map parsing alternative binary data is filled
            self.get_structured_data()

        output_binary = b''.join(self.output_data_binary)
        with open(self.output_filename, 'wb') as f:
            f.write(output_binary)


class MapTranslationFileGenerator(MapParser):
    def __init__(
        self, filename: str, output_filename: str = None, encoding='cp1251', *args, **kwargs
    ) -> None:
        super().__init__(filename)
        self.strings_to_translate = {}
        if not output_filename:
            output_filename, ext = filename.rsplit('.', maxsplit=1)
            self.output_filename = f'{output_filename}_translations.json'

    def process_string(self) -> str:
        string_from_map = super().process_string()
        self.strings_to_translate[string_from_map] = ''
        return string_from_map

    def write_output_file(self):
        if not self.data:
            self.get_structured_data()

        with open(self.output_filename, 'w', encoding=self.encoding) as f:
            f.write(
                json.dumps(self.strings_to_translate, indent=4, ensure_ascii=False)
            )


class MapSimpleTranslator(MapParserWriter):
    def __init__(
        self,
        filename: str,
        translations_filename: str = None,
        output_filename: str = None,
        encoding='cp1251',
        *args,
        **kwargs,
    ) -> None:
        super().__init__(filename, *args, **kwargs)
        if not translations_filename:
            translations_filename, ext = filename.rsplit('.', maxsplit=1)
            self.translations_filename = f'{translations_filename}_translations.json'
        if not output_filename:
            output_filename, ext = filename.rsplit('.', maxsplit=1)
            self.output_filename = f'{output_filename}_translated.{ext}'

        with open(self.translations_filename, 'r', encoding=self.encoding) as f:
            self.translations = json.load(f)

    def process_string(self) -> str:
        string_len = self.process_uint32(write_same=False)
        string_end = self._cursor_position + string_len
        string_from_map = self.map_binary[self._cursor_position:string_end].decode(self.encoding)
        self._cursor_position = string_end

        if self.translations.get(string_from_map):
            string_from_map = self.translations[string_from_map]
            string_len = len(string_from_map)

        self.output_data_binary.append(string_len.to_bytes(4, 'little'))
        self.output_data_binary.append(string_from_map.encode(self.encoding))

        return string_from_map

    def write_output_file(self):
        if not self.data:
            self.get_structured_data()

        output_binary = b''.join(self.output_data_binary)
        with open(self.output_filename, 'wb') as f:
            f.write(output_binary)
