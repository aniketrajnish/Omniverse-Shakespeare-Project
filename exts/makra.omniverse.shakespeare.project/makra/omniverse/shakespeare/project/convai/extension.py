import math, os
import asyncio
import numpy as np
import omni.ext
import carb.events
import configparser
import pyaudio
import grpc
from .rpc import service_pb2 as convai_service_msg
from .rpc import service_pb2_grpc as convai_service
from .convai_audio_player import ConvaiAudioPlayer
from typing import Generator
import io
from pydub import AudioSegment
import threading
import traceback
import time
from collections import deque
import random
from functools import partial

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 12000

def log(text: str, warning: bool =False):
    print(f"[convai] {'[Warning]' if warning else ''} {text}")

class ConvaiExtension(omni.ext.IExt):
    _instance = None

    def __init__(self):
        if ConvaiExtension._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            ConvaiExtension._instance = self

        self.IsCapturingAudio = False
        self.on_new_frame_sub = None
        self.channel_address = None
        self.channel = None
        self.SessionID = None
        self.channelState = grpc.ChannelConnectivity.IDLE
        self.client = None
        self.ConvaiGRPCGetResponseProxy = None
        self.PyAudio = pyaudio.PyAudio()
        self.stream = None
        self.Tick = False
        self.TickThread = None
        self.ConvaiAudioPlayer = ConvaiAudioPlayer(self._on_start_talk_callback, self._on_stop_talk_callback)
        self.LastReadyTranscription = ""
        self.ResponseTextBuffer = ""
        self.OldCharacterID = ""

        self.UI_Lock = threading.Lock()
        self.Mic_Lock = threading.Lock()
        self.UI_update_counter = 0
        self.on_new_update_sub = None

        self.read_config()
        self.create_channel()

        log("ConvaiExtension initialized")

    @staticmethod
    def get_instance():
        if ConvaiExtension._instance is None:
            ConvaiExtension()
        return ConvaiExtension._instance

    def on_startup(self, ext_id: str):
        log("ConvaiExtension started") 

    def read_config(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(__location__, 'convai.env'))
        self.api_key = config.get("CONVAI", "API_KEY")
        self.character_id = config.get("CONVAI", "CHARACTER_ID")
        self.channel_address = config.get("CONVAI", "CHANNEL")
        self.actions_text = config.get("CONVAI", "ACTIONS")

    def create_channel(self):
        if (self.channel):
            log("gRPC channel already created")
            return
        
        self.channel = grpc.secure_channel(self.channel_address, grpc.ssl_channel_credentials())
        log("Created gRPC channel")

    def close_channel(self):
        if (self.channel):
            self.channel.close()
            self.channel = None
            log("close_channel - Closed gRPC channel")
        else:
            log("close_channel - gRPC channel already closed")
    
    def start_convai(self):
        # Reset Session ID if Character ID changes
        if self.OldCharacterID != self.character_id:
            self.OldCharacterID = self.character_id
            self.SessionID = ""

        # Reset transcription UI text
        self.LastReadyTranscription = ""

        # Open Mic stream
        self.start_mic()

        # Stop any on-going audio
        self.ConvaiAudioPlayer.stop()

        # Create gRPC stream
        self.ConvaiGRPCGetResponseProxy = ConvaiGRPCGetResponseProxy(self)

    def stop_convai(self):
        # Do one last mic read
        self.read_mic_and_send_to_grpc(True) 
        # Stop Mic
        self.stop_mic()

    def on_shutdown(self):
        self.clean_grpc_stream()
        self.close_channel()
        self.stop_tick()

        log("ConvaiExtension shutdown")

    def start_mic(self):
        if self.IsCapturingAudio == True:
            log("start_mic - mic is already capturing audio", 1)
            return
        self.stream = self.PyAudio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        self.IsCapturingAudio = True
        self.start_tick()
        log("start_mic - Started Recording")

    def stop_mic(self):
        if self.IsCapturingAudio == False:
            log("stop_mic - mic has not started yet", 1)
            return
        
        self.stop_tick()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        else:
            log("stop_mic - could not close mic stream since it is None", 1)
        
        self.IsCapturingAudio = False
        log("stop_mic - Stopped Recording")

    def clean_grpc_stream(self):
        if self.ConvaiGRPCGetResponseProxy:
            self.ConvaiGRPCGetResponseProxy.Parent = None
            del self.ConvaiGRPCGetResponseProxy
        self.ConvaiGRPCGetResponseProxy = None

    def on_data_received(self, ReceivedText: str, ReceivedAudio: bytes, SampleRate: int, IsFinal: bool):
        '''
	    Called when new text and/or Audio data is received
        '''
        self.ResponseTextBuffer += str(ReceivedText)
        if IsFinal:
            with self.UI_Lock:
                self.ResponseTextBuffer = ""
        self.ConvaiAudioPlayer.append_to_stream(ReceivedAudio)
        return

    def on_actions_received(self, Action: str):
        '''
	    Called when actions are received
        '''
        self.UI_Lock.acquire()
        for InputAction in self.parse_actions():
            if Action.find(InputAction) >= 0:
                self.fire_event(InputAction)
                self.UI_Lock.release()
                return
        self.UI_Lock.release()
        
    def on_session_ID_received(self, SessionID: str):
        '''
	    Called when new SessionID is received
        '''
        self.SessionID = SessionID

    def on_finish(self):
        '''
	    Called when the response stream is done
        '''

        self.ConvaiGRPCGetResponseProxy = None
        self.clean_grpc_stream()
        log("Received on_finish")

    def on_failure(self, ErrorMessage: str):
        '''
        Called when there is an unsuccessful response
        '''
        log(f"on_failure called with message: {ErrorMessage}", 1)
        self.stop_mic()
        self.on_finish()

    def _on_tick(self):
        while self.Tick:
            time.sleep(0.1)
            if self.IsCapturingAudio == False or self.ConvaiGRPCGetResponseProxy is None:
                continue
            self.read_mic_and_send_to_grpc(False)

    def _on_start_talk_callback(self):
        self.fire_event("start")
        log("Character Started Talking")

    def _on_stop_talk_callback(self):
        self.fire_event("stop")
        log("Character Stopped Talking")
    
    def read_mic_and_send_to_grpc(self, LastWrite):
        with self.Mic_Lock:
            if self.stream:
                data = self.stream.read(CHUNK)
            else:
                log("read_mic_and_send_to_grpc - could not read mic stream since it is none", 1)
                data = bytes()

            if self.ConvaiGRPCGetResponseProxy:
                self.ConvaiGRPCGetResponseProxy.write_audio_data_to_send(data, LastWrite)
            else:
                log("read_mic_and_send_to_grpc - ConvaiGRPCGetResponseProxy is not valid", 1)

    def fire_event(self, event_name):
        def registered_event_name(event_name):
            """Returns the internal name used for the given custom event name"""
            n = "omni.graph.action." + event_name
            return carb.events.type_from_string(n)

        reg_event_name = registered_event_name(event_name)
        message_bus = omni.kit.app.get_app().get_message_bus_event_stream()

        message_bus.push(reg_event_name, payload={})

    def parse_actions(self):
        actions = ["None"] + self.actions_text.split(',')
        actions = [a.lstrip(" ").rstrip(" ") for a in actions]
        return actions

    def start_tick(self):
        if self.Tick:
            log("Tick already started", 1)
            return
        self.Tick = True
        self.TickThread = threading.Thread(target=self._on_tick)
        self.TickThread.start()

    def stop_tick(self):
        if self.TickThread and self.Tick:
            self.Tick = False
            self.TickThread.join()
            

class ConvaiGRPCGetResponseProxy:
    def __init__(self, Parent: ConvaiExtension):
        self.Parent = Parent

        self.AudioBuffer = deque(maxlen=4096*2)
        self.InformOnDataReceived = False
        self.LastWriteReceived = False
        self.client = None
        self.NumberOfAudioBytesSent = 0
        self.call = None
        self._write_task = None
        self._read_task = None

        self.activate()
        log("ConvaiGRPCGetResponseProxy constructor")

    def activate(self):
        # Validate API key
        if (len(self.Parent.api_key) == 0):
            self.Parent.on_failure("API key is empty")
            return
        
        # Validate Character ID
        if (len(self.Parent.character_id) == 0):
            self.Parent.on_failure("Character ID is empty")
            return
        
        # Validate Channel
        if self.Parent.channel is None:
            log("grpc - self.Parent.channel is None", 1)
            self.Parent.on_failure("gRPC channel was not created")
            return

        # Create the stub
        self.client = convai_service.ConvaiServiceStub(self.Parent.channel)

        threading.Thread(target=self.init_stream).start()

    def init_stream(self):
        log("grpc - stream initialized")
        try:
            for response in self.client.GetResponse(self.create_getGetResponseRequests()):
                if response.HasField("audio_response"):
                    log("gRPC - audio_response: {} {} {}".format(response.audio_response.audio_config, response.audio_response.text_data, response.audio_response.end_of_response))
                    log("gRPC - session_id: {}".format(response.session_id))
                    self.Parent.on_session_ID_received(response.session_id)
                    self.Parent.on_data_received(
                        response.audio_response.text_data,
                        response.audio_response.audio_data,
                        response.audio_response.audio_config.sample_rate_hertz,
                        response.audio_response.end_of_response)

                elif response.HasField("action_response"):
                    log(f"gRPC - action_response: {response.action_response.action}")
                    self.Parent.on_actions_received(response.action_response.action)

                else:
                    log("Stream Message: {}".format(response))
            time.sleep(0.1)
                
        except Exception as e:
            if 'response' in locals() and response is not None and response.HasField("audio_response"):
                self.Parent.on_failure(f"gRPC - Exception caught in loop: {str(e)} - Stream Message: {response}")
            else:
                self.Parent.on_failure(f"gRPC - Exception caught in loop: {str(e)}")
            traceback.print_exc()
            return
        self.Parent.on_finish()

    def create_initial_GetResponseRequest(self)-> convai_service_msg.GetResponseRequest:
        action_config = convai_service_msg.ActionConfig(
            classification = 'singlestep',
            context_level = 1
        )
        action_config.actions[:] = self.Parent.parse_actions()
        action_config.objects.append(
            convai_service_msg.ActionConfig.Object(
                name = "dummy",
                description = "A dummy object."
            )
        )

        log(f"gRPC - actions parsed: {action_config.actions}")
        action_config.characters.append(
            convai_service_msg.ActionConfig.Character(
                name = "User",
                bio = "Person playing the game and asking questions."
            )
        )
        get_response_config = convai_service_msg.GetResponseRequest.GetResponseConfig(
                character_id = self.Parent.character_id,
                api_key = self.Parent.api_key,
                audio_config = convai_service_msg.AudioConfig(
                    sample_rate_hertz = RATE
                ),
                action_config = action_config
            )
        if self.Parent.SessionID and self.Parent.SessionID != "":
            get_response_config.session_id = self.Parent.SessionID
        return convai_service_msg.GetResponseRequest(get_response_config = get_response_config)

    def create_getGetResponseRequests(self)-> Generator[convai_service_msg.GetResponseRequest, None, None]:
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
                GetResponseData = convai_service_msg.GetResponseRequest.GetResponseData(audio_data = data)

            req = convai_service_msg.GetResponseRequest(get_response_data = GetResponseData)
            yield req

            if IsThisTheFinalWrite:
                log(f"gRPC - Done Writing - {self.NumberOfAudioBytesSent} audio bytes sent")
                break
            time.sleep(0.1)

    def write_audio_data_to_send(self, Data: bytes, LastWrite: bool):
        self.AudioBuffer.append(Data)
        if LastWrite:
            self.LastWriteReceived = True
            log(f"gRPC LastWriteReceived")

    def finish_writing(self):
        self.write_audio_data_to_send(bytes(), True)

    def consume_from_audio_buffer(self):
        Length = len(self.AudioBuffer)
        IsThisTheFinalWrite = False
        data = bytes()

        if Length:
            data = self.AudioBuffer.pop()
        
        if self.LastWriteReceived and Length == 0:
            IsThisTheFinalWrite = True
        else:
            IsThisTheFinalWrite = False

        if IsThisTheFinalWrite:
            log(f"gRPC Consuming last mic write")

        return data, IsThisTheFinalWrite
    
    def __del__(self):
        self.Parent = None
        log("ConvaiGRPCGetResponseProxy Destructor")