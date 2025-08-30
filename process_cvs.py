import os
import threading
import concurrent.futures
import logging
import json
from typing import Dict, Any
from ai_prompts import GroqClient 
from utils_cv import extract_text_from_file
from openings_db_manager import load_openings_db
from database import AnalysisDatabase

# ---------- CONFIGURAÇÃO ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações globais
MAX_WORKERS = 4 # Aumentado para 4 para um processamento mais rápido em máquinas modernas
OUTPUT_DIR = "analises_cv"
GROQ_CLIENT = GroqClient()
# Cria uma única instância do banco de dados no escopo global
database = AnalysisDatabase(db_path='applicants.json')
# Lock para garantir que a escrita no console não se misture
console_lock = threading.Lock()

# ---------- FUNÇÃO DE PROCESSAMENTO ----------
def process_single_cv(cv_path: str, opening_data: Dict[str, Any]):
    """Processa um único CV e gera a análise de alinhamento."""
    
    MAX_RETRIES = 5
    retries = 0
    full_analysis = None
    
    try:
        with console_lock:
            logger.info(f"--- Processando CV: {os.path.basename(cv_path)} para a vaga '{opening_data.get('title', 'N/A')}' (ID: {opening_data.get('id', 'N/A')}) ---")

        cv_text = extract_text_from_file(cv_path)
        
        if not cv_text or len(cv_text.split()) < 50:
            with console_lock:
                logger.error(f"Falha na extração de texto do CV {os.path.basename(cv_path)} ou conteúdo muito curto. Pulando.")
            return

        cleaned_cv_text = ' '.join(cv_text.split()[:4000])
        
    except Exception as e:
        with console_lock:
            logger.error(f"Erro ao extrair texto do CV {os.path.basename(cv_path)}: {e}")
        return

    # Lógica de retentativa para a chamada da API
    while retries < MAX_RETRIES:
        try:
            job_description = (
                opening_data.get('intro', '') + ' ' + 
                opening_data.get('main_activities', '') + ' ' + 
                opening_data.get('add_infos', '') + ' ' +
                opening_data.get('pre_requisites', '')
            ).strip()

            full_analysis = GROQ_CLIENT.generate_full_cv_analysis(cleaned_cv_text, job_description)
            
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
    total_experience_years = full_analysis.get('total_experience_years', 'Não avaliado')
    
    # Adiciona a análise ao banco de dados - Lógica movida para dentro da função
    opening_id = opening_data.get("id")
    brief_data = {
        'cv_text': cv_text,
        'cv_path': cv_path,
        'content': conclusion
    }
    brief_id = database.add_brief_data(brief_data)

    analysis_to_save = {
        "name": structured_data.get('name'),
        "formal_education": structured_data.get('formal_education'),
        "hard_skills": structured_data.get('hard_skills'),
        "soft_skills": structured_data.get('soft_skills'),
        "score": score,
        "total_experience_years": total_experience_years
    }
    
    database.add_analysis_data(opening_id, brief_id, analysis_to_save)
    with console_lock:
        logger.info(f"Análise de {structured_data.get('name')} salva no banco de dados para a vaga '{opening_data.get('title')}'")

    # Criação do diretório e escrita do arquivo .md
    output_folder = os.path.join(OUTPUT_DIR, opening_data.get('folder', 'outros'))
    os.makedirs(output_folder, exist_ok=True)
    candidate_name = structured_data.get('name', os.path.basename(cv_path))
    safe_name = "".join(c for c in candidate_name if c.isalnum() or c in (' ', '.', '_')).rstrip()
    safe_opening_title = "".join(c for c in opening_data.get('title', 'vaga_desconhecida') if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
    output_file = os.path.join(output_folder, f"{safe_name}_{safe_opening_title}.md")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Análise do Currículo\n\n")
        f.write(f"## {candidate_name}\n")
        f.write(f"**Vaga:** {opening_data.get('title', 'N/A')}\n") 
        f.write(f"**Pontuação:** {score:.2f}/10\n")
        f.write(f"**Tempo de Experiência:** {total_experience_years} anos\n\n")
        f.write("---\n\n")
        f.write("## Resumo do Candidato\n")
        
        f.write("### Nome Completo\n")
        f.write(f"{structured_data.get('name', 'Nenhuma informação disponível')}\n\n")
        f.write("### Habilidades Técnicas\n")
        f.write(", ".join(structured_data.get('hard_skills', [])))
        f.write("\n\n### Habilidades Comportamentais\n")
        f.write(", ".join(structured_data.get('soft_skills', [])))
        f.write("\n\n### Formação Principal\n")
        f.write(f"{structured_data.get('formal_education', 'Nenhuma informação disponível')}\n\n")
        
        f.write("---\n\n")
        f.write("## Conclusão\n")
        f.write(conclusion)
        
    with console_lock:
        logger.info(f"Análise de {candidate_name} para a vaga '{opening_data.get('title', 'N/A')}' salva em {output_file}")

# ---------- FUNÇÃO PRINCIPAL ----------
def main():
    """Função principal para processar todos os currículos para todas as vagas."""
    
    cv_base_dir = "banco-de-talentos"
    job_openings = load_openings_db()

    if not job_openings:
        logger.error("Nenhuma vaga encontrada para processamento. Verifique o arquivo 'openings_db.json'.")
        return

    # Mapeia as pastas para as vagas para um loop mais eficiente
    folder_to_opening = {data['folder']: data for data in job_openings.values()}

    all_tasks = []
    
    # Itera sobre as pastas de currículos
    for folder_name in os.listdir(cv_base_dir):
        folder_path = os.path.join(cv_base_dir, folder_name)

        if not os.path.isdir(folder_path) or folder_name not in folder_to_opening:
            continue

        opening_data = folder_to_opening[folder_name]
        cv_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.pdf', '.docx'))]
        
        if not cv_files:
            logger.warning(f"Nenhum currículo encontrado no diretório '{folder_path}'.")
            continue

        logger.info(f"## Processando {len(cv_files)} currículos para a vaga '{opening_data['title']}' (Pasta: {folder_name}). ##")
        
        for cv_file in cv_files:
            all_tasks.append((cv_file, opening_data))

    if not all_tasks:
        logger.info("Nenhum currículo para processar. Finalizando.")
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_single_cv, cv_file, opening_data) for cv_file, opening_data in all_tasks]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Uma das tarefas de processamento falhou: {e}")
    
    logger.info("## Processamento de todos os currículos concluído. ##\n")

if __name__ == "__main__":
    main()