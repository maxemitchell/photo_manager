# photo_manager

A Python script that uploads a folder of images to Cloudflare R2 and Google Drive. Photos are automatically numbered (1.jpg, 2.jpg, etc.) and uploaded to R2 in the format `photo_collections/{collection_name}/{number}.jpg`.

## Installation

1. **Clone this repository**

2. **Install dependencies using uv:**
   ```bash
   uv sync
   ```

3. **Set up configuration:**
   - Copy `constants.py.example` to `constants.py`
   - Fill in your Cloudflare R2 credentials:
     - `R2_ENDPOINT_URL`: Your R2 endpoint (e.g., `https://abc123.r2.cloudflarestorage.com`)
     - `R2_ACCESS_KEY_ID`: Your R2 access key
     - `R2_SECRET_ACCESS_KEY`: Your R2 secret key
     - `R2_BUCKET_NAME`: Your R2 bucket name

4. **For Google Drive (optional):**
   - Get a `credentials.json` file from the [Google Cloud Platform](https://console.cloud.google.com/)
   - Enable the Google Drive API for your project

## Usage

```bash
uv run photo_manager.py folderName
```

The script will:
1. Ask if you want to upload to Cloudflare R2
2. Ask if you want to upload to Google Drive
3. Process all JPG files in the specified folder, numbering them sequentially
4. Upload to your selected destinations

**First-time Google Drive usage:** A browser will open to authenticate with Google Drive. This creates a `token.pickle` file for future use.

**Resumability:** The script checks for existing files and skips them, so you can safely restart interrupted uploads.

## Testing

Run the test suite to verify everything is working correctly:

```bash
uv run python -m unittest test_photo_manager -v
```

## License
[MIT](https://choosealicense.com/licenses/mit/)
