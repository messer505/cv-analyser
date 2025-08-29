import time
import re
import unicodedata
from typing import Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# ------------------ UTILITÁRIOS ------------------
def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))

def _safe_json_parse(raw: str) -> dict:
    try:
        import json
        return json.loads(raw)
    except Exception:
        return {}

def normalize_text(text: str) -> str:
    """Remove acentos e normaliza ç/Ç para c/C"""
    nfkd = unicodedata.normalize('NFKD', text)
    text = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    text = text.replace('ç', 'c').replace('Ç', 'C')
    return text.strip()

# ------------------ CLIENTE GROQ ------------------
class GroqClient:
    def __init__(self, model_id: str = 'llama-3.1-8b-instant') -> None:
        self.client = ChatGroq(model=model_id, max_tokens=4096)

    def generate_response(self, prompt: str, max_retries: int = 3) -> str:
        for attempt in range(max_retries):
            try:
                response = self.client.invoke(prompt)
                if hasattr(response, "content") and response.content:
                    return response.content
            except Exception as e:
                print(f"Erro na API (tentativa {attempt+1}): {e}")
            time.sleep(5)
        return ""

    @staticmethod
    def extract_markdown(result_raw: str) -> str:
        match = re.search(r'```(?:markdown)?\s*(.*?)\s*```', result_raw, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else result_raw.strip()

    @staticmethod
    def extract_score_from_result(result_raw: str) -> Optional[float]:
        match = re.search(r'(?i)Pontuação Final[:\s]*([\d]+[.,]?\d*)', result_raw)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except ValueError:
                return None
        return None

    # ------------------ CV BRIEF ------------------
    def cv_brief(self, cv_text: str, max_retries: int = 5) -> str:
        prompt = f"""
        Extraia do CV as seguintes informações em Markdown:
        Nome Completo, Habilidades Técnicas, Habilidades Comportamentais, Local, Disponibilidade
        CV: {cv_text}
        """
        for _ in range(max_retries):
            result = self.generate_response(prompt)
            if result.strip():
                return self.extract_markdown(result)
        return "ERRO: Não foi possível gerar o resumo do CV."

    # ------------------ CONVERSÃO PARA JSON ------------------
    @staticmethod
    def parse_brief_to_json(brief_markdown: str) -> dict:
        nome, local, disponibilidade = "", "", ""
        hard_skills, soft_skills = set(), set()
        current_section = None
        section_pattern = re.compile(r'##\s*(.*)')
        for line in brief_markdown.splitlines():
            line = line.strip()
            if not line: continue
            match = section_pattern.match(line)
            if match:
                current_section = match.group(1)
                continue
            if current_section == "Nome Completo": nome = normalize_text(line)
            elif current_section == "Habilidades Técnicas":
                hard_skills.update([normalize_text(x) for x in re.split(r'[,\\n]', line) if x.strip()])
            elif current_section == "Habilidades Comportamentais":
                soft_skills.update([normalize_text(x) for x in re.split(r'[,\\n]', line) if x.strip()])
            elif current_section == "Local": local = normalize_text(line)
            elif current_section == "Disponibilidade": disponibilidade = normalize_text(line)
        return {
            "title": nome or "Nome nao extraido",
            "hard_skills": sorted(hard_skills),
            "soft_skills": sorted(soft_skills),
            "local": local,
            "disponibilidade": disponibilidade
        }

    # ------------------ SCORE ------------------
    def _build_prompt(self, cv_text: str, opening_text: str) -> str:
        return f"""
        Avalie o CURRÍCULO em relação à VAGA e retorne JSON rigoroso.
        CURRÍCULO: {cv_text}
        VAGA: {opening_text}
        Regras: Exp:25%, Técnicas:15%, Comportamentais:10%(realocar 5%+5% se ausente), Educação:15%, Pontos Fortes:15%, Pontos Fracos: desconto 15%.
        """

    def _recalculate_score(self, data: dict) -> float:
        pesos, notas = data.get("pesos", {}), data.get("notas", {})
        w_exp = float(pesos.get("experiencia",0.25))
        w_tech = float(pesos.get("habilidades_tecnicas",0.15))
        w_soft = float(pesos.get("habilidades_comportamentais",0.10))
        w_edu = float(pesos.get("educacao",0.15))
        w_str = float(pesos.get("pontos_fortes",0.15))
        if str(data.get("redistribuicao_soft_skills", {}).get("aplicada","")).lower() in ("true","1"):
            w_soft, w_exp, w_tech = 0.0, w_exp+0.05, w_tech+0.05
        n = lambda k: _clamp(notas.get(k,0.0),0,10)
        parcial = w_exp*n("experiencia")+w_tech*n("habilidades_tecnicas")+w_soft*n("habilidades_comportamentais")+w_edu*n("educacao")+w_str*n("pontos_fortes")
        max_disc = float(pesos.get("desconto_pontos_fracos_max",0.15))*10
        desconto = _clamp(float(str(data.get("desconto_pontos_fracos",0)).replace(",",".") or 0),0,max_disc)
        return _clamp(parcial-desconto,0,10)

    def generate_score(self, cv_text: str, opening_text: str, max_retries: int = 3) -> float:
        data = {}
        prompt = self._build_prompt(cv_text, opening_text)
        for _ in range(max_retries):
            data = _safe_json_parse(self.generate_response(prompt))
            if data: break
        if not data:
            fb = self.extract_score_from_result(self.generate_response("Retorne: 'Pontuação Final: x.x'"))
            return _clamp(fb if fb is not None else 0.0,0,10)
        try:
            return _clamp(float(str(data.get("pontuacao_final","")).replace(",", ".")),0,10)
        except (ValueError, TypeError):
            return self._recalculate_score(data)

    # ------------------ CONCLUSÃO ------------------
    def generate_conclusion(self, cv_text: str, opening_text: str, max_retries: int = 5) -> str:
        prompt = f"""
        Analise o CV em relacao à vaga e gere opiniao critica detalhada.
        Seções: Pontos de Alinhamento, Pontos de Desalinhamento, Pontos de Atencao.
        CV: {cv_text}
        VAGA: {opening_text}
        """
        for _ in range(max_retries):
            result = self.generate_response(prompt)
            if result.strip(): return result.strip()
        return "ERRO: Conclusao nao gerada."
