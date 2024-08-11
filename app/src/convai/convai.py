# ------------------------------------------------------------------------------
# Handles the Convai backend operations such as gRPC communication, audio
# Also handles the connection to the A2F server
# We're using sockects to communicate as the protobuf & gRPC versions,
# are different between backend and A2F & the implementation is incompatible.
# Backend uses grpcio==1.65.1 & protobuf==4.21.10 due to requirements of Convai
# A2F uses grpcio==1.51.3 & protobuf==3.17.3
# ------------------------------------------------------------------------------

import os, configparser, pyaudio, grpc, requests, json, threading, time
from typing import Generator
from collections import deque
from PyQt5.QtCore import pyqtSignal, QObject
from .rpc import service_pb2 as convaiServiceMsg, service_pb2_grpc as convaiService
from pydub import AudioSegment, playback
from io import BytesIO
from socket import socket, AF_INET, SOCK_STREAM
from struct import pack
from .localaudioplayer import LocalAudioPlayer

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__))) # current file's directory

CHUNK = 1024 # audio chunk size
FORMAT = pyaudio.paInt16 # 16 bit int audio format
CHANNELS = 1
RATE = 6000 # 6kHz sample rate

def log(text: str, warning: bool = False):
    print(f'[convai] {'[Warning]' if warning else ''} {text}')

def loadConvaiConfig():
    ''''
    Load the Convai configuration from the convai.env file.

    Returns:
        dict: The Convai configuration data
    '''
    configPath = os.path.join(os.path.dirname(__file__), 'convai.env')
    if not os.path.exists(configPath):
        raise FileNotFoundError('Convai configuration file not found.')

    config = configparser.ConfigParser()
    config.read(configPath)

    try:
        convaiConfig = {
            'apiKey': config.get('CONVAI', 'API_KEY'),
            'characterId': config.get('CONVAI', 'CHARACTER_ID'),
            'channel': config.get('CONVAI', 'CHANNEL'),
            'actions': config.get('CONVAI', 'ACTIONS'),
            'sessionId': config.get('CONVAI', 'SESSION_ID'),
            'baseBackstory': config.get('CONVAI', 'BASE_BACKSTORY').replace('\\n', '\n')
        }
    except configparser.NoOptionError as e:
        raise KeyError(f'Missing configuration key in convai.env: {e}')

    return convaiConfig

def updateCharBackstory(newBackstory):
    '''
    Updates shakespeares backstory on Convai.

    Args:
        newBackstory (str): The new backstory to update
    '''
    config = loadConvaiConfig()
    url = 'https://api.convai.com/character/update'
    payload = json.dumps({
        'charID': config['characterId'],
        'backstory': newBackstory
    })
    headers = {
        'CONVAI-API-KEY': config['apiKey'],
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        log('Character updated successfully.')
    else:
        log(f'Failed to update character: {response.status_code} - {response.text}')

def appendToCharBackstory(backstoryUpdate):
    '''
    Appends text recieved from gemini to the current backstory.

    Args:
        backstoryUpdate (str): The text to append to the backstory,
                               recieved from gemini.
    '''
    config = loadConvaiConfig()
    currBackstory = config['baseBackstory']
    if currBackstory:
        newBackstory = f'{currBackstory}\n{backstoryUpdate}'
        updateCharBackstory(newBackstory)

# ------------------------------------------------------------------------------------
# ConvaiBackend class is a singleton class that derives from PyQt5.QtCore.QObject.
# It handles the Convai backend operations as well as the connection to the A2F server.
# ------------------------------------------------------------------------------------

class ConvaiBackend(QObject):
    '''
    Handles the Convai conversation, audio streaming, 
    gRPC communication, and connecting to the A2F server.
    This class is a singleton, ensuring only one instance exists.
    '''
    _instance = None
    stateChangeSignal = pyqtSignal(bool)
    errorSignal = pyqtSignal(str)
    updateBtnTextSignal = pyqtSignal(str)  
    setBtnEnabledSignal = pyqtSignal(bool)
    isSendingAudSignal = pyqtSignal(bool)

    @staticmethod
    def getInstance():
        '''
        Get the singleton instance of the ConvaiBackend class.
        '''
        if ConvaiBackend._instance is None:
            ConvaiBackend._instance = ConvaiBackend()
        return ConvaiBackend._instance

    def __init__(self):
        '''
        Initializes the ConvaiBackend class.
        Enforces the singleton pattern.
        '''
        super().__init__()
        if ConvaiBackend._instance is not None:
            raise Exception('This class is a singleton!')
        else:
            ConvaiBackend._instance = self
        
        self.initVars()
        self.readConfig()
        self.createChannel()

        log('ConvaiBackend initialized')

    def initVars(self):
        '''
        Initializes the class variables.
        '''
        self.localAudPlayer = LocalAudioPlayer(self.onStartTalkCallback, self.onStopTalkCallback)

        self.audQueue = deque(maxlen=4096 * 8)
        self.audSocket = None
        self.cntrlSocket = None
        self.audSocketThread = None
        self.a2fHst = 'localhost'
        self.a2fPrt = 65432 # port for audio data
        self.cntrlPrt = 65433 # port to stop the stream
        self.audQueueCondition = threading.Condition()

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
        self.ResponseTextBuffer = ''
        self.OldCharacterID = ''

        self.uiLock = threading.Lock()
        self.micLock = threading.Lock()    

    def connectToA2F(self):
        '''
        Connects to the Audio2Face server's audio socket.
        Raises an exception if the connection fails.
        '''
        try:
            self.audSocket = socket(AF_INET, SOCK_STREAM)
            self.audSocket.connect((self.a2fHst, self.a2fPrt))
            self.audSocketThread = threading.Thread(target=self.audioSocketLoop)
            self.audSocketThread.daemon = True
            self.audSocketThread.start()
            log('Connected to A2F audio socket')
        except Exception as e:
            self.audSocket = None
            raise Exception(f'Error connecting to A2F: {e}')

    def connectCntrlSocket(self):
        '''
        Connects to the Audio2Face server's control socket.
        Meant to send control signals to the A2F server.
        '''
        try:
            self.cntrlSocket = socket(AF_INET, SOCK_STREAM)
            self.cntrlSocket.connect((self.a2fHst, self.cntrlPrt))
            log('Connected to control socket')
        except Exception as e:
            log(f'Error connecting to control socket: {e}', 1)
            self.cntrlSocket = None

    def audioSocketLoop(self):
        '''
        Main loop to send audio data to the A2F server.
        Uses struct.pack to pack the audio data with the sample rate.
        '''
        while True:
            try:
                with self.audQueueCondition:
                    while not self.audQueue:
                        print('[Convai - audioSocketLoop] Waiting for audio data...')
                        self.audQueueCondition.wait()

                    while self.audQueue:
                        wavData, sampleRate = self.audQueue.popleft()
                        message = pack('>i', sampleRate) + b'|' + wavData
                        message_length = len(message)
                        
                        print(f'[Convai] Sending message length: {message_length}')
                        self.audSocket.sendall(pack('>i', message_length) + message)
                        print('[Convai] Audio chunk sent')

            except Exception as e:
                log(f'Error sending audio data: {e}', 1)
                self.audSocket.close()
                self.audSocket = None 
                break 

    def readConfig(self):
        '''
        Again, reads the API configuration.
        '''
        config = configparser.ConfigParser()
        config.read(os.path.join(__location__, 'convai.env'))

        self.apiKey = config.get('CONVAI', 'API_KEY')
        self.charId = config.get('CONVAI', 'CHARACTER_ID')
        self.channelAddress = config.get('CONVAI', 'CHANNEL')

    def createChannel(self):
        '''
        Creates gRPC channel for comm with Convai.
        '''
        if self.channel:
            log('gRPC channel already created')
            return

        self.channel = grpc.secure_channel(self.channelAddress, grpc.ssl_channel_credentials())
        log('Created gRPC channel')

    def closeChannel(self):
        '''
        Closes the gRPC channel.
        '''
        if self.channel:
            self.channel.close()
            self.channel = None
            log('closeChannel - Closed gRPC channel')
        else:
            log('closeChannel - gRPC channel already closed')
            pass

    def startConvai(self):
        if self.OldCharacterID != self.charId:
            self.OldCharacterID = self.charId
            self.sessionId = ''       

        self.updateBtnText('Stop')
        self.isSendingAudSignal.emit(True)
        self.startMic()
        self.convaiGRPCGetResponseProxy = ConvaiGRPCGetResponseProxy(self)
        
        if not self.audSocket:
            try:
                self.connectToA2F()
            except Exception as e:
                log(f'Failed to connect to A2F: {e}. Will play audio locally.', 1)
        
        if not self.cntrlSocket:
            try:
                self.connectCntrlSocket()
            except Exception as e:
                log(f'Failed to connect control socket: {e}', 1)

        self.isSendingAudSignal.emit(False)
        self.localAudPlayer.stop()

    def stopConvai(self):
        '''
        Stops the Convai conversation and audio streaming.
        '''
        self.updateBtnText('Processing...')
        self.setBtnEnabled(False)
        self.isSendingAudSignal.emit(True)
        self.readMicAndSendToGrpc(True)  
        self.stopMic()
        if not self.audSocket:
            self.localAudPlayer.stop()

    def stopShakespeare(self):
        '''
        Sends a stop signal to the A2F server through the control socket.
        '''
        try:
            self.localAudPlayer.stop()
            if self.cntrlSocket:
                self.cntrlSocket.sendall(b'stop')
                log('Sent stop signal to A2F')
                response = self.cntrlSocket.recv(7) # waiting for 'stopped' 
                if response == b'stopped':          # from A2F
                    log('Received confirmation of stop from A2F')
            if self.audSocket:
                self.audSocket.close()
                self.audSocket = None
                log('Closed audio socket')
            self.isSendingAudSignal.emit(False)
        except Exception as e:
            log(f'Error sending stop signal to A2F: {e}', 1)
        finally:
            self.cntrlSocket = None

    def startMic(self):
        '''
        Starts capturing audio from the microphone using PyAudio.
        '''
        if self.isCapturingAudio:
            log('startMic - mic is already capturing audio', 1)
            return

        self.stream = self.pyAudio.open(format=FORMAT,
                                        channels=CHANNELS,
                                        rate=RATE,
                                        input=True,
                                        frames_per_buffer=CHUNK)
        self.isCapturingAudio = True
        self.startTick()
        log('startMic - Started Recording')

    def stopMic(self):
        '''
        Stops capturing audio from the microphone.
        '''
        if not self.isCapturingAudio:
            log('stopMic - mic has not started yet', 1)
            return

        self.stopTick()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        else:
            pass
            log('stopMic - could not close mic stream since it is None', 1)

        self.isCapturingAudio = False
        log('stopMic - Stopped Recording')

    def cleanGrpcStream(self):
        '''
        Cleans up the gRPC stream object.
        '''
        if self.convaiGRPCGetResponseProxy:
            self.convaiGRPCGetResponseProxy.parent = None
            del self.convaiGRPCGetResponseProxy
        self.convaiGRPCGetResponseProxy = None

    def onDataReceived(self, receivedText: str, receivedAudio: bytes, SampleRate: int, isFinal: bool):
        '''
        Handles the received audio data from the Convai server.
        Streams to A2F if connected, otherwise plays locally using LocalAudioPlayer.
        '''
        try:
            print(f'Received audio data: length={len(receivedAudio)}, sample_rate={SampleRate}')
            if self.audSocket:
                segment = AudioSegment.from_wav(BytesIO(receivedAudio)).fade_in(10).fade_out(10)
                
                wavBuffer = BytesIO()
                segment.export(wavBuffer, format='wav')
                wavData = wavBuffer.getvalue()
                
                with self.audQueueCondition:
                    self.audQueue.append((wavData, SampleRate))
                    print(f'Added audio chunk to queue. Queue size: {len(self.audQueue)}')
                    self.audQueueCondition.notify()
                print(f'Processed audio: length={len(segment)}, channels={segment.channels}, sample_width={segment.sample_width}, frame_rate={segment.frame_rate}')
            else:
                log('A2F connection not established. Playing audio locally.')
                self.localAudPlayer.appendToStream(receivedAudio)
        
        except Exception as e:
            log(f'Error in onDataReceived: {e}', 1)  

    def onSessionIdReceived(self, sessionId: str):
        '''
        Handles the received session ID from the Convai server.
        '''
        self.sessionId = sessionId

    def onFin(self, resetUI=True):
        '''
        Handles the end of the Convai conversation.
        '''
        self.convaiGRPCGetResponseProxy = None
        self.cleanGrpcStream()
        if resetUI:
            self.updateBtnText('Start Talking')
            self.setBtnEnabled(True)

    def onFail(self, ErrorMessage: str):
        '''
        If any error occurs during the Convai conversation, this function is called.
        The error message is displayed to the user and the conversation is stopped.
        '''
        log(f'onFail called with message: {ErrorMessage}', 1)
        self.stopMic()
        self.errorSignal.emit('Try Again!')
        self.onFin(resetUI=True)

    def onTick(self):
        '''
        Periodically reads audio data from the microphone,
        and sends it to the Convai server.
        '''
        while self.tick:
            time.sleep(0.1)
            if not self.isCapturingAudio or self.convaiGRPCGetResponseProxy is None:
                continue
            self.readMicAndSendToGrpc(False)

    def onStartTalkCallback(self):
        self.updateBtnText('Start Talking')
        self.setBtnEnabled(True)
        self.isSendingAudSignal.emit(True)
        log('Character Started Talking')

    def onStopTalkCallback(self):       
        log('Character Stopped Talking')

    def readMicAndSendToGrpc(self, lastWrite):
        '''
        Reads audio data from the microphone and sends it to the gRPC stream.
        '''
        with self.micLock:
            if self.stream:
                data = self.stream.read(CHUNK)
            else:
                log('readMicAndSendToGrpc - could not read mic stream since it is none', 1)
                data = bytes()

            if self.convaiGRPCGetResponseProxy:
                self.convaiGRPCGetResponseProxy.writeAudDataToSend(data, lastWrite)
            else:
                pass
                log('readMicAndSendToGrpc - ConvaiGRPCGetResponseProxy is not valid', 1)    

    def startTick(self):
        '''
        Audio processing tick.
        '''
        if self.tick:
            log('Tick already started', 1)
            return
        self.tick = True
        self.tickThread = threading.Thread(target=self.onTick)
        self.tickThread.start()

    def stopTick(self):
        '''
        Stops the audio processing tick.
        '''
        if self.tickThread and self.tick:
            self.tick = False
            self.tickThread.join()

    def updateBtnText(self, newText):
        '''
        Sends a signal to update the button text in PyQt.
        '''
        self.updateBtnTextSignal.emit(newText)  

    def setBtnEnabled(self, enabled):
        '''
        Sends a signal to enable/disable the button in PyQt.
        '''
        self.setBtnEnabledSignal.emit(enabled)  

# ------------------------------------------------------------------------------------
# Proxy object for handling gRPC communication with the Convai server.
# ------------------------------------------------------------------------------------

class ConvaiGRPCGetResponseProxy:
    '''
    Handles the gRPC GetResponse stream with the Convai server.
    '''
    def __init__(self, parent: ConvaiBackend):
        '''
        Initializes the audio buffer and the gRPC client.

        Args:
            parent (ConvaiBackend): The parent ConvaiBackend object.
        '''
        self.parent = parent

        self.audBuffer = deque(maxlen=4096 * 8)
        self.lastWriteReceived = False
        self.client = None
        self.noOfAudioBytesSent = 0
        self.audQueue = deque(maxlen=4096 * 8)

        self.activate()
        log('ConvaiGRPCGetResponseProxy constructor')

    def activate(self):
        '''
        Activates the Convai gRPC GetResponse stream.
        '''
        if (len(self.parent.apiKey) == 0): # convai checks
            self.parent.onFail('API key is empty')
            return

        if (len(self.parent.charId) == 0):
            self.parent.onFail('Character ID is empty')
            return

        if self.parent.channel is None:
            log('grpc - self.parent.channel is None', 1)
            self.parent.onFail('gRPC channel was not created')
            return

        self.client = convaiService.ConvaiServiceStub(self.parent.channel)

        threading.Thread(target=self.initStream).start() # start the gRPC stream
                                                         # in a separate thread
    def initStream(self):       
        '''
        Initializes and handles the gRPC GetResponse stream.
        ''' 
        log('grpc - stream initialized')
        try:
            for response in self.client.GetResponse(self.createGetResponseRequests()):
                if response.HasField('audio_response'):
                    log(
                        'gRPC - audio_response: {} {} {}'.format(response.audio_response.audio_config,
                                                                response.audio_response.text_data,
                                                                response.audio_response.end_of_response))
                    log('gRPC - session_id: {}'.format(response.session_id))
                    self.parent.onSessionIdReceived(response.session_id)
                    self.parent.onDataReceived(
                        response.audio_response.text_data,
                        response.audio_response.audio_data,
                        response.audio_response.audio_config.sample_rate_hertz,
                        response.audio_response.end_of_response)
                    
                    print('Received sample rate: ', response.audio_response.audio_config.sample_rate_hertz)
                else:
                    log('Unexpected response type: {}'.format(response))
            time.sleep(0.1)

        except Exception as e:
            self.parent.onFail(str(e))
            return
        self.parent.onFin()


    def createInitGetResponseRequest(self) -> convaiServiceMsg.GetResponseRequest:
        '''
        Intializes the GetResponse request with the config data.

        Returns:
            convaiServiceMsg.GetResponseRequest: The GetResponse request object.
        '''
        getResponseConfig = convaiServiceMsg.GetResponseRequest.GetResponseConfig(
            character_id=self.parent.charId,
            api_key=self.parent.apiKey,
            audio_config=convaiServiceMsg.AudioConfig(
                sample_rate_hertz=RATE
            ),            
        )
        
        if self.parent.sessionId and self.parent.sessionId != '':
            getResponseConfig.session_id = self.parent.sessionId
        
        return convaiServiceMsg.GetResponseRequest(get_response_config=getResponseConfig) # req object

    def createGetResponseRequests(self) -> Generator[convaiServiceMsg.GetResponseRequest, None, None]:
        '''
        Generator fn to yield GetResponseRequest for the gRPC stream.
        '''
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
                log(f'gRPC - Done Writing - {self.noOfAudioBytesSent} audio bytes sent')
                break
            time.sleep(0.1)  

    def writeAudDataToSend(self, Data: bytes, lastWrite: bool):
        '''
        Writes audio data to the audio buffer.
        This data is to be sent to the gRPC stream.
        '''
        self.audBuffer.append(Data)
        if lastWrite:
            self.lastWriteReceived = True
            log(f'gRPC lastWriteReceived')

    def consumeFromAudioBuffer(self):
        '''
        Consumes audio data from the audio buffer.
        '''
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
            pass
            log(f'gRPC Consuming last mic write')

        return data, isThisTheFinalWrite

    def __del__(self):
        '''
        Destructor
        '''
        self.parent = None
        log('ConvaiGRPCGetResponseProxy Destructor')