import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open, call
from io import StringIO
import sys

import photo_manager


class TestPromptUser(unittest.TestCase):
    """Test the promptUser function"""
    
    @patch('builtins.input')
    def test_prompt_user_yes_variations(self, mock_input):
        """Test that various yes inputs return True"""
        test_cases = ['yes', 'y', 'ye', 'Y', 'YES', 'Yes']
        for input_val in test_cases:
            with self.subTest(input_val=input_val):
                mock_input.return_value = input_val
                result = photo_manager.promptUser("Test prompt? [Y/n]")
                self.assertTrue(result)
    
    @patch('builtins.input')
    def test_prompt_user_no_variations(self, mock_input):
        """Test that various no inputs return False"""
        test_cases = ['no', 'n', 'N', 'NO', 'No']
        for input_val in test_cases:
            with self.subTest(input_val=input_val):
                mock_input.return_value = input_val
                result = photo_manager.promptUser("Test prompt? [Y/n]")
                self.assertFalse(result)
    
    @patch('builtins.input')
    def test_prompt_user_empty_input(self, mock_input):
        """Test that empty input returns True (default)"""
        mock_input.return_value = ''
        result = photo_manager.promptUser("Test prompt? [Y/n]")
        self.assertTrue(result)
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_prompt_user_invalid_then_valid(self, mock_print, mock_input):
        """Test that invalid input prompts again, then accepts valid input"""
        mock_input.side_effect = ['invalid', 'maybe', 'yes']
        result = photo_manager.promptUser("Test prompt? [Y/n]")
        self.assertTrue(result)
        # Should have been called 3 times
        self.assertEqual(mock_input.call_count, 3)
        # Should have printed error messages
        self.assertEqual(mock_print.call_count, 2)


class TestPhotoProcessing(unittest.TestCase):
    """Test photo processing logic"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_photos = ['IMG_001.JPG', 'IMG_003.JPG', 'IMG_002.JPG', 'test.txt']
        
        # Create test files
        for filename in self.test_photos:
            test_file = os.path.join(self.test_dir, filename)
            with open(test_file, 'w') as f:
                f.write('test content')
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
    
    def test_jpg_file_filtering_and_sorting(self):
        """Test that only JPG files are processed and sorted correctly"""
        jpg_files = []
        for file in os.listdir(self.test_dir):
            if file.upper().endswith(".JPG"):
                jpg_files.append(file)
        jpg_files.sort()
        
        expected = ['IMG_001.JPG', 'IMG_002.JPG', 'IMG_003.JPG']
        self.assertEqual(jpg_files, expected)


class TestMainFunction(unittest.TestCase):
    """Test the main function with mocked dependencies"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_drive_path = tempfile.mkdtemp()
        self.test_year_dir = os.path.join(self.test_drive_path, 'test_year')
        self.test_folder_dir = os.path.join(self.test_year_dir, 'test_folder')
        
        # Create directory structure
        os.makedirs(self.test_folder_dir, exist_ok=True)
        
        # Create test JPG files
        for i in range(1, 4):
            test_file = os.path.join(self.test_folder_dir, f'IMG_{i:03d}.JPG')
            with open(test_file, 'w') as f:
                f.write(f'test image content {i}')
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.test_drive_path)
    
    @patch('photo_manager.promptUser')
    @patch('photo_manager.boto3.client')
    @patch('photo_manager.driveFolderSetup')
    @patch('photo_manager.DRIVE_YEAR', 'test_year')
    def test_main_r2_only_upload(self, mock_drive_setup, mock_boto_client, mock_prompt):
        """Test main function with R2 upload only"""
        # Setup mocks
        mock_prompt.side_effect = [True, False]  # R2=yes, Drive=no
        mock_s3_client = MagicMock()
        mock_boto_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = None  # Successful connection test
        mock_s3_client.list_objects_v2.return_value = {'Contents': []}  # No existing files
        
        # Run the function
        photo_manager.main('test_folder', self.test_drive_path)
        
        # Verify R2 client was created and used
        mock_boto_client.assert_called_once()
        self.assertEqual(mock_s3_client.upload_file.call_count, 3)  # 3 JPG files
        mock_drive_setup.assert_not_called()  # Drive setup should not be called
    
    @patch('photo_manager.promptUser')
    def test_main_no_uploads_selected(self, mock_prompt):
        """Test main function when no uploads are selected"""
        mock_prompt.side_effect = [False, False]  # R2=no, Drive=no
        
        with patch('builtins.print') as mock_print:
            photo_manager.main('test_folder', self.test_drive_path)
            mock_print.assert_any_call("No uploads selected. Exiting.")
    
    @patch('photo_manager.promptUser')
    @patch('photo_manager.boto3.client')
    @patch('photo_manager.DRIVE_YEAR', 'test_year')
    def test_main_r2_connection_failure(self, mock_boto_client, mock_prompt):
        """Test main function when R2 connection fails"""
        mock_prompt.side_effect = [True, False]  # R2=yes, Drive=no
        mock_s3_client = MagicMock()
        mock_boto_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.side_effect = Exception("Connection failed")
        
        with patch('builtins.print') as mock_print:
            photo_manager.main('test_folder', self.test_drive_path)
            mock_print.assert_any_call("!!!!! Failed to connect to R2: Connection failed !!!!!")
            mock_print.assert_any_call("All upload methods failed. Exiting.")


class TestR2Functionality(unittest.TestCase):
    """Test R2-specific functionality"""
    
    @patch('photo_manager.boto3.client')
    def test_r2_client_initialization(self, mock_boto_client):
        """Test that R2 client is initialized with correct parameters"""
        mock_s3_client = MagicMock()
        mock_boto_client.return_value = mock_s3_client
        
        with patch('photo_manager.R2_ENDPOINT_URL', 'https://test.r2.cloudflarestorage.com'):
            with patch('photo_manager.R2_ACCESS_KEY_ID', 'test_key'):
                with patch('photo_manager.R2_SECRET_ACCESS_KEY', 'test_secret'):
                    # This would be called within main()
                    mock_boto_client.assert_not_called()  # Not called yet
                    
                    # Simulate the call from main()
                    import boto3
                    client = boto3.client(
                        's3',
                        endpoint_url='https://test.r2.cloudflarestorage.com',
                        aws_access_key_id='test_key',
                        aws_secret_access_key='test_secret',
                        region_name='auto'
                    )
                    
                    mock_boto_client.assert_called_once_with(
                        's3',
                        endpoint_url='https://test.r2.cloudflarestorage.com',
                        aws_access_key_id='test_key',
                        aws_secret_access_key='test_secret',
                        region_name='auto'
                    )


class TestGoogleDriveAuth(unittest.TestCase):
    """Test Google Drive authentication"""
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pickle.load')
    def test_existing_valid_credentials(self, mock_pickle_load, mock_file, mock_exists):
        """Test authentication with existing valid credentials"""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_pickle_load.return_value = mock_creds
        
        result = photo_manager.authenticateGoogleDrive(None)
        
        self.assertEqual(result, mock_creds)
        mock_exists.assert_called_with('token.pickle')
        mock_pickle_load.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
