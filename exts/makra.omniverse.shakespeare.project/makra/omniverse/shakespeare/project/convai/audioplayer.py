import pyaudio
from pydub import AudioSegment
import io

class ConvaiAudioPlayer:
    def __init__(self, startTalkingCallback, stopTalkingCallback):
        self.startTalkingCallback = startTalkingCallback
        self.stopTalkingCallback = stopTalkingCallback
        self.audSegment = None
        self.pa = pyaudio.PyAudio()
        self.paStream = None
        self.isPlaying = False
    
    def appendToStream(self, data: bytes):
        segment = AudioSegment.from_wav(io.BytesIO(data)).fade_in(100).fade_out(100)
        if self.audSegment is None:
            self.audSegment = segment
        else:
            self.audSegment._data += segment._data
        self.play()

    def play(self):    
        if self.isPlaying:
            return
        print("ConvaiAudioPlayer - Started playing")
        self.startTalkingCallback()
        self.paStream = self.pa.open(
            format=pyaudio.get_format_from_width(self.audSegment.sample_width),
            channels=self.audSegment.channels,
            rate=self.audSegment.frame_rate,
            output=True, 
            stream_callback=self.streamCallback
        )
        self.isPlaying = True

    def pause(self):
        '''
        Pause playing
        '''
        self.isPlaying = False
    
    def stop(self):
        '''
        Pause playing and clear audio
        '''
        self.pause()
        self.audSegment = None

    def streamCallback(self, inData, frameCount, timeInfo, statusFlags):
        if not self.isPlaying:
            frames = bytes()
        else:
            frames = self.consumeFrames(frameCount)
        
        if self.audSegment and len(frames) < frameCount*self.audSegment.frame_width:
            print("ConvaiAudioPlayer - Stopped playing")
            self.stopTalkingCallback()
            self.isPlaying = False
            return frames, pyaudio.paComplete
        else:
            return frames, pyaudio.paContinue
        
    def consumeFrames(self, count: int):
        if self.audSegment is None:
            return bytes()
        
        frameEnd = self.audSegment.frame_width*count
        if frameEnd > len(self.audSegment._data):
            return bytes()

            
        framesToReturn = self.audSegment._data[0:frameEnd]
        if frameEnd == len(self.audSegment._data):
            self.audSegment._data = bytes()
        else:
            self.audSegment._data = self.audSegment._data[frameEnd:]

        return framesToReturn

if __name__ == '__main__':
    import time
    import pyaudio
    import grpc
    from rpc import service_pb2 as convaiServiceMsg
    from rpc import service_pb2_grpc as convaiService
    from typing import Generator
    import io
    from pydub import AudioSegment
    import configparser

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    RECORD_SECONDS = 3

    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    convaiAudPlayer = ConvaiAudioPlayer(None)

    def startMic():
        global stream
        stream = PyAudio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        print("startMic - Started Recording")

    def stopMic():
        global stream
        if stream:
            stream.stop_stream()
            stream.close()
        else:
            print("stopMic - could not close mic stream since it is None")
            return
        print("stopMic - Stopped Recording")

    def getGetResponseRequests(apiKey: str, charId: str, sessionId: str = "") -> Generator[convaiServiceMsg.GetResponseRequest, None, None]:
        action_config = convaiServiceMsg.ActionConfig(
            classification = 'multistep',
            context_level = 1
        )
        action_config.actions[:] = ["fetch", "jump", "dance", "swim"]
        action_config.objects.append(
            convaiServiceMsg.ActionConfig.Object(
                name = "ball",
                description = "A round object that can bounce around."
            )
        )
        action_config.objects.append(
            convaiServiceMsg.ActionConfig.Object(
                name = "water",
                description = "Liquid found in oceans, seas and rivers that you can swim in. You can also drink it."
            )
        )
        action_config.characters.append(
            convaiServiceMsg.ActionConfig.Character(
                name = "User",
                bio = "Person playing the game and asking questions."
            )
        )
        action_config.characters.append(
            convaiServiceMsg.ActionConfig.Character(
                name = "Learno",
                bio = "A medieval farmer from a small village."
            )
        )
        get_response_config = convaiServiceMsg.GetResponseRequest.GetResponseConfig(
                character_id = charId,
                api_key = apiKey,
                audio_config = convaiServiceMsg.AudioConfig(
                    sample_rate_hertz = 16000
                ),
                action_config = action_config
            )
        
        if sessionId != "":
            get_response_config.session_id = sessionId
        yield convaiServiceMsg.GetResponseRequest(
            get_response_config = get_response_config    
        )
        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            yield convaiServiceMsg.GetResponseRequest(
                get_response_data = convaiServiceMsg.GetResponseRequest.GetResponseData(
                    audio_data = data
                )
            )
        stream.stop_stream()
        stream.close()
        print("* recording stopped")

    config = configparser.ConfigParser()
    config.read("exts\convai\convai\convai.env")
    apiKey = config.get("CONVAI", "API_KEY")
    charId = config.get("CONVAI", "CHARACTER_ID")
    channelAddress = config.get("CONVAI", "CHANNEL")

    channel = grpc.secure_channel(channelAddress, grpc.ssl_channel_credentials())
    client = convaiService.ConvaiServiceStub(channel)
    for response in client.GetResponse(getGetResponseRequests(apiKey, charId)):
        if response.HasField("audio_response"):
            print("Stream Message: {} {} {}".format(response.session_id, response.audio_response.audio_config, response.audio_response.text_data))
            convaiAudPlayer.appendToStream(response.audio_response.audio_data)

        else:
            print("Stream Message: {}".format(response))
    p.terminate()

    time.sleep(10)