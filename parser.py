import os
import json
import uuid
import zipfile
import shutil
import nbtlib

def create_manifest(pack_name):
    # Генерация уникальных UUID для манифеста ресурс-пака
    return {
        "format_version": 2,
        "header": {
            "description": f"HoloPrint Схематика для {pack_name}",
            "name": f"HoloPrint_{pack_name}",
            "uuid": str(uuid.uuid4()),
            "version":,
            "min_engine_version": [1, 20, 0]
        },
        "modules": [
            {
                "description": "HoloPrint Ресурс пак",
                "type": "resources",
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0]
            }
        ]
    }

def build_hologram_geometry(structure_path):
    # Чтение .mcstructure файла через nbtlib
    nbt_file = nbtlib.load(structure_path)
    
    # Извлечение размеров структуры
    size = nbt_file.root['size']
    width, height, depth = int(size[0]), int(size[1]), int(size[2])
    
    # Извлечение палитры блоков и индексов блоков
    # В Bedrock структурах блоки могут лежать в слоях (block_indices)
    block_indices = nbt_file.root['structure']['block_indices'][0]
    palette = nbt_file.root['structure']['palette']['default']['block_palette']
    
    # Базовая структура геометрии Bedrock модели бронестенда
    geometry = {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": "geometry.armor_stand.holoprint",
                    "texture_width": 64,
                    "texture_height": 64,
                    "visible_bounds_width": float(width + 2),
                    "visible_bounds_height": float(height + 2),
                    "visible_bounds_offset": [0, float(height)/2, 0]
                },
                "bones": []
            }
        ]
    }
    
    # Основная кость-контейнер
    base_bone = {
        "name": "root",
        "pivot":,
        "cubes": []
    }
    geometry["minecraft:geometry"][0]["bones"].append(base_bone)

    # Послойный парсинг по вертикали (ось Y)
    # Позы Armor Stand в Bedrock (0-12). Разделяем слои блоков по позам.
    idx = 0
    for x in range(width):
        for y in range(height):
            for z in range(depth):
                block_idx = int(block_indices[idx])
                idx += 1
                
                if block_idx == -1: # Воздух
                    continue
                    
                block_data = palette[block_idx]
                block_name = block_data['name']
                if "air" in block_name:
                    continue
                
                # Каждому слою Y сопоставляем кость, управляемую позами
                # Поза Armor Stand переключает видимость/положение костей
                layer_bone_name = f"layer_y_{y}"
                
                # Ищем, создана ли уже кость для этого слоя
                layer_bone = next((b for b in geometry["minecraft:geometry"][0]["bones"] if b["name"] == layer_bone_name), None)
                if not layer_bone:
                    # Условия видимости кости привязаны к анимации/позам (через render_controllers)
                    # Для упрощения создаем кость, которая будет позиционироваться скриптом
                    layer_bone = {
                        "name": layer_bone_name,
                        "parent": "root",
                        "pivot": [0, float(y)*16, 0],
                        "cubes": []
                    }
                    geometry["minecraft:geometry"][0]["bones"].append(layer_bone)
                
                # Добавляем куб блока (в майнкрафт-координатах: 1 блок = 16 единиц текстуры)
                layer_bone["cubes"].append({
                    "origin": [float(x)*16, float(y)*16, float(z)*16],
                    "size":,
                    "uv": [0, 0] # Статическая заглушка текстуры для голограммы
                })
                
    return geometry

def compile_mcpack(structure_file_path, output_dir, file_id):
    pack_name = f"holo_{file_id}"
    work_dir = os.path.join(output_dir, pack_name)
    os.makedirs(work_dir, exist_ok=True)
    
    # 1. Создаем manifest.json
    manifest = create_manifest(pack_name)
    with open(os.path.join(work_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)
        
    # 2. Создаем директорию моделей и генерируем геометрию
    models_dir = os.path.join(work_dir, "models", "entity")
    os.makedirs(models_dir, exist_ok=True)
    
    try:
        geometry_data = build_hologram_geometry(structure_file_path)
        with open(os.path.join(models_dir, "armor_stand.geo.json"), "w", encoding="utf-8") as f:
            json.dump(geometry_data, f, indent=4)
    except Exception as e:
        shutil.rmtree(work_dir)
        raise RuntimeError(f"Ошибка при парсинге NBT структуры: {e}")

    # 3. Упаковка в .zip и переименование в .mcpack
    mcpack_path = os.path.join(output_dir, f"{pack_name}.mcpack")
    with zipfile.ZipFile(mcpack_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(work_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, work_dir)
                zipf.write(full_path, rel_path)
                
    # Очищаем временную рабочую папку
    shutil.rmtree(work_dir)
    return mcpack_path
