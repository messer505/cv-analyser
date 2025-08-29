import os
import threading
import concurrent.futures
import logging
from typing import Dict, Any, List
from ai_prompts import GroqClient # Importa a classe otimizada
from utils_cv import extract_text_from_file

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações globais
MAX_WORKERS = 2
OUTPUT_DIR = "analises_cv"
GROQ_CLIENT = GroqClient()

# Estrutura das vagas
JOB_OPENINGS = {
    "Analista de Desenvolvimento de Sistemas I": {
        "id": "123456789",
        "folder": "desenvolvimento",
        "description": "Vaga para Analista de Desenvolvimento de Sistemas, com foco em back-end, utilizando Python, Django, bancos de dados SQL e API REST. Desejável conhecimento em metodologias ágeis e sistemas de controle de versão como Git.",
    },
    "Tech Lead e Desenvolvedor de Sistemas": {
        "id": "142535001",
        "folder": "desenvolvimento",
        "description": "Vaga de Tech Lead e Desenvolvedor Sênior. Liderança técnica de equipe, arquitetura de sistemas escaláveis, código limpo e refatoração. Requisitos: 8+ anos de experiência, domínio de Python, Java ou C#, experiência com microsserviços, AWS/Azure, Docker e Kubernetes. Habilidades comportamentais como comunicação, mentoria e resolução de conflitos são essenciais.",
    },
    "Assistente Administrativo-Financeiro": {
        "id": "411010001",
        "folder": "adm-financeiro",
        "description": "Vaga para Assistente Administrativo-Financeiro. Responsável por rotinas de contas a pagar/receber, conciliação bancária, emissão de notas fiscais, elaboração de relatórios financeiros e suporte administrativo. Requisitos: Superior em Administração, Ciências Contábeis ou áreas afins. Experiência com Pacote Office e sistemas ERP. Proatividade e organização são cruciais.",
    },
}

# Lock para garantir que a escrita no console não se misture
console_lock = threading.Lock()

def process_single_cv(cv_path: str, opening_data: Dict[str, Any]):
    """Processa um único CV e gera a análise de alinhamento."""
    try:
        with console_lock:
            logger.info(f"--- Processando CV: {os.path.basename(cv_path)} para a vaga '{opening_data['description']}' ---")

        # Extração de texto do CV usando a função única
        # Não precisa mais do if/elif para formatos, a função já lida com isso.
        cv_text = extract_text_from_file(cv_path)

        if not cv_text:
            with console_lock:
                logger.warning(f"Nenhum conteúdo extraído do CV de {os.path.basename(cv_path)}. Pulando.")
            return

        # ... O resto da sua lógica de processamento fica igual ...
        cv_brief = GROQ_CLIENT.cv_brief(cv_text, opening_data['description'])
        conclusion = GROQ_CLIENT.generate_conclusion(cv_text, opening_data['description'])
        score = GROQ_CLIENT.generate_score(cv_text, opening_data['description'])
        structured_data = GROQ_CLIENT.extract_structured_data(cv_text)

        # ... verificação e salvamento dos resultados ...
        if not all([cv_brief, conclusion, score is not None, structured_data]):
            with console_lock:
                logger.error(f"Erro na análise do CV {os.path.basename(cv_path)}: dados incompletos.")
            return

        # ... criação do diretório e escrita do arquivo ...
        output_folder = os.path.join(OUTPUT_DIR, opening_data['folder'])
        os.makedirs(output_folder, exist_ok=True)
        output_file = os.path.join(output_folder, f"{structured_data.get('name', 'Analise_CV')}.md")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Análise do Currículo\n\n")
            f.write(f"## {structured_data.get('name', 'Nome não extraído')}\n")
            f.write(f"**Vaga:** {opening_data['description']}\n")
            f.write(f"**Pontuação:** {score:.2f}/10\n\n")
            f.write(f"---\n\n")
            f.write(f"## Resumo do Candidato\n")
            f.write(cv_brief)
            f.write(f"\n\n---\n\n")
            f.write(f"## Conclusão\n")
            f.write(conclusion)
            
        with console_lock:
            logger.info(f"Análise de {structured_data.get('name', 'candidato')} para a vaga '{opening_data['description']}' salva em {output_file}")

    except Exception as e:
        with console_lock:
            logger.error(f"Erro ao executar a thread para o CV {cv_path}: {e}")

def main():
    """Função principal para processar todos os CVs para todas as vagas."""
    
    cv_base_dir = "banco-de-talentos"
    
    for opening_title, opening_data in JOB_OPENINGS.items():
        with console_lock:
            logger.info(f"## Processando candidatos para a vaga: {opening_title} (ID: {opening_data['id']}) ##")

        folder_path = os.path.join(cv_base_dir, opening_data['folder'])
        
        if not os.path.exists(folder_path):
            with console_lock:
                logger.warning(f"Diretório de CVs não encontrado: {folder_path}. Pulando.")
            continue
            
        cv_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.pdf', '.docx'))]
        with console_lock:
            logger.info(f"Encontrados {len(cv_files)} CVs em '{folder_path}'.")

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_single_cv, cv_file, opening_data) for cv_file in cv_files]
            
            # Opcional: para visualizar o progresso
            for future in concurrent.futures.as_completed(futures):
                pass 
                
        with console_lock:
            logger.info(f"## Processamento para a vaga '{opening_title}' concluído. ##\n")

if __name__ == "__main__":
    main()