import os
import json
import uuid
import zipfile
import shutil
import nbtlib

def create_manifest(pack_name):
    v_head = list()
    v_head.append(1)
    v_head.append(0)
    v_head.append(0)
    
    v_engine = list()
    v_engine.append(1)
    v_engine.append(14)
    v_engine.append(0)

    return {
        "format_version": 2,
        "header": {
            "description": f"HoloPrint Схематика для {pack_name}",
            "name": f"HoloPrint_{pack_name}",
            "uuid": str(uuid.uuid4()),
            "version": v_head,
            "min_engine_version": v_engine
        },
        "modules": [
            {
                "description": "HoloPrint Ресурс пак",
                "type": "resources",
                "uuid": str(uuid.uuid4()),
                "version": v_head
            }
        ]
    }

def build_hologram_geometry(structure_path):
    # Загружаем файл с явным указанием Little Endian (формат Бедрок)
    nbt_file = nbtlib.load(structure_path, byteorder="little")
    
    # Исправление чтения размеров: преобразуем элементы NBT-списка в чистый Python-список чисел
    size_list = [int(x) for x in nbt_file.root['size']]
    width = size_list[0]   # X
    height = size_list[1]  # Y
    depth = size_list[2]   # Z
    
    # В Bedrock блок-индексы хранятся в списке слоев 'block_indices'
    # layer_0 - это обычные блоки, layer_1 - вода/растения внутри блоков. Берем layer_0.
    all_layers = nbt_file.root['structure']['block_indices']
    
    # Преобразуем индексы блоков в плоский Python-список целых чисел
    # Это решает ошибку "list indices must be integers or slices, not str"
    block_indices = [int(x) for x in all_layers[0]]
    
    # Извлекаем палитру блоков
    palette = nbt_file.root['structure']['palette']['default']['block_palette']
    
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
                    "visible_bounds_offset": list([0.0, float(height)/2, 0.0])
                },
                "bones": list()
            }
        ]
    }
    
    piv_root = list()
    piv_root.append(0.0)
    piv_root.append(0.0)
    piv_root.append(0.0)
    
    base_bone = {
        "name": "root",
        "pivot": piv_root,
        "cubes": list()
    }
    geometry["minecraft:geometry"]["bones"].append(base_bone)

    # Обходим трехмерную матрицу постройки
    idx = 0
    for x in range(width):
        for y in range(height):
            for z in range(depth):
                if idx >= len(block_indices):
                    break
                    
                block_idx = block_indices[idx]
                idx += 1
                
                # Индекс -1 означает отсутствие блока (воздух)
                if block_idx == -1:
                    continue
                    
                # Безопасно берем данные блока из палитры по индексу
                block_data = palette[block_idx]
                block_name = str(block_data['name'])
                
                # Пропускаем воздух
                if "air" in block_name:
                    continue
                
                layer_bone_name = f"layer_y_{y}"
                
                layer_bone = next((b for b in geometry["minecraft:geometry"]["bones"] if b["name"] == layer_bone_name), None)
                if not layer_bone:
                    piv_layer = list()
                    piv_layer.append(0.0)
                    piv_layer.append(float(y)*16.0)
                    piv_layer.append(0.0)
                    
                    layer_bone = {
                        "name": layer_bone_name,
                        "parent": "root",
                        "pivot": piv_layer,
                        "cubes": list()
                    }
                    geometry["minecraft:geometry"]["bones"].append(layer_bone)
                
                c_origin = list()
                c_origin.append(float(x)*16.0)
                c_origin.append(float(y)*16.0)
                c_origin.append(float(z)*16.0)
                
                c_size = list()
                c_size.append(16.0)
                c_size.append(16.0)
                c_size.append(16.0)
                
                c_uv = list()
                c_uv.append(0.0)
                c_uv.append(0.0)
                
                layer_bone["cubes"].append({
                    "origin": c_origin,
                    "size": c_size,
                    "uv": c_uv
                })
                
    return geometry

def compile_mcpack(structure_file_path, output_dir, file_id):
    pack_name = f"holo_{file_id}"
    work_dir = os.path.join(output_dir, pack_name)
    os.makedirs(work_dir, exist_ok=True)
    
    manifest = create_manifest(pack_name)
    with open(os.path.join(work_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)
        
    models_dir = os.path.join(work_dir, "models", "entity")
    os.makedirs(models_dir, exist_ok=True)
    
    try:
        geometry_data = build_hologram_geometry(structure_file_path)
        with open(os.path.join(models_dir, "armor_stand.geo.json"), "w", encoding="utf-8") as f:
            json.dump(geometry_data, f, indent=4)
    except Exception as e:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        raise RuntimeError(f"Ошибка при парсинге NBT структуры: {e}")

    mcpack_path = os.path.join(output_dir, f"{pack_name}.mcpack")
    with zipfile.ZipFile(mcpack_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(work_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, work_dir)
                zipf.write(full_path, rel_path)
                
    shutil.rmtree(work_dir)
    return mcpack_path
