# --------------------------------------------------------------------------------------------------
# This is the main file of the application. 
# It creates the pyqt application's main window and starts the application.
# We're no longer running the application from here as we precompiled the source into an executable.
# --------------------------------------------------------------------------------------------------
import sys
from PyQt5 import QtWidgets
from sp import ShakespeareWindow

def main():
    '''
    Main function to start the application.
    '''
    app = QtWidgets.QApplication(sys.argv)
    shakespeareWindow = ShakespeareWindow()
    sys.exit(app.exec_()) # Running application's main event loop

if __name__ == '__main__':
    main()