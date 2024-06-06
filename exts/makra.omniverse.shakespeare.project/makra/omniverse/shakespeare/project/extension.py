import os
import omni.ext
import omni.ui as ui
from omni.kit.window.file_importer import get_file_importer
from .gemini import gemini
from .convai import convai, ConvaiExtension

class ShakespeareProjectExtension(omni.ext.IExt):
    def __init__(self):
        super().__init__()
        self.convai_ext = None 

    def on_startup(self, ext_id):
        print("[Shakespeare Project] Startup")
        self.initUI()
        self.convai_ext = ConvaiExtension.get_instance()

    def initUI(self):
        self._window = ui.Window("Shakespeare Project", width=400, height=300)
        with self._window.frame:
            with ui.VStack():
                self.selectImgBtn = ui.Button("Select Image", clicked_fn=self.selectImage, width=100, height=30)
                ui.Spacer(height=10) 
                self.imgWidget = ui.Image(width=320, height=180, fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT)
                ui.Spacer(height=10)
                self.startTalkingBtn = ui.Button("Start Talking", clicked_fn=self.onStartTalkingBtnClick, width=100, height=30)

    def onStartTalkingBtnClick(self):
        if self.convai_ext and hasattr(self.convai_ext, 'IsCapturingAudio'):
            if self.convai_ext.IsCapturingAudio:
                self.convai_ext.stop_convai()
                self.startTalkingBtn.text = "Start Talking"
            else:
                self.convai_ext.start_convai()
                self.startTalkingBtn.text = "Stop"
        else: 
            print("[ShakespeareProject] Convai extension not initialized properly.")

    def selectImage(self):
        fileImporter = get_file_importer()
        fileImporter.show_window(
            title="Import File",
            import_handler=self.onFileSelected,
            file_extension_types=[
                ("jpg", "JPEG image"),
                ("jpeg", "JPEG image"),
                ("png", "PNG image"),
                ("webp", "WebP image"),
                ("heic", "HEIC image"),
                ("heif", "HEIF image")
            ],
            import_button_label="Select"
        )

    def onFileSelected(self, filename, dirname, selections):
        if selections:
            filepath = os.path.join(dirname, selections[0])
            print(f"Selected file: {filepath}")
            self.processImage(filepath)
            if self.convai_ext:
                convai.appendToCharBackstory(self.geminiResponse) 

    def processImage(self, imgPath):
        self.imgWidget.source_url = f"file:///{imgPath.replace(os.sep, '/')}" 
        self.geminiResponse = gemini.getGeminiResponse(imgPath)
        print(f"Gemini Response: {self.geminiResponse}")

    def on_shutdown(self):
        print("[Shakespeare Project] Shutdown")
        if self._window:
            self._window.destroy()