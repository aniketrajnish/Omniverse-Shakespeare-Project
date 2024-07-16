from PyQt5 import QtWidgets, QtGui, QtCore
from gemini import gemini
from convai import convai

class ShakespeareWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.convaiBackend = None
        self.initUI()     

    def initUI(self):
        self.initWindow()
        self.initLayouts()
        self.initComponents()

    def initWindow(self):
        self.setWindowTitle('Shakespeare AI')
        self.setWindowIcon(QtGui.QIcon('misc/logo.png'))
        self.setFixedSize(400, 400)
        self.show()

    def initLayouts(self):
        self.centralWidget = QtWidgets.QWidget()
        self.setCentralWidget(self.centralWidget)
        self.mainLayout = QtWidgets.QVBoxLayout(self.centralWidget)

        self.btnLayout = QtWidgets.QHBoxLayout()
        self.mainLayout.addLayout(self.btnLayout)

    def initComponents(self):
        self.initBtns()
        self.initImgHolder()
        self.initStatusBar()

    def initBtns(self):
        self.selectImgBtn = QtWidgets.QPushButton('Select Image')
        self.btnLayout.addWidget(self.selectImgBtn)
        self.selectImgBtn.clicked.connect(self.selectImg)

        self.convaiBtn = QtWidgets.QPushButton('Start Talking')
        self.btnLayout.addWidget(self.convaiBtn)
        self.convaiBtn.clicked.connect(self.onConvaiBtnClick)

    def initImgHolder(self):
        self.imgGb = QtWidgets.QGroupBox('Selected Image')
        self.imgGb.setLayout(QtWidgets.QVBoxLayout())

        self.imgLabel = QtWidgets.QLabel()
        self.imgLabel.setFixedSize(340, 300)
        self.imgLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.imgLabel.setScaledContents(False)

        self.imgGb.layout().addWidget(self.imgLabel)
        self.mainLayout.addWidget(self.imgGb)

    def initStatusBar(self):
        self.statusBar = QtWidgets.QStatusBar()  
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready", 5000) 

    def selectImg(self):
        fName, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select Image', '',
                                                      'Images (*.jpg *.jpeg *.png *.heic *.heif)')
        if fName:
            self.processImg(fName)

    def processImg(self, imgPath):
        pixmap = QtGui.QPixmap(imgPath)

        if not pixmap.isNull():
            pixmap = pixmap.scaled(self.imgLabel.size(), QtCore.Qt.KeepAspectRatio,
                                 QtCore.Qt.SmoothTransformation)
            self.imgLabel.setPixmap(pixmap)
            self.geminiResponse = gemini.getGeminiResponse(imgPath)
            self.showMsg('Talk to Shakespeare about this image!')
            convai.appendToCharBackstory(self.geminiResponse)

    def onConvaiBtnClick(self):
        if self.convaiBackend is None:
            self.convaiBackend = convai.ConvaiBackend.getInstance()
            self.connectEventsToConvai()

        if self.convaiBackend.isCapturingAudio:
            self.convaiBackend.stopConvai()
        else:
            self.convaiBackend.startConvai()

    def connectEventsToConvai(self):
        self.convaiBackend.updateBtnTextSignal.connect(self.convaiBtn.setText)
        self.convaiBackend.setBtnEnabledSignal.connect(self.convaiBtn.setEnabled) 
        self.convaiBackend.stateChangeSignal.connect(self.handleConvaiStateChange)
        self.convaiBackend.errorSignal.connect(self.showMsg)        

    def updateConvaiBtn(self, data):
        try:
            enabled = bool(data)
            self.convaiBtn.setEnabled(enabled)
        except ValueError:
            self.convaiBtn.setText(data)

    def handleConvaiStateChange(self, isTalking):
        if isTalking:
            self.statusBar.showMessage("Shakespeare started speaking!", 5000)
        else:
            self.convaiBtn.setText("Start Talking")
            self.convaiBtn.setEnabled(True)

    def showMsg(self, msg):
        self.statusBar.showMessage(msg, 50000) 