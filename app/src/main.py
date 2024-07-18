import sys
from PyQt5 import QtWidgets
from sp import ShakespeareWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    shakespeareWindow = ShakespeareWindow()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()