import io
import os
import tempfile
import zipfile
import struct
import zlib
import uuid
from typing import List, Tuple

import nbtlib
from nbtlib.tag import Compound, List as NBTList

def create_png(width: int, height: int, rgba: Tuple[int, int, int, int]) -> bytes:
    """Генератор валидного PNG без сторонних библиотек."""
    def chunk(ctype: bytes, data: bytes) -> bytes:
        c = ctype + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        return struct.pack('>I', len(data)) + c + crc

    signature = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr = chunk(b'IHDR', ihdr_data)

    raw = b''
    for y in range(height):
        raw += b'\x00'  # filter none
        for x in range(width):
            raw += struct.pack('BBBB', *rgba)
    compressed = zlib.compress(raw)
    idat = chunk(b'IDAT', compressed)
    iend = chunk(b'IEND', b'')
    return signature + ihdr + idat + iend

def parse_mcstructure(file_bytes: bytes) -> List[Tuple[int, int, int, str]]:
    """
    Парсит .mcstructure (Little-Endian) и возвращает список (x, y, z, block_name).
    Поднимает исключение при ошибке парсинга.
    """
    # ИСПРАВЛЕНО: loads вместо load и передаём байты напрямую
    root: Compound = nbtlib.loads(file_bytes, byteorder='little')
    size_tag = root['size']
    size_x = int(size_tag[0])
    size_y = int(size_tag[1])
    size_z = int(size_tag[2])

    structure: Compound = root['structure']
    block_indices: NBTList = structure['block_indices']
    palette: Compound = structure['palette']
    default_palette: Compound = palette['default']
    block_palette: NBTList = default_palette['block_palette']

    expected_len = size_x * size_y * size_z
    if len(block_indices) != expected_len:
        raise ValueError(f"Некорректная длина block_indices: ожидалось {expected_len}, получено {len(block_indices)}")

    result = []
    for y in range(size_y):
        for z in range(size_z):
            for x in range(size_x):
                idx_1d = x + z * size_x + y * size_x * size_z
                entry = block_indices[idx_1d]
                if isinstance(entry, list):
                    palette_index = int(entry[0]) if len(entry) > 0 else -1
                else:
                    palette_index = int(entry)

                if palette_index < 0 or palette_index >= len(block_palette):
                    continue

                block_data = block_palette[palette_index]
                block_name = str(block_data['name'])
                result.append((x, y, z, block_name))
    return result

def generate_geometry(blocks: List[Tuple[int, int, int, str]]) -> dict:
    """Создаёт геометрию для Armor Stand с костями для каждого блока."""
    bones = [{"name": "body", "pivot": [0, 0, 0]}]
    for (x, y, z, block_name) in blocks:
        bone_name = f"block_{x}_{y}_{z}"
        bones.append({
            "name": bone_name,
            "parent": "body",
            "pivot": [x, y, z],
            "cubes": [{
                "origin": [0, 0, 0],
                "size": [1, 1, 1],
                "uv": [0, 0]
            }]
        })
    geometry = {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": "geometry.armor_stand_custom",
                    "texture_width": 16,
                    "texture_height": 16
                },
                "bones": bones
            }
        ]
    }
    return geometry

def generate_animation(blocks: List[Tuple[int, int, int, str]]) -> dict:
    """Анимация, делающая видимыми кости блоков, если pose_index >= Y."""
    bones_visibility = {}
    for (x, y, z, _) in blocks:
        bone_name = f"block_{x}_{y}_{z}"
        bones_visibility[bone_name] = {
            "visible": f"query.armor_stand_pose_index >= {y}"
        }
    animation = {
        "format_version": "1.8.0",
        "animations": {
            "animation.armor_stand.visibility": {
                "loop": True,
                "bones": bones_visibility
            }
        }
    }
    return animation

def generate_entity_definition() -> dict:
    """Клиентское определение сущности."""
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": "minecraft:armor_stand",
                "materials": {"default": "entity_alphatest"},
                "textures": {"default": "textures/blocks/hologram"},
                "geometry": {"default": "geometry.armor_stand_custom"},
                "animations": {
                    "layer_visibility": "animation.armor_stand.visibility"
                },
                "scripts": {
                    "animate": ["layer_visibility"]
                }
            }
        }
    }

def generate_manifest() -> dict:
    """Манифест с уникальными UUID."""
    return {
        "format_version": 2,
        "header": {
            "description": "Structure hologram pack",
            "name": "Structure Hologram",
            "uuid": str(uuid.uuid4()),
            "version": [1, 0, 0],
            "min_engine_version": [1, 13, 0]
        },
        "modules": [
            {
                "type": "resources",
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0]
            }
        ]
    }

def pack_mcpack(geometry: dict, animation: dict, entity: dict, manifest: dict) -> bytes:
    """Упаковывает все файлы в ZIP (mcpack)."""
    hologram_tex = create_png(16, 16, (0, 100, 200, 100))
    pack_icon = create_png(64, 64, (0, 80, 180, 255))

    with tempfile.TemporaryDirectory() as tmpdir:
        base = os.path.join(tmpdir, "hologram_pack")
        os.makedirs(os.path.join(base, "entity"), exist_ok=True)
        os.makedirs(os.path.join(base, "models", "entity"), exist_ok=True)
        os.makedirs(os.path.join(base, "animations"), exist_ok=True)
        os.makedirs(os.path.join(base, "textures", "blocks"), exist_ok=True)

        import json
        with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)
        with open(os.path.join(base, "pack_icon.png"), "wb") as f:
            f.write(pack_icon)
        with open(os.path.join(base, "entity", "armor_stand.entity.json"), "w", encoding="utf-8") as f:
            json.dump(entity, f, indent=4)
        with open(os.path.join(base, "models", "entity", "geometry.armor_stand_custom.json"), "w", encoding="utf-8") as f:
            json.dump(geometry, f, indent=4)
        with open(os.path.join(base, "animations", "armor_stand.animation.json"), "w", encoding="utf-8") as f:
            json.dump(animation, f, indent=4)
        with open(os.path.join(base, "textures", "blocks", "hologram.png"), "wb") as f:
            f.write(hologram_tex)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_dir, dirs, files in os.walk(base):
                for file in files:
                    full_path = os.path.join(root_dir, file)
                    arcname = os.path.relpath(full_path, tmpdir)
                    zf.write(full_path, arcname)
        return zip_buffer.getvalue()
