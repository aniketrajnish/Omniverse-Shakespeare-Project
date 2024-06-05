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
import carb.events


__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 12000

def log(text: str, warning: bool =False):
    print(f"[convai] {'[Warning]' if warning else ''} {text}")

class ConvaiBackend:  # Renamed from ConvaiExtension 
    def __init__(self):
        self.is_capturing_audio = False # renamed to lowercase 
        self.channel_address = None
        self.channel = None
        self.session_id = None 
        self.client = None
        self.convai_grpc_response_proxy = None 
        self.pyaudio = pyaudio.PyAudio()
        self.stream = None
        self.tick = False
        self.tick_thread = None
        self.convai_audio_player = ConvaiAudioPlayer(self._on_start_talk_callback, self._on_stop_talk_callback)
        self.last_ready_transcription = "" 
        self.response_text_buffer = ""
        self.old_character_id = ""
        self.sp_transcription_text = ""  
        self.user_transcription_text = ""
        self.ui_update_counter = 0
        self.on_new_update_sub = None

        self.ui_lock = threading.Lock()
        self.mic_lock = threading.Lock()

        # Read config values from convai.env
        self.read_config()
        self.create_channel()

        log("Convai Backend initialized")

    def read_config(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(__location__, 'convai.env'))
        self.api_key = config.get("CONVAI", "API_KEY")
        self.character_id = config.get("CONVAI", "CHARACTER_ID")
        self.channel_address = config.get("CONVAI", "CHANNEL")
        self.actions_text = config.get("CONVAI", "ACTIONS")

    def create_channel(self):
        if self.channel:
            log("gRPC channel already created")
            return
        self.channel = grpc.secure_channel(self.channel_address, grpc.ssl_channel_credentials())
        log("Created gRPC channel")

    def close_channel(self):
        if self.channel:
            self.channel.close()
            self.channel = None
            log("close_channel - Closed gRPC channel")
        else:
            log("close_channel - gRPC channel already closed")

    def start_conversation(self):
        if self.is_capturing_audio:
            log("start_conversation - Microphone is already capturing audio", 1)
            return

        # Reset Session ID if Character ID changes
        if self.old_character_id != self.character_id:
            self.old_character_id = self.character_id
            self.session_id = ""

        # Reset transcription 
        self.transcription_text = ""
        self.last_ready_transcription = ""

        # Open Mic stream
        self.start_mic()

        # Stop any on-going audio
        self.convai_audio_player.stop()

        # Create gRPC stream
        self.convai_grpc_response_proxy = ConvaiGRPCGetResponseProxy(self)

        if self.on_new_update_sub is None: # This check is important
            self.on_new_update_sub = (
                omni.kit.app.get_app()
                .get_update_event_stream()
                .create_subscription_to_pop(self._on_ui_update_event, name="convai new UI update")
            )

    def stop_conversation(self):
        if not self.is_capturing_audio:
            log("stop_conversation - Microphone is not capturing audio", 1)
            return
        
        with self.ui_lock:
            self.StartTalking_Btn_text = "Processing..." # Set button text to processing
            self.StartTalking_Btn_state = False # Disable the button

        # Do one last mic read
        self.read_mic_and_send_to_grpc(True) 

        # Stop Mic
        self.stop_mic()
        self._trigger_ui_update()

    def _trigger_ui_update(self):
        if self.on_new_update_sub:
            self.on_new_update_sub.unsubscribe()
            self.on_new_update_sub = None
        self.start_conversation()

    def on_shutdown(self):
        self.clean_grpc_stream()
        self.close_channel()
        self.stop_tick()
        log("Convai Backend shutdown")

    def start_mic(self):
        if self.is_capturing_audio:
            log("start_mic - mic is already capturing audio", 1)
            return
        self.stream = self.pyaudio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        self.is_capturing_audio = True
        self.start_tick()
        log("start_mic - Started Recording")

    def stop_mic(self):
        if not self.is_capturing_audio:
            log("stop_mic - mic has not started yet", 1)
            return
        
        self.stop_tick()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        else:
            log("stop_mic - could not close mic stream since it is None", 1)
        
        self.is_capturing_audio = False
        log("stop_mic - Stopped Recording")

    def start_tick(self):
        if self.tick:
            log("Tick already started", 1)
            return
        self.tick = True
        self.tick_thread = threading.Thread(target=self._on_tick)
        self.tick_thread.start()

    def stop_tick(self):
        if self.tick_thread and self.tick:
            self.tick = False
            self.tick_thread.join()

    def clean_grpc_stream(self):
        if self.convai_grpc_response_proxy:
            self.convai_grpc_response_proxy.parent = None
            del self.convai_grpc_response_proxy
        self.convai_grpc_response_proxy = None 

    def on_transcription_received(self, transcription: str, is_transcription_ready: bool, is_final: bool):
        '''
        Called when user transcription is received
        '''
        with self.ui_lock:
            self.user_transcription_text = self.last_ready_transcription + " " + transcription # Update user_transcription_text
        if is_transcription_ready:
            self.last_ready_transcription = self.last_ready_transcription + " " + transcription

    def on_data_received(self, received_text: str, received_audio: bytes, sample_rate: int, is_final: bool):
        '''
	    Called when new text and/or Audio data is received
        '''
        self.response_text_buffer += str(received_text)
        if is_final:
            with self.ui_lock:
                self.sp_transcription_text = self.response_text_buffer  # This stores Shakespeare's response
                self.response_text_buffer = ""
        self.convai_audio_player.append_to_stream(received_audio)
        return

    def _on_ui_update_event(self, e):
        if self.ui_update_counter > 1000:
            self.ui_update_counter = 0
        self.ui_update_counter += 1

        if self.ui_lock.locked():
            log("UI_Lock is locked", 1)
            return

        with self.ui_lock:
            if self.user_transcription_text or self.sp_transcription_text:
                # Prepare the payload for the event
                payload = {
                    "user_text": self.user_transcription_text,
                    "sp_text": self.sp_transcription_text
                }
                # Push the event with the correct event type and payload
                omni.kit.app.get_app().get_message_bus_event_stream().push(
                    event_type=0,  # You might need to define or obtain the correct event type if necessary
                    sender=0,      # Sender ID, if needed, should be obtained or defined
                    payload=payload
                )
                # Clear the transcription texts after pushing the event
                self.user_transcription_text = ""  
                self.sp_transcription_text = ""


    def on_actions_received(self, action: str):
        '''
	    Called when actions are received
        '''
        with self.ui_lock:
            for input_action in self.parse_actions():
                if action.find(input_action) >= 0:
                    self.fire_event(input_action)
                    return

    def on_session_id_received(self, session_id: str):
        '''
	    Called when new SessionID is received
        '''
        self.session_id = session_id

    def on_finish(self):
        '''
	    Called when the response stream is done
        '''
        self.convai_grpc_response_proxy = None
        with self.ui_lock:
            self.StartTalking_Btn_text = "Start Talking"  # Reset button text
            self.StartTalking_Btn_state = True           # Enable button
        self.clean_grpc_stream()
        log("Received on_finish")

    def on_failure(self, error_message: str):
        '''
        Called when there is an unsuccessful response
        '''
        log(f"on_failure called with message: {error_message}", 1)
        with self.ui_lock:
            self.transcription_text = "ERROR: Please double check API key and the character ID - Send logs to support@convai.com for further assistance."
        self.stop_mic()
        self.on_finish()

    def _on_tick(self):
        while self.tick:
            time.sleep(0.1)
            if not self.is_capturing_audio or self.convai_grpc_response_proxy is None:
                continue
            self.read_mic_and_send_to_grpc(False)

    def _on_start_talk_callback(self):
        self.fire_event("start")
        log("Character Started Talking")

    def _on_stop_talk_callback(self):
        self.fire_event("stop")
        log("Character Stopped Talking")
    
    def read_mic_and_send_to_grpc(self, last_write):
        with self.mic_lock:
            if self.stream:
                data = self.stream.read(CHUNK)
            else:
                log("read_mic_and_send_to_grpc - could not read mic stream since it is none", 1)
                data = bytes()

            if self.convai_grpc_response_proxy:
                self.convai_grpc_response_proxy.write_audio_data_to_send(data, last_write)
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

class ConvaiGRPCGetResponseProxy:
    def __init__(self, parent: ConvaiBackend): # changed ConvaiExtension to ConvaiBackend 
        self.parent = parent

        self.audio_buffer = deque(maxlen=4096*2)
        self.inform_on_data_received = False
        self.last_write_received = False
        self.client = None
        self.number_of_audio_bytes_sent = 0
        self.call = None
        self._write_task = None
        self._read_task = None

        self.activate()
        log("ConvaiGRPCGetResponseProxy constructor")

    def activate(self):
        # Validate API key
        if (len(self.parent.api_key) == 0):
            self.parent.on_failure("API key is empty")
            return
        
        # Validate Character ID
        if (len(self.parent.character_id) == 0):
            self.parent.on_failure("Character ID is empty")
            return
        
        # Validate Channel
        if self.parent.channel is None:
            log("grpc - self.parent.channel is None", 1)
            self.parent.on_failure("gRPC channel was not created")
            return

        # Create the stub
        self.client = convai_service.ConvaiServiceStub(self.parent.channel)

        threading.Thread(target=self.init_stream).start()

    def init_stream(self):
        log("grpc - stream initialized")
        try:
            for response in self.client.GetResponse(self.create_get_get_response_requests()):
                if response.HasField("audio_response"):
                    log("gRPC - audio_response: {} {} {}".format(response.audio_response.audio_config, response.audio_response.text_data, response.audio_response.end_of_response))
                    log("gRPC - session_id: {}".format(response.session_id))
                    self.parent.on_session_id_received(response.session_id)
                    self.parent.on_data_received(
                        response.audio_response.text_data,
                        response.audio_response.audio_data,
                        response.audio_response.audio_config.sample_rate_hertz,
                        response.audio_response.end_of_response)

                elif response.HasField("action_response"):
                    log(f"gRPC - action_response: {response.action_response.action}")
                    self.parent.on_actions_received(response.action_response.action)

                elif response.HasField("user_query"):
                    log(f"gRPC - user_query: {response.user_query}")
                    self.parent.on_transcription_received(response.user_query.text_data, response.user_query.is_final, response.user_query.end_of_response)

                else:
                    log("Stream Message: {}".format(response))
            time.sleep(0.1)
                
        except Exception as e:
            if 'response' in locals() and response is not None and response.HasField("audio_response"):
                self.parent.on_failure(f"gRPC - Exception caught in loop: {str(e)} - Stream Message: {response}")
            else:
                self.parent.on_failure(f"gRPC - Exception caught in loop: {str(e)}")
            traceback.print_exc()
            return
        self.parent.on_finish()

    def create_initial_get_response_request(self) -> convai_service_msg.GetResponseRequest:
        action_config = convai_service_msg.ActionConfig(
            classification='singlestep',
            context_level=1
        )
        action_config.actions[:] = self.parent.parse_actions()
        action_config.objects.append(
            convai_service_msg.ActionConfig.Object(
                name="dummy",
                description="A dummy object."
            )
        )

        log(f"gRPC - actions parsed: {action_config.actions}")
        action_config.characters.append(
            convai_service_msg.ActionConfig.Character(
                name="User",
                bio="Person playing the game and asking questions."
            )
        )
        get_response_config = convai_service_msg.GetResponseRequest.GetResponseConfig(
            character_id=self.parent.character_id,
            api_key=self.parent.api_key,
            audio_config=convai_service_msg.AudioConfig(
                sample_rate_hertz=RATE
            ),
            action_config=action_config
        )
        if self.parent.session_id and self.parent.session_id != "":
            get_response_config.session_id = self.parent.session_id
        return convai_service_msg.GetResponseRequest(get_response_config=get_response_config)

    def create_get_get_response_requests(self) -> Generator[convai_service_msg.GetResponseRequest, None, None]:
        req = self.create_initial_get_response_request()
        yield req

        while 1:
            is_this_the_final_write = False
            get_response_data = None

            if (0):  # check if this is a text request
                pass
            else:
                data, is_this_the_final_write = self.consume_from_audio_buffer()
                if len(data) == 0 and not is_this_the_final_write:
                    time.sleep(0.05)
                    continue
                self.number_of_audio_bytes_sent += len(data)
                get_response_data = convai_service_msg.GetResponseRequest.GetResponseData(audio_data=data)

            req = convai_service_msg.GetResponseRequest(get_response_data=get_response_data)
            yield req

            if is_this_the_final_write:
                log(f"gRPC - Done Writing - {self.number_of_audio_bytes_sent} audio bytes sent")
                break
            time.sleep(0.1)

    def write_audio_data_to_send(self, data: bytes, last_write: bool):
        self.audio_buffer.append(data)
        if last_write:
            self.last_write_received = True
            log(f"gRPC LastWriteReceived")

    def finish_writing(self):
        self.write_audio_data_to_send(bytes(), True)

    def consume_from_audio_buffer(self):
        length = len(self.audio_buffer)
        is_this_the_final_write = False
        data = bytes()

        if length:
            data = self.audio_buffer.pop()

        if self.last_write_received and length == 0:
            is_this_the_final_write = True
        else:
            is_this_the_final_write = False

        if is_this_the_final_write:
            log(f"gRPC Consuming last mic write")

        return data, is_this_the_final_write

    def __del__(self):
        self.parent = None
        log("ConvaiGRPCGetResponseProxy Destructor")