import omni.ext, omni.usd, omni.kit.app, os, asyncio, subprocess, psutil
import omni.ui as ui
from .a2f import server

def log(text: str, warning: bool = False):
    print(f"[Shakespeare AI] {'[Warning]' if warning else ''} {text}")

class ShakespeareProjectExtension(omni.ext.IExt):
    def __init__(self):
        super().__init__()
        self.stopEvent = None
        self.serverThread = None
        self.convoProcess = None

    def on_startup(self, ext_id):
        log("Startup")
        self.extId = ext_id    
        self.initUI()

    def initUI(self):
        self._window = ui.Window("Shakespeare AI Server", width=225, height=125)
        with self._window.frame:
            with ui.VStack(spacing=5):
                ui.Spacer(height=10)
                self.openProjectBtn = ui.Button("Open Project", clicked_fn=self.onOpenProjectBtnClick, height=30)
                self.serverBtn = ui.Button("Connect to Server", clicked_fn=self.onServerBtnClick, height=30)
                ui.Spacer(height=10)

    def onOpenProjectBtnClick(self):
        if self.isShakespeareStageOpen():
            log("Shakespeare project is already open.")
        else:
            self.openShakespeareStage()

    def onServerBtnClick(self):
        try:
            if not self.stopEvent:
                self.stopEvent, self.serverThread = server.startA2FServer()
                self.serverBtn.text = "Disconnect from Server"
                log("Connected to server")
                self.openConversationWindow()
            else:
                asyncio.ensure_future(self.stopServerAsync())
        except Exception as e:
            log(f"Error with server connection: {e}", warning=True)

    def openConversationWindow(self):
        try:
            extPath = omni.kit.app.get_app().get_extension_manager().get_extension_path(self.extId)
            rootPath = os.path.join(extPath, "..", "..", "..", "..")
            exePath = os.path.normpath(os.path.join(rootPath, "app", "build", "Shakespeare AI.exe"))
            self.convoProcess = subprocess.Popen([exePath])
            log(f"Opened conversation window with PID: {self.convoProcess.pid}")
            asyncio.ensure_future(self.monitorConversationWindow())
        except Exception as e:
            log(f"Error opening conversation window: {e}", warning=True)

    def closeConversationWindow(self):
        if self.convoProcess:
            try:
                process = psutil.Process(self.convoProcess.pid)
                for child in process.children(recursive=True):
                    child.terminate()
                process.terminate()
                process.wait(timeout=5)  # Wait for up to 5 seconds
                log(f"Closed conversation window with PID: {self.convoProcess.pid}")
            except psutil.NoSuchProcess:
                log("Conversation window process not found", warning=True)
            except Exception as e:
                log(f"Error closing conversation window: {e}", warning=True)
            finally:
                self.convoProcess = None

    async def monitorConversationWindow(self):
        while True:
            await asyncio.sleep(1)
            if self.convoProcess is None or self.convoProcess.poll() is not None:
                log("Conversation window closed")
                await self.stopServerAsync()
                break

    def normalizePath(self, path):
        return path.replace("\\", "/").lower()

    def isShakespeareStageOpen(self):
        usdContext = omni.usd.get_context()
        currentStagePath = self.normalizePath(usdContext.get_stage_url())
        desiredStagePath = self.normalizePath(self.getShakespeareStageFilePath())
        log(f"Is Shakespeare stage open? {currentStagePath == desiredStagePath}")
        return currentStagePath == desiredStagePath

    def getShakespeareStageFilePath(self):
        extPath = omni.kit.app.get_app().get_extension_manager().get_extension_path(self.extId)
        if not extPath:
            log("Failed to get extension path", warning=True)
            return None
        projectRoot = os.path.dirname(os.path.dirname(extPath))
        return os.path.normpath(os.path.join(projectRoot, "usd", "shakespeare.usd"))
    
    async def stopServerAsync(self):
        if self.stopEvent and self.serverThread:
            server.stopA2FServer(self.stopEvent, self.serverThread)
            self.stopEvent = None
            self.serverThread = None
            self.serverBtn.text = "Connect to Server"
            log("Disconnected from server")
            self.closeConversationWindow()

    def openShakespeareStage(self):
        stagePath = self.getShakespeareStageFilePath()
        if not stagePath:
            return False
        
        usdContext = omni.usd.get_context()
        result, err = usdContext.open_stage(stagePath)

        if result:
            log(f"Opened stage: {stagePath}")
            return True
        else:
            log(f"Failed to open stage: {err}", warning=True)
            return False

    def on_shutdown(self):
        log("Shutdown")
        if self.stopEvent:
            asyncio.get_event_loop().run_until_complete(self.stopServerAsync())
        self.closeConversationWindow()
        if self._window:
            self._window.destroy()