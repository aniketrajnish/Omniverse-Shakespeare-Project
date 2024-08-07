import os, json

def loadConfig(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception(f"Could not find config file: {file}")
    except json.JSONDecodeError:
        raise Exception(f"Could not parse config file: {file}")
    
def currPath():
    return os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

def determineMimeType(fileName):
    ext = fileName.split(".")[-1].lower()

    if ext == 'jpg':
        return 'image/jpeg'

    supportedExts = ["jpg", "jpeg", "png", "heic", "heif"]
    
    if ext not in supportedExts:
        raise Exception(f"Unsupported file extension: {ext}")
    else:
        return f"image/{ext}"
    