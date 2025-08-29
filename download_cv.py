import os
import configparser
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from drive.authenticate import TOKEN_FILE

# ---------- CONFIGURAÇÃO ----------
config = configparser.ConfigParser()
config.read('config.ini')
CV_FOLDER_ID = config['GOOGLE_DRIVE']['CV_FOLDER_ID']

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
service = build('drive', 'v3', credentials=creds)

def download_folder(folder_id, local_path):
    if not os.path.exists(local_path):
        os.makedirs(local_path)

    results = service.files().list(
        q=f"'{folder_id}' in parents",
        fields="files(id, name, mimeType)"
    ).execute()

    files = results.get('files', [])

    if not files:
        print(f"[VAZIO] {folder_id}")
        return

    for item in files:
        file_id = item['id']
        file_name = item['name']
        mime_type = item['mimeType']

        if mime_type == 'application/vnd.google-apps.folder':
            print(f"[PASTA] {file_name}")
            sub_folder_path = os.path.join(local_path, file_name)
            download_folder(file_id, sub_folder_path)
        else:
            print(f"[ARQUIVO] {file_name}")
            request = service.files().get_media(fileId=file_id)
            file_path = os.path.join(local_path, file_name)
            with open(file_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        print(f"  Progresso: {int(status.progress() * 100)}%")

if __name__ == "__main__":
    download_folder(CV_FOLDER_ID, "./banco-de-talentos")
