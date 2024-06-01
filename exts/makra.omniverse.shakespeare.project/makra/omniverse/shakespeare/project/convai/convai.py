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
            'apiKey': config.get('CONVAI', 'api_key'),
            'characterId': config.get('CONVAI', 'character_id'),
            'channel': config.get('CONVAI', 'channel'),
            'actions': config.get('CONVAI', 'actions'),
            'sessionId': config.get('CONVAI', 'session_id')            
        }
    except configparser.NoOptionError as e:
        raise KeyError(f"Missing configuration key in convai.env: {e}")

    return convaiConfig

def fetchCurrCharBackstory():
    config = loadConvaiConfig()
    url = "https://api.convai.com/character/get"
    payload = json.dumps({
        "charID": config['characterId']
    })
    headers = {
        'CONVAI-API-KEY': config['apiKey'],
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        data = response.json()
        return data.get('backstory', "No backstory found.")
    else:
        print(f"Failed to fetch character details: {response.status_code} - {response.text}")
        return None

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
    currBackstory = fetchCurrCharBackstory()
    if currBackstory:
        newBackstory = f"{currBackstory}\n{backstoryUpdate}"
        updateCharBackstory(newBackstory)