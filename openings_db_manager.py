import json
import os
from typing import List, Dict, Any

# Define o nome do arquivo do banco de dados
DB_FILE = 'openings_db.json'

def load_openings_db() -> Dict[str, Any]:
    """Carrega o banco de dados de vagas do arquivo JSON."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file_path = os.path.join(script_dir, DB_FILE)
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('openings', {})
    except (FileNotFoundError, json.JSONDecodeError):
        # Cria o arquivo se ele não existir ou estiver corrompido
        save_openings_db({})
        return {}

def save_openings_db(openings: Dict[str, Any]):
    """Salva o banco de dados de vagas no arquivo JSON."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file_path = os.path.join(script_dir, DB_FILE)
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump({"openings": openings}, f, indent=4)

def create_new_opening(
    title: str,
    intro: str,
    pre_requisites: str,
    main_activities: str,
    add_infos: str,
    folder: str,
    local: str = None,
    nivel: str = None,
    disponibilidade: str = None,
    soft_skills: List[str] = [],
    hard_skills: List[str] = [],
    opening_id: str = None
) -> Dict[str, Any]:
    """
    Cria uma nova vaga com base nos dados fornecidos e a salva no banco de dados.
    Todos os campos da vaga são incluídos para análise completa.
    """
    openings = load_openings_db()
    
    # Cria o dicionário da nova vaga com todos os campos
    new_opening = {
        "id": opening_id,
        "title": title,
        "intro": intro,
        "pre_requisites": pre_requisites,
        "main_activities": main_activities,
        "add_infos": add_infos,
        "folder": folder,
        "local": local,
        "nivel": nivel,
        "disponibilidade": disponibilidade,
        "soft_skills": soft_skills,
        "hard_skills": hard_skills
    }
    
    # Adiciona a nova vaga ao dicionário de vagas, usando o título como chave
    openings[title] = new_opening
    
    # Salva o banco de dados atualizado
    save_openings_db(openings)

    # Cria a pasta de currículos se ela não existir
    folder_path = os.path.join("banco-de-talentos", folder)
    os.makedirs(folder_path, exist_ok=True)
    
    return new_opening