import pickle
import os.path
import sys
import platform
import boto3
from botocore.exceptions import ClientError
from exif import Image
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
from constants import SCOPES, DRIVE_PATH_WINDOWS, DRIVE_PATH_WSL, DRIVE_YEAR, R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME


def main(folder, drive_path):
    """A personal Photo Manager for Cloudflare R2 and Google Drive.
    Creates a Root Google Drive folder, along with a year and individual folder for the album.
    Renames photos to numbered format and uploads to R2 bucket.
    """

    r2_upload = promptUser("Do you want to upload to Cloudflare R2? [Y/n]")
    drive_upload = promptUser("Do you want to upload to Google Drive? [Y/n]")

    if not r2_upload and not drive_upload:
        print("No uploads selected. Exiting.")
        return

    # Initialize R2 client if needed
    s3_client = None
    if r2_upload:
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=R2_ENDPOINT_URL,
                aws_access_key_id=R2_ACCESS_KEY_ID,
                aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                region_name='auto'
            )
            # Test connection
            s3_client.head_bucket(Bucket=R2_BUCKET_NAME)
            print("===== Connected to Cloudflare R2 =====")
        except Exception as e:
            print(f"!!!!! Failed to connect to R2: {e} !!!!!")
            r2_upload = False

    # Initialize Google Drive if needed
    service = None
    folder_id = None
    if drive_upload:
        service, folder_id = driveFolderSetup(folder)
        if not service:
            drive_upload = False

    if not r2_upload and not drive_upload:
        print("All upload methods failed. Exiting.")
        return

    print("===== Processing Photos =====")
    directory = os.path.join(drive_path, DRIVE_YEAR, folder)
    
    if not os.path.isdir(directory):
        print(f"Directory {directory} does not exist.")
        return

    # Get all JPG files and sort them for consistent numbering
    jpg_files = []
    for file in os.listdir(directory):
        if file.upper().endswith(".JPG"):
            jpg_files.append(file)
    
    jpg_files.sort()  # Sort for consistent numbering
    
    if not jpg_files:
        print("No JPG files found in directory.")
        return

    print(f"Found {len(jpg_files)} JPG files")

    # Check existing R2 files if uploading to R2
    existing_r2_files = set()
    if r2_upload:
        try:
            r2_prefix = f"photo_collections/{folder}/"
            response = s3_client.list_objects_v2(Bucket=R2_BUCKET_NAME, Prefix=r2_prefix)
            if 'Contents' in response:
                existing_r2_files = {obj['Key'].split('/')[-1] for obj in response['Contents']}
            print(f"Found {len(existing_r2_files)} existing files in R2")
        except Exception as e:
            print(f"Warning: Could not check existing R2 files: {e}")

    # Process each photo
    for index, filename in enumerate(jpg_files, 1):
        filepath = os.path.join(directory, filename)
        new_filename = f"{index}.jpg"
        
        print(f"Processing {filename} -> {new_filename}")

        # Upload to R2 if requested
        if r2_upload:
            r2_key = f"photo_collections/{folder}/{new_filename}"
            
            if new_filename not in existing_r2_files:
                try:
                    s3_client.upload_file(
                        filepath, 
                        R2_BUCKET_NAME, 
                        r2_key,
                        ExtraArgs={'ContentType': 'image/jpeg'}
                    )
                    print(f"Uploaded {new_filename} to R2")
                except Exception as e:
                    print(f"!!!!! Error uploading {new_filename} to R2: {e}")
            else:
                print(f"File {new_filename} already exists in R2. Skipping.")

        # Upload to Google Drive if requested
        if drive_upload:
            # Check if file already exists in Google Drive
            file_exists = service.files().list(
                q=f"name='{new_filename}' and '{folder_id}' in parents",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            if not file_exists.get('files', []):
                try:
                    photo_metadata = {
                        'name': new_filename,
                        'parents': [folder_id]
                    }
                    photo_media = MediaFileUpload(filepath, mimetype='image/jpeg', resumable=True)
                    request = service.files().create(media_body=photo_media, body=photo_metadata)

                    response = None
                    while response is None:
                        status, response = request.next_chunk()
                        if status:
                            print(f"Uploaded {int(status.progress() * 100)}%")
                    print(f"Uploaded {new_filename} to Google Drive")
                except Exception as e:
                    print(f"!!!!! Error uploading {new_filename} to Google Drive: {e}")
            else:
                print(f"File {new_filename} already exists in Google Drive. Skipping.")

    print("===== Upload Complete! =====")


def driveFolderSetup(folder):
    print("===== Authenticating Google Drive =====")
    try:
        creds = authenticateGoogleDrive(None)
        service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"!!!!! Authenticating Google Drive Failed: {e} !!!!!")
        return None, None

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
    year_response = service.files().list(q=f"mimeType = 'application/vnd.google-apps.folder' and name='{DRIVE_YEAR}' and '{root_id}' in parents",
                                        spaces='drive',
                                        fields='nextPageToken, files(id, name)').execute()
    year_files = year_response.get('files', [])

    if not year_files:
        print("===== Creating Google Drive Year Folder =====")
        year_metadata = {
            'name': DRIVE_YEAR,
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

    print("===== Finding or Creating Provided Folder in Google Drive =====")
    folder_response = service.files().list(q=f"mimeType = 'application/vnd.google-apps.folder' and name='{folder}' and '{year_id}' in parents",
                                           spaces='drive',
                                           fields='nextPageToken, files(id, name)').execute()
    folder_files = folder_response.get('files', [])

    if not folder_files:
        folder_metadata = {
            'name': folder,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [year_id]
        }
        drive_folder = service.files().create(body=folder_metadata,
                                             fields='id').execute()
        folder_id = drive_folder.get('id')
        print('Folder Created with ID: ', folder_id)
    else:
        folder_id = folder_files[0].get('id')
        print('Found existing folder:', folder_id)

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

        if os.path.isdir(os.path.join(drive_path, DRIVE_YEAR, sys.argv[1])):
            main(sys.argv[1], drive_path)
        else:
            print("Please provide a folder that exists.")
