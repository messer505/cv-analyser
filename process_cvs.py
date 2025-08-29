import os
import uuid
import hashlib
import re
import json
import logging
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import ValidationError

from tinydb import Query, TinyDB

# 1. ADICIONE A IMPORTAÇÃO DO UTILS AQUI
from utils_cv import extract_text_from_file

from ai_prompts import GroqClient
from models.opening import Opening
from models.analysis import Analysis
from models.brief import Brief

# ---------- CONFIGURAÇÃO DE LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='processing.log',
    filemode='a'
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
if not any(isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers):
    logging.getLogger().addHandler(console_handler)


# ---------- CONFIGURAÇÃO ----------
TALENT_POOL_BASE_DIR = "banco-de-talentos"
APPLICANTS_DB_FILE = "applicants.json"
OPENINGS_DB_FILE = "openings_db.json"
MAX_ATTEMPTS = 5
MAX_WORKERS = 3

# ---------- INICIALIZAÇÃO ----------
db_openings = TinyDB(OPENINGS_DB_FILE)
openings_table = db_openings.table("openings")

db = TinyDB(APPLICANTS_DB_FILE, indent=2, ensure_ascii=False)
analysis_table = db.table("analysis")
briefs_table = db.table("briefs")
files_table = db.table("files")

ai = GroqClient()

# ---------- FUNÇÕES AUXILIARES ----------

def get_cv_paths(dir_path: str) -> List[str]:
    if not os.path.isdir(dir_path):
        return []
    return [
        os.path.join(dir_path, f)
        for f in os.listdir(dir_path)
        if f.lower().endswith((".pdf", ".docx"))
    ]

def get_file_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def is_file_processed(file_path: str, content_hash: str) -> bool:
    file = Query()
    return files_table.contains((file.path == file_path) & (file.content_hash == content_hash))

def safe_json_parse(raw_text: str) -> dict:
    if not raw_text:
        return {}
    cleaned = re.sub(r"```.*?```", "", raw_text, flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        logging.error("Nenhum JSON encontrado na resposta da IA.")
        return {}
    json_str = match.group(0).replace("'", '"')
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logging.error(f"Erro de decodificação JSON: {e}")
        json_str_fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            data = json.loads(json_str_fixed)
        except json.JSONDecodeError:
            logging.error("Falha na correção do JSON.")
            data = {}
            
    for k, v in data.items():
        if isinstance(v, str): data[k] = v # A normalização já é feita em extract_text_from_file
        elif isinstance(v, list): data[k] = [str(x) for x in v]
    return data


def try_generate(func, *args, description: str, max_attempts=MAX_ATTEMPTS):
    for attempt in range(1, max_attempts + 1):
        try:
            result = func(*args)
            if result:
                return result
            logging.warning(f"Tentativa {attempt}/{max_attempts} de '{description}' retornou vazio.")
        except Exception as e:
            logging.error(f"Tentativa {attempt}/{max_attempts} de '{description}' falhou: {e}")
    logging.error(f"Falha em '{description}' após {max_attempts} tentativas.")
    return None

# ---------- PROCESSAMENTO DE UM CV ----------
def process_cv(cv_path: str, opening: Opening):
    logging.info(f"--- Processando CV: {os.path.basename(cv_path)} para a vaga '{opening.title}' ---")
    content_hash = get_file_hash(cv_path)

    if is_file_processed(cv_path, content_hash):
        logging.info(f"CV '{cv_path}' com hash '{content_hash}' já processado. Pulando.")
        return

    # 2. A CHAMADA AGORA USA A FUNÇÃO IMPORTADA DE UTILS_CV
    cv_text = extract_text_from_file(cv_path)
    if not cv_text:
        logging.warning("Nenhum conteúdo extraído do CV. Pulando.")
        return

    brief_content = try_generate(ai.cv_brief, cv_text, description="gerar resumo do CV") or "Resumo nao gerado."
    conclusion = try_generate(ai.generate_conclusion, cv_text, json.dumps(opening.model_dump()), description="gerar conclusao critica") or "Conclusao nao gerada."
    score = try_generate(ai.generate_score, cv_text, json.dumps(opening.model_dump()), description="calcular score")
    score = float(score) if score is not None else 0.0

    analysis_prompt = f"""
    Extraia do CV um JSON válido com os seguintes campos: name, formal_education, hard_skills, soft_skills.
    CV: {cv_text}
    """
    analysis_data = try_generate(ai.generate_response, analysis_prompt, description="extração JSON de análise")
    analysis_data = safe_json_parse(analysis_data)
    
    brief_id = str(uuid.uuid4())
    analysis_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())

    try:
        brief_entry_data = {
            "id": brief_id,
            "opening_id": opening.id,
            "opening_title": opening.title,
            "content": brief_content,
            "conclusion": conclusion,
            "file": cv_path
        }
        brief_to_insert = Brief(**brief_entry_data)
        briefs_table.insert(brief_to_insert.model_dump())

        analysis_entry_data = {
            "id": analysis_id,
            "opening_id": opening.id,
            "opening_title": opening.title,
            "brief_id": brief_id,
            "name": analysis_data.get("name", "Nome nao extraido"),
            "formal_education": analysis_data.get("formal_education", ""),
            "soft_skills": analysis_data.get("soft_skills", []),
            "hard_skills": analysis_data.get("hard_skills", []),
            "score": score
        }
        analysis_to_insert = Analysis(**analysis_entry_data)
        analysis_table.insert(analysis_to_insert.model_dump())

        files_table.insert({
            "id": file_id,
            "path": cv_path,
            "content_hash": content_hash,
            "opening_id": opening.id
        })

        logging.info(f"SUCESSO: CV processado com score {score}.")

    except ValidationError as e:
        logging.error(f"Erro de validação Pydantic ao processar '{cv_path}': {e}")
    except Exception as e:
        logging.error(f"Erro inesperado ao salvar dados do CV '{cv_path}': {e}")

# ---------- ORQUESTRADOR PRINCIPAL ----------
def main():
    all_openings_data = openings_table.all()
    if not all_openings_data:
        logging.warning(f"Nenhuma vaga encontrada em '{OPENINGS_DB_FILE}'. Saindo.")
        return

    for opening_data in all_openings_data:
        try:
            opening = Opening(**opening_data)
            logging.info(f"## Processando candidatos para a vaga: {opening.title} (ID: {opening.id}) ##")
            
            cv_dir = os.path.join(TALENT_POOL_BASE_DIR, opening.folder)
            cv_paths = get_cv_paths(cv_dir)
            logging.info(f"Encontrados {len(cv_paths)} CVs em '{cv_dir}'.")

            if not cv_paths:
                continue

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(process_cv, cv_path, opening): cv_path for cv_path in cv_paths}
                for future in as_completed(futures):
                    cv_path = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        logging.error(f"Erro ao executar a thread para o CV {cv_path}: {e}")
        
        except ValidationError as e:
            logging.error(f"Vaga com dados inválidos no banco de dados. Pulando. Detalhes: {e}")
            continue

    logging.info("===== PROCESSAMENTO DE CVs FINALIZADO =====")
    logging.info(f"Todos os resultados foram salvos em '{APPLICANTS_DB_FILE}'.")

if __name__ == "__main__":
    main()