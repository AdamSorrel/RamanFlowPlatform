from PyQt5.QtWidgets import QDialog
from PyQt5.uic import loadUi

class loadStageSidebar(QDialog):
    def __init__(self):
        super().__init__()

        loadUi("goToPositionHelp.ui", self)

        