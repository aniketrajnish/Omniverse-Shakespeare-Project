import grpc, struct, socket, threading, time
import audio2face_pb2, audio2face_pb2_grpc
import numpy as np
from pydub import AudioSegment

class A2FClient:
    def __init__(self, url, instanceName):
        self.url = url
        self.instanceName = instanceName
        self.channel = grpc.insecure_channel(url)
        self.stub = audio2face_pb2_grpc.Audio2FaceStub(self.channel)
        self.channels = 1
        self.sampleWidth = 2 
        self.accAud = bytearray()
        self.sampleRate = None
        self.lock = threading.Lock()
        self.streamThread = None
        self.isStreaming = False
        self.chunkDuration = .3

    def appendAudData(self, audData, sampleRate):
        with self.lock:
            if self.sampleRate is None:
                self.sampleRate = sampleRate
            elif self.sampleRate != sampleRate:
                print(f"[A2FClient] Warning: Sample rate changed from {self.sampleRate} to {sampleRate}")
                self.sampleRate = sampleRate

            audSegment = AudioSegment(
                data=audData,
                sample_width=self.sampleWidth,
                frame_rate=sampleRate,
                channels=self.channels
            )
            audSegment = audSegment.fade_in(25).fade_out(25)
            self.accAud += audSegment.raw_data            

        if not self.isStreaming:
            self.startStreaming()

    def startStreaming(self):
        if self.isStreaming:
            return
        self.isStreaming = True
        self.streamThread = threading.Thread(target=self.streamAud)
        self.streamThread.start()

    def streamAud(self):
        def generateAudChunks():
            startMarker = audio2face_pb2.PushAudioRequestStart(
                samplerate=self.sampleRate,
                instance_name=self.instanceName,
                block_until_playback_is_finished=False,
            )
            yield audio2face_pb2.PushAudioStreamRequest(start_marker=startMarker)           

            while self.isStreaming:
                with self.lock:
                    chunkSize = int(self.sampleRate * 2 * self.chunkDuration)
                    if len(self.accAud) >= chunkSize:
                        audChunk = self.accAud[:chunkSize]
                        self.accAud = self.accAud[chunkSize:]
                    else:
                        audChunk = None

                if audChunk:
                    audNp = np.frombuffer(audChunk, dtype=np.int16).astype(np.float32) / 32768.0
                    yield audio2face_pb2.PushAudioStreamRequest(audio_data=audNp.tobytes())
                    time.sleep(self.chunkDuration - .1)
                else:
                    time.sleep(.01)

        try:
            response = self.stub.PushAudioStream(generateAudChunks())
            if response.success:
                print("[A2FClient] Audio stream completed successfully")
            else:
                print(f"[A2FClient] Error in audio stream: {response.message}")
        except Exception as e:
            print(f"[A2FClient] Error during audio streaming: {e}")

    def stopStreaming(self):
        self.isStreaming = False
        if self.streamThread:
            self.streamThread.join()

HOST = 'localhost'
AUD_PORT = 65432
CNTRL_PORT = 65433
BUFFER_SIZE = 4194304  # 4MB

def runA2FServer(stopEvent):
    a2fClient = A2FClient("localhost:50051", "/World/LazyGraph/PlayerStreaming")
    
    audSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    audSocket.bind((HOST, AUD_PORT))
    audSocket.listen(1)
    audSocket.settimeout(1)
    print(f"[Audio2Face Socket Server] Waiting for an audio connection on {HOST}:{AUD_PORT}")

    cntrlSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cntrlSocket.bind((HOST, CNTRL_PORT))
    cntrlSocket.listen(1)
    cntrlSocket.settimeout(1)
    print(f"[Audio2Face Socket Server] Waiting for a control connection on {HOST}:{CNTRL_PORT}")

    audThread = threading.Thread(target=handleAudioSocket, args=(audSocket, a2fClient, stopEvent))
    cntrlThread = threading.Thread(target=handleCntrlSocket, args=(cntrlSocket, a2fClient, stopEvent))
    
    audThread.start()
    cntrlThread.start()

    audThread.join()
    cntrlThread.join()

    if a2fClient.isStreaming:
        a2fClient.stopStreaming()

    audSocket.close()
    cntrlSocket.close()
    print("[Audio2Face Socket Server] Server stopped.")

def handleAudioSocket(audSocket, a2fClient, stopEvent):
    while not stopEvent.is_set():
        try:
            conn, addr = audSocket.accept()
            print(f"[Audio2Face Socket Server] Audio connection established with {addr}")
            clientThread = threading.Thread(target=handleAudClient, args=(conn, a2fClient, stopEvent))
            clientThread.start()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[Audio2Face Socket Server] Audio socket error: {e}")
            break

def handleCntrlSocket(cntrlSocket, a2fClient, stopEvent):
    while not stopEvent.is_set():
        try:
            conn, addr = cntrlSocket.accept()
            print(f"[Audio2Face Socket Server] Control connection established with {addr}")
            cntrlThread = threading.Thread(target=handleCntrlClient, args=(conn, a2fClient, stopEvent))
            cntrlThread.start()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[Audio2Face Socket Server] Control socket error: {e}")
            break

def handleCntrlClient(conn, a2fClient, stopEvent):
    try:
        while not stopEvent.is_set():
            data = conn.recv(4)
            if not data:
                break
            if data == b'stop':
                print("[Audio2Face Socket Server] Received stop command")
                if a2fClient.isStreaming:
                    a2fClient.stopStreaming()
                    a2fClient = A2FClient("localhost:50051", "/World/LazyGraph/PlayerStreaming")
    except Exception as e:
        print(f"[Audio2Face Socket Server] Control client error: {e}")
    finally:
        conn.close()

def handleAudClient(conn, a2fClient, stopEvent):
    try:
        while not stopEvent.is_set():
            msgLenData = conn.recv(4)
            if not msgLenData:
                print("[Audio2Face Socket Server] Client disconnected.")
                break
            msgLen = struct.unpack('>i', msgLenData)[0]

            print(f"[Audio2Face Socket Server] Receiving message of length: {msgLen}")

            data = bytearray()
            bytesRec = 0
            while bytesRec < msgLen:
                chunk = conn.recv(min(BUFFER_SIZE, msgLen - bytesRec))
                if not chunk:
                    print("[Audio2Face Socket Server] Connection closed before receiving complete message.")
                    return
                data.extend(chunk)
                bytesRec += len(chunk)

            if bytesRec != msgLen:
                print(f"[Audio2Face Socket Server] Received incomplete message! Expected {msgLen} bytes, got {bytesRec}.")
                continue

            srBytes, audData = data.split(b'|', 1)
            sr = struct.unpack('>i', srBytes)[0]

            print(f"[Audio2Face Socket Server] Received audio data: length={len(audData)}, sr={sr}")

            a2fClient.appendAudData(audData, sr)

    except Exception as e:
        print(f"[Audio2Face Socket Server] Error receiving audio data: {e}")
    finally:
        conn.close()

def startA2FServer():
    stopEvent = threading.Event()
    serverThread = threading.Thread(target=runA2FServer, args=(stopEvent,))
    serverThread.start()
    return stopEvent, serverThread

def stopA2FServer(stopEvent, serverThread):
    stopEvent.set()
    serverThread.join(timeout=5) 
    if serverThread.is_alive():
        print("[Audio2Face Socket Server] Server thread did not stop in time. Forcing shutdown.")