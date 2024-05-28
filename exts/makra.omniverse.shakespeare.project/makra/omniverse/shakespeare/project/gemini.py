import base64
import requests
import json
import keys

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

api_key = 'AIzaSyAlabG-TbAU0dIKA4KbilwCOcs6N4WYZlQ'
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + api_key

image_path = 'exts/makra.omniverse.shakespeare.project/makra/omniverse/shakespeare/project/iphone.jpeg'
base64_image = encode_image_to_base64(image_path)

headers = {
    'Content-Type': 'application/json'
}

data = json.dumps({
    "contents": [
        {
            "parts": [
                {"text": "Describe this scene as Shakespeare might have. Remember to use the language of the time. Make him sound confused if an object is not from his time."},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64_image
                    }
                }
            ]
        }
    ]
})

response = requests.post(url, headers=headers, data=data)
result = response.json()
print(result['candidates'][0]['content']['parts'][0]['text'])