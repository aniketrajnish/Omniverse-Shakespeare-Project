from pydub import AudioSegment
from pydub.playback import play as pydub_play
import io
import threading

class LocalAudioPlayer:
    def __init__(self, startTalkingCallback, stopTalkingCallback):
        self.startTalkingCallback = startTalkingCallback
        self.stopTalkingCallback = stopTalkingCallback
        self.audSegment = None
        self.isPlaying = False
        self.playbackThread = None
    
    def appendToStream(self, data: bytes):
        segment = AudioSegment.from_wav(io.BytesIO(data)).fade_in(25).fade_out(25)
        if self.audSegment is None:
            self.audSegment = segment
        else:
            self.audSegment = self.audSegment + segment
        self.play()

    def play(self):    
        if self.isPlaying:
            return
        print("LocalAudioPlayer - Started playing")
        self.startTalkingCallback()
        self.isPlaying = True
        if self.playbackThread is None or not self.playbackThread.is_alive():
            self.playbackThread = threading.Thread(target=self._play_audio)
            self.playbackThread.start()

    def _play_audio(self):
        while self.isPlaying and self.audSegment:
            segment_to_play = self.audSegment
            self.audSegment = None
            pydub_play(segment_to_play)
            if not self.audSegment:
                self.isPlaying = False
                self.stopTalkingCallback()
                print("LocalAudioPlayer - Stopped playing")

    def pause(self):
        self.isPlaying = False
    
    def stop(self):
        self.isPlaying = False
        self.audSegment = None
        if self.playbackThread:
            self.playbackThread.join()
        self.playbackThread = None
        self.stopTalkingCallback()