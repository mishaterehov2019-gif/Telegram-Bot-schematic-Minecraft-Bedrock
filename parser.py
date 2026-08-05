# parser.py
import io
import json
import zipfile
import uuid
import struct
import zlib
import nbtlib

# ---------- Минимальный генератор 1x1 PNG (без Pillow) ----------
def _create_png_1x1(r: int, g: int, b: int, a: int) -> bytes:
    """Возвращает байты валидного PNG размером 1x1 пиксель RGBA."""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + chunk_type + data + crc

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)   # 8-bit RGBA
    ihdr = chunk(b'IHDR', ihdr_data)
    raw = b'\x00' + struct.pack('BBBB', r, g, b, a)  # filter byte + pixel
    compressed = zlib.compress(raw)
    idat = chunk(b'IDAT', compressed)
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend

HOLOGRAM_RGBA = (0, 255, 255, 128)   # полупрозрачный бирюзовый
HOLOGRAM_PNG = _create_png_1x1(*HOLOGRAM_RGBA)
ICON_PNG = _create_png_1x1(0, 255, 255, 128)  # та же иконка

# ---------- Генерация .mcpack ----------
def generate_mcpack(structure_bytes: bytes) -> bytes:
    """
    Принимает байты .mcstructure, возвращает байты .mcpack (zip-архива).
    Генерирует голограмму постройки с послойным отображением через позы Armor Stand.
    """
    # 1. Парсинг NBT
    f = io.BytesIO(structure_bytes)
    root = nbtlib.load(f)
    structure = root["structure"]
    size = list(structure["size"])            # [x, y, z]
    size_x, size_y, size_z = size

    # Защита от слишком высокой постройки (поз Armor Stand 0-12)
    max_layer = min(size_y - 1, 12)
    layer_cap_note = ""
    if size_y > 13:
        layer_cap_note = " (постройка выше 13 блоков, отображаются только первые 13 слоёв)"

    # Палитра
    palette = structure["palette"]["default"]["block_palette"]
    block_indices = structure["block_indices"]   # [z][y][x]

    # Собираем блоки по слоям Y (игнорируем air)
    layers = {y: [] for y in range(max_layer + 1)}
    for z in range(size_z):
        for y in range(min(size_y, max_layer + 1)):
            row = block_indices[z][y]
            for x in range(size_x):
                idx = row[x]
                if 0 <= idx < len(palette):
                    name = str(palette[idx]["name"])
                else:
                    name = "minecraft:air"
                if name != "minecraft:air":
                    layers[y].append((x, y, z))   # координаты блока

    # Определяем максимальную позу по фактическим слоям
    max_pose = max_layer   # даже если выше слои пусты, оставим до max_layer

    # Создаём zip в памяти
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
                "min_engine_version": [1, 16, 0]
            },
            "modules": [
                {
                    "type": "resources",
                    "uuid": module_uuid,
                    "version": [1, 0, 0]
                }
            ]
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # pack_icon.png
        zf.writestr("pack_icon.png", ICON_PNG)

        # Текстура для голограммы
        zf.writestr("textures/entity/hologram.png", HOLOGRAM_PNG)

        # Геометрии для каждой позы (0 … max_pose)
        for pose in range(max_pose + 1):
            bones = []
            for y in range(pose + 1):
                if y in layers and layers[y]:
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
            geometry = {
                "format_version": "1.12.0",
                "minecraft:geometry": [
                    {
                        "description": {
                            "identifier": f"geometry.hologram_pose_{pose}",
                            "texture_width": 1,
                            "texture_height": 1
                        },
                        "bones": bones
                    }
                ]
            }
            zf.writestr(
                f"models/entity/geometry.hologram_pose_{pose}.json",
                json.dumps(geometry, indent=2)
            )

        # Render controller для выбора геометрии по позе
        geo_array = [f"geometry.hologram_pose_{i}" for i in range(max_pose + 1)]
        render_controller = {
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
        zf.writestr(
            "render_controllers/armor_stand_hologram.render_controllers.json",
            json.dumps(render_controller, indent=2)
        )

        # Клиентская сущность, заменяющая бронестойку
        client_entity = {
            "format_version": "1.10.0",
            "minecraft:client_entity": {
                "description": {
                    "identifier": "minecraft:armor_stand",
                    "materials": {
                        "default": "entity_alphatest"
                    },
                    "textures": {
                        "default": "textures/entity/hologram"
                    },
                    "geometry": {
                        "default": "geometry.hologram_pose_0"
                    },
                    "render_controllers": [
                        "controller.render.armor_stand_hologram"
                    ]
                }
            }
        }
        zf.writestr("entity/armor_stand.entity.json", json.dumps(client_entity, indent=2))

    return zip_buf.getvalue()
