# --------------------------------------------------------------------------------------------------
# Audio2Face Socket Server
# --------------------------------------------------------------------------------------------------

import grpc, struct, socket, threading, time
import audio2face_pb2, audio2face_pb2_grpc
import numpy as np
from pydub import AudioSegment

def log(text: str, warning: bool = False, source: str = 'A2FClient'):                           
    print(f"[{source}] {'[Warning]' if warning else ''} {text}") 

# --------------------------------------------------------------------------------------------------
# Audio2Face Client for streaming audio data recieved from the audio socket server
# to the streaming audio player in Audio2Face
# --------------------------------------------------------------------------------------------------

class A2FClient:
    '''
    A client for streaming audio data to the Audio2Face server.
    '''
    def __init__(self, url, instanceName):
        '''
        Initializes the client with the given server URL and instance name.

        Args:
            url (str): The URL of the Audio2Face server
            instanceName (str): The name of Audio2Face instance to stream audio to
        '''
        self.url = url
        self.instanceName = instanceName
        self.channel = grpc.insecure_channel(url)
        self.stub = audio2face_pb2_grpc.Audio2FaceStub(self.channel)
        self.channels = 1
        self.sampleWidth = 2 
        self.accAud = bytearray() # using bytearray to avoid memory fragmentation
        self.sampleRate = None
        self.lock = threading.Lock()
        self.streamThread = None
        self.isStreaming = False
        self.chunkDuration = .3
        self.stopEvent = threading.Event()

    def appendAudData(self, audData, sampleRate):
        '''
        Appends audio data to the accumulated audio buffer and starts streaming if not already streaming.

        Args:
            audData (bytes): The audio data to append
            sampleRate (int): The sample rate of the audio data, 44100 Hz in our case
        '''
        with self.lock:
            if self.sampleRate is None:
                self.sampleRate = sampleRate
            elif self.sampleRate != sampleRate:
                log(f'Sample rate changed from {self.sampleRate} to {sampleRate}', warning=True)
                self.sampleRate = sampleRate

            audSegment = AudioSegment(
                data=audData,
                sample_width=self.sampleWidth,
                frame_rate=sampleRate,
                channels=self.channels
            )
            audSegment = audSegment.fade_in(25).fade_out(25) # fade in and out 
            self.accAud += audSegment.raw_data               # to avoid clicks between chunks

        if not self.isStreaming:
            self.startStreaming()

    def startStreaming(self):
        '''
        Starts the audio streaming thread.        
        '''
        if self.isStreaming: 
            return
        self.isStreaming = True
        self.stopEvent.clear()
        self.streamThread = threading.Thread(target=self.streamAud)
        self.streamThread.start()

    def streamAud(self):
        '''
        Streams audio data to the Audio2Face server in chunks.

        yields:
            audio2face_pb2.PushAudioStreamRequest: The audio stream request        
        '''
        def generateAudChunks():
            '''
            To yield audio chunks to the server.            
            '''
            startMarker = audio2face_pb2.PushAudioRequestStart(
                samplerate=self.sampleRate,
                instance_name=self.instanceName,
                block_until_playback_is_finished=False,
            )
            yield audio2face_pb2.PushAudioStreamRequest(start_marker=startMarker)           

            while not self.stopEvent.is_set():
                with self.lock:
                    chunkSize = int(self.sampleRate * 2 * self.chunkDuration) # 2 bytes per sample
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

            yield audio2face_pb2.PushAudioStreamRequest(audio_data=b'') # end marker

        try:
            response = self.stub.PushAudioStream(generateAudChunks())
            if response.success:
                log('Audio stream completed successfully')
            else:
                log(f'Error in audio stream: {response.message}', warning=True)
        except Exception as e:
            log(f'Error during audio streaming: {e}', warning=True)
        finally:
            self.isStreaming = False

    def stopStreaming(self):
        '''
        Stops the audio streaming thread and clears the accumulated audio buffer.
        '''
        if not self.isStreaming:
            return

        log('Stopping audio stream...')
        self.stopEvent.set()
        self.isStreaming = False  
        
        if self.streamThread:
            self.streamThread.join(timeout=0)  
            if self.streamThread.is_alive():
                log('Stream thread did not stop in time', warning=True)
        
        self.accAud.clear()
        log('Audio stream stopped')

# --------------------------------------------------------------------------------------------------
# Main function calls for the Audio2Face socket server
# --------------------------------------------------------------------------------------------------

HOST = 'localhost'
AUD_PORT = 65432 # audio socket port from the backend
CNTRL_PORT = 65433 # control socket port from the backend
BUFFER_SIZE = 4194304  # 4MB

socketServerSource = 'Audio2Face Socket Server'

def runA2FServer(stopEvent):
    '''
    Main function to run the Audio2Face socket server.

    Args:
        stopEvent (threading.Event): The event to stop the server
    '''
    a2fClient = A2FClient('localhost:50051', '/World/LazyGraph/PlayerStreaming')
    
    audSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    audSocket.bind((HOST, AUD_PORT))
    audSocket.listen(1)
    audSocket.settimeout(1)
    log(f'Waiting for an audio connection on {HOST}:{AUD_PORT}', source=socketServerSource)

    cntrlSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cntrlSocket.bind((HOST, CNTRL_PORT))
    cntrlSocket.listen(1)
    cntrlSocket.settimeout(1)
    log(f'Waiting for a control connection on {HOST}:{CNTRL_PORT}', source=socketServerSource)

    audThread = threading.Thread(target=handleAudioSocket, args=(audSocket, a2fClient, stopEvent))
    cntrlThread = threading.Thread(target=handleCntrlSocket, args=(cntrlSocket, a2fClient, stopEvent))
    
    try:
        audThread.start()
        cntrlThread.start()

        while not stopEvent.is_set():
            time.sleep(0.1)

    except Exception as e:
        log(f'Error in main server loop: {e}', warning=True, source=socketServerSource)

    finally:
        log('Stopping server...', source=socketServerSource)
        
        if a2fClient.isStreaming:
            a2fClient.stopStreaming()

        stopEvent.set()

        audThread.join(timeout=-0)
        cntrlThread.join(timeout=0)

        audSocket.close()
        cntrlSocket.close()

        log('Server stopped', source=socketServerSource)

def handleCntrlSocket(cntrlSocket, a2fClient, stopEvent):
    '''
    Handles the control socket connection.

    Args:
        cntrlSocket (socket.socket): The control socket meant for stopping the audio stream
        a2fClient (A2FClient): The Audio2Face client defined above
        stopEvent (threading.Event): The event to stop the server
    '''
    while not stopEvent.is_set():
        try:
            conn, addr = cntrlSocket.accept()
            log(f'Control connection established with {addr}', source=socketServerSource)
            cntrlThread = threading.Thread(target=handleCntrlClient, args=(conn, a2fClient, stopEvent))
            cntrlThread.start()
        except socket.timeout:
            continue
        except Exception as e:
            log(f'Control socket error: {e}', warning=True, source=socketServerSource)
            break

def handleAudioSocket(audSocket, a2fClient, stopEvent):
    '''
    Handles the audio socket connection.

    Args:
        audSocket (socket.socket): The audio socket meant for streaming audio data
        a2fClient (A2FClient): The Audio2Face client defined above
        stopEvent (threading.Event): The event to stop the server
    '''
    while not stopEvent.is_set(): # loops until stopEvent is set
        try:
            conn, addr = audSocket.accept()
            log(f'Audio connection established with {addr}', source=socketServerSource)
            clientThread = threading.Thread(target=handleAudClient, args=(conn, a2fClient, stopEvent))
            clientThread.start()
        except socket.timeout:
            continue
        except Exception as e:
            log(f'Audio socket error: {e}', warning=True, source=socketServerSource)
            break

def handleCntrlClient(conn, a2fClient, stopEvent):
    '''
    Handles comms with the control client.

    Args:
        conn (socket.socket): The control socket connection
        a2fClient (A2FClient): The Audio2Face client defined above
        stopEvent (threading.Event): The event to stop the server
    '''
    try:
        while not stopEvent.is_set():
            data = conn.recv(4)
            if not data:
                break
            if data == b'stop': # hax
                log('Received stop command', source=socketServerSource)
                if a2fClient.isStreaming:
                    a2fClient.stopStreaming()
                conn.sendall(b'stopped') 
    except Exception as e:
        log(f'Control client error: {e}', warning=True, source=socketServerSource)

def handleAudClient(conn, a2fClient, stopEvent):
    '''
    Handles comms with the audio client.

    Args:
        conn (socket.socket): The audio socket connection
        a2fClient (A2FClient): The Audio2Face client defined above
        stopEvent (threading.Event): The event to stop the server
    '''
    try:
        while not stopEvent.is_set():
            msgLenData = conn.recv(4) # read message length
            if not msgLenData:
                log('Client disconnected', source=socketServerSource)
                break
            msgLen = struct.unpack('>i', msgLenData)[0] # using struct to unpack bytes to int

            log(f'Receiving message of length: {msgLen}', source=socketServerSource)

            data = bytearray()
            bytesRec = 0
            while bytesRec < msgLen:
                chunk = conn.recv(min(BUFFER_SIZE, msgLen - bytesRec)) # read data in chunks
                if not chunk:
                    log('Connection closed before receiving complete message', source=socketServerSource)
                    return
                data.extend(chunk)
                bytesRec += len(chunk)

            if bytesRec != msgLen:
                log(f'Received incomplete message! Expected {msgLen} bytes, got {bytesRec}', warning=True, source=socketServerSource)
                continue

            srBytes, audData = data.split(b'|', 1) # split audio data from sample rate
            sr = struct.unpack('>i', srBytes)[0]

            log(f'Received audio data: length={len(audData)}, sr={sr}', source=socketServerSource)

            a2fClient.appendAudData(audData, sr)

    except Exception as e:
        log(f'Error receiving audio data: {e}', warning=True, source=socketServerSource)
    finally:
        conn.close()

def startA2FServer():
    '''
    Meant to start the Audio2Face server in a separate thread.
    '''
    stopEvent = threading.Event()
    serverThread = threading.Thread(target=runA2FServer, args=(stopEvent,))
    serverThread.start()
    return stopEvent, serverThread

def stopA2FServer(stopEvent, serverThread):
    '''
    Stops the Audio2Face server.
    '''
    stopEvent.set()
    serverThread.join(timeout=5) 
    if serverThread.is_alive():
        log('Server thread did not stop in time. Forcing shutdown.', warning=True, source=socketServerSource)