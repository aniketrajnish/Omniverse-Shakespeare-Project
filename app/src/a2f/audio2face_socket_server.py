import grpc, io, wave, struct, socket
import audio2face_pb2, audio2face_pb2_grpc
import numpy as np
import threading
import time

class A2FClient:
    def __init__(self, url, instance_name):
        self.url = url
        self.instance_name = instance_name
        self.channel = grpc.insecure_channel(url)
        self.stub = audio2face_pb2_grpc.Audio2FaceStub(self.channel)
        self.channels = 1
        self.sample_width = 2  # 2 bytes for int16
        self.accumulated_audio = b''
        self.sample_rate = None
        self.lock = threading.Lock()
        self.stream_thread = None
        self.is_streaming = False
        self.chunk_duration = 2

    def append_audio_data(self, audio_data, sample_rate):
        with self.lock:
            if self.sample_rate is None:
                self.sample_rate = sample_rate
            elif self.sample_rate != sample_rate:
                print(f"[A2FClient] Warning: Sample rate changed from {self.sample_rate} to {sample_rate}")
                self.sample_rate = sample_rate

            self.accumulated_audio += audio_data

        if not self.is_streaming:
            self.start_streaming()

    def start_streaming(self):
        if self.is_streaming:
            return
        self.is_streaming = True
        self.stream_thread = threading.Thread(target=self.stream_audio)
        self.stream_thread.start()

    def stream_audio(self):
        def generate_audio_chunks():
            start_marker = audio2face_pb2.PushAudioRequestStart(
                samplerate=self.sample_rate,
                instance_name=self.instance_name,
                block_until_playback_is_finished=False,
            )
            yield audio2face_pb2.PushAudioStreamRequest(start_marker=start_marker)

            while self.is_streaming:
                with self.lock:
                    chunk_size = int(self.sample_rate * 2 * self.chunk_duration)
                    if len(self.accumulated_audio) >= chunk_size:
                        audio_chunk = self.accumulated_audio[:chunk_size]
                        self.accumulated_audio = self.accumulated_audio[chunk_size:]
                    else:
                        audio_chunk = None

                if audio_chunk:
                    audio_np = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    yield audio2face_pb2.PushAudioStreamRequest(audio_data=audio_np.tobytes())
                    time.sleep(self.chunk_duration - 1)
                else:
                    time.sleep(.01)

        try:
            response = self.stub.PushAudioStream(generate_audio_chunks())
            if response.success:
                print("[A2FClient] Audio stream completed successfully")
            else:
                print(f"[A2FClient] Error in audio stream: {response.message}")
        except Exception as e:
            print(f"[A2FClient] Error during audio streaming: {e}")

    def stop_streaming(self):
        self.is_streaming = False
        if self.stream_thread:
            self.stream_thread.join()

HOST = 'localhost'
PORT = 65432

a2f_client = A2FClient("localhost:50051", "/World/LazyGraph/PlayerStreaming")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print(f"[Audio2Face Socket Server] Waiting for a connection on {HOST}:{PORT}")
    conn, addr = s.accept()
    print(f"[Audio2Face Socket Server] Connected by {addr}")
    
    try:
        while True:
            message_length_data = conn.recv(4)
            if not message_length_data:
                print("[Audio2Face Socket Server] Client disconnected.")
                break
            message_length = struct.unpack('>i', message_length_data)[0]

            print(f"[Audio2Face Socket Server] Receiving message of length: {message_length}")

            data = b''
            while len(data) < message_length:
                packet = conn.recv(message_length - len(data))
                if not packet:
                    print("[Audio2Face Socket Server] Incomplete message received.")
                    break
                data += packet

            if len(data) != message_length:
                print(f"[Audio2Face Socket Server] Received incomplete message! Expected {message_length} bytes, got {len(data)}.")
                continue

            sample_rate_bytes, audio_data = data.split(b'|', 1)
            sample_rate = struct.unpack('>i', sample_rate_bytes)[0]

            print(f"[Audio2Face Socket Server] Received audio data: length={len(audio_data)}, sample_rate={sample_rate}")

            a2f_client.append_audio_data(audio_data, sample_rate)

    except Exception as e:
        print(f"[Audio2Face Socket Server] Error receiving audio data: {e}")
    finally:
        a2f_client.stop_streaming()

    print("[Audio2Face Socket Server] Closing the connection.")