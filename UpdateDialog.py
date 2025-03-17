from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices

from UI_UpdateDialog import Ui_UpdateDialog


def check_update():
    return 0


class UpdateDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, url=None, title=None, content=None, necessary=False):
        super(UpdateDialog, self).__init__(parent)
        self.ui = Ui_UpdateDialog()
        self.ui.setupUi(self)
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.dialogTitle = title
        self.lastlyVersionUrl = url
        self.content = content
        self.necessary = necessary
        if necessary:
            self.ui.pushButton_cancel.hide()
        self.ui.label_title.setText(self.dialogTitle)
        self.ui.label_content.setText(self.content)
        self.ui.pushButton_cancel.clicked.connect(self.reject)
        self.ui.pushButton_download.clicked.connect(self.accept_download)

    def accept_download(self):
        QDesktopServices.openUrl(QUrl(self.lastlyVersionUrl))
        exit(0)
