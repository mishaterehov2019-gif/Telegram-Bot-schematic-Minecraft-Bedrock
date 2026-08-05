import io
import json
import uuid
import zipfile
import struct
import zlib

import nbtlib

# ---------- Генератор однопиксельного PNG (без Pillow) ----------
def _create_png_1x1(r: int, g: int, b: int, a: int) -> bytes:
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + chunk_type + data + crc

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)  # RGBA
    ihdr = chunk(b'IHDR', ihdr_data)
    raw = b'\x00' + struct.pack('BBBB', r, g, b, a)
    compressed = zlib.compress(raw)
    idat = chunk(b'IDAT', compressed)
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend

HOLOGRAM_PNG = _create_png_1x1(0, 255, 255, 128)
ICON_PNG = _create_png_1x1(0, 255, 255, 128)

# ---------- Основная функция ----------
def generate_mcpack(structure_bytes: bytes) -> bytes:
    """
    Принимает байты .mcstructure, возвращает байты готового .mcpack (zip).
    Постройка визуализируется послойно через позы бронестойки (0–12).
    """
    f = io.BytesIO(structure_bytes)
    root_nbt = nbtlib.load(f)                     # nbtlib.File
    structure = root_nbt.root["structure"]        # доступ к корневому тегу ""
    size_raw = structure["size"]
    size_x, size_y, size_z = int(size_raw[0]), int(size_raw[1]), int(size_raw[2])

    # Палитра
    palette_tag = structure["palette"]["default"]["block_palette"]
    # block_indices — список слоёв по Z, каждый слой содержит Y строк, каждая строка — X индексов
    block_indices = list(structure["block_indices"])  # принудительно в list для удобства

    # Разложим блоки по слоям (ось Y). Всё, что выше 12, сложим в Y=12.
    layers = {y: [] for y in range(13)}   # 0..12
    for z in range(size_z):
        z_slice = list(block_indices[z])   # список по Y
        for y in range(size_y):
            y_row = list(z_slice[y])
            target_y = y if y <= 12 else 12
            for x in range(size_x):
                idx = y_row[x]
                # Получаем имя блока
                if 0 <= idx < len(palette_tag):
                    block_name = str(palette_tag[idx]["name"])
                else:
                    block_name = "minecraft:air"
                if block_name != "minecraft:air":
                    layers[target_y].append((x, y, z))   # сохраняем реальную Y для правильной позиции в кубе

    # Определим максимальную позу – последний непустой слой, но не меньше 0
    max_pose = 12
    while max_pose > 0 and not layers[max_pose]:
        max_pose -= 1

    # ---------- Сборка .mcpack ----------
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # manifest.json
        header_uuid = str(uuid.uuid4())
        module_uuid = str(uuid.uuid4())
        manifest = {
            "format_version": 2,
            "header": {
                "description": "Hologram structure pack",
                "name": "Structure Hologram",
                "uuid": header_uuid,
                "version": [1, 0, 0],
                "min_engine_version": [1, 20, 0]
            },
            "modules": [{
                "type": "resources",
                "uuid": module_uuid,
                "version": [1, 0, 0]
            }]
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("pack_icon.png", ICON_PNG)

        # Текстура
        zf.writestr("textures/entity/hologram.png", HOLOGRAM_PNG)

        # Геометрии для поз 0..max_pose
        for pose in range(max_pose + 1):
            bones = []
            for y in range(pose + 1):
                if not layers[y]:
                    continue
                cubes = []
                for (bx, by, bz) in layers[y]:
                    cubes.append({
                        "origin": [bx + 0.5, by + 0.5, bz + 0.5],
                        "size": [1, 1, 1],
                        "uv": [0, 0]
                    })
                bones.append({
                    "name": f"layer_{y}",
                    "pivot": [0, 0, 0],
                    "cubes": cubes
                })
            geo = {
                "format_version": "1.12.0",
                "minecraft:geometry": [{
                    "description": {
                        "identifier": f"geometry.hologram_pose_{pose}",
                        "texture_width": 1,
                        "texture_height": 1
                    },
                    "bones": bones
                }]
            }
            zf.writestr(f"models/entity/geometry.hologram_pose_{pose}.json", json.dumps(geo, indent=2))

        # Render controller
        geo_array = [f"geometry.hologram_pose_{i}" for i in range(max_pose + 1)]
        rc = {
            "format_version": "1.10.0",
            "render_controllers": {
                "controller.render.armor_stand_hologram": {
                    "arrays": {
                        "geometries": {
                            "Array.geos": geo_array
                        }
                    },
                    "geometry": f"Array.geos[math.min(q.pose_index, {max_pose})]",
                    "materials": [{"*": "entity_alphatest"}],
                    "textures": ["textures/entity/hologram"]
                }
            }
        }
        zf.writestr("render_controllers/armor_stand_hologram.render_controllers.json", json.dumps(rc, indent=2))

        # Клиентская сущность, заменяющая стойку для брони
        client_entity = {
            "format_version": "1.10.0",
            "minecraft:client_entity": {
                "description": {
                    "identifier": "minecraft:armor_stand",
                    "materials": {"default": "entity_alphatest"},
                    "textures": {"default": "textures/entity/hologram"},
                    "geometry": {"default": "geometry.hologram_pose_0"},
                    "render_controllers": ["controller.render.armor_stand_hologram"]
                }
            }
        }
        zf.writestr("entity/armor_stand.entity.json", json.dumps(client_entity, indent=2))

    return zip_buf.getvalue()
