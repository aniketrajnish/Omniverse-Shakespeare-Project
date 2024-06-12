import os, asyncio, omni.ext, carb.events, configparser, pyaudio, grpc
from .rpc import service_pb2 as convaiServiceMsg, service_pb2_grpc as convaiService
from .convai_audio_player import ConvaiAudioPlayer
from typing import Generator
import threading, time
from collections import deque

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 12000

def log(text: str, warning: bool =False):
    print(f"[convai] {'[Warning]' if warning else ''} {text}")

class ConvaiBackend:
    _instance = None

    def __init__(self, convaiBtn, _window):
        if ConvaiBackend._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            ConvaiBackend._instance = self
        
        self.convaiBtn = convaiBtn
        self._window = _window        

        self.initVars()
        self.readConfig()
        self.createChannel()

        log("ConvaiBackend initialized")

    @staticmethod
    def get_instance(convaiBtn, _window):
        if ConvaiBackend._instance is None:
            ConvaiBackend(convaiBtn, _window)
        return ConvaiBackend._instance

    def initVars(self):
        self.isCapturingAudio = False
        self.channelAddress = None
        self.channel = None
        self.sessionId = None
        self.channelState = grpc.ChannelConnectivity.IDLE
        self.client = None
        self.convaiGRPCGetResponseProxy = None
        self.pyAudio = pyaudio.PyAudio()
        self.stream = None
        self.tick = False
        self.tickThread = None
        self.convaiAudioPlayer = ConvaiAudioPlayer(self.onStartTalkCallback, self.onStopTalkCallback)
        self.ResponseTextBuffer = ""
        self.OldCharacterID = ""

        self.uiLock = threading.Lock()
        self.micLock = threading.Lock()
        self.uiUpdateCounter = 0
        self.onNewUpdateSub = None

        self.convaiBtnTxt = "Start Talking"
        self.convaiBtnState = True

    def readConfig(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(__location__, 'convai.env'))

        self.apiKey = config.get("CONVAI", "API_KEY")
        self.charId = config.get("CONVAI", "CHARACTER_ID")
        self.channelAddress = config.get("CONVAI", "CHANNEL")
        self.actionsTxt = config.get("CONVAI", "ACTIONS")

    def createChannel(self):
        if (self.channel):
            log("gRPC channel already created")
            return
        
        self.channel = grpc.secure_channel(self.channelAddress, grpc.ssl_channel_credentials())
        log("Created gRPC channel")

    def closeChannel(self):
        if (self.channel):
            self.channel.close()
            self.channel = None
            log("closeChannel - Closed gRPC channel")
        else:
            log("closeChannel - gRPC channel already closed")
    
    def startConvai(self):
        if self.OldCharacterID != self.charId:
            self.OldCharacterID = self.charId
            self.sessionId = ""

        with self.uiLock:
            self.convaiBtnTxt = "Stop"

        self.startMic()

        self.convaiAudioPlayer.stop()

        self.convaiGRPCGetResponseProxy = ConvaiGRPCGetResponseProxy(self)

    def stopConvai(self):
        with self.uiLock:
            self.convaiBtnTxt = "Processing..."
            self.convaiBtnState = False

        asyncio.ensure_future(self.processAudDelay())

    async def processAudDelay(self):
        await asyncio.sleep(2)

        self.readMicAndSendToGrpc(True)

        self.stopMic()

    def on_shutdown(self):
        self.cleanGrpcStream()
        self.closeChannel()
        self.stopTick()

        log("ConvaiBackend shutdown")

    def startMic(self):
        if self.isCapturingAudio == True:
            log("startMic - mic is already capturing audio", 1)
            return
        self.stream = self.pyAudio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        self.isCapturingAudio = True
        self.startTick()
        log("startMic - Started Recording")

    def stopMic(self):
        if self.isCapturingAudio == False:
            log("stopMic - mic has not started yet", 1)
            return
        
        self.stopTick()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        else:
            log("stopMic - could not close mic stream since it is None", 1)
        
        self.isCapturingAudio = False
        log("stopMic - Stopped Recording")

    def cleanGrpcStream(self):
        if self.convaiGRPCGetResponseProxy:
            self.convaiGRPCGetResponseProxy.Parent = None
            del self.convaiGRPCGetResponseProxy
        self.convaiGRPCGetResponseProxy = None

    def onDataReceived(self, receivedText: str, receivedAudio: bytes, SampleRate: int, isFinal: bool):
        '''
	    Called when new text and/or Audio data is received
        '''
        self.ResponseTextBuffer += str(receivedText)
        if isFinal:
            with self.uiLock:
                self.ResponseTextBuffer = ""
        self.convaiAudioPlayer.appendToStream(receivedAudio)
        return
    
    def onUIUpdateEvent(self, e):
        if self.uiUpdateCounter > 1000:
            self.uiUpdateCounter = 0
        self.uiUpdateCounter += 1

        if self.uiLock.locked():
            log("UI update event - uiLock is locked", 1)
            return

        with self.uiLock:
            self.convaiBtn.text = self.convaiBtnTxt
            self.convaiBtn.enabled = self.convaiBtnState

    def onActionsReceived(self, action: str):
        '''
	    Called when actions are received
        '''
        self.uiLock.acquire()
        for InputAction in self.parseActions():
            if action.find(InputAction) >= 0:
                self.fireEvent(InputAction)
                self.uiLock.release()
                return
        self.uiLock.release()
        
    def onSessionIdReceived(self, sessionId: str):
        '''
	    Called when new SessionID is received
        '''
        self.sessionId = sessionId

    def onFin(self, resetUI = True):
        '''
	    Called when the response stream is done
        '''

        self.convaiGRPCGetResponseProxy = None
        with self.uiLock:
            if resetUI:
                if resetUI:
                    self.convaiBtnTxt = "Start Talking"
                self.convaiBtnState = True
        self.cleanGrpcStream()
        log("Received onFin")

    def onFail(self, ErrorMessage: str):
        '''
        Called when there is an unsuccessful response
        '''
        log(f"onFail called with message: {ErrorMessage}", 1)
        self.stopMic()

        with self.uiLock:
            self.convaiBtnTxt = "Try Again"
            self.convaiBtnState = True
        self.onFin(resetUI=False)

        if self._window:
            self.onUIUpdateEvent(None)

    def onTick(self):
        while self.tick:
            time.sleep(0.1)
            if self.isCapturingAudio == False or self.convaiGRPCGetResponseProxy is None:
                continue
            self.readMicAndSendToGrpc(False)

    def onStartTalkCallback(self):
        self.fireEvent("start")
        log("Character Started Talking")

    def onStopTalkCallback(self):
        self.fireEvent("stop")
        log("Character Stopped Talking")
    
    def readMicAndSendToGrpc(self, lastWrite):
        with self.micLock:
            if self.stream:
                data = self.stream.read(CHUNK)
            else:
                log("readMicAndSendToGrpc - could not read mic stream since it is none", 1)
                data = bytes()

            if self.convaiGRPCGetResponseProxy:
                self.convaiGRPCGetResponseProxy.writeAudDataToSend(data, lastWrite)
            else:
                log("readMicAndSendToGrpc - ConvaiGRPCGetResponseProxy is not valid", 1)

    def fireEvent(self, eventName):
        def resgisteredEventName(eventName):
            """Returns the internal name used for the given custom event name"""
            n = "omni.graph.action." + eventName
            return carb.events.type_from_string(n)

        regEventName = resgisteredEventName(eventName)
        msgBus = omni.kit.app.get_app().get_message_bus_event_stream()

        msgBus.push(regEventName, payload={})

    def parseActions(self):
        actions = ["None"] + self.actionsTxt.split(',')
        actions = [a.lstrip(" ").rstrip(" ") for a in actions]
        return actions

    def startTick(self):
        if self.tick:
            log("Tick already started", 1)
            return
        self.tick = True
        self.tickThread = threading.Thread(target=self.onTick)
        self.tickThread.start()

    def stopTick(self):
        if self.tickThread and self.tick:
            self.tick = False
            self.tickThread.join()            

class ConvaiGRPCGetResponseProxy:
    def __init__(self, Parent: ConvaiBackend):
        self.Parent = Parent

        self.AudioBuffer = deque(maxlen=4096*2)
        self.InformOnDataReceived = False
        self.lastWriteReceived = False
        self.client = None
        self.NumberOfAudioBytesSent = 0
        self.call = None
        self._write_task = None
        self._read_task = None

        self.activate()
        log("ConvaiGRPCGetResponseProxy constructor")

    def activate(self):
        if (len(self.Parent.apiKey) == 0):
            self.Parent.onFail("API key is empty")
            return
  
        if (len(self.Parent.charId) == 0):
            self.Parent.onFail("Character ID is empty")
            return
  
        if self.Parent.channel is None:
            log("grpc - self.Parent.channel is None", 1)
            self.Parent.onFail("gRPC channel was not created")
            return

        self.client = convaiService.ConvaiServiceStub(self.Parent.channel)

        threading.Thread(target=self.init_stream).start()

    def init_stream(self):
        log("grpc - stream initialized")
        try:
            for response in self.client.GetResponse(self.create_getGetResponseRequests()):
                if response.HasField("audio_response"):
                    log("gRPC - audio_response: {} {} {}".format(response.audio_response.audio_config, response.audio_response.text_data, response.audio_response.end_of_response))
                    log("gRPC - session_id: {}".format(response.session_id))
                    self.Parent.onSessionIdReceived(response.session_id)
                    self.Parent.onDataReceived(
                        response.audio_response.text_data,
                        response.audio_response.audio_data,
                        response.audio_response.audio_config.sample_rate_hertz,
                        response.audio_response.end_of_response)

                elif response.HasField("action_response"):
                    log(f"gRPC - action_response: {response.action_response.action}")
                    self.Parent.onActionsReceived(response.action_response.action)

                else:
                    log("Stream Message: {}".format(response))
            time.sleep(0.1)
                
        except Exception as e:
            self.Parent.onFail(str(e))
            return
        self.Parent.onFin()

    def create_initial_GetResponseRequest(self)-> convaiServiceMsg.GetResponseRequest:
        action_config = convaiServiceMsg.ActionConfig(
            classification = 'singlestep',
            context_level = 1
        )
        action_config.actions[:] = self.Parent.parseActions()
        action_config.objects.append(
            convaiServiceMsg.ActionConfig.Object(
                name = "dummy",
                description = "A dummy object."
            )
        )

        log(f"gRPC - actions parsed: {action_config.actions}")
        action_config.characters.append(
            convaiServiceMsg.ActionConfig.Character(
                name = "User",
                bio = "Person playing the game and asking questions."
            )
        )
        get_response_config = convaiServiceMsg.GetResponseRequest.GetResponseConfig(
                character_id = self.Parent.charId,
                api_key = self.Parent.apiKey,
                audio_config = convaiServiceMsg.AudioConfig(
                    sample_rate_hertz = RATE
                ),
                action_config = action_config
            )
        if self.Parent.sessionId and self.Parent.sessionId != "":
            get_response_config.session_id = self.Parent.sessionId
        return convaiServiceMsg.GetResponseRequest(get_response_config = get_response_config)

    def create_getGetResponseRequests(self)-> Generator[convaiServiceMsg.GetResponseRequest, None, None]:
        req = self.create_initial_GetResponseRequest()
        yield req

        while 1:
            IsThisTheFinalWrite = False
            GetResponseData = None

            if (0): # check if this is a text request
                pass
            else:
                data, IsThisTheFinalWrite = self.consume_from_audio_buffer()
                if len(data) == 0 and IsThisTheFinalWrite == False:
                    time.sleep(0.05)
                    continue
                self.NumberOfAudioBytesSent += len(data)
                GetResponseData = convaiServiceMsg.GetResponseRequest.GetResponseData(audio_data = data)

            req = convaiServiceMsg.GetResponseRequest(get_response_data = GetResponseData)
            yield req

            if IsThisTheFinalWrite:
                log(f"gRPC - Done Writing - {self.NumberOfAudioBytesSent} audio bytes sent")
                break
            time.sleep(0.1)

    def writeAudDataToSend(self, Data: bytes, lastWrite: bool):
        self.AudioBuffer.append(Data)
        if lastWrite:
            self.lastWriteReceived = True
            log(f"gRPC lastWriteReceived")

    def finish_writing(self):
        self.writeAudDataToSend(bytes(), True)

    def consume_from_audio_buffer(self):
        Length = len(self.AudioBuffer)
        IsThisTheFinalWrite = False
        data = bytes()

        if Length:
            data = self.AudioBuffer.pop()
        
        if self.lastWriteReceived and Length == 0:
            IsThisTheFinalWrite = True
        else:
            IsThisTheFinalWrite = False

        if IsThisTheFinalWrite:
            log(f"gRPC Consuming last mic write")

        return data, IsThisTheFinalWrite
    
    def __del__(self):
        self.Parent = None
        log("ConvaiGRPCGetResponseProxy Destructor")