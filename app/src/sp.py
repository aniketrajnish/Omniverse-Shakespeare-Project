from PyQt5 import QtWidgets, QtGui, QtCore
from convai import convai
from gemini import gemini
import os, sys

class ShakespeareWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.convaiBackend = None
        self.initUI()     

    def initUI(self):
        self.initWindow()
        self.initLayouts()
        self.initComponents()
        self.applyOvStylesheet()

    def initWindow(self):
        self.setWindowTitle('Shakespeare AI')
        basePath = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        self.setWindowIcon(QtGui.QIcon(os.path.join(basePath, 'misc/sp_logo.png')))
        self.setFixedSize(400, 500)
        self.show()

    def initLayouts(self):
        self.centralWidget = QtWidgets.QWidget()
        self.setCentralWidget(self.centralWidget)
        self.mainLayout = QtWidgets.QVBoxLayout(self.centralWidget)

    def initComponents(self):
        self.initBtns()
        self.initImgHolder()
        self.initStatusBar()

    def initBtns(self):
        self.btnLayout = QtWidgets.QHBoxLayout()
        self.mainLayout.addLayout(self.btnLayout)

        self.selectImgBtn = QtWidgets.QPushButton('Select Image')
        self.btnLayout.addWidget(self.selectImgBtn)
        self.selectImgBtn.clicked.connect(self.selectImg)

        self.convaiBtn = QtWidgets.QPushButton('Start Talking')
        self.btnLayout.addWidget(self.convaiBtn)
        self.convaiBtn.clicked.connect(self.onConvaiBtnClick)

        self.stopBtnLayout = QtWidgets.QHBoxLayout()
        self.mainLayout.addLayout(self.stopBtnLayout)

        self.stopSpBtn = QtWidgets.QPushButton('Stop Shakespeare')
        self.stopBtnLayout.addWidget(self.stopSpBtn)
        self.stopSpBtn.clicked.connect(self.onStopSpBtnClick)
        self.stopSpBtn.setEnabled(False)  # Initially disabled

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

    def onStopSpBtnClick(self):
        if self.convaiBackend is not None:
            self.convaiBackend.sendStopSignalToA2F()

    def connectEventsToConvai(self):
        self.convaiBackend.updateBtnTextSignal.connect(self.convaiBtn.setText)
        self.convaiBackend.setBtnEnabledSignal.connect(self.convaiBtn.setEnabled) 
        self.convaiBackend.stateChangeSignal.connect(self.handleConvaiStateChange)
        self.convaiBackend.errorSignal.connect(self.showMsg)
        self.convaiBackend.isSendingAudSignal.connect(self.updateStopButtonState)

    def handleConvaiStateChange(self, isTalking):
        if isTalking:
            self.statusBar.showMessage("Shakespeare started speaking!", 5000)
        else:
            self.convaiBtn.setText("Start Talking")
            self.convaiBtn.setEnabled(True)

    def updateStopButtonState(self, isSendingAudio):
        self.stopSpBtn.setEnabled(isSendingAudio)

    def showMsg(self, msg):
        self.statusBar.showMessage(msg, 50000) 

    def applyOvStylesheet(self):
        # Define the stylesheet to mimic Omniverse's grey theme with white text
        stylesheet = """
        QMainWindow {
            background-color: #454444;
            color: white;
        }
        QPushButton {
            background-color: #282829;
            color: white;
            border: 1px solid #555555;
            padding: 5px;
        }
        QPushButton:hover {
            background-color: #555555;
        }
        QLabel {
            color: white;
        }
        QGroupBox {
            border: 1px solid #555555;
            margin-top: 10px;
            padding: 10px;
            color: white;
        }
        QStatusBar {
            background-color: #454444;
            color: white;
        }
        """
        self.setStyleSheet(stylesheet)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = ShakespeareWindow()
    sys.exit(app.exec_())