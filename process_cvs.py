import os
import threading
import concurrent.futures
import logging
from typing import Dict, Any, List
import json
from ai_prompts import GroqClient 
from utils_cv import extract_text_from_file

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações globais
MAX_WORKERS = 1
OUTPUT_DIR = "analises_cv"
GROQ_CLIENT = GroqClient()

# --- CARREGAMENTO DO ARQUIVO DE VAGAS ---
def load_job_openings() -> Dict[str, Any]:
    """
    Carrega os dados das vagas do arquivo JSON e retorna um dicionário
    mapeando o título da vaga para seus dados.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file_path = os.path.join(script_dir, 'openings_db.json')
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Valida se a chave 'openings' existe e é um dicionário
            if "openings" not in data or not isinstance(data["openings"], dict):
                logger.error(f"Erro: A chave 'openings' não foi encontrada ou não é um dicionário em '{json_file_path}'.")
                return {}
            
            openings_dict = data["openings"]
            
            # Constrói o dicionário principal usando o título como chave
            processed_openings = {}
            for key, job in openings_dict.items():
                if 'title' in job and 'id' in job and 'folder' in job:
                    processed_openings[job['title']] = job
                else:
                    logger.warning(f"Vaga com ID '{key}' tem formato inválido. Pulando.")

            return processed_openings

    except FileNotFoundError:
        logger.error(f"Erro: O arquivo '{json_file_path}' não foi encontrado.")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Erro: O arquivo '{json_file_path}' não é um JSON válido.")
        return {}

JOB_OPENINGS = load_job_openings()
# --- FIM DO CARREGAMENTO ---

# Lock para garantir que a escrita no console não se misture
console_lock = threading.Lock()

def process_single_cv(cv_path: str, opening_data: Dict[str, Any]):
    """Processa um único CV e gera a análise de alinhamento."""
    
    MAX_RETRIES = 3
    retries = 0
    full_analysis = None
    
    try:
        with console_lock:
            logger.info(f"--- Processando CV: {os.path.basename(cv_path)} para a vaga '{opening_data.get('title', 'N/A')}' (ID: {opening_data.get('id', 'N/A')}) ---")

        cv_text = extract_text_from_file(cv_path)
        
        # Verifica se o texto é inválido ou muito curto
        if not cv_text or len(cv_text.split()) < 500:
            with console_lock:
                logger.error(f"O conteúdo extraído de '{os.path.basename(cv_path)}' é inválido ou muito curto. Pulando.")
            return
        
        # Limita e limpa o texto para garantir uma requisição segura
        cleaned_cv_text = ' '.join(cv_text.split()[:4000])
        
    except Exception as e:
        with console_lock:
            logger.error(f"Erro ao extrair texto do CV {os.path.basename(cv_path)}: {e}")
        return

    # Lógica de retentativa para a chamada da API
    while retries < MAX_RETRIES:
        try:
            # Concatena os campos relevantes para a descrição da vaga
            job_description = (
                opening_data.get('intro', '') + ' ' + 
                opening_data.get('main_activities', '') + ' ' + 
                opening_data.get('add_infos', '') + ' ' +
                opening_data.get('pre_requisites', '')
            ).strip()

            full_analysis = GROQ_CLIENT.generate_full_cv_analysis(cleaned_cv_text, job_description)
            
            # Verifica se a resposta é válida
            if full_analysis and 'conclusion' in full_analysis and 'score' in full_analysis:
                break 
            
            with console_lock:
                logger.warning(f"Resposta incompleta da API para {os.path.basename(cv_path)}. Tentando novamente ({retries + 1}/{MAX_RETRIES}).")
            retries += 1
            
        except Exception as e:
            with console_lock:
                logger.error(f"Erro na requisição para {os.path.basename(cv_path)}: {e}")
            retries += 1

    if not full_analysis or retries >= MAX_RETRIES:
        with console_lock:
            logger.error(f"Falha ao analisar o CV {os.path.basename(cv_path)} após {MAX_RETRIES} tentativas. Pulando.")
        return

    # Extrai os dados da análise final
    conclusion = full_analysis.get('conclusion', 'Conclusão não gerada.')
    score = full_analysis.get('score', 0.0)
    structured_data = full_analysis.get('structured_data', {})

    # Criação do diretório e escrita do arquivo
    output_folder = os.path.join(OUTPUT_DIR, opening_data.get('folder', 'outros'))
    os.makedirs(output_folder, exist_ok=True)
    candidate_name = structured_data.get('name', os.path.basename(cv_path))
    safe_name = "".join(c for c in candidate_name if c.isalnum() or c in (' ', '.', '_')).rstrip()
    output_file = os.path.join(output_folder, f"{safe_name}.md")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# Análise do Currículo\n\n")
        f.write(f"## {candidate_name}\n")
        f.write(f"**Vaga:** {opening_data.get('title', 'N/A')}\n") 
        f.write(f"**Pontuação:** {score:.2f}/10\n\n")
        f.write(f"---\n\n")
        f.write(f"## Resumo do Candidato\n")
        
        f.write(f"### Nome Completo\n")
        f.write(f"{structured_data.get('name', 'Nenhuma informação disponível')}\n\n")
        f.write(f"### Habilidades Técnicas\n")
        f.write(", ".join(structured_data.get('hard_skills', [])))
        f.write(f"\n\n### Habilidades Comportamentais\n")
        f.write(", ".join(structured_data.get('soft_skills', [])))
        f.write(f"\n\n### Formação Principal\n")
        f.write(f"{structured_data.get('formal_education', 'Nenhuma informação disponível')}\n\n")
        
        f.write(f"---\n\n")
        f.write(f"## Conclusão\n")
        f.write(conclusion)
        
    with console_lock:
        logger.info(f"Análise de {candidate_name} para a vaga '{opening_data.get('title', 'N/A')}' salva em {output_file}")

def main():
    """Função principal para processar todos os CVs para todas as vagas."""
    
    cv_base_dir = "banco-de-talentos"
    
    if not JOB_OPENINGS:
        logger.error("Nenhuma vaga encontrada para processamento. Verifique o arquivo 'openings_db.json'.")
        return

    for opening_title, opening_data in JOB_OPENINGS.items():
        with console_lock:
            logger.info(f"## Processando candidatos para a vaga: {opening_title} (ID: {opening_data.get('id', 'N/A')}) ##")

        folder_path = os.path.join(cv_base_dir, opening_data.get('folder', 'outros'))
        
        if not os.path.exists(folder_path):
            with console_lock:
                logger.warning(f"Diretório de CVs não encontrado: {folder_path}. Pulando.")
            continue
            
        cv_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.pdf', '.docx'))]
        with console_lock:
            logger.info(f"Encontrados {len(cv_files)} CVs em '{folder_path}'.")

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_single_cv, cv_file, opening_data) for cv_file in cv_files]
            
            for future in concurrent.futures.as_completed(futures):
                pass 
                
        with console_lock:
            logger.info(f"## Processamento para a vaga '{opening_title}' concluído. ##\n")

if __name__ == "__main__":
    main()