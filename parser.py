import nbtlib
from typing import Optional, Dict, List, Any

class HoloGenerator:
    def __init__(self, template_dir: str):
        self.template_dir = template_dir
        self.structure_data = None

    def parse_mcstructure(self, file_path: str) -> Optional[Dict]:
        """
        Парсит .mcstructure файл с защитой от любых ошибок формата.
        Поддерживает как списки, так и словари для поля 'size',
        а также корректно обрабатывает вложенные теги библиотеки nbtlib.
        """
        try:
            data = nbtlib.load(file_path)
            
            # --- 1. Обработка размера структуры (size) ---
            size_data = data.get("size", [0, 0, 0])
            if isinstance(size_data, list):
                # Если это список [x, y, z] (стандартный формат .mcstructure)
                x = size_data[0] if len(size_data) > 0 else 0
                y = size_data[1] if len(size_data) > 1 else 0
                z = size_data[2] if len(size_data) > 2 else 0
            else:
                # Если это словарь {'x': 10, 'y': 10, 'z': 10}
                x = size_data.get("x", 0)
                y = size_data.get("y", 0)
                z = size_data.get("z", 0)

            # --- 2. Обработка палитры блоков (palette) ---
            raw_palette = data.get("palette", [])
            if hasattr(raw_palette, "value"):
                # Библиотека nbtlib часто оборачивает списки в TagList
                palette = raw_palette.value
            elif isinstance(raw_palette, list):
                palette = raw_palette
            else:
                palette = []

            # --- 3. Обработка списка блоков (blocks) ---
            raw_blocks = data.get("blocks", [])
            if hasattr(raw_blocks, "value"):
                blocks = raw_blocks.value
            elif isinstance(raw_blocks, list):
                blocks = raw_blocks
            else:
                blocks = []

            # Формируем итоговый объект для остальных методов
            self.structure_data = {
                "name": data.get("name", "Голограмма"),
                "size": {
                    "x": x,
                    "y": y,
                    "z": z
                },
                "palette": palette,
                "blocks": blocks
            }
            
            return self.structure_data
            
        except Exception as e:
            print(f"Критическая ошибка при парсинге .mcstructure: {e}")
            return None

    def _get_block_id(self, block_name: str) -> str:
        """Безопасное получение ID блока (заглушка)"""
        if not block_name:
            return "air"
        # Убираем префикс minecraft:, если он есть
        return block_name.replace("minecraft:", "")

    def _create_pack_structure(self, output_path: str) -> bool:
        """
        Создает структуру пака (заглушка).
        Тут ты пишешь свою логику генерации файлов структуры (.mcstructure на выходе или что-то подобное).
        """
        if not self.structure_data:
            print("Ошибка: Нет данных о структуре.")
            return False
        
        print(f"Генерация структуры по пути: {output_path}")
        # Пример доступа к безопасным данным:
        # size_x = self.structure_data['size']['x']
        return True

    def _create_behavior_pack(self) -> bool:
        """Заглушка для создания поведенческого пака"""
        print("Генерация behavior pack (заглушка)...")
        return True

    def _create_holo_functions(self) -> bool:
        """Заглушка для создания функций голограммы"""
        print("Генерация функций (заглушка)...")
        return True

    def generate_holo_pack(self, output_path: str) -> Dict:
        """
        Основной метод генерации голографического пака.
        Вызывает все остальные методы и возвращает результат.
        """
        if not self.structure_data:
            return {"status": "error", "message": "Сначала загрузите структуру через parse_mcstructure()"}

        # Прогоняем все этапы генерации
        pack_ok = self._create_pack_structure(output_path)
        func_ok = self._create_holo_functions()
        behavior_ok = self._create_behavior_pack()

        return {
            "status": "success" if (pack_ok and func_ok and behavior_ok) else "partial",
            "size": self.structure_data["size"],
            "blocks_count": len(self.structure_data["blocks"]),
            "palette_count": len(self.structure_data["palette"]),
            "message": "Пак голограммы готов к сборке."
        }

    def get_generator(self):
        """Возвращает объект генератора для использования в боте"""
        return self
