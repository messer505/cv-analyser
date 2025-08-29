import configparser
import io
import json
import re
import unicodedata
import logging
from typing import List

import fitz  # PyMuPDF
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from tinydb import Query, TinyDB
from pydantic import ValidationError

from drive.authenticate import TOKEN_FILE
from ai_prompts import GroqClient
from models.opening import Opening

# ---------- CONFIGURAÇÃO DE LOGGING ----------
# Configura um logger para registrar informações e erros em um arquivo.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='processing.log',
    filemode='w'
)
# Adiciona um handler para também exibir os logs no console.
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)


# ---------- CONFIGURAÇÃO ----------
config = configparser.ConfigParser()
config.read('config.ini')
OPENINGS_FOLDER_ID = config['GOOGLE_DRIVE']['OPENINGS_FOLDER_ID']

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
service = build("drive", "v3", credentials=creds)

DB_FILE = "openings_db.json"
db_openings = TinyDB(DB_FILE, indent=2, ensure_ascii=False)
openings_table = db_openings.table('openings')

groq = GroqClient()

# ---------- FUNÇÕES DE LEITURA ----------

def read_drive_file(file_id: str, file_name: str) -> str:
    """
    Baixa o conteúdo de um arquivo do Google Drive e tenta decodificá-lo
    com uma lista de encodings comuns.
    """
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, service.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)

    if file_name.endswith(".pdf"):
        try:
            doc = fitz.open(stream=fh.read(), filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            logging.error(f"Erro ao ler o arquivo PDF '{file_name}': {e}")
            return ""

    # Tratamento de encoding melhorado para arquivos de texto
    file_content = fh.read()
    common_encodings = ['utf-8', 'latin-1', 'windows-1252']
    for encoding in common_encodings:
        try:
            text = file_content.decode(encoding)
            logging.info(f"Arquivo '{file_name}' decodificado com sucesso usando '{encoding}'.")
            return text
        except UnicodeDecodeError:
            continue # Tenta o próximo encoding

    logging.warning(f"Não foi possível decodificar '{file_name}' com os encodings testados. Usando 'ignore' errors.")
    return file_content.decode('utf-8', errors='ignore')


def list_drive_folder(folder_id: str):
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get("files", [])

# ---------- NORMALIZAÇÃO DE TEXTOS ----------

def remove_accents_and_special_chars(text: str) -> str:
    if not text:
        return ""
    nfkd_form = unicodedata.normalize('NFD', text)
    no_accents = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    no_accents = no_accents.replace("Ç", "C").replace("ç", "c")
    cleaned = re.sub(r"[^\w\s.,;:()-]", "", no_accents) # Mantém alguns caracteres úteis
    return cleaned.strip()

# ---------- FUNÇÕES DE PROCESSAMENTO E IA ----------

def safe_json_parse(raw_text: str) -> dict:
    if not raw_text:
        return {}
    # Remove blocos de código markdown para limpar o JSON
    cleaned = re.sub(r"```.*?```", "", raw_text, flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        logging.error("Nenhum objeto JSON encontrado na resposta da IA.")
        return {}
    json_str = match.group(0)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logging.error(f"Erro de decodificação JSON: {e}\nTexto recebido: {json_str}")
        return {}

def build_prompt(folder_name: str, file_name: str, text: str, add_infos: str) -> str:
    # O prompt permanece o mesmo, pois sua estrutura já é bem definida.
    return f"""
        **Sua única função é extrair dados e retornar um único e válido objeto JSON.**
        Você receberá o conteúdo de arquivos sobre uma vaga de emprego. Analise os dados de entrada e preencha a estrutura JSON.
        **NUNCA, em nenhuma circunstância, retorne código Python, explicações, comentários ou qualquer texto que não seja o JSON final.**
        A estrutura do JSON de saída deve ser **exatamente** esta:
        {{
            "id": 0, "title": "", "intro": "", "main_activities": "", "add_infos": "", "pre_requisites": "",
            "soft_skills": ["Exemplo: Comunicacao", "Exemplo: Trabalho em Equipe"],
            "hard_skills": ["Exemplo: C#", "Exemplo: .NET", "Exemplo: SQL"],
            "local": "", "disponibilidade": "", "folder": ""
        }}
        ### Dados de Entrada para Análise:
        - Nome do Arquivo: {file_name}
        - Conteúdo Principal (do PDF/TXT): {text}
        - Informações Adicionais (do TXT): {add_infos}
        - Nome da Pasta: {folder_name}
        ### Regras de Preenchimento:
        1. **id e title**: Extraia diretamente do "Nome do Arquivo".
        2. **intro ("Descrição Sumária"), main_activities ("Descrição das atividades"), pre_requisites ("Requisitos" "Formação" "Desejável"), soft_skills ("Competências Comportamentais"), hard_skills ("Competências Técnicas")**: Extraia do "Conteúdo Principal" de maneira integral - Descrição de Cargo.
        3. **add_infos, local, disponibilidade**: Extraia das "add_infos" encontradas no arquivo txt relacionadas a atividades principais.
        4. **folder**: Use o "Nome da Pasta" fornecido.
        5. **Valores Padrão**: Se "add_infos" estiver vazio, use `local: "Juiz de Fora - MG"` e `disponibilidade: "Híbrido"`.
        6. **Formato**: Se não encontrar informação, use `""` para strings ou `[]` para listas.
        **Lembre-se: Sua resposta deve ser APENAS o objeto JSON, começando com `{{` e terminando com `}}`.**
    """

def extract_opening_data_with_groq(folder_name: str, file_name: str, text: str, add_infos: str) -> dict:
    logging.info("Enviando dados para a IA para extração...")
    prompt = build_prompt(folder_name, file_name, text, add_infos)
    result = {}
    for i in range(5): # Tenta até 5 vezes
        raw_response = groq.generate_response(prompt)
        result = safe_json_parse(raw_response)
        if "title" in result and result.get("title"): # Verifica se um campo essencial foi preenchido
            logging.info(f"IA retornou um JSON válido na tentativa {i + 1}.")
            return result
        logging.warning(f"Tentativa {i + 1} de extração com IA falhou ou retornou JSON inválido.")
    return result

def process_opening_file(sector_name: str, file_name: str, file_id: str, file_dict: dict) -> Opening | None:
    logging.info(f"--- Processando o arquivo: {file_name} ---")
    is_main_file = file_name.lower().endswith((".pdf", ".txt"))
    is_add_infos = "_add_infos.txt" in file_name.lower()

    if is_add_infos or not is_main_file:
        logging.info(f"Arquivo '{file_name}' não é um arquivo principal de vaga. Pulando.")
        return None

    text = read_drive_file(file_id, file_name)
    if not text:
        logging.warning(f"Nenhum texto extraído do arquivo {file_name}. Pulando.")
        return None

    # Normaliza o texto antes de enviar para a IA
    text = remove_accents_and_special_chars(text)

    file_id_prefix = file_name.split("_")[0]
    add_infos_name = file_id_prefix + "_add_infos.txt"
    add_infos_text = ""
    if add_infos_name in file_dict:
        logging.info(f"Encontrado arquivo de informações adicionais: {add_infos_name}")
        add_infos_id = file_dict[add_infos_name]
        add_infos_text = read_drive_file(add_infos_id, add_infos_name)
        add_infos_text = remove_accents_and_special_chars(add_infos_text)
    else:
        logging.info(f"Nenhum arquivo de informações adicionais encontrado para '{file_name}'.")

    # Extrai os dados usando a IA
    extracted_data = extract_opening_data_with_groq(sector_name, file_name, text, add_infos_text)

    # Adiciona o nome da pasta e preenche valores padrão se necessário
    extracted_data["folder"] = sector_name
    if not add_infos_text:
        extracted_data.setdefault("local", "Juiz de Fora - MG")
        extracted_data.setdefault("disponibilidade", "Híbrido")
    
    # Validação Robusta com Pydantic
    try:
        # Extrai id e title do nome do arquivo como fallback
        if not extracted_data.get("id") or not extracted_data.get("title"):
             match = re.match(r"(\d+)_?(.*)", file_name)
             if match:
                 extracted_data["id"] = int(match.group(1))
                 extracted_data["title"] = match.group(2).replace('.pdf', '').replace('.txt', '').replace('_', ' ').strip()

        opening = Opening(**extracted_data)
        logging.info(f"Validação Pydantic bem-sucedida para a vaga '{opening.title}'.")
        
        # Salva no banco de dados
        openings_table.upsert(opening.model_dump(), Query().id == opening.id)
        logging.info(f"SUCESSO: Vaga '{opening.title}' (ID: {opening.id}) processada e salva.")
        return opening
    except ValidationError as e:
        logging.error(f"Erro de validação Pydantic para o arquivo '{file_name}': {e}")
        return None
    except Exception as e:
        logging.error(f"Erro inesperado ao processar '{file_name}': {e}")
        return None


def clear_openings_table():
    logging.info("Limpando a tabela de vagas ('openings') no openings_db.json...")
    openings_table.truncate()
    logging.info("Tabela 'openings' limpa.")

def read_openings_from_drive() -> List[Opening]:
    openings_list = []
    logging.info("Iniciando varredura de vagas no Google Drive...")
    folders = list_drive_folder(OPENINGS_FOLDER_ID)
    for sector in folders:
        if sector["mimeType"] != "application/vnd.google-apps.folder":
            continue
        sector_name = sector["name"]
        logging.info(f"===== Processando setor: {sector_name} =====")
        files = list_drive_folder(sector["id"])
        logging.info(f"Encontrados {len(files)} itens no setor.")
        file_dict = {f["name"]: f["id"] for f in files}
        for file_info in files:
            opening = process_opening_file(sector_name, file_info["name"], file_info["id"], file_dict)
            if opening:
                openings_list.append(opening)
    return openings_list

# ---------- EXECUÇÃO ----------
if __name__ == "__main__":
    clear_openings_table()
    lista_de_vagas = read_openings_from_drive()
    logging.info("=======================================================")
    logging.info("===== PROCESSO DE EXTRAÇÃO DE VAGAS FINALIZADO =====")
    logging.info(f"    Total de vagas salvas com sucesso: {len(lista_de_vagas)}")
    logging.info("=======================================================")