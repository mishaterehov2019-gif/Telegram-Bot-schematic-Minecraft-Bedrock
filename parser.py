import os
import json
import zipfile
import tempfile
import shutil
import uuid
from typing import Dict, List, Tuple, Optional
import nbtlib
from PIL import Image

class HoloGenerator:
    def __init__(self, template_dir: str):
        self.template_dir = template_dir

    def parse_mcstructure(self, file_path: str) -> Optional[Dict]:
        """Парсит .mcstructure файл"""
        try:
            data = nbtlib.load(file_path)
            
                 # Получаем данные структуры через .get()
        # NBT теги ведут себя как словари, поэтому используем .get()
        size_tag = data.get("size")
        
        # Если size_tag не найден или это не список, пытаемся найти его внутри data["size"]
        # Иногда .mcstructure хранят это поле немного иначе
        if size_tag is None:
            # Пробуем достать из корневого тега "size", который может быть словарем
            size_tag = data.get("size", {})
        
        # Теперь проверяем, что это за объект и берем координаты
        # Используем .get() для всех осей
        x = size_tag.get("x", 0)
        y = size_tag.get("y", 0)
        z = size_tag.get("z", 0)

        structure_data = {
            "name": data.get("name", "Голограмма"),
            "size": {
                "x": x,
                "y": y,
                "z": z
            },
            "palette": [],
            "blocks": []
        }
                "palette": [],
                "blocks": []
            }

            palette = data["palette"]
            for block in palette:
                block_info = {
                    "name": block.get("name", "minecraft:air"),
                    "states": {}
                }
                if "states" in block:
                    for key, value in block["states"].items():
                        block_info["states"][key] = value
                structure_data["palette"].append(block_info)

            blocks = data["blocks"]
            for block in blocks:
                block_info = {
                    "pos": [block["pos"]["x"], block["pos"]["y"], block["pos"]["z"]],
                    "state": block.get("state", 0)
                }
                structure_data["blocks"].append(block_info)

            return structure_data

        except Exception as e:
            print(f"Ошибка парсинга .mcstructure: {e}")
            return None

    def generate_holo_pack(self, structure_data: Dict, output_path: str) -> Tuple[bool, str, int]:
        """Генерирует .mcpack с голограммой и авто-спавном через стойку"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                pack_dir = os.path.join(temp_dir, "holo_pack")
                os.makedirs(pack_dir, exist_ok=True)

                # Создаём структуру пака
                self._create_pack_structure(pack_dir, structure_data)
                
                # Создаём поведенческий пак для авто-спавна
                self._create_behavior_pack(pack_dir, structure_data)
                
                # Создаём функции для голограммы
                self._create_holo_functions(pack_dir, structure_data)

                # Упаковываем в .mcpack
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(pack_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, pack_dir)
                            zipf.write(file_path, arcname)

                return True, "Голограмма готова! Просто поставь стойку для брони!", len(structure_data["blocks"])

        except Exception as e:
            print(f"Ошибка генерации .mcpack: {e}")
            return False, f"Ошибка: {str(e)}", 0

    def _create_pack_structure(self, pack_dir: str, structure_data: Dict):
        """Создаёт базовую структуру пака"""
        # Создаём папки
        os.makedirs(os.path.join(pack_dir, "behavior_pack"), exist_ok=True)
        os.makedirs(os.path.join(pack_dir, "resource_pack"), exist_ok=True)
        
        # --- Ресурс-пак ---
        rp_dir = os.path.join(pack_dir, "resource_pack")
        
        # manifest.json для ресурс-пака
        manifest = {
            "format_version": 2,
            "header": {
                "name": "HoloPrint Auto",
                "description": f"Голограмма: {structure_data['name']}",
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0],
                "min_engine_version": [1, 19, 0]
            },
            "modules": [
                {
                    "type": "resources",
                    "uuid": str(uuid.uuid4()),
                    "version": [1, 0, 0]
                }
            ]
        }
        with open(os.path.join(rp_dir, "manifest.json"), 'w') as f:
            json.dump(manifest, f, indent=2)

        # pack_icon.png
        img = Image.new('RGB', (128, 128), color=(52, 152, 219))
        img.save(os.path.join(rp_dir, "pack_icon.png"))

        # Текстуры
        os.makedirs(os.path.join(rp_dir, "textures", "blocks"), exist_ok=True)
        os.makedirs(os.path.join(rp_dir, "textures", "items"), exist_ok=True)
        os.makedirs(os.path.join(rp_dir, "texts"), exist_ok=True)
        
        with open(os.path.join(rp_dir, "texts", "languages.json"), 'w') as f:
            json.dump(["en_US"], f)
        
        with open(os.path.join(rp_dir, "texts", "en_US.lang"), 'w') as f:
            f.write("pack.name=HoloPrint Auto\npack.description=Голограмма при установке стойки")

    def _create_behavior_pack(self, pack_dir: str, structure_data: Dict):
        """Создаёт поведенческий пак с авто-спавном через стойку"""
        bp_dir = os.path.join(pack_dir, "behavior_pack")
        
        # manifest.json для поведенческого пака
        manifest = {
            "format_version": 2,
            "header": {
                "name": "HoloPrint Auto BP",
                "description": "Авто-спавн голограммы через стойку",
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0],
                "min_engine_version": [1, 19, 0]
            },
            "modules": [
                {
                    "type": "data",
                    "uuid": str(uuid.uuid4()),
                    "version": [1, 0, 0]
                }
            ],
            "dependencies": [
                {
                    "module_name": "HoloPrint Auto",
                    "version": [1, 0, 0]
                }
            ]
        }
        with open(os.path.join(bp_dir, "manifest.json"), 'w') as f:
            json.dump(manifest, f, indent=2)

        # Создаём кастомную сущность - модифицированную стойку
        entities_dir = os.path.join(bp_dir, "entities")
        os.makedirs(entities_dir, exist_ok=True)
        
        # Создаём поведение для стойки
        armor_stand_behavior = {
            "format_version": "1.19.0",
            "minecraft:entity": {
                "description": {
                    "identifier": "holo:armor_stand",
                    "is_spawnable": True,
                    "is_summonable": True,
                    "is_experimental": False
                },
                "components": {
                    "minecraft:type_family": {
                        "family": ["armor_stand", "mob"]
                    },
                    "minecraft:collision_box": {
                        "width": 0.5,
                        "height": 1.975
                    },
                    "minecraft:health": {
                        "value": 20,
                        "max": 20
                    },
                    "minecraft:damage_sensor": {
                        "triggers": [
                            {
                                "on_damage": {
                                    "filters": {
                                        "test": "is_family",
                                        "subject": "other",
                                        "value": "player"
                                    }
                                },
                                "deals_damage": False
                            }
                        ]
                    },
                    "minecraft:knockback_resistance": {
                        "value": 1.0
                    },
                    "minecraft:pushable": {
                        "is_pushable": False,
                        "is_pushable_by_piston": True
                    },
                    "minecraft:inventory": {
                        "inventory_size": 4,
                        "container_type": "armor"
                    },
                    "minecraft:interact": {
                        "interactions": [
                            {
                                "on_interact": {
                                    "filters": {
                                        "all_of": [
                                            {
                                                "test": "is_family",
                                                "subject": "other",
                                                "value": "player"
                                            }
                                        ]
                                    },
                                    "event": "holo:spawn"
                                }
                            }
                        ]
                    }
                },
                "events": {
                    "minecraft:entity_spawned": {
                        "add": {
                            "component_groups": ["holo:trigger"]
                        }
                    },
                    "holo:spawn": {
                        "run_command": {
                            "command": [
                                "function holo_spawn"
                            ]
                        }
                    }
                }
            }
        }
        
        with open(os.path.join(entities_dir, "armor_stand.json"), 'w') as f:
            json.dump(armor_stand_behavior, f, indent=2)

        # Создаём функцию для спавна голограммы
        functions_dir = os.path.join(bp_dir, "functions")
        os.makedirs(functions_dir, exist_ok=True)

        # Создаём функцию спавна голограммы
        self._create_holo_functions(functions_dir, structure_data)
        
        # Создаём функцию, которая запускается при взаимодействии со стойкой
        spawn_function = [
            "say Голограмма активирована!",
            "function holo_spawn"
        ]
        
        with open(os.path.join(functions_dir, "holo_activate.mcfunction"), 'w') as f:
            f.write("\n".join(spawn_function))

    def _create_holo_functions(self, functions_dir: str, structure_data: Dict):
        """Создаёт функции для спавна голограммы"""
        blocks = structure_data["blocks"]
        palette = structure_data["palette"]
        
        # Разбиваем на слои по 10 блоков
        layers = {}
        for block in blocks:
            pos = block["pos"]
            y = pos[1]
            layer = y // 10
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(block)

        # Создаём функцию для каждого слоя
        for layer_idx, layer_blocks in layers.items():
            commands = []
            
            # Спавним стойки для блоков в слое
            for block in layer_blocks:
                pos = block["pos"]
                palette_idx = block.get("state", 0)
                if palette_idx < len(palette):
                    block_name = palette[palette_idx]["name"]
                    if ":" in block_name:
                        block_name = block_name.split(":")[1]
                    
                    # Спавним стойку с блоком на голове
                    cmd = (
                        f"summon armor_stand {pos[0]} {pos[1]} {pos[2]} {{"
                        f"NoGravity:1b,Invisible:1b,Small:1b,"
                        f"ShowArms:0b,NoBasePlate:1b,Marker:0b,"
                        f"ArmorItems:[{{}},{{}},{{}},{{id:'minecraft:{block_name}',Count:1b}}]"
                        f"}}"
                    )
                    commands.append(cmd)

            # Функция слоя
            with open(os.path.join(functions_dir, f"layer_{layer_idx}.mcfunction"), 'w') as f:
                f.write("\n".join(commands))

        # Основная функция спавна
        all_layers = sorted(layers.keys())
        main_commands = [
            "say 🏗️ Создание голограммы...",
            f"say Всего слоёв: {len(all_layers)}",
            "say Голограмма готова!"
        ]
        
        # Добавляем вызов всех слоёв
        for layer in all_layers:
            main_commands.append(f"function layer_{layer}")
        
        # Сохраняем основную функцию
        with open(os.path.join(functions_dir, "holo_spawn.mcfunction"), 'w') as f:
            f.write("\n".join(main_commands))

        # Функция для очистки голограммы
        clear_commands = [
            "say 🧹 Очистка голограммы...",
            "kill @e[type=armor_stand,tag=!holo_stand]",
            "say ✅ Голограмма удалена!"
        ]
        
        with open(os.path.join(functions_dir, "holo_clear.mcfunction"), 'w') as f:
            f.write("\n".join(clear_commands))

        # Функция для переключения слоёв (через предметы)
        toggle_commands = []
        for i, layer in enumerate(all_layers):
            toggle_commands.append(f"execute if entity @s[tag=layer_{i}] run function layer_{i}")
            toggle_commands.append(f"execute unless entity @s[tag=layer_{i}] run function hide_layer_{i}")
        
        with open(os.path.join(functions_dir, "toggle_layers.mcfunction"), 'w') as f:
            f.write("\n".join(toggle_commands))

    def _get_block_id(self, block_name: str) -> str:
        """Конвертирует имя блока в ID для стойки"""
        # Упрощаем
        if ":" in block_name:
            block_name = block_name.split(":")[1]
        
        # Маппинг для некоторых блоков
        mapping = {
            "air": "air",
            "stone": "stone",
            "grass": "grass_block",
            "dirt": "dirt",
            "planks": "oak_planks",
            "log": "oak_log",
            "leaves": "oak_leaves",
            "glass": "glass",
            "wool": "white_wool"
        }
        
        return mapping.get(block_name, block_name)

def get_generator():
    from config import TEMPLATE_DIR
    return HoloGenerator(TEMPLATE_DIR)
