import os
import requests
import json
import configparser

def loadConvaiConfig():
    configPath = os.path.join(os.path.dirname(__file__), 'convai.env')
    if not os.path.exists(configPath):
        raise FileNotFoundError("Convai configuration file not found.")

    config = configparser.ConfigParser()
    config.read(configPath)
    
    try:    
        convaiConfig = {            
            'apiKey': config.get('CONVAI', 'API_KEY'),
            'characterId': config.get('CONVAI', 'CHARACTER_ID'),
            'channel': config.get('CONVAI', 'CHANNEL'),
            'actions': config.get('CONVAI', 'ACTIONS'),
            'sessionId': config.get('CONVAI', 'SESSION_ID'),
            'baseBackstory' : config.get('CONVAI', 'BASE_BACKSTORY').replace("\\n", "\n")    
        }
    except configparser.NoOptionError as e:
        raise KeyError(f"Missing configuration key in convai.env: {e}")

    return convaiConfig

def updateCharBackstory(newBackstory):
    config = loadConvaiConfig()
    url = "https://api.convai.com/character/update"
    payload = json.dumps({
        "charID": config['characterId'],
        "backstory": newBackstory
    })
    headers = {
        'CONVAI-API-KEY': config['apiKey'],
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        print("Character updated successfully.")
    else:
        print(f"Failed to update character: {response.status_code} - {response.text}")

def appendToCharBackstory(backstoryUpdate):
    config = loadConvaiConfig()
    currBackstory = config['baseBackstory']
    if currBackstory:
        newBackstory = f"{currBackstory}\n{backstoryUpdate}"
        updateCharBackstory(newBackstory)