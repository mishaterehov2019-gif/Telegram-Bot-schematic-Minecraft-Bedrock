def build_hologram_geometry(structure_path):
    # Загружаем файл с явным указанием Little Endian (формат Бедрок)
    nbt_file = nbtlib.load(structure_path, byteorder="little")
    
    # Преобразуем элементы NBT-размеров в стандартный Python-список чисел [X, Y, Z]
    size_list = [int(x) for x in nbt_file.root['size']]
    width = size_list[0]   # X
    height = size_list[1]  # Y
    depth = size_list[2]   # Z
    
    # В Bedrock block_indices — это словарь (Compound). Основной слой блоков лежит под ключом '0' (или строкой "0")
    # Достаем его и принудительно превращаем в плоский список целых чисел Python
    raw_indices = nbt_file.root['structure']['block_indices']
    
    # Пытаемся получить слой 0 как по индексу 0, так и по строковому ключу "0" для совместимости версий
    if "0" in raw_indices:
        layer_0 = raw_indices["0"]
    else:
        layer_0 = raw_indices[0]
        
    block_indices = [int(x) for x in layer_0]
    
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

    # В Minecraft Bedrock индексация слоев идет строго по формуле: (x * height + y) * depth + z
    # Поэтому циклы должны идти в порядке: X -> Y -> Z
    for x in range(width):
        for y in range(height):
            for z in range(depth):
                # Математический расчет индекса блока в массиве Bedrock
                idx = (x * height + y) * depth + z
                
                if idx >= len(block_indices):
                    break
                    
                block_idx = block_indices[idx]
                
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
