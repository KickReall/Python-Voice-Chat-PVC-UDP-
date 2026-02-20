import os
import sys
from PySide6.QtWidgets import QMainWindow, QListWidgetItem
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt

class VoiceInterface(QMainWindow):
    def __init__(self, client_logic):
        super().__init__()
        self.client = client_logic
        
        # 1. Загрузка UI
        loader = QUiLoader()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = os.path.join(script_dir, "interface", "main_interface.ui")
        
        ui_file = QFile(ui_path)
        if not ui_file.open(QFile.ReadOnly):
            print(f"ОШИБКА: Не удалось открыть {ui_path}")
            return

        self.ui = loader.load(ui_file)
        ui_file.close()

        if self.ui:
            self.setCentralWidget(self.ui.centralwidget)
            self.setWindowTitle(self.ui.windowTitle() or "Voice Chat v1.0")
            self.setFixedSize(self.ui.size()) 
            
            # Привязываем логику клиента к методам интерфейса (Callback)
            self.client.on_users_received = self.handle_users_update
            self.client.on_messages_received = self.handle_messages_update
            self.client.on_server_name_received = self.handle_server_name
            
            self.init_widgets()
            self.update_server_list_ui()

    def init_widgets(self):
        """Настройка начальных состояний виджетов и коннектов"""
        # Слайдеры
        self.ui.SoundVolume.setRange(0, 100)
        self.ui.MicVolume.setRange(0, 100)
        self.ui.ThresholdVolume.setRange(0, 1000)
        
        self.ui.SoundVolume.setValue(self.client.sound_volume)
        self.ui.MicVolume.setValue(self.client.mic_volume)
        self.ui.ThresholdVolume.setValue(self.client.threshold)

        # Кнопки
        self.ui.AddIP.clicked.connect(self.add_server_to_list)
        
        # Изменено: реагируем на смену текущего элемента (левый клик/выбор в списке)
        self.ui.ServerList.itemClicked.connect(self.connect_server)
        
        self.ui.MicOnOff.clicked.connect(self.toggle_mic)
        self.ui.SoundOnOff.clicked.connect(self.toggle_sound)
        
        if hasattr(self.ui, 'SendMessage'):
            self.ui.SendMessage.clicked.connect(self.send_text_msg)
        
        # Обновление параметров
        self.ui.SoundVolume.valueChanged.connect(self.sync_settings)
        self.ui.MicVolume.valueChanged.connect(self.sync_settings)
        self.ui.ThresholdVolume.valueChanged.connect(self.sync_settings)

    # --- ОБРАБОТЧИКИ API (Incoming Data) ---

    def handle_users_update(self, users):
        self.ui.UserList.clear()
        for user in users:
            item = QListWidgetItem(f"👤 {user['name']}")
            self.ui.UserList.addItem(item)

    def handle_messages_update(self, messages):
        for msg in messages:
            text = f"{msg['id']}: {msg['message']}" if 'id' in msg else msg['message']
            self.ui.MessageList.addItem(text)
        self.ui.MessageList.scrollToBottom()

    def handle_server_name(self, name):
        """Когда сервер прислал свое имя, обновляем статусбар"""
        if hasattr(self.ui, 'statusbar'):
            self.ui.statusbar.showMessage(f"Подключено к: {name}")

    # --- ЛОГИКА ИНТЕРФЕЙСА (Outgoing Actions) ---

    def add_server_to_list(self):
        """Добавляет IP в список серверов"""
        ip = self.ui.EnterIP.toPlainText().strip()
        if ip:
            # При добавлении используем IP как временное имя
            new_srv = {"ip": ip, "port": "5555", "name": ip}
            self.client.server_list.append(new_srv)
            self.client.save_servers()
            
            self.update_server_list_ui()
            self.ui.EnterIP.clear()
            if hasattr(self.ui, 'statusbar'):
                self.ui.statusbar.showMessage(f"IP {ip} добавлен в список", 2000)

    def connect_server(self, item):
        """Срабатывает при клике на сервер в списке"""
        srv = item.data(Qt.UserRole)
        
        # Берем ник пользователя из поля EnterName
        user_nickname = self.ui.EnterName.toPlainText().strip() or "User"
        
        self.client.stop() 
        self.client.connect_to_server(srv['ip'], int(srv['port']), user_name=user_nickname)
        
        # Визуальная очистка при переключении
        self.ui.MessageList.clear()
        self.ui.UserList.clear()
        if hasattr(self.ui, 'statusbar'):
            self.ui.statusbar.showMessage(f"Попытка подключения к {srv['ip']}...")

    def send_text_msg(self):
        text = self.ui.EnterMessage.toPlainText().strip()
        if text:
            self.client.send_text_message(text)
            self.ui.EnterMessage.clear()

    def sync_settings(self):
        self.client.sound_volume = self.ui.SoundVolume.value()
        self.client.mic_volume = self.ui.MicVolume.value()
        self.client.threshold = self.ui.ThresholdVolume.value()

    def update_server_list_ui(self):
        self.ui.ServerList.clear()
        for srv in self.client.server_list:
            display_name = f"🌐 {srv['ip']}"
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, srv)
            self.ui.ServerList.addItem(item)

    def toggle_mic(self):
        self.client.is_mic_muted = not self.client.is_mic_muted
        style = "background-color: #ff4444; color: white; border-radius: 5px;" if self.client.is_mic_muted else ""
        self.ui.MicOnOff.setStyleSheet(style)

    def toggle_sound(self):
        self.client.is_sound_muted = not self.client.is_sound_muted
        style = "background-color: #ff4444; color: white; border-radius: 5px;" if self.client.is_sound_muted else ""
        self.ui.SoundOnOff.setStyleSheet(style)