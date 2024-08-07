from base64 import b64encode

class ImageHandler:
    @staticmethod
    def encodeImg(imgPath):
        with open(imgPath, "rb") as imgFile:
            return b64encode(imgFile.read()).decode("utf-8")