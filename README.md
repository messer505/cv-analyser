## CV Analyser
Sistema para análise de currículos, extração de dados de vagas e classificação de candidatos utilizando IA (Groq) e Streamlit.

## ✨ Novidades
Criação de Vagas na Interface: Agora é possível criar e gerenciar novas vagas diretamente no aplicativo Streamlit, eliminando a necessidade de scripts externos.

## 📂 Estrutura do Projeto
cv-analyser/
│
├─ streamlit_app.py        # Interface Streamlit (Análise e Criação de Vagas)
├─ process_cvs.py          # Processamento de CVs via IA
├─ download_cv.py          # Baixa CVs do Google Drive
├─ database.py             # Gerencia TinyDB (Análises e Resumos)
├─ openings_db_manager.py  # Gerencia as vagas (Carregar/Salvar/Criar)
├─ pyproject.toml          # Configuração do projeto (Poetry)
├─ poetry.lock             # Lockfile do Poetry
├─ .env                    # Variáveis de ambiente (Groq API)
├─ token.json              # Credenciais OAuth
├─ credentials.json        # Client secrets OAuth
├─ banco-de-talentos/      # CVs baixados do Drive
├─ openings_db.json        # Banco de vagas
├─ applicants.json         # Banco de candidatos processados
├─ ai_prompts.py           # Prompts para IA
├─ utils_cv.py             # Funções utilitárias para CVs
└─ drive/
    └─ authenticate.py     # Autenticação Google Drive

## 🔄 Fluxo do Sistema
flowchart TD
    A[Usuário] -->|Cria vaga via UI| B[streamlit_app.py]
    B -->|Dados da Vaga| C[openings_db.json]
    
    D[Google Drive] -->|CVs PDF/DOCX| E[download_cv.py]
    E --> F[banco-de-talentos/]
    
    F -->|Processamento IA| G[process_cvs.py]
    G -->|Resumos e Scores| H[applicants.json]
    
    C & H --> I[Streamlit Interface]
    I -->|Visualização| J[Usuário analisa candidatos]

## ⚡ Comandos Principais
Ação

Comando

Executar a Aplicação

streamlit run streamlit_app.py

Criar ambiente virtual

python -m venv venv<br>source venv/bin/activate (Linux/Mac)<br>venv\Scripts\activate (Windows)

Instalar dependências

poetry install ou pip install -r requirements.txt

Baixar CVs do Drive

python download_cv.py

Processar CVs

python process_cvs.py

## ⚙️ Configuração
API Groq
Crie um arquivo .env na raiz do projeto com sua chave de API:

GROQ_API_KEY=your_groq_api_key_here

Google Drive
Você ainda pode baixar CVs de pastas do Google Drive.

Autenticação: Execute python drive/authenticate.py para gerar as credenciais OAuth.

IDs das Pastas: Configure os IDs da pasta de CVs no config.ini.

## 📦 Dependências
streamlit, streamlit-aggrid, tinydb, pydantic, langchain-groq, python-dotenv, requests, utilz, utils, pymupdf, python-docx, chardet, google-api-python-client, google-auth-oauthlib, google-auth-httplib2

## 📞 Autoria
Autora: Messer
Projeto: cv-analyser

## 📝 Licença
MIT License