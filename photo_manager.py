import pickle
import os.path
import sys
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
DRIVE_PATH = "D:/edited pics/twenty twenty/"

def main(folder):
    """A personal Photo Manager for Contentful and Google Drive.
    Creates a google drive folder and adds the photos to it.
    """
    
    print("===== Authenticating =====")
    creds = authenticate(None)

    service = build('drive', 'v3', credentials=creds)

    print('===== Finding Root Folder =====')
    response = service.files().list(q="mimeType = 'application/vnd.google-apps.folder' and name='managed_photos'",
                                        spaces='drive',
                                        fields='nextPageToken, files(id, name)').execute()
    files = response.get('files', [])

    if not files:
        print("===== Creating Root Folder =====")
        root_metadata = {
            'name': 'managed_photos',
            'mimeType': 'application/vnd.google-apps.folder'
        }
        root = service.files().create(body=root_metadata,
                                            fields='id').execute()
        root_id = root.get('id')
        print('Root Folder Created with ID: ', root_id)
    else:
        root_id = files[0].get('id')
        print('Found Root Folder:', root_id)

    print("===== Creating Provided Folder =====")
    folder_metadata = {
        'name': [folder],
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [root_id]
    }
    drive_folder = service.files().create(body=folder_metadata,
                                    fields='id').execute()
    folder_id = drive_folder.get('id')
    print('Folder Created with ID: ', folder_id)

    print("===== Iterating Through Folder =====")
    directory = os.fsencode(DRIVE_PATH + folder)

    for file in os.listdir(directory):
        filename = os.fsdecode(file)

        if filename.endswith(".jpg"):
            photo_metadata = {
                'name': [filename],
                'parents': [folder_id]
            }
            filepath = os.fsencode(DRIVE_PATH + folder + "/" + filename)
            photo_media = MediaFileUpload(filepath, mimetype='image/jpeg', resumable=True)
            request = service.files().create(media_body=photo_media, body=photo_metadata)

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print("Uploaded", int(status.progress() * 100))
            print("Uploaded", filename)

    print("Sync Complete!")

def authenticate(creds):
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds

if __name__ == '__main__':
    # if len(sys.argv) < 2:
    #     print("Please provide a folder path.")
    # else:
    #     main(sys.argv[1])
    main("03_15_sb_road_trip")
    
