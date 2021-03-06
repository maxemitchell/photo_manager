import pickle
import os.path
import sys
import datetime
import contentful_management
import platform
from exif import Image
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
from constants import CONTENTFUL_MANAGEMENT_TOKEN, CONTENTFUL_SPACE_ID, SCOPES, DRIVE_PATH_WINDOWS, DRIVE_PATH_WSL, DRIVE_YEAR


def main(folder, drive_path):
    """A personal Photo Manager for Contentful and Google Drive.
    Creates a Root Google Drive folder, along with a year and individual folder for the album.
    Asks the user if they want to upload to Contentful as well, and if so asks for a collection Title.
    """

    contentful_upload = promptUser(
        "Do you want to upload to Contentful? [Y/n]")
    drive_upload = promptUser(
        "Do you want to upload to Google Drive? [Y/n]")

    if contentful_upload:
        collection_title = input("Please provide a title for the Photo Collection:").strip()
        photos = []
        collection_date = None

        print("===== Authenticating Contentful =====")
        try:
            client = contentful_management.Client(CONTENTFUL_MANAGEMENT_TOKEN)
            portfolio_space = client.spaces().find(CONTENTFUL_SPACE_ID)
            master_env = portfolio_space.environments().find('master')
        except:
            contentful_upload = False
            print("!!!!! Authenticating Contentful Failed. Ensure the Management Token and Space ID are correct !!!!!")

    if drive_upload:
        service, folder_id = driveFolderSetup(folder)

    print("===== Iterating Through Photos =====")
    directory = os.fsencode(drive_path + DRIVE_YEAR + "/" + folder)

    for file in os.listdir(directory):
        filename = os.fsdecode(file)

        if filename.endswith(".jpg"):
            filepath = os.fsencode(
                drive_path + DRIVE_YEAR + "/" + folder + "/" + filename)

            if drive_upload:
                photo_metadata = {
                    'name': [filename],
                    'parents': [folder_id]
                }
                photo_media = MediaFileUpload(filepath, mimetype='image/jpeg', resumable=True)
                request = service.files().create(media_body=photo_media, body=photo_metadata)

                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        print("Uploaded", int(status.progress() * 100))
                print("Uploaded", filename, "to Google Drive")

            if contentful_upload:
                if not collection_date:
                    with open(os.fsdecode(filepath), 'rb') as image_file:
                        image = Image(image_file)
                        collection_date = datetime.datetime.strptime(image.datetime_original, '%Y:%m:%d %H:%M:%S').date()

                try:
                    contentful_upload = portfolio_space.uploads().create(os.fsdecode(filepath))
                    asset_attributes = {
                        'fields': {
                            'title': {
                                "en-US": filename
                            },
                            'file': {
                                'en-US': {
                                    'fileName': filename,
                                    'contentType': 'image/jpeg',
                                    'uploadFrom': contentful_upload.to_link().to_json()
                                }
                            }
                        }
                    }
                    contentful_asset = master_env.assets().create(None, asset_attributes) # None lets API generate ID
                    contentful_asset = contentful_asset.process()  # Processing is an async task, so I need to wait to publish it

                except:
                    print('!!!!! Error Uploading Contentful Asset:', filename)
                else:
                    photos.append(contentful_asset)
                    print("Uploaded", filename, "to Contentful")

    if contentful_upload:
        print("===== Creating Contentful Photo Collection =====")
        photoCollection_attributes = {
            'content_type_id': 'photoCollection',
            'fields': {
                'title': {
                    'en-US': collection_title
                },
                'photos': {
                    'en-US': [item.to_link().to_json() for item in photos]
                },
                'collectionDate': {
                    'en-US': collection_date.isoformat()
                },
                'featuredImage': {
                    'en-US': photos[0].to_link().to_json()
                }
            }
        }
        try:
            new_photoCollection = master_env.entries().create(
                None,
                photoCollection_attributes
            ) # None lets API auto generate unique ID
        except:
            print('!!!!! Error Creating Contentful Photo Collection !!!!!')

        print("===== Publishing Uploaded Contentful Images =====")
        for photo in photos:
            try:
                master_env.assets().find(photo.id).publish()
            except:
                print('!!!!! Error Publishing Contentful Asset:', photo.file.fileName)

        print("===== Contentful Upload and Publish Complete! =====")


def driveFolderSetup(folder):
    print("===== Authenticating Google Drive =====")
    try:
        creds = authenticateGoogleDrive(None)
        service = build('drive', 'v3', credentials=creds)
    except:
        print("!!!!! Authenticating Google Drive Failed !!!!!")
        return

    print('===== Finding Google Drive Root Folder =====')
    root_response = service.files().list(q="mimeType = 'application/vnd.google-apps.folder' and name='managed_photos'",
                                            spaces='drive',
                                            fields='nextPageToken, files(id, name)').execute()
    root_files = root_response.get('files', [])

    if not root_files:
        print("===== Creating Google Drive Root Folder =====")
        root_metadata = {
            'name': 'managed_photos',
            'mimeType': 'application/vnd.google-apps.folder'
        }
        root = service.files().create(body=root_metadata,
                                        fields='id').execute()
        root_id = root.get('id')
        print('Google Drive Root Folder Created with ID: ', root_id)
    else:
        root_id = root_files[0].get('id')
        print('Found Google Drive Root Folder:', root_id)

    print('===== Finding Google Drive Year Folder =====')
    year_response = service.files().list(q="mimeType = 'application/vnd.google-apps.folder' and name='"+DRIVE_YEAR+"'",
                                            spaces='drive',
                                            fields='nextPageToken, files(id, name)').execute()
    year_files = year_response.get('files', [])

    if not year_files:
        print("===== Creating Google Drive Year Folder =====")
        year_metadata = {
            'name': [DRIVE_YEAR],
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [root_id]
        }
        year_folder = service.files().create(body=year_metadata,
                                                fields='id').execute()
        year_id = year_folder.get('id')
        print('Google Drive Year Folder Created with ID: ', year_id)
    else:
        year_id = year_files[0].get('id')
        print('Found Year Folder:', year_id)

    print("===== Creating Provided Folder in Google Drive =====")
    folder_metadata = {
        'name': [folder],
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [year_id]
    }
    drive_folder = service.files().create(body=folder_metadata,
                                            fields='id').execute()
    folder_id = drive_folder.get('id')
    print('Folder Created with ID: ', folder_id)

    return service, folder_id


def authenticateGoogleDrive(creds):
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


def promptUser(prompt):
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    while True:
        choice = input(prompt).lower().strip()
        if choice == '':
            return True
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes' or 'no' (or 'y' or 'n').")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Please provide a folder path.")
    else:
        if platform.system() == 'Windows':
            drive_path = DRIVE_PATH_WINDOWS
        else:
            drive_path = DRIVE_PATH_WSL

        if os.path.isdir(drive_path + DRIVE_YEAR + "/" + sys.argv[1]):
            main(sys.argv[1], drive_path)
        else:
            print("Please provide a folder that exists.")
