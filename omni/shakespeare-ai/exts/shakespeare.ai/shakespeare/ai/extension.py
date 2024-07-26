import omni.ext, omni.usd, omni.kit.app, os, asyncio, subprocess
import omni.ui as ui
from .a2f import server
import omni.usd

class ShakespeareProjectExtension(omni.ext.IExt):
    def __init__(self):
        super().__init__()
        self.stopEvent = None
        self.serverThread = None

    def on_startup(self, ext_id):
        print("[Shakespeare AI] Startup") 
        self.extId = ext_id    
        self.initUI()

    def initUI(self):
        self._window = ui.Window("Shakespeare AI Server", width=200, height=150)
        with self._window.frame:
            with ui.VStack(spacing=5):
                ui.Spacer(height=10)
                self.openProjectBtn = ui.Button("Open Project", clicked_fn=self.onOpenProjectBtnClick, height=30)
                ui.Spacer(height=0)
                self.serverBtn = ui.Button("Connect to Server", clicked_fn=self.onServerBtnClick, height=30)
                ui.Spacer(height=0)
                self.convoBtn = ui.Button("Open Conversation Window", clicked_fn=self.onConvoBtnClick, height=30)

    def onOpenProjectBtnClick(self):
        if self.isShakespeareStageOpen():
            print("[Shakespeare AI] Shakespeare project is already open.")
        else:
            self.openShakespeareStage()

    def onServerBtnClick(self):
        try:
            if not self.stopEvent:
                self.stopEvent, self.serverThread = server.start_audio2face_server()
                self.serverBtn.text = "Disconnect from Server"
                print("[Shakespeare AI] Connected to server")
            else:
                asyncio.ensure_future(self.stopServerAsync())
                print("[Shakespeare AI] Disconnected from server")
        except Exception as e:
            print(f"[Shakespeare AI] Error with server connection: {e}")

    def onConvoBtnClick(self):
        try:
            extPath = omni.kit.app.get_app().get_extension_manager().get_extension_path(self.extId)
            rootPath = os.path.join(extPath, "..", "..", "..", "..")
            exePath = os.path.normpath(os.path.join(rootPath, "app", "build", "Shakespeare AI.exe"))
            subprocess.Popen([exePath])
            print("[Shakespeare AI] Opened conversation window")
        except Exception as e:
            print(f"[Shakespeare AI] Error opening conversation window: {e}")

    def normalizePath(self, path):
        return path.replace("\\", "/").lower()

    def isShakespeareStageOpen(self):
        usdContext = omni.usd.get_context()
        currentStagePath = self.normalizePath(usdContext.get_stage_url())
        desiredStagePath = self.normalizePath(self.getShakespeareStageFilePath())
        print(f"Is Shakespeare stage open? {currentStagePath == desiredStagePath}")
        return currentStagePath == desiredStagePath

    def getShakespeareStageFilePath(self):
        extPath = omni.kit.app.get_app().get_extension_manager().get_extension_path(self.extId)
        if not extPath:
            print("[Shakespeare AI] Failed to get extension path")
            return None
        projectRoot = os.path.dirname(os.path.dirname(extPath))
        return os.path.normpath(os.path.join(projectRoot, "usd", "shakespeare.usd"))
    
    def stopServerAsync(self):
        if self.stopEvent and self.serverThread:
            server.stop_audio2face_server(self.stopEvent, self.serverThread)
            self.stopEvent = None
            self.serverThread = None
            self.serverBtn.text = "Connect to Server"
            print("[Shakespeare AI] Disconnected from server")

    def openShakespeareStage(self):
        stagePath = self.getShakespeareStageFilePath()
        if not stagePath:
            return False
        
        usdContext = omni.usd.get_context()
        result, err = usdContext.open_stage(stagePath)

        if result:
            print(f"[Shakespeare AI] Opened stage: {stagePath}")
            return True
        else:
            print(f"[Shakespeare AI] Failed to open stage: {err}")
            return False

    def on_shutdown(self):
        print("[Shakespeare AI] Shutdown")
        if self.stopEvent:
            server.stop_audio2face_server(self.stopEvent, self.serverThread)
        if self._window:
            self._window.destroy()