import fitz
import docx
import re
import unicodedata
import logging
from io import StringIO
from pdfminer.high_level import extract_text_to_fp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _extract_text_with_pymupdf(file_path: str) -> str:
    """Extrai texto de PDFs usando PyMuPDF."""
    try:
        with fitz.open(file_path) as pdf:
            text = "\n".join(page.get_text() for page in pdf)
        return text
    except Exception as e:
        logger.warning(f"Falha na extração de PDF com PyMuPDF para {file_path}: {e}")
        return ""

def _extract_text_with_pdfminer(file_path: str) -> str:
    """Extrai texto de PDFs usando pdfminer.six."""
    try:
        output_string = StringIO()
        with open(file_path, 'rb') as in_file:
            extract_text_to_fp(in_file, output_string)
        text = output_string.getvalue()
        return text
    except Exception as e:
        logger.error(f"Falha na extração de PDF com pdfminer.six para {file_path}: {e}")
        return ""

def extract_text_from_file(file_path: str) -> str:
    """Extrai texto de PDFs e DOCXs de forma robusta, com fallback para PDFs."""
    text = ""
    try:
        if file_path.lower().endswith(".pdf"):
            text = _extract_text_with_pymupdf(file_path)
            
            # Tenta com pdfminer.six se a primeira extração falhar ou for muito curta
            if not text or len(text.split()) < 50: # Reduzi o limite para 50, é mais realista
                logger.warning(f"Extração com PyMuPDF falhou ou gerou pouco conteúdo. Tentando com pdfminer.six...")
                text = _extract_text_with_pdfminer(file_path)

        elif file_path.lower().endswith(".docx"):
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        else:
            logger.warning(f"Formato de arquivo não suportado: {file_path}")
            return ""

    except Exception as e:
        logger.error(f"Erro geral ao ler {file_path}: {e}")
        return ""

    # Normaliza e limpa o texto apenas uma vez, no final da função
    text = re.sub(r"\s+", " ", text).strip()
    nfkd_form = unicodedata.normalize('NFD', text)
    text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    text = text.replace("ç", "c").replace("Ç", "C")
    
    return text.strip()