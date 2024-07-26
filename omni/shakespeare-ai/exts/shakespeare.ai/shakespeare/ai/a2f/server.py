import grpc, struct, socket, threading, time
import audio2face_pb2, audio2face_pb2_grpc
import numpy as np
from pydub import AudioSegment

class A2FClient:
    def __init__(self, url, instance_name):
        self.url = url
        self.instance_name = instance_name
        self.channel = grpc.insecure_channel(url)
        self.stub = audio2face_pb2_grpc.Audio2FaceStub(self.channel)
        self.channels = 1
        self.sample_width = 2 
        self.accumulated_audio = bytearray()
        self.sample_rate = None
        self.lock = threading.Lock()
        self.stream_thread = None
        self.is_streaming = False
        self.chunk_duration = .3
        self.total_duration = 0

    def append_audio_data(self, audio_data, sample_rate):
        with self.lock:
            if self.sample_rate is None:
                self.sample_rate = sample_rate
            elif self.sample_rate != sample_rate:
                print(f"[A2FClient] Warning: Sample rate changed from {self.sample_rate} to {sample_rate}")
                self.sample_rate = sample_rate

            audio_segment = AudioSegment(
                data=audio_data,
                sample_width=self.sample_width,
                frame_rate=sample_rate,
                channels=self.channels
            )
            audio_segment = audio_segment.fade_in(25).fade_out(25)
            self.accumulated_audio += audio_segment.raw_data            

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
                    time.sleep(.2)
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
BUFFER_SIZE = 4194304  # 4MB

def run_audio2face_server(stop_event):
    a2f_client = A2FClient("localhost:50051", "/World/LazyGraph/PlayerStreaming")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        s.settimeout(1)  # Set a timeout for the accept() call
        print(f"[Audio2Face Socket Server] Waiting for a connection on {HOST}:{PORT}")

        while not stop_event.is_set():
            try:
                conn, addr = s.accept()
                print(f"[Audio2Face Socket Server] Connected by {addr}")
                client_thread = threading.Thread(target=handle_client, args=(conn, a2f_client, stop_event))
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[Audio2Face Socket Server] Error: {e}")
                break

    # Stop the A2FClient
    if a2f_client.is_streaming:
        a2f_client.stop_streaming()

    print("[Audio2Face Socket Server] Server stopped.")

def handle_client(conn, a2f_client, stop_event):
    try:
        while not stop_event.is_set():
            message_length_data = conn.recv(4)
            if not message_length_data:
                print("[Audio2Face Socket Server] Client disconnected.")
                break
            message_length = struct.unpack('>i', message_length_data)[0]

            print(f"[Audio2Face Socket Server] Receiving message of length: {message_length}")

            data = bytearray()
            bytes_received = 0
            while bytes_received < message_length:
                chunk = conn.recv(min(BUFFER_SIZE, message_length - bytes_received))
                if not chunk:
                    print("[Audio2Face Socket Server] Connection closed before receiving complete message.")
                    return
                data.extend(chunk)
                bytes_received += len(chunk)

            if bytes_received != message_length:
                print(f"[Audio2Face Socket Server] Received incomplete message! Expected {message_length} bytes, got {bytes_received}.")
                continue

            sample_rate_bytes, audio_data = data.split(b'|', 1)
            sample_rate = struct.unpack('>i', sample_rate_bytes)[0]

            print(f"[Audio2Face Socket Server] Received audio data: length={len(audio_data)}, sample_rate={sample_rate}")

            a2f_client.append_audio_data(audio_data, sample_rate)

    except Exception as e:
        print(f"[Audio2Face Socket Server] Error receiving audio data: {e}")
    finally:
        conn.close()

# This function can be called from the UI module to start the server
def start_audio2face_server():
    stop_event = threading.Event()
    server_thread = threading.Thread(target=run_audio2face_server, args=(stop_event,))
    server_thread.start()
    return stop_event, server_thread

# This function can be called from the UI module to stop the server
def stop_audio2face_server(stop_event, server_thread):
    stop_event.set()
    server_thread.join(timeout=5)  # Wait for up to 5 seconds
    if server_thread.is_alive():
        print("[Audio2Face Socket Server] Server thread did not stop in time. Forcing shutdown.")

if __name__ == "__main__":
    # This is just for testing the server independently
    stop_event, server_thread = start_audio2face_server()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping server...")
        stop_audio2face_server(stop_event, server_thread)