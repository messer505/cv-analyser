import os
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from database import AnalysisDatabase

# ---------- CONFIGURAÇÃO ----------
COL_PONTUACAO = "Pontuação"  # variável única para pontuação
database = AnalysisDatabase(db_path='applicants.json') 
st.set_page_config(layout='wide', page_title='Analisador de Talentos')

# ---------- SELEÇÃO DE VAGA ----------
openings = database.get_all_openings()
opening_titles = [o.get('title') for o in openings] if openings else []
option = st.selectbox('Escolha a vaga:', opening_titles)

if option:
    selected_opening = next((o for o in openings if o.get('title') == option), None)
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
                'brief_id',
                'id',
            ]
        )

        # Renomeia colunas para exibição
        df.rename(
            columns={
                'name': 'Nome',
                'formal_education': 'Formação',
                'hard_skills': 'Habilidades Técnicas',
                'soft_skills': 'Competências Comportamentais',
                'score': COL_PONTUACAO,
                'brief_id': 'ID do resumo',
                'id': 'ID do candidato',
            },
            inplace=True
        )

        # Configura tabela interativa
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_column(COL_PONTUACAO, header_name=COL_PONTUACAO, sort='desc')
        gb.configure_selection(selection_mode='multiple', use_checkbox=True)
        grid_options = gb.build()

        # Exibe gráfico de pontuação
        st.subheader('Classificação dos Candidatos')
        st.bar_chart(df, x='Nome', y=COL_PONTUACAO, color='Nome', horizontal=True)

        # Exibe tabela interativa
        response = AgGrid(
            df,
            gridOptions=grid_options,
            enable_enterprise_modules=True,
            update_mode=GridUpdateMode.COLUMN_CHANGED,
            theme='streamlit'
        )

        selected_applicants = response.get('selected_rows', [])
        applicants_df = pd.DataFrame(selected_applicants)

        # Função para apagar arquivos de brief
        def delete_files_brief(briefs):
            for brief in briefs:
                path = brief.get('file')
                if os.path.isfile(path):
                    os.remove(path)

        # Botão para limpar análise
        if st.button('Limpar Análise'):
            database.delete_all_briefs_by_opening_id(opening_id)
            database.delete_all_analysis_by_opening_id(opening_id)
            database.delete_all_files_by_opening_id(opening_id)
            st.experimental_rerun()

        # Exibe briefs selecionados
        if not applicants_df.empty:
            for idx, row in applicants_df.iterrows():
                brief_data = database.get_brief_by_id(row['ID do resumo'])
                if brief_data:
                    st.markdown(brief_data.get('content', ''))
                    st.markdown(brief_data.get('conclusion', ''))

                    # Download do PDF
                    file_path = brief_data.get('file', '')
                    if os.path.isfile(file_path):
                        with open(file_path, 'rb') as file:
                            pdf_data = file.read()
                        st.download_button(
                            label=f"Baixar Currículo {row['Nome']}",
                            data=pdf_data,
                            file_name=f"{row['Nome']}.pdf",
                            mime='application/pdf'
                        )
    else:
        st.info("Nenhuma análise encontrada para esta vaga.")
else:
    st.info("Selecione uma vaga para visualizar os candidatos.")
