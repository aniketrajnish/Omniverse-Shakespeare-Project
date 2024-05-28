import requests
import json
from image import ImageHandler
import helpers

geminiConfig = helpers.loadConfig(f"{helpers.currPath()}/config.json")["gemini"]

url = f"{geminiConfig["baseUrl"]}/{geminiConfig["model"]}:generateContent?key={geminiConfig["apiKey"]}"

imgPath = f"{helpers.currPath()}/imgs/sp.jpg"
base64Img = ImageHandler.encodeImg(imgPath)

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

response = requests.post(url, headers=headers, data=data)

if response.status_code != 200:
    print(f"Error: {response.status_code}")
    print(response.text)
else:
    result = response.json()
    print(result["candidates"][0]["content"]["parts"][0]["text"])