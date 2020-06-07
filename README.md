# photo_manager

A Python script that uploads a folder of images to both Contentful and Google Drive.

## Installation

Clone this repo, and create your own *constants.py* file. You'll also need to get a *credentials.json* file from the [Google Cloud Platform](https://console.cloud.google.com/).

## Usage

```python
pip3 install -r requirements.txt
python3 photo_manager.py folderName
```

The first time you run it, a browser will open up to ask you to authenticate with Google Drive in order to allow the script to create Google Drive files and folders. This is only done once, and afterwards the generated *token.pickle* file stores your encrypted credentials.

## License
[MIT](https://choosealicense.com/licenses/mit/)
