# -----------------------------------------------------------------------------
# Functions for interacting with the Gemini API using cURL requests.
# Using gemini to generate context for shakespeare about an image.
# -----------------------------------------------------------------------------

import requests, json, os, configparser
from . import image, helpers

def loadGeminiConfig():
    '''
    Load the Gemini configuration from the gemini.env file using ConfigParser.

    Returns:
        dict: The Gemini configuration data
    '''
    configPath = os.path.join(helpers.currPath(), 'gemini.env')
    if not os.path.exists(configPath):
        raise FileNotFoundError('Gemini configuration file not found.')

    config = configparser.ConfigParser()
    config.read(configPath)
    
    try:        
        geminiConfig = {
            'baseUrl': config.get('GEMINI', 'BASE_URL'),
            'apiKey': config.get('GEMINI', 'API_KEY'),
            'model': config.get('GEMINI', 'MODEL'),
            'prompt': config.get('GEMINI', 'PROMPT')
        }
    except configparser.NoOptionError as e:
        raise KeyError(f'Missing configuration key in gemini.env: {e}')

    return geminiConfig

def getGeminiResponse(imgPath):
    '''
    Send a POST request to the Gemini API to generate content based on an image.

    Args:
        imgPath (str): The path to the image file.

    Returns:
        str: The response from the Gemini API
    '''
    geminiConfig = loadGeminiConfig()

    url = f"{geminiConfig['baseUrl']}/{geminiConfig['model']}:generateContent?key={geminiConfig['apiKey']}"
    base64Img = image.ImageHandler.encodeImg(imgPath)

    headers = {
        'Content-Type': 'application/json'
    }

    data = json.dumps({
        'contents': [
            {
                'parts': [
                    {'text': geminiConfig['prompt']},
                    {
                        'inline_data': {
                            'mime_type': helpers.determineMimeType(imgPath),
                            'data': base64Img
                        }
                    }
                ]
            }
        ]
    })

    try:
        response = requests.post(url, headers=headers, data=data)

        if response.status_code != 200:
            return f'Error: {response.status_code} - {response.text}'
        
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    
    except requests.exceptions.RequestException as e:
        return f'Request failed: {str(e)}'