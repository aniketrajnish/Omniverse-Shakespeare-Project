import os
import sys
from concurrent import futures

import grpc
import numpy as np
from grpc import _common, _server
from omni.audio2face.common import log_error, log_info, log_warn

if 0:  # Use this only during development, this helps to hot-reload grpc/protobuf properly
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    from google.protobuf.internal import api_implementation

    log_warn("DEV MODE (turn it off in production): api_implementation.Type() == {}".format(api_implementation.Type()))

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)
import audio2face_pb2
import audio2face_pb2_grpc


class Audio2FaceServicer(audio2face_pb2_grpc.Audio2FaceServicer):
    def __init__(self, audio_start_callback, push_chunk_callback, audio_end_callback):
        self._audio_start_callback = audio_start_callback
        self._push_chunk_callback = push_chunk_callback
        self._audio_end_callback = audio_end_callback

    def PushAudio(self, request, context):
        instance_name = request.instance_name
        samplerate = request.samplerate
        block_until_playback_is_finished = request.block_until_playback_is_finished
        audio_data = np.frombuffer(request.audio_data, dtype=np.float32)
        log_info(
            "PushAudio request: [instance_name = {} ; samplerate = {} ; data.shape = {}]".format(
                instance_name, samplerate, audio_data.shape
            )
        )
        if self._audio_start_callback is not None:
            try:
                self._audio_start_callback(instance_name, samplerate)
            except RuntimeError as e:
                return audio2face_pb2.PushAudioResponse(success=False, message=str(e))
        if self._push_chunk_callback is not None:
            try:
                self._push_chunk_callback(instance_name, audio_data)
            except RuntimeError as e:
                return audio2face_pb2.PushAudioResponse(success=False, message=str(e))
        if self._audio_end_callback is not None:
            try:
                self._audio_end_callback(instance_name, block_until_playback_is_finished)
            except RuntimeError as e:
                return audio2face_pb2.PushAudioResponse(success=False, message=str(e))
        log_info("PushAudio request -- DONE")
        return audio2face_pb2.PushAudioResponse(success=True, message="")

    def PushAudioStream(self, request_iterator, context):
        first_item = next(request_iterator)
        if not first_item.HasField("start_marker"):
            return audio2face_pb2.PushAudioResponse(
                success=False, message="First item in the request should containt start_marker"
            )
        instance_name = first_item.start_marker.instance_name
        samplerate = first_item.start_marker.samplerate
        block_until_playback_is_finished = first_item.start_marker.block_until_playback_is_finished
        log_info("PushAudioStream request: [instance_name = {} ; samplerate = {}]".format(instance_name, samplerate))
        if self._audio_start_callback is not None:
            try:
                self._audio_start_callback(instance_name, samplerate)
            except RuntimeError as e:
                return audio2face_pb2.PushAudioResponse(success=False, message=str(e))

        for item in request_iterator:
            audio_data = np.frombuffer(item.audio_data, dtype=np.float32)
            if self._push_chunk_callback is not None and instance_name is not None:
                try:
                    self._push_chunk_callback(instance_name, audio_data)
                except RuntimeError as e:
                    return audio2face_pb2.PushAudioResponse(success=False, message=str(e))

        if self._audio_end_callback is not None and instance_name is not None:
            try:
                self._audio_end_callback(instance_name, block_until_playback_is_finished)
            except RuntimeError as e:
                return audio2face_pb2.PushAudioResponse(success=False, message=str(e))
        log_info("PushAudioStream request -- DONE")
        return audio2face_pb2.PushAudioResponse(success=True, message="")


class StreamingServer:
    def __init__(self):
        self._server = None
        self._max_workers = 10  # ADJUST
        self._port = "50051"  # ADJUST
        self._address = f"[::]:{self._port}"  # ADJUST

    def start(self, audio_start_callback, push_chunk_callback, audio_end_callback):
        log_info("StreamingServer -- START")
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=self._max_workers))
        audio2face_pb2_grpc.add_Audio2FaceServicer_to_server(
            Audio2FaceServicer(audio_start_callback, push_chunk_callback, audio_end_callback), self._server
        )
        success = _server._add_insecure_port(self._server._state, _common.encode(self._address))
        while success == 0:
            self._port = str(int(self._port) + 1)
            self._address = f"[::]:{self._port}"
            success = _server._add_insecure_port(self._server._state, _common.encode(self._address))
        self._server.start()
        log_info("StreamingServer -- START -- Done")

    def shutdown(self):
        log_info("StreamingServer -- SHUTDOWN")
        self._server.stop(None)
        self._server = None
        log_info("StreamingServer -- SHUTDOWN -- Done")

    def get_port(self):
        return self._port
