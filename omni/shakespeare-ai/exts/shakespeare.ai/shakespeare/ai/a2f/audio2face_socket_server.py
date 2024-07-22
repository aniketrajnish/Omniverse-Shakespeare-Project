import socket, audio2face_pb2, audio2face_pb2_grpc, grpc
import numpy as np

class A2FClient:
    def __init__(self, url, instance_name):
        self.url = url
        self.instance_name = instance_name
        self.channel = grpc.insecure_channel(url)
        self.stub = audio2face_pb2_grpc.Audio2FaceStub(self.channel)
        self.is_streaming = False

    def push_audio_stream(self, audio_data, samplerate):
        if self.is_streaming:
            return
        
        self.is_streaming = True
        chunk_size = samplerate // 10
        block_until_playback_is_finished = True

        def make_generator():
            start_marker = audio2face_pb2.PushAudioRequestStart(
                samplerate=samplerate,
                instance_name=self.instance_name,
                block_until_playback_is_finished=block_until_playback_is_finished,
            )

            yield audio2face_pb2.PushAudioStreamRequest(start_marker=start_marker)

            for i in range(len(audio_data) // chunk_size + 1):
                chunk = audio_data[i * chunk_size : (i + 1) * chunk_size]
                yield audio2face_pb2.PushAudioStreamRequest(
                    audio_data=chunk.astype(np.float32).tobytes()
                )

        request_generator = make_generator()
        response = self.stub.PushAudioStream(request_generator)

        if response.success:
            print(f"[Audio2FaceClient] Audio streamed successfully.")
        else:
            print(f"[Audio2FaceClient] Error streaming audio: {response.message}")

        self.is_streaming = False 

def log(message, warning=False):
    print(f"[Audio2Face Socket Server] {'[Warning]' if warning else ''} {message}")

HOST = 'localhost'  
PORT = 65432        

a2f_client = A2FClient("localhost:50051", "/World/LazyGraph/PlayerStreaming")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    conn, addr = s.accept()
    log(f"Connected by {addr}")
    while True:
        try:
            data = conn.recv(4096 * 2)  # Adjust buffer size if needed
            if not data:
                break

            samplerate = int.from_bytes(data[:4], 'big')
            audio_data = np.frombuffer(data[4:], dtype=np.float32)

            # Stream received audio to Audio2Face
            a2f_client.push_audio_stream(audio_data, samplerate) 

        except Exception as e:
            log(f"Error receiving audio data: {e}", warning=True)
            break  