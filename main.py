import sys
from PySide6.QtWidgets import QApplication
from client import VoiceClient
from interface import VoiceInterface

def main():
    app = QApplication(sys.argv)
    
    # 1. Инициализируем логику
    logic = VoiceClient()
    
    # 2. Инициализируем интерфейс
    window = VoiceInterface(logic)
    window.show()
    
    # 3. При закрытии окна останавливаем потоки
    app.aboutToQuit.connect(logic.stop)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()