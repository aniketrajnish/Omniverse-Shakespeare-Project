# ----------------------------------------------------------------------------------
# Helper functions to load confi, getting current path and determine image mime type
# ----------------------------------------------------------------------------------

import os, json

def loadConfig(file):
    '''
    Load a JSON configuration file.

    Args:
        file (str): The path to the configuration file.

    Returns:
        dict: The configuration data
    '''
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception(f'Could not find config file: {file}')
    except json.JSONDecodeError:
        raise Exception(f'Could not parse config file: {file}')
    
def currPath():
    '''
    Get the current path of the script.

    Returns:
        str: The current path of the script
    '''
    return os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

def determineMimeType(fileName):
    '''
    Determine the MIME type of an image file based on its extension.

    Args:
        fileName (str): The name of the image file.

    Returns:
        str: The MIME type of the image file.
    '''
    ext = fileName.split('.')[-1].lower()

    if ext == 'jpg':
        return 'image/jpeg'

    supportedExts = ['jpg', 'jpeg', 'png', 'heic', 'heif']
    
    if ext not in supportedExts:
        raise Exception(f'Unsupported file extension: {ext}')
    else:
        return f'image/{ext}'
    