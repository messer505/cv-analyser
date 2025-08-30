import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from database import AnalysisDatabase
from openings_db_manager import load_openings_db, create_new_opening
import json

# ---------- CONFIGURAÇÃO ----------
COL_PONTUACAO = "Pontuação"
database = AnalysisDatabase(db_path='applicants.json')
st.set_page_config(layout='wide', page_title='Analisador de Talentos')

# ---------- FUNÇÕES DO APP ----------
def show_analysis_tab():
    """Exibe a interface de análise de vagas existentes."""
    openings = load_openings_db()
    opening_titles = [o.get('title') for o in openings.values()] if openings else []
    
    if not opening_titles:
        st.info("Nenhuma vaga cadastrada. Vá para a aba 'Criar Nova Vaga'.")
        return

    option = st.selectbox('Escolha a vaga:', opening_titles)

    if option:
        selected_opening = openings.get(option)
        if not selected_opening:
            st.warning("Vaga selecionada não encontrada.")
            return

        opening_id = selected_opening.get("id")
        data = database.get_analysis_by_opening_id(opening_id)

        if data:
            df = pd.DataFrame(data)
            df['name'] = df['structured_data'].apply(lambda x: x.get('name'))
            df['formal_education'] = df['structured_data'].apply(lambda x: x.get('formal_education'))
            df['hard_skills'] = df['structured_data'].apply(lambda x: ", ".join(x.get('hard_skills', [])))
            df['soft_skills'] = df['structured_data'].apply(lambda x: ", ".join(x.get('soft_skills', [])))
            df['score'] = df['score'].fillna(0)
            df['total_experience_years'] = df['total_experience_years'].fillna('N/A')

            df = df.rename(columns={
                'name': 'Nome',
                'formal_education': 'Formação',
                'hard_skills': 'Habilidades Técnicas',
                'soft_skills': 'Competências Comportamentais',
                'score': COL_PONTUACAO,
                'total_experience_years': 'Experiência (Anos)'
            })
            
            df = df[['Nome', 'Formação', 'Habilidades Técnicas', 'Competências Comportamentais', 'Experiência (Anos)', COL_PONTUACAO, 'brief_id', 'id']]
            df[COL_PONTUACAO] = pd.to_numeric(df[COL_PONTUACAO], errors='coerce').fillna(0)
            
            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_pagination(paginationAutoPageSize=True)
            gb.configure_column(COL_PONTUACAO, header_name=COL_PONTUACAO, sort='desc')
            gb.configure_selection(selection_mode='multiple', use_checkbox=True)
            grid_options = gb.build()

            st.subheader('Classificação dos Candidatos')
            st.bar_chart(df.sort_values(COL_PONTUACAO, ascending=False), x='Nome', y=COL_PONTUACAO, color='Nome', horizontal=True)

            response = AgGrid(
                df,
                gridOptions=grid_options,
                enable_enterprise_modules=True,
                update_mode=GridUpdateMode.COLUMN_CHANGED,
                theme='streamlit'
            )

            selected_applicants = response.get('selected_rows', [])
            applicants_df = pd.DataFrame(selected_applicants)

            if st.button('Limpar Análise'):
                database.delete_all_briefs_by_opening_id(opening_id)
                database.delete_all_analysis_by_opening_id(opening_id)
                st.experimental_rerun()

            if not applicants_df.empty:
                st.subheader('Análise Detalhada')
                for idx, row in applicants_df.iterrows():
                    brief_data = database.get_brief_by_id(row['brief_id'])
                    if brief_data:
                        st.markdown(brief_data.get('content', ''))
        else:
            st.info("Nenhuma análise encontrada para esta vaga.")
    else:
        st.info("Selecione uma vaga para visualizar os candidatos.")

def show_create_opening_tab():
    """Exibe o formulário para criar novas vagas."""
    st.subheader('Criar Nova Vaga')
    with st.form(key='create_opening_form'):
        st.write('Campos marcados com * são obrigatórios.')
        
        # ID da vaga com a dica no ícone de interrogação
        opening_id = st.text_input(
            'ID da Vaga *', 
            help="O ID é composto pelo CBO (sem traços ou pontos) + 00Y, em que Y representa o nível da vaga (1, 2, 3...)"
        )

        title = st.text_input('Título da Vaga *')
        folder = st.text_input('Nome da Pasta de Currículos *', help="Ex: 'desenvolvimento', 'vendas'...")
        intro = st.text_area('Introdução/Descrição da Vaga *')
        pre_requisites = st.text_area('Pré-requisitos *')
        main_activities = st.text_area('Principais Atividades *')
        add_infos = st.text_area('Informações Adicionais *')
        
        # Campos de habilidades e detalhes adicionais sem o título de seção
        local = st.text_input('Localização *', help="Ex: 'Juiz de Fora - MG'")
        nivel = st.text_input('Nível da Vaga *', help="Ex: 'júnior', 'pleno', 'sênior' ou 'júnior: 1 a 3 anos'")
        disponibilidade = st.text_input('Disponibilidade *', help="Ex: 'Remoto', 'Híbrido' ou 'Presencial'")
        
        soft_skills_str = st.text_area('Soft Skills * (separar por vírgula)', help="Ex: 'Comunicação, Liderança, Empatia'")
        hard_skills_str = st.text_area('Hard Skills * (separar por vírgula)', help="Ex: 'Python, JavaScript, SQL'")
        
        submit_button = st.form_submit_button(label='Criar Vaga')

    if submit_button:
        if not (title and folder and intro and pre_requisites and main_activities and add_infos and local and nivel and disponibilidade and soft_skills_str and hard_skills_str and opening_id):
            st.error("Por favor, preencha todos os campos obrigatórios.")
        else:
            soft_skills = [s.strip() for s in soft_skills_str.split(',') if s.strip()]
            hard_skills = [h.strip() for h in hard_skills_str.split(',') if h.strip()]
            
            new_opening = create_new_opening(
                title=title,
                intro=intro,
                pre_requisites=pre_requisites,
                main_activities=main_activities,
                add_infos=add_infos,
                folder=folder,
                local=local,
                nivel=nivel,
                disponibilidade=disponibilidade,
                soft_skills=soft_skills,
                hard_skills=hard_skills,
                opening_id=opening_id
            )
            st.success(f"Vaga '{new_opening['title']}' criada com sucesso! (ID: {new_opening['id']})")
            st.info("Para analisar currículos para esta vaga, adicione os PDFs à pasta 'banco-de-talentos/" + new_opening['folder'] + "'.")

# ---------- NAVEGAÇÃO E EXECUÇÃO PRINCIPAL ----------
def main():
    tab1, tab2 = st.tabs(["Análise de Vagas", "Criar Nova Vaga"])
    with tab1:
        show_analysis_tab()
    with tab2:
        show_create_opening_tab()

if __name__ == "__main__":
    main()