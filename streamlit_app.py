import os
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from database import AnalysisDatabase
from openings_db_manager import load_openings_db, create_new_opening

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
            st.stop()

        opening_id = selected_opening.get("id")
        data = database.get_analysis_by_opening_id(opening_id)

        if data:
            df = pd.DataFrame(
                data,
                columns=[
                    'name',
                    'formal_education',
                    'hard_skills',
                    'soft_skills',
                    'score',
                    'seniority_fit',
                    'brief_id',
                    'id',
                ]
            )

            df.rename(
                columns={
                    'name': 'Nome',
                    'formal_education': 'Formação',
                    'hard_skills': 'Habilidades Técnicas',
                    'soft_skills': 'Competências Comportamentais',
                    'score': COL_PONTUACAO,
                    'seniority_fit': 'Senioridade',
                    'brief_id': 'ID do resumo',
                    'id': 'ID do candidato',
                },
                inplace=True
            )
            
            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_pagination(paginationAutoPageSize=True)
            gb.configure_column(COL_PONTUACAO, header_name=COL_PONTUACAO, sort='desc')
            gb.configure_selection(selection_mode='multiple', use_checkbox=True)
            grid_options = gb.build()

            st.subheader('Classificação dos Candidatos')
            st.bar_chart(df.sort_values(COL_PONTUACAO), x='Nome', y=COL_PONTUACAO, color='Nome', horizontal=True)

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
                for idx, row in applicants_df.iterrows():
                    brief_data = database.get_brief_by_id(row['ID do resumo'])
                    if brief_data:
                        st.markdown(brief_data.get('content', ''))
                        st.markdown(brief_data.get('conclusion', ''))

        else:
            st.info("Nenhuma análise encontrada para esta vaga.")
    else:
        st.info("Selecione uma vaga para visualizar os candidatos.")

def show_create_opening_tab():
    """Exibe o formulário para criar novas vagas."""
    st.subheader('Criar Nova Vaga')
    with st.form(key='create_opening_form'):
        title = st.text_input('Título da Vaga *')
        folder = st.text_input('Nome da Pasta de Currículos *', help="Ex: 'desenvolvimento', 'vendas'...")
        intro = st.text_area('Introdução/Descrição da Vaga')
        pre_requisites = st.text_area('Pré-requisitos')
        main_activities = st.text_area('Principais Atividades')
        add_infos = st.text_area('Informações Adicionais')
        
        submit_button = st.form_submit_button(label='Criar Vaga')

    if submit_button:
        if not title or not folder:
            st.error("O Título e o Nome da Pasta são obrigatórios.")
        else:
            new_opening = create_new_opening(title, intro, pre_requisites, main_activities, add_infos, folder)
            st.success(f"Vaga '{new_opening['title']}' criada com sucesso! (ID: {new_opening['id']})")
            st.info("Para analisar currículos para esta vaga, adicione os PDFs à pasta 'banco-de-talentos/" + new_opening['folder'] + "'.")

# ---------- NAVEGAÇÃO ----------
tab1, tab2 = st.tabs(["Análise de Vagas", "Criar Nova Vaga"])

with tab1:
    show_analysis_tab()

with tab2:
    show_create_opening_tab()
