from tinydb import TinyDB, Query
import os

class AnalysisDatabase(TinyDB):
    def __init__(self, db_path='db.json'):
        super().__init__(db_path)
        self.openings = self.table('openings')
        self.briefs = self.table('briefs')
        self.analysis = self.table('analysis')
        self.files = self.table('files')

    # Retorna todas as vagas
    def get_all_openings(self):
        return self.openings.all()

    # Busca vaga por ID
    def get_opening_by_id(self, id):
        opening = Query()
        result = self.openings.search(opening.id == id)
        return result[0] if result else None

    # Busca vaga por título
    def get_opening_by_title(self, title):
        opening = Query()
        result = self.openings.search(opening.title == title)
        return result[0] if result else None

    # Busca brief por ID
    def get_brief_by_id(self, id):
        brief = Query()
        result = self.briefs.search(brief.id == id)
        return result[0] if result else None

    # Busca briefs por ID da vaga
    def get_brief_by_opening_id(self, opening_id):
        brief = Query()
        return self.briefs.search(brief.opening_id == opening_id)

    # Busca briefs por título da vaga
    def get_brief_by_opening_title(self, opening_title):
        brief = Query()
        return self.briefs.search(brief.opening_title == opening_title)

    # Busca análises por ID da vaga
    def get_analysis_by_opening_id(self, opening_id):
        analysis = Query()
        return self.analysis.search(analysis.opening_id == opening_id)

    # Busca análises por título da vaga
    def get_analysis_by_opening_title(self, opening_title):
        analysis = Query()
        return self.analysis.search(analysis.opening_title == opening_title)

    # Deleta todos os briefs de uma vaga por ID
    def delete_all_briefs_by_opening_id(self, opening_id):
        brief = Query()
        self.briefs.remove(brief.opening_id == opening_id)

    # Deleta todas as análises de uma vaga por ID
    def delete_all_analysis_by_opening_id(self, opening_id):
        analysis = Query()
        self.analysis.remove(analysis.opening_id == opening_id)

    # Deleta todos os arquivos de uma vaga por ID
    def delete_all_files_by_opening_id(self, opening_id):
        file = Query()
        self.files.remove(file.opening_id == opening_id)

    # Deleta todos os briefs de uma vaga por título
    def delete_all_briefs_by_opening_title(self, opening_title):
        brief = Query()
        self.briefs.remove(brief.opening_title == opening_title)

    # Deleta todas as análises de uma vaga por título
    def delete_all_analysis_by_opening_title(self, opening_title):
        analysis = Query()
        self.analysis.remove(analysis.opening_title == opening_title)

    # Deleta todos os arquivos de uma vaga por título
    def delete_all_files_by_opening_title(self, opening_title):
        file = Query()
        self.files.remove(file.opening_title == opening_title)
