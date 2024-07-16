import os
import asyncio
import configparser
import pyaudio
import grpc
import requests
import json
from typing import Generator
import threading, time
from collections import deque
from PyQt5.QtCore import pyqtSignal, QObject, QMetaObject, Qt, Q_ARG

from .rpc import service_pb2 as convaiServiceMsg, service_pb2_grpc as convaiService
from .audioplayer import ConvaiAudioPlayer

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 12000


def log(text: str, warning: bool = False):
    print(f"[convai] {'[Warning]' if warning else ''} {text}")


def loadConvaiConfig():
    configPath = os.path.join(os.path.dirname(__file__), 'convai.env')
    if not os.path.exists(configPath):
        raise FileNotFoundError("Convai configuration file not found.")

    config = configparser.ConfigParser()
    config.read(configPath)

    try:
        convaiConfig = {
            'apiKey': config.get('CONVAI', 'API_KEY'),
            'characterId': config.get('CONVAI', 'CHARACTER_ID'),
            'channel': config.get('CONVAI', 'CHANNEL'),
            'actions': config.get('CONVAI', 'ACTIONS'),
            'sessionId': config.get('CONVAI', 'SESSION_ID'),
            'baseBackstory': config.get('CONVAI', 'BASE_BACKSTORY').replace("\\n", "\n")
        }
    except configparser.NoOptionError as e:
        raise KeyError(f"Missing configuration key in convai.env: {e}")

    return convaiConfig


def updateCharBackstory(newBackstory):
    config = loadConvaiConfig()
    url = "https://api.convai.com/character/update"
    payload = json.dumps({
        "charID": config['characterId'],
        "backstory": newBackstory
    })
    headers = {
        'CONVAI-API-KEY': config['apiKey'],
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        log("Character updated successfully.")
    else:
        log(f"Failed to update character: {response.status_code} - {response.text}")


def appendToCharBackstory(backstoryUpdate):
    config = loadConvaiConfig()
    currBackstory = config['baseBackstory']
    if currBackstory:
        newBackstory = f"{currBackstory}\n{backstoryUpdate}"
        updateCharBackstory(newBackstory)


class ConvaiBackend(QObject):
    _instance = None
    stateChangeSignal = pyqtSignal(bool)
    errorSignal = pyqtSignal(str)
    updateBtnTextSignal = pyqtSignal(str)  
    setBtnEnabledSignal = pyqtSignal(bool)  

    @staticmethod
    def getInstance():
        if ConvaiBackend._instance is None:
            ConvaiBackend._instance = ConvaiBackend()
        return ConvaiBackend._instance

    def __init__(self):
        super().__init__()
        if ConvaiBackend._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            ConvaiBackend._instance = self
        
        self.initVars()
        self.readConfig()
        self.createChannel()

        log("ConvaiBackend initialized")

    def initVars(self):
        self.isCapturingAudio = False
        self.channelAddress = None
        self.channel = None
        self.sessionId = None
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

    def readConfig(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(__location__, 'convai.env'))

        self.apiKey = config.get("CONVAI", "API_KEY")
        self.charId = config.get("CONVAI", "CHARACTER_ID")
        self.channelAddress = config.get("CONVAI", "CHANNEL")
        self.actionsTxt = config.get("CONVAI", "ACTIONS")

    def createChannel(self):
        if self.channel:
            log("gRPC channel already created")
            return

        self.channel = grpc.secure_channel(self.channelAddress, grpc.ssl_channel_credentials())
        log("Created gRPC channel")

    def closeChannel(self):
        if self.channel:
            self.channel.close()
            self.channel = None
            log("closeChannel - Closed gRPC channel")
        else:
            log("closeChannel - gRPC channel already closed")

    def startConvai(self):
        if self.OldCharacterID != self.charId:
            self.OldCharacterID = self.charId
            self.sessionId = ""

        self.updateBtnText("Stop")
        self.startMic()
        self.convaiAudioPlayer.stop()
        self.convaiGRPCGetResponseProxy = ConvaiGRPCGetResponseProxy(self)

    def stopConvai(self):
        self.updateBtnText("Processing...")
        self.setBtnEnabled(False)

        self.readMicAndSendToGrpc(True)  
        self.stopMic() 

    def startMic(self):
        if self.isCapturingAudio:
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
        if not self.isCapturingAudio:
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
            self.convaiGRPCGetResponseProxy.parent = None
            del self.convaiGRPCGetResponseProxy
        self.convaiGRPCGetResponseProxy = None

    def onDataReceived(self, receivedText: str, receivedAudio: bytes, SampleRate: int, isFinal: bool):
        self.ResponseTextBuffer += str(receivedText)
        if isFinal:
            self.ResponseTextBuffer = ""
        self.convaiAudioPlayer.appendToStream(receivedAudio)

    def onActionsReceived(self, action: str):
        self.uiLock.acquire()
        for InputAction in self.parseActions():
            if action.find(InputAction) >= 0:
                self.uiLock.release()
                return
        self.uiLock.release()

    def onSessionIdReceived(self, sessionId: str):
        self.sessionId = sessionId

    def onFin(self, resetUI=True):
        self.convaiGRPCGetResponseProxy = None
        self.cleanGrpcStream()
        log("Received onFin")
        if resetUI:
            self.updateBtnText("Start Talking")
            self.setBtnEnabled(True)

    def onFail(self, ErrorMessage: str):
        log(f"onFail called with message: {ErrorMessage}", 1)
        self.stopMic()
        self.errorSignal.emit('Try Again!')
        self.onFin(resetUI=True)

    def onTick(self):
        while self.tick:
            time.sleep(0.1)
            if not self.isCapturingAudio or self.convaiGRPCGetResponseProxy is None:
                continue
            self.readMicAndSendToGrpc(False)

    def onStartTalkCallback(self):
        self.stateChangeSignal.emit(True)
        log("Character Started Talking")

    def onStopTalkCallback(self):
        self.stateChangeSignal.emit(False)
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

    def updateBtnText(self, newText):
        self.updateBtnTextSignal.emit(newText)  

    def setBtnEnabled(self, enabled):
        self.setBtnEnabledSignal.emit(enabled)  


class ConvaiGRPCGetResponseProxy:
    def __init__(self, parent: ConvaiBackend):
        self.parent = parent

        self.audBuffer = deque(maxlen=4096 * 2)
        self.lastWriteReceived = False
        self.client = None
        self.noOfAudioBytesSent = 0

        self.activate()
        log("ConvaiGRPCGetResponseProxy constructor")

    def activate(self):
        if (len(self.parent.apiKey) == 0):
            self.parent.onFail("API key is empty")
            return

        if (len(self.parent.charId) == 0):
            self.parent.onFail("Character ID is empty")
            return

        if self.parent.channel is None:
            log("grpc - self.parent.channel is None", 1)
            self.parent.onFail("gRPC channel was not created")
            return

        self.client = convaiService.ConvaiServiceStub(self.parent.channel)

        threading.Thread(target=self.initStream).start()

    def initStream(self):
        log("grpc - stream initialized")
        try:
            for response in self.client.GetResponse(self.createGetResponseRequests()):
                if response.HasField("audio_response"):
                    log(
                        "gRPC - audio_response: {} {} {}".format(response.audio_response.audio_config,
                                                                response.audio_response.text_data,
                                                                response.audio_response.end_of_response))
                    log("gRPC - session_id: {}".format(response.session_id))
                    self.parent.onSessionIdReceived(response.session_id)
                    self.parent.onDataReceived(
                        response.audio_response.text_data,
                        response.audio_response.audio_data,
                        response.audio_response.audio_config.sample_rate_hertz,
                        response.audio_response.end_of_response)

                elif response.HasField("action_response"):
                    log(f"gRPC - action_response: {response.action_response.action}")
                    self.parent.onActionsReceived(response.action_response.action)

                else:
                    log("Stream Message: {}".format(response))
            time.sleep(0.1)

        except Exception as e:
            self.parent.onFail(str(e))
            return
        self.parent.onFin()

    def createInitGetResponseRequest(self) -> convaiServiceMsg.GetResponseRequest:
        actionConfig = convaiServiceMsg.ActionConfig(
            classification='singlestep',
            context_level=1
        )
        actionConfig.actions[:] = self.parent.parseActions()
        actionConfig.objects.append(
            convaiServiceMsg.ActionConfig.Object(
                name="dummy",
                description="A dummy object."
            )
        )

        log(f"gRPC - actions parsed: {actionConfig.actions}")
        actionConfig.characters.append(
            convaiServiceMsg.ActionConfig.Character(
                name="User",
                bio="Person playing the game and asking questions."
            )
        )
        getResponseConfig = convaiServiceMsg.GetResponseRequest.GetResponseConfig(
            character_id=self.parent.charId,
            api_key=self.parent.apiKey,
            audio_config=convaiServiceMsg.AudioConfig(
                sample_rate_hertz=RATE
            ),
            action_config=actionConfig
        )
        if self.parent.sessionId and self.parent.sessionId != "":
            getResponseConfig.session_id = self.parent.sessionId
        return convaiServiceMsg.GetResponseRequest(get_response_config=getResponseConfig)

    def createGetResponseRequests(self) -> Generator[convaiServiceMsg.GetResponseRequest, None, None]:
        req = self.createInitGetResponseRequest()
        yield req

        while 1:
            isThisTheFinalWrite = False
            GetResponseData = None
            data, isThisTheFinalWrite = self.consumeFromAudioBuffer()
            if len(data) == 0 and isThisTheFinalWrite == False:
                time.sleep(0.05)
                continue
            self.noOfAudioBytesSent += len(data)
            GetResponseData = convaiServiceMsg.GetResponseRequest.GetResponseData(audio_data=data)

            req = convaiServiceMsg.GetResponseRequest(get_response_data=GetResponseData)
            yield req

            if isThisTheFinalWrite:
                log(f"gRPC - Done Writing - {self.noOfAudioBytesSent} audio bytes sent")
                break
            time.sleep(0.1)

    def writeAudDataToSend(self, Data: bytes, lastWrite: bool):
        self.audBuffer.append(Data)
        if lastWrite:
            self.lastWriteReceived = True
            log(f"gRPC lastWriteReceived")

    def consumeFromAudioBuffer(self):
        length = len(self.audBuffer)
        isThisTheFinalWrite = False
        data = bytes()

        if length:
            data = self.audBuffer.pop()

        if self.lastWriteReceived and length == 0:
            isThisTheFinalWrite = True
        else:
            isThisTheFinalWrite = False

        if isThisTheFinalWrite:
            log(f"gRPC Consuming last mic write")

        return data, isThisTheFinalWrite

    def __del__(self):
        self.parent = None
        log("ConvaiGRPCGetResponseProxy Destructor")