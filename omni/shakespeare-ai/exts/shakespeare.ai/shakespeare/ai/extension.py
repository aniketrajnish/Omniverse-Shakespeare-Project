# ---------------------------------------------------------------------------------------------------
# Extension for the Shakespeare AI project, which manages the server connection and project launch.
# ---------------------------------------------------------------------------------------------------

import omni.ext, omni.usd, omni.kit.app, os, asyncio, subprocess, psutil, carb.events
import omni.ui as ui
from .a2f import server

def log(text: str, warning: bool = False):                             # attaching a tag w the print statement,
    print(f"[Shakespeare AI] {'[Warning]' if warning else ''} {text}") # to easily find it in the console

# ---------------------------------------------------------------------------------------------------
# Main extension class derrived from omni.ext.IExt, which is the main entry point for the extension
# ---------------------------------------------------------------------------------------------------

class ShakespeareProjectExtension(omni.ext.IExt):
    '''
    This extension manages:
        - omniverse specific UI
        - server connection with the executable compiled from the backend,
        - launching the project
        - omniverse-specific cleanup
    '''
    def __init__(self):
        '''
        Initializes the extension with the following attributes:
            - stopEvent: event to stop the server
            - serverThread: thread to run the server
            - convoProcess: process to run the conversation window            
        '''
        super().__init__()
        self.stopEvent = None
        self.serverThread = None
        self.convoProcess = None

    def on_startup(self, ext_id):
        '''
        Called when the extension starts up.
        Initializes the UI and registers the shutdown listener.

        Args:
            ext_id (str): The extension ID
        '''
        log('Startup')
        self.extId = ext_id    
        self.initUI()
        self.registerShutDownListener()

    def initUI(self):
        '''
        Initializes the UI with the following components:
            - openProjectBtn: button to open the project
            - serverBtn: button to connect to the conversation window server            
        '''
        self._window = ui.Window('Shakespeare AI Server', width=225, height=125)
        with self._window.frame:
            with ui.VStack(spacing=5):
                ui.Spacer(height=10)
                self.openProjectBtn = ui.Button('Open Project', clicked_fn=self.onOpenProjectBtnClick, height=30)
                self.serverBtn = ui.Button('Connect to Server', clicked_fn=self.onServerBtnClick, height=30)
                ui.Spacer(height=10)

    def onOpenProjectBtnClick(self):
        '''
        Bound to the openProjectBtn click event, it opens the Shakespeare project when clicked.
        '''
        if self.isShakespeareStageOpen():
            log('Shakespeare project is already open.')
        else:
            self.openShakespeareStage()

    def onServerBtnClick(self):
        '''
        Bound to the serverBtn click event, 
        it connects to the conversation window server when clicked.
        '''
        try:
            if not self.stopEvent:
                self.stopEvent, self.serverThread = server.startA2FServer()
                self.serverBtn.text = 'Disconnect from Server'
                log('Connected to server')
                self.openConversationWindow()
            else:
                asyncio.ensure_future(self.stopServerAsync()) 
        except Exception as e:
            log(f'Error with server connection: {e}', warning=True)

    def openConversationWindow(self):
        '''
        Opens the precompiled conversation window executable.
        Then, starts monitoring the conversation window for closing.
        '''
        try:
            extPath = omni.kit.app.get_app().get_extension_manager().get_extension_path(self.extId)
            rootPath = os.path.join(extPath, '..', '..', '..', '..')
            exePath = os.path.normpath(os.path.join(rootPath, 'app', 'build', 'Shakespeare AI.exe'))
            self.convoProcess = subprocess.Popen([exePath])
            log(f'Opened conversation window with PID: {self.convoProcess.pid}')
            asyncio.ensure_future(self.monitorConversationWindow())
        except Exception as e:
            log(f'Error opening conversation window: {e}', warning=True)

    def closeConversationWindow(self):
        '''
        Closes the conversation window process if it is running.
        We first terminate the process and its children, 
        then wait for up to 5 seconds for the process to close.
        '''
        if self.convoProcess:
            try:
                process = psutil.Process(self.convoProcess.pid)
                for child in process.children(recursive=True):
                    child.terminate()
                process.terminate()
                process.wait(timeout=5) 
                log(f'Closed conversation window with PID: {self.convoProcess.pid}')
            except psutil.NoSuchProcess:
                log('Conversation window process not found', warning=True)
            except Exception as e:
                log(f'Error closing conversation window: {e}', warning=True)
            finally:
                self.convoProcess = None

    async def monitorConversationWindow(self):
        '''
        Uses asyncio to monitor the conversation window process.
        '''
        while True:
            await asyncio.sleep(1)
            if self.convoProcess is None or self.convoProcess.poll() is not None:
                log('Conversation window closed')
                await self.stopServerAsync()
                break

    def normalizePath(self, path):
        '''
        Helper function to normalize a path.
        Used to compare paths in a case-insensitive manner.

        Args:
            path (str): The path to normalize

        Returns:
            str: The normalized path
        '''
        return path.replace('\\', '/').lower()

    def isShakespeareStageOpen(self):
        '''
        Checks if the Shakespeare stage is already open.

        Returns:
            bool: True if the Shakespeare stage is open, False otherwise
        '''
        usdContext = omni.usd.get_context()
        currentStagePath = self.normalizePath(usdContext.get_stage_url())
        desiredStagePath = self.normalizePath(self.getShakespeareStageFilePath())
        log(f'Is Shakespeare stage open? {currentStagePath == desiredStagePath}')
        return currentStagePath == desiredStagePath

    def getShakespeareStageFilePath(self):
        '''
        Gets the path to the Shakespeare stage file.
        We have kept the stage file in the usd folder of the project.

        Returns:
            str: The path to the Shakespeare stage file
        '''
        extPath = omni.kit.app.get_app().get_extension_manager().get_extension_path(self.extId)
        if not extPath:
            log('Failed to get extension path', warning=True)
            return None
        projectRoot = os.path.dirname(os.path.dirname(extPath))
        return os.path.normpath(os.path.join(projectRoot, 'usd', 'shakespeare.usd'))
    
    async def stopServerAsync(self):
        '''
        Asynchronously stops the server, 
        updates the UI, and closes the conversation window.        
        '''
        if self.stopEvent and self.serverThread:
            server.stopA2FServer(self.stopEvent, self.serverThread)
            self.stopEvent = None
            self.serverThread = None
            self.serverBtn.text = 'Connect to Server'
            log('Disconnected from server')
            self.closeConversationWindow()

    def openShakespeareStage(self):
        stagePath = self.getShakespeareStageFilePath()
        if not stagePath:
            return False
        
        usdContext = omni.usd.get_context()
        result, err = usdContext.open_stage(stagePath)

        if result:
            log(f'Opened stage: {stagePath}')
            return True
        else:
            log(f'Failed to open stage: {err}', warning=True)
            return False

    def registerShutDownListener(self):
        '''
        We register a shutdown listener to close the conversation window when the app is about to shutdown.
        '''
        shutdownStream = omni.kit.app.get_app().get_shutdown_event_stream()
        self.shutdownStub = shutdownStream.create_subscription_to_pop(
            self.onAppShutdown,
            name = 'SPAIShutdownListener'
        )

    def onAppShutdown(self, e: carb.events.IEvent):
        '''
        Called when the app is about to shutdown.
        This function is a callback for the shutdown listener.
        '''
        if e.type == omni.kit.app.POST_QUIT_EVENT_TYPE:
            log('Ov about to shutdown')
            self.closeConversationWindow()

    def on_shutdown(self):
        '''
        Called when the extension is about to shutdown.
        '''
        log('Shutdown')
        if hasattr(self, 'shutdownStub'):
            self.shutdownStub = None
        if self.stopEvent:
            asyncio.get_event_loop().run_until_complete(self.stopServerAsync())        
        if self._window:
            self._window.destroy()