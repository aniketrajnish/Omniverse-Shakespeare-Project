import threading
from queue import Queue
from pydub import AudioSegment, playback
from io import BytesIO

class LocalAudioPlayer:
    def __init__(self):
        self.audioQueue = Queue()
        self.playThread = None
        self.isPlaying = False
        self.currentAudio = None

    def start(self):
        if not self.playThread or not self.playThread.is_alive():
            self.isPlaying = True
            self.playThread = threading.Thread(target=self._playAudioLoop)
            self.playThread.daemon = True
            self.playThread.start()

    def addAudio(self, audioData: bytes, sampleRate: int):
        audio = AudioSegment(
            audioData,
            sample_width=2,
            channels=1,
            frame_rate=sampleRate
        )
        audio = audio.fade_in(25).fade_out(25)
        self.audioQueue.put(audio)
        
        if not self.isPlaying:
            self.start()

    def _playAudioLoop(self):
        while self.isPlaying:
            try:
                if self.currentAudio is None:
                    self.currentAudio = self.audioQueue.get(timeout=1)
                
                if self.currentAudio:
                    playback.play(self.currentAudio)
                    self.currentAudio = None
                
            except Queue.empty:
                continue
            except Exception as e:
                print(f"Error playing audio: {e}")