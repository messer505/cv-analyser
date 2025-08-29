import time
import re
import json
import unicodedata
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# ------------------ UTILITÁRIOS ------------------
def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))

def _safe_json_parse(raw: str) -> dict:
    # Aprimorado para extrair o JSON mesmo com texto antes ou depois
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        return {}
    json_str = match.group(0)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return {}

def normalize_text(text: str) -> str:
    """Remove acentos e normaliza ç/Ç para c/C"""
    if not isinstance(text, str):
        text = str(text)
    nfkd = unicodedata.normalize('NFKD', text)
    text = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    text = text.replace('ç', 'c').replace('Ç', 'C')
    return text.strip()

# ------------------ CLIENTE GROQ ------------------
class GroqClient:
    def __init__(self, model_id: str = 'llama-3.1-8b-instant') -> None:
        self.client = ChatGroq(model=model_id, max_tokens=8192) # Aumentado max_tokens para respostas completas

    def generate_response(self, prompt: str, max_retries: int = 3) -> str:
        for attempt in range(max_retries):
            try:
                response = self.client.invoke(prompt)
                if hasattr(response, "content") and response.content:
                    return response.content
            except Exception as e:
                print(f"Erro na API (tentativa {attempt+1}): {e}")
            time.sleep(5) # Aumenta a espera em caso de falha
        return ""

    def generate_full_cv_analysis(self, cv_text: str, opening_text: str) -> Optional[Dict[str, Any]]:
        """
        Executa uma única chamada à API para obter todas as informações de análise de um CV.
        """
        prompt = f"""
        Sua tarefa é analisar um CURRÍCULO em relação a uma VAGA e retornar um único objeto JSON.
        Não inclua NENHUM texto, explicação ou formatação fora do objeto JSON.

        CURRÍCULO:
        ---
        {cv_text}
        ---

        VAGA:
        ---
        {opening_text}
        ---

        A estrutura de saída DEVE ser este JSON:
        {{
          "brief_content": "## Nome Completo\\n<nome>\\n\\n## Habilidades Técnicas\\n<lista>\\n\\n## Habilidades Comportamentais\\n<lista>\\n\\n## Local\\n<local>\\n\\n## Disponibilidade\\n<disponibilidade>",
          "conclusion": "## Pontos de Alinhamento\\n<texto>\\n\\n## Pontos de Desalinhamento\\n<texto>\\n\\n## Pontos de Atencao\\n<texto>",
          "score": <numero_de_0_a_10>,
          "structured_data": {{
            "name": "<nome>",
            "formal_education": "<formacao>",
            "hard_skills": ["<habilidade1>", "<habilidade2>"],
            "soft_skills": ["<habilidade1>", "<habilidade2>"]
          }}
        }}

        REGRAS:
        1.  **brief_content**: Resuma o CV em formato Markdown, extraindo Nome, Habilidades Técnicas, Habilidades Comportamentais, Local e Disponibilidade.
        2.  **conclusion**: Forneça uma análise crítica em Markdown com as seções: Pontos de Alinhamento, Pontos de Desalinhamento e Pontos de Atenção.
        3.  **score**: Atribua uma pontuação numérica de 0.0 a 10.0 baseada na compatibilidade do CV com a VAGA.
        4.  **structured_data**: Extraia as informações estruturadas do CV.
        """
        response = self.generate_response(prompt)
        parsed_json = _safe_json_parse(response)

        # Validação mínima para garantir que a estrutura principal foi retornada
        if all(k in parsed_json for k in ["brief_content", "conclusion", "score", "structured_data"]):
            return parsed_json
        else:
            print(f"Erro: A resposta da IA não continha a estrutura JSON esperada. Resposta: {response}")
            return None