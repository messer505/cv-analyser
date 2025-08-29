import time
import re
import json
import unicodedata
import random # <--- Adicione esta linha
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from langchain_groq import ChatGroq
import logging

load_dotenv()

# Configuração de logging
logger = logging.getLogger(__name__)

# ------------------ UTILITÁRIOS ------------------
def _clamp(value: float, min_value: float, max_value: float) -> float:
    """Limita um valor entre min e max"""
    return max(min_value, min(value, max_value))

def _safe_json_parse(raw: str) -> dict:
    """Parser JSON robusto"""
    if not raw or not raw.strip():
        return {}
    
    # Remove markdown blocks
    cleaned = re.sub(r'```(?:json)?|```', '', raw).strip()
    
    # Procura por JSON válido
    brace_count = 0
    start_idx = -1
    
    for i, char in enumerate(cleaned):
        if char == '{':
            if start_idx == -1:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                json_str = cleaned[start_idx:i+1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
    
    # Fallback: regex search
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    return {}

def normalize_text(text: str) -> str:
    """Remove acentos e normaliza caracteres especiais"""
    if not isinstance(text, str):
        text = str(text)
    
    # Remove acentos
    nfkd = unicodedata.normalize('NFKD', text)
    text = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    
    # Normaliza caracteres especiais
    text = text.replace('ç', 'c').replace('Ç', 'C')
    
    return text.strip()

# ------------------ CLIENTE GROQ COMPATÍVEL -----------------
class GroqClient:
    def __init__(self, model_id: str = 'llama-3.1-8b-instant') -> None:
        self.client = ChatGroq(
            model=model_id,
            max_tokens=6000,
            temperature=0.1
        )
        self.last_request_time = 0
        self.min_interval = 10.0  # Aumente este valor para 10 segundos ou mais
        self.request_count = 0
        
        # Cache para análises completas
        self._full_analysis_cache = {}

    def _wait_for_rate_limit(self):
        """Rate limiting inteligente e conservador"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        dynamic_interval = self.min_interval + (self.request_count * 0.1)
        
        if elapsed < dynamic_interval:
            sleep_time = dynamic_interval - elapsed
            logger.info(f"Intervalo mínimo não atingido. Aguardando {sleep_time:.2f}s...")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
    def generate_response(self, prompt: str, max_retries: int = 5) -> str:
        """
        Método base para geração de respostas com backoff exponencial para rate limits.
        """
        base_wait_time = 2  # Tempo de espera base em segundos
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()

                response = self.client.invoke(prompt)
                if hasattr(response, "content") and response.content:
                    return response.content.strip()
                    
            except Exception as e:
                error_msg = str(e).lower()
                logger.warning(f"Erro na API (tentativa {attempt+1}/{max_retries}): {e}")
                
                # Checa se o erro é de rate limit
                if any(keyword in error_msg for keyword in ["rate limit", "too many requests", "quota"]):
                    # Implementação do backoff exponencial
                    wait_time = base_wait_time * (2 ** attempt) + random.uniform(0, 1) # 'random' precisa ser importado
                    logger.info(f"Rate limit detectado. Tentativa {attempt+1}. Aguardando {wait_time:.2f}s...")
                    time.sleep(wait_time)
                elif "timeout" in error_msg:
                    time.sleep(10)
                else:
                    time.sleep(5)
                    
        return ""

    def _get_or_create_full_analysis(self, cv_text: str, opening_json: str) -> Optional[Dict[str, Any]]:
        """
        Gera análise completa uma única vez e cacheia o resultado
        """
        # Cria chave de cache
        cache_key = hash(cv_text + opening_json)
        
        if cache_key in self._full_analysis_cache:
            return self._full_analysis_cache[cache_key]
        
        # Limita tamanho dos inputs
        cv_text = cv_text[:3500] if len(cv_text) > 3500 else cv_text
        
        # Parse da vaga
        try:
            opening_data = json.loads(opening_json)
            opening_text = f"Vaga: {opening_data.get('title', '')}\nDescrição: {opening_data.get('description', '')}"
        except:
            opening_text = opening_json[:1500]
        
        prompt = f"""
            SISTEMA: Você é um especialista em RH, muito justo e rigoroso, que analisa currículos e os pontua de forma precisa, sem dar notas muito parecidas. Sua pontuação deve refletir a aderência do candidato aos requisitos da vaga.

            TAREFA: Analise o CV vs VAGA e retorne APENAS JSON válido (sem explicações, markdown ou texto extra).

            CURRÍCULO:
            {cv_text}

            VAGA:
            {opening_text}

            FORMATO EXATO:
            {{
            "conclusion": "## Pontos de Alinhamento\\n- [3-4 pontos específicos]\\n\\n## Pontos de Desalinhamento\\n- [2-3 pontos específicos]\\n\\n## Pontos de Atenção\\n- [2-3 observações importantes]",
            "score": [número 0.0-10.0],
            "structured_data": {{
            "name": "[Nome completo]",
            "formal_education": "[Formação principal]",
            "hard_skills": ["[max 8 skills]"],
            "soft_skills": ["[max 6 skills]"]
            }}
            }}

            CRITÉRIOS DE PONTUAÇÃO (DETALHADOS):
            - Pontuação base (6.0): Todo candidato começa com esta nota.
            - Experiência Profissional (Peso 3.0): Adiciona até 3.0 pontos se a experiência for diretamente relevante para a vaga. Subtrai até 3.0 pontos se a experiência for irrelevante ou inexistente.
            - Hard Skills (Peso 2.0): Adiciona 0.5 por cada hard skill listada na vaga que o candidato possui. Subtrai 0.5 por cada hard skill obrigatória na vaga que o candidato não possui.
            - Soft Skills (Peso 1.0): Adiciona 0.2 por cada soft skill listada na vaga que o candidato possui.
            - Formação (Peso 1.0): Adiciona até 1.0 ponto se a formação for diretamente relacionada à vaga.
            - Pontos de desalinhamento (Penalidade -1.0 a -3.0): Subtrai de 1.0 a 3.0 pontos dependendo da gravidade dos pontos de desalinhamento.
            - Bônus (até 2.0 pontos): Adiciona pontos extras por diferenciais como certificações, cursos relevantes e experiência em projetos notáveis.

            Exemplo de pontuação:
            - Candidato Ideal: Experiência 100% alinhada, todas as skills, formação perfeita. Pontuação: 9.5 a 10.0.
            - Candidato Forte: Experiência relevante, mas falta 1-2 skills. Pontuação: 8.0 a 9.4.
            - Candidato Mediano: Pouca experiência, mas possui algumas skills. Pontuação: 6.0 a 7.9.
            - Candidato Fraco: Experiência irrelevante, falta skills essenciais. Pontuação: Abaixo de 6.0.

            RETORNE APENAS O JSON.
        """

        response = self.generate_response(prompt, max_retries=4)
        
        if not response:
            return None
            
        parsed_json = _safe_json_parse(response)
        
        # --- LINHA CORRIGIDA: AQUI ESTAVA A CAUSA DO ERRO ---
        # Removido 'brief_content' da validação, pois o prompt não o solicita
        if not parsed_json or not all(k in parsed_json for k in ["conclusion", "score", "structured_data"]):
            return None
    
    # Normaliza dados
        try:
            parsed_json["score"] = _clamp(float(parsed_json["score"]), 0.0, 10.0)
            
            if "structured_data" in parsed_json:
                struct_data = parsed_json["structured_data"]
                for skill_type in ["hard_skills", "soft_skills"]:
                    if skill_type in struct_data and isinstance(struct_data[skill_type], list):
                        struct_data[skill_type] = [
                            normalize_text(skill) 
                            for skill in struct_data[skill_type] 
                            if skill and skill.strip()
                        ]
        except Exception as e:
            logger.error(f"Erro na normalização: {e}")
        
        # Cacheia resultado
        self._full_analysis_cache[cache_key] = parsed_json
        return parsed_json

    # ------------------ MÉTODOS COMPATÍVEIS (ANTIGOS) ------------------
    
    def cv_brief(self, cv_text: str, max_retries: int = 3) -> str:
        """
        Compatibilidade: Gera resumo do CV usando análise completa
        """
        # Usa uma vaga genérica para análise
        generic_opening = json.dumps({
            "title": "Posição Genérica",
            "description": "Análise geral de currículo"
        })
        
        full_analysis = self._get_or_create_full_analysis(cv_text, generic_opening)
        
        if full_analysis and "brief_content" in full_analysis:
            return full_analysis["brief_content"]
        
        return "ERRO: Não foi possível gerar o resumo do CV."

    def generate_conclusion(self, cv_text: str, opening_json: str, max_retries: int = 3) -> str:
        """
        Compatibilidade: Gera conclusão usando análise completa
        """
        full_analysis = self._get_or_create_full_analysis(cv_text, opening_json)
        
        if full_analysis and "conclusion" in full_analysis:
            return full_analysis["conclusion"]
        
        return "ERRO: Conclusão não gerada."

    def generate_score(self, cv_text: str, opening_json: str, max_retries: int = 3) -> Optional[float]:
        """
        Compatibilidade: Gera score usando análise completa
        """
        full_analysis = self._get_or_create_full_analysis(cv_text, opening_json)
        
        if full_analysis and "score" in full_analysis:
            return full_analysis["score"]
        
        return None

    # ------------------ MÉTODOS NOVOS ------------------
    
    def generate_full_cv_analysis(self, cv_text: str, opening_text: str) -> Optional[Dict[str, Any]]:
        """
        Método principal: análise completa otimizada
        """
        # Converte opening_text para formato JSON se necessário
        if not opening_text.strip().startswith('{'):
            opening_json = json.dumps({"title": "Vaga", "description": opening_text})
        else:
            opening_json = opening_text
            
        return self._get_or_create_full_analysis(cv_text, opening_json)

    def extract_structured_data(self, cv_text: str) -> Dict[str, Any]:
        """
        Extrai dados estruturados do CV (compatibilidade com script principal)
        """
        generic_opening = json.dumps({
            "title": "Análise Estrutural",
            "description": "Extração de dados estruturados"
        })
        
        full_analysis = self._get_or_create_full_analysis(cv_text, generic_opening)
        
        if full_analysis and "structured_data" in full_analysis:
            return full_analysis["structured_data"]
        
        return {
            "name": "Nome não extraído",
            "formal_education": "",
            "hard_skills": [],
            "soft_skills": []
        }

    # ------------------ MÉTODOS ESTÁTICOS DE UTILIDADE ------------------
    
    @staticmethod
    def extract_markdown(result_raw: str) -> str:
        """Compatibilidade: extrai markdown de resposta"""
        match = re.search(r'```(?:markdown)?\s*(.*?)\s*```', result_raw, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else result_raw.strip()

    @staticmethod
    def extract_score_from_result(result_raw: str) -> Optional[float]:
        """Compatibilidade: extrai score de texto"""
        match = re.search(r'(?i)Pontuação Final[:\s]*([\d]+[.,]?\d*)', result_raw)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except ValueError:
                return None
        return None

    @staticmethod
    def parse_brief_to_json(brief_markdown: str) -> dict:
        """Compatibilidade: converte brief markdown para JSON"""
        nome, local, disponibilidade = "", "", ""
        hard_skills, soft_skills = set(), set()
        current_section = None
        
        section_pattern = re.compile(r'##\s*(.*)')
        
        for line in brief_markdown.splitlines():
            line = line.strip()
            if not line:
                continue
                
            match = section_pattern.match(line)
            if match:
                current_section = match.group(1)
                continue
                
            if current_section == "Nome Completo":
                nome = normalize_text(line)
            elif current_section == "Habilidades Técnicas":
                hard_skills.update([normalize_text(x) for x in re.split(r'[,\n]', line) if x.strip()])
            elif current_section == "Habilidades Comportamentais":
                soft_skills.update([normalize_text(x) for x in re.split(r'[,\n]', line) if x.strip()])
            elif current_section == "Local":
                local = normalize_text(line)
            elif current_section == "Disponibilidade":
                disponibilidade = normalize_text(line)
        
        return {
            "title": nome or "Nome não extraído",
            "hard_skills": sorted(hard_skills),
            "soft_skills": sorted(soft_skills),
            "local": local,
            "disponibilidade": disponibilidade
        }
    