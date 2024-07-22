import grpc
import audio2face_pb2
import audio2face_pb2_grpc
import numpy as np
import io
import wave

class A2FClient:
    def __init__(self, url, instance_name):
        self.url = url
        self.instance_name = instance_name
        self.channel = grpc.insecure_channel(url)
        self.stub = audio2face_pb2_grpc.Audio2FaceStub(self.channel)
        self.channels = 1
        self.sample_width = 4  # 4 bytes for float32

    def push_audio_track(self, audio_data, sample_rate):
        """
        This function pushes the whole audio track at once via PushAudioRequest()
        """
        try:
            # Convert to float32 and normalize
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(self.sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_np.tobytes())

            # Get the WAV data
            wav_data = wav_buffer.getvalue()

            request = audio2face_pb2.PushAudioRequest()
            request.audio_data = wav_data
            request.samplerate = sample_rate
            request.instance_name = self.instance_name
            request.block_until_playback_is_finished = False  # Set to True if you want to block until playback is finished

            print(f"[A2FClient] Sending audio data: length={len(wav_data)}, sample_rate={sample_rate}")
            response = self.stub.PushAudio(request)
            
            if response.success:
                print("[A2FClient] Audio sent successfully")
            else:
                print(f"[A2FClient] Error sending audio: {response.message}")
        
        except Exception as e:
            print(f"[A2FClient] Error during audio sending: {e}")

# Main loop
import socket
import struct

HOST = 'localhost'
PORT = 65432

a2f_client = A2FClient("localhost:50051", "/World/LazyGraph/PlayerStreaming")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print(f"[Audio2Face Socket Server] Waiting for a connection on {HOST}:{PORT}")
    conn, addr = s.accept()
    print(f"[Audio2Face Socket Server] Connected by {addr}")
    
    while True:
        try:
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

            a2f_client.push_audio_track(audio_data, sample_rate)

        except Exception as e:
            print(f"[Audio2Face Socket Server] Error receiving audio data: {e}")
            break

    print("[Audio2Face Socket Server] Closing the connection.")