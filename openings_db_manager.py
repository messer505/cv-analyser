import json
import os
import uuid

def load_openings_db():
    """Carrega o banco de dados de vagas."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file_path = os.path.join(script_dir, 'openings_db.json')
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('openings', {})
    except (FileNotFoundError, json.JSONDecodeError):
        # Cria o arquivo se ele não existir ou estiver corrompido
        save_openings_db({})
        return {}

def save_openings_db(openings):
    """Salva o banco de dados de vagas."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file_path = os.path.join(script_dir, 'openings_db.json')
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump({"openings": openings}, f, indent=4)

def create_new_opening(title, intro, pre_requisites, main_activities, add_infos, folder):
    """Cria e salva uma nova vaga."""
    openings = load_openings_db()
    
    new_id = str(uuid.uuid4())
    
    new_opening = {
        "id": new_id,
        "title": title,
        "intro": intro,
        "pre_requisites": pre_requisites,
        "main_activities": main_activities,
        "add_infos": add_infos,
        "folder": folder
    }
    
    openings[title] = new_opening
    save_openings_db(openings)

    # Cria a pasta de currículos se ela não existir
    folder_path = os.path.join("banco-de-talentos", folder)
    os.makedirs(folder_path, exist_ok=True)
    
    return new_opening