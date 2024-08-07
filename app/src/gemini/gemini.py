import requests, json, os, configparser
from . import image, helpers

def loadGeminiConfig():
    configPath = os.path.join(helpers.currPath(), 'gemini.env')
    if not os.path.exists(configPath):
        raise FileNotFoundError("Gemini configuration file not found.")

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
        raise KeyError(f"Missing configuration key in gemini.env: {e}")

    return geminiConfig

def getGeminiResponse(imgPath):
    geminiConfig = loadGeminiConfig()

    url = f"{geminiConfig['baseUrl']}/{geminiConfig['model']}:generateContent?key={geminiConfig['apiKey']}"
    base64Img = image.ImageHandler.encodeImg(imgPath)

    headers = {
        "Content-Type": "application/json"
    }

    data = json.dumps({
        "contents": [
            {
                "parts": [
                    {"text": geminiConfig["prompt"]},
                    {
                        "inline_data": {
                            "mime_type": helpers.determineMimeType(imgPath),
                            "data": base64Img
                        }
                    }
                ]
            }
        ]
    })

    try:
        response = requests.post(url, headers=headers, data=data)

        if response.status_code != 200:
            return f"Error: {response.status_code} - {response.text}"
        
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    
    except requests.exceptions.RequestException as e:
        return f"Request failed: {str(e)}"