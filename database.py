from tinydb import TinyDB, Query
import os
import json
import uuid

class AnalysisDatabase(TinyDB):
    def __init__(self, db_path='db.json'):
        super().__init__(db_path)
        # Note: The 'openings' table logic is now handled by openings_db_manager.py
        self.briefs = self.table('briefs')
        self.analysis = self.table('analysis')
        self.files = self.table('files')

    # Add brief data
    def add_brief_data(self, content, file_path):
        brief_id = str(uuid.uuid4())
        self.briefs.insert({
            "id": brief_id,
            "content": content,
            "file": file_path
        })
        return brief_id

    # Add analysis data
    def add_analysis_data(self, opening_id, brief_id, analysis_data):
        analysis_id = str(uuid.uuid4())
        self.analysis.insert({
            "id": analysis_id,
            "opening_id": opening_id,
            "brief_id": brief_id,
            **analysis_data
        })
        return analysis_id

    # Getters
    def get_brief_by_id(self, brief_id):
        brief = Query()
        result = self.briefs.search(brief.id == brief_id)
        return result[0] if result else None
    
    def get_analysis_by_opening_id(self, opening_id):
        analysis = Query()
        return self.analysis.search(analysis.opening_id == opening_id)
    
    # You can keep the 'by_title' getters if you need them for some reason,
    # but the new logic is designed to use IDs.
    def get_analysis_by_opening_title(self, opening_title):
        analysis = Query()
        return self.analysis.search(analysis.opening_title == opening_title)

    # Deletion methods
    def delete_all_briefs_by_opening_id(self, opening_id):
        analysis_q = Query()
        analyses_to_delete = self.analysis.search(analysis_q.opening_id == opening_id)
        brief_ids_to_delete = {a.get("brief_id") for a in analyses_to_delete}
        
        brief_q = Query()
        self.briefs.remove(brief_q.id.one_of(brief_ids_to_delete))

    def delete_all_analysis_by_opening_id(self, opening_id):
        analysis_q = Query()
        self.analysis.remove(analysis_q.opening_id == opening_id)

    def delete_all_files_by_opening_id(self, opening_id):
        # This function should be moved or refactored. The app should handle file deletion
        # based on the folder name provided by the openings_db_manager.
        # It's better not to tightly couple file system operations to the TinyDB class.
        pass