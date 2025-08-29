import fitz
import docx
import re
import unicodedata

def extract_text_from_file(file_path: str) -> str:
    text = ""
    try:
        if file_path.lower().endswith(".pdf"):
            with fitz.open(file_path) as pdf:
                text = "\n".join(page.get_text() for page in pdf)
        elif file_path.lower().endswith(".docx"):
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        print(f"ERRO ao ler {file_path}: {e}")
    text = re.sub(r"\s+", " ", text).strip()
    # Normaliza e remove acentos
    nfkd_form = unicodedata.normalize('NFD', text)
    text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    text = text.replace("ç", "c").replace("Ç", "C")
    return text.strip()
