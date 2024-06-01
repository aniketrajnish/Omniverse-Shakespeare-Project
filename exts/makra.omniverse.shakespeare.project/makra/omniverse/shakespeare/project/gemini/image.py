import base64

class ImageHandler:
    @staticmethod
    def encodeImg(imgPath):
        with open(imgPath, "rb") as imgFile:
            return base64.b64encode(imgFile.read()).decode("utf-8")