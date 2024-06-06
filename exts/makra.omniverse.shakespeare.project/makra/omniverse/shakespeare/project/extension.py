import os
import omni.ext
import omni.kit
import omni.ui as ui
from omni.kit.window.file_importer import get_file_importer
from .gemini import gemini
from .convai import convai, extension

class ShakespeareProjectExtension(omni.ext.IExt):
    def __init__(self):
        pass

    def on_startup(self, ext_id):     
        self.initUI()
        self.initConvaiBackend()

    def initConvaiBackend(self):
        self.convaiBackend = extension.ConvaiBackend()
        omni.kit.app.get_app().get_message_bus_event_stream().create_subscription_to_pop(
            self.onConvaiUpdate, name="convai_update"
        )

    def initUI(self):
        self._window = ui.Window("Shakespearean Vision", width=400, height=300)

        with self._window.frame:
            with ui.VStack():
                self.selectImgBtn = ui.Button("Select Image", clicked_fn=self.selectImage, width=100, height=30)
                ui.Spacer(height=10)

                self.imgWidget = ui.Image(width=32, height=18, fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT)
                ui.Spacer(height=10)

                self.startTalkingBtn = ui.Button("Start Talking", clicked_fn=self.startTalking, width=100, height=30)
                ui.Spacer(height=10)
                
                self.userTranscriptLabel = ui.Label("You: ", height = ui.Length(30), word_wrap=True)
                self.userTranscriptLabel.alignment = ui.Alignment.CENTER
                self.userTranscriptLabel.text = ""

                self.shakespeareTranscriptLabel = ui.Label("Shakespeare:", height = ui.Length(30), word_wrap=True)
                self.shakespeareTranscriptLabel.alignment = ui.Alignment.CENTER
                self.shakespeareTranscriptLabel.text = ""

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
            self.processImage(filepath)
            convai.appendToCharBackstory(self.geminiResponse)

    def processImage(self, imgPath):
        self.imgWidget.source_url = f"file:///{imgPath.replace(os.sep, '/')}" 
        self.geminiResponse = gemini.getGeminiResponse(imgPath)

    def startTalking(self):
        if self.convaiBackend.is_capturing_audio: 
            self.convaiBackend.stop_conversation() 
            self.startTalkingBtn.text = "Start Talking"
        else:
            self.convaiBackend.start_conversation()
            self.startTalkingBtn.text = "Stop"

    def onConvaiUpdate(self, event):
        """Handle the "convai_update" event emitted from ConvaiBackend."""
        if self.userTranscriptLabel and self.shakespeareTranscriptLabel:
            self.userTranscriptLabel.text = event.payload.get("user_text", "")
            self.shakespeareTranscriptLabel.text = event.payload.get("sp_text", "")

        # Update button state based on ConvaiBackend
        self.startTalkingBtn.text = self.convaiBackend.StartTalking_Btn_text
        self.startTalkingBtn.enabled = self.convaiBackend.StartTalking_Btn_state

    def on_shutdown(self):
        print("[Shakespeare Project] Shutdown")
        if self._window:
            self._window.destroy()
        if self.convaiBackend:
            self.convaiBackend.on_shutdown()
