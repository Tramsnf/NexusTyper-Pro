import sys
import time
import re
import random
import numpy as np
import platform
import threading
import os

from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QCheckBox, QSlider, QMessageBox, QProgressBar,
    QFileDialog, QAction, QMenuBar, QDialog, QLineEdit,
    QDialogButtonBox, QComboBox, QInputDialog, QTabWidget, QKeySequenceEdit,
    QFormLayout, QGroupBox, QRadioButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QSettings, QEvent
from PyQt5.QtGui import QKeySequence, QPixmap, QIcon