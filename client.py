import socket
import threading
import sounddevice as sd
import numpy as np
import json
import os

class VoiceClient:
    def __init__(self):
        self.config_file = "servers.json"
        self.server_list = self.load_servers()
        
        # Настройки звука
        self.sound_volume = 50
        self.mic_volume = 50
        self.threshold = 200
        self.is_sound_muted = False
        self.is_mic_muted = False
        
        # Состояние подключения
        self.running = False
        self.socket = None
        self.server_addr = None
        self.user_name = "Anonymous"

        # Коллбэки для связи с интерфейсом (назначаются в interface.py)
        self.on_users_received = None
        self.on_messages_received = None
        self.on_server_name_received = None

    def load_servers(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return []
        return []

    def save_servers(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.server_list, f, indent=4, ensure_ascii=False)

    def connect_to_server(self, ip, port, user_name="User"):
        self.user_name = user_name
        self.server_addr = (ip, port)
        
        # Создаем новый UDP сокет
        if self.socket:
            self.stop()
            
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(1.0)
        self.running = True
        
        # Пакет типа 0: Регистрация (флаг 0 + имя)
        connect_packet = bytes([0]) + self.user_name.encode('utf-8')
        self.socket.sendto(connect_packet, self.server_addr)
        
        # Запускаем потоки
        threading.Thread(target=self._listen_loop, daemon=True).start()
        threading.Thread(target=self._audio_input_loop, daemon=True).start()

    def send_text_message(self, text):
        """Отправка текстового сообщения (Тип 2)"""
        if self.socket and self.running:
            packet = bytes([2]) + text.encode('utf-8')
            self.socket.sendto(packet, self.server_addr)

    def _audio_input_loop(self):
        """Поток захвата звука с микрофона"""
        with sd.RawInputStream(samplerate=16000, blocksize=1024, channels=1, dtype='int16') as stream:
            while self.running:
                if self.is_mic_muted:
                    sd.sleep(100)
                    continue
                
                try:
                    data, _ = stream.read(1024)
                    audio_array = np.frombuffer(data, dtype=np.int16)
                    
                    # Усиление микрофона
                    gain = self.mic_volume / 50.0
                    audio_array = (audio_array * gain).clip(-32768, 32767).astype(np.int16)
                    
                    # Проверка порога активации (VOX)
                    rms = np.sqrt(np.mean(audio_array.astype(np.float64)**2))
                    if rms > self.threshold:
                        # Пакет типа 1: Аудио (флаг 1 + байты звука)
                        packet = bytes([1]) + audio_array.tobytes()
                        self.socket.sendto(packet, self.server_addr)
                except Exception:
                    continue

    def _listen_loop(self):
        """Единый поток для приема ВСЕХ данных от сервера (аудио, текст, API)"""
        with sd.RawOutputStream(samplerate=16000, blocksize=1024, channels=1, dtype='int16') as stream:
            while self.running:
                try:
                    raw_data, _ = self.socket.recvfrom(8192)
                    if not raw_data: continue
                    
                    packet_type = raw_data[0]
                    payload = raw_data[1:]

                    # 0: Информация о сервере (Приветствие)
                    if packet_type == 0:
                        msg = payload.decode('utf-8', errors='ignore')
                        if msg.startswith("SERVER_NAME|") and self.on_server_name_received:
                            name = msg.split("|")[1]
                            self.on_server_name_received(name)

                    # 1: Входящий звук
                    elif packet_type == 1:
                        if not self.is_sound_muted:
                            audio_array = np.frombuffer(payload, dtype=np.int16)
                            gain = self.sound_volume / 50.0
                            audio_array = (audio_array * gain).clip(-32768, 32767).astype(np.int16)
                            stream.write(audio_array.tobytes())

                    # 2: Текстовое сообщение (рассылка от сервера)
                    elif packet_type == 2:
                        if self.on_messages_received:
                            text = payload.decode('utf-8', errors='ignore')
                            self.on_messages_received([{"message": text}])

                    # 3: JSON API (Участники или История)
                    elif packet_type == 3:
                        api_data = json.loads(payload.decode('utf-8'))
                        if api_data["action"] == "users" and self.on_users_received:
                            self.on_users_received(api_data["objects"])
                        elif api_data["action"] == "messages" and self.on_messages_received:
                            self.on_messages_received(api_data["objects"])

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Ошибка приема данных: {e}")
                    continue

    def stop(self):
        """Корректное завершение работы"""
        if self.running:
            self.running = False
            if self.socket:
                try:
                    self.socket.sendto(b"bye", self.server_addr)
                except: pass
                self.socket.close()
                self.socket = None