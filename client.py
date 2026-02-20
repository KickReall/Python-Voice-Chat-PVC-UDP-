import socket
import sounddevice as sd
import numpy as np
import threading
import sys

# Настройки звука
RATE = 16000
CHUNK = 1024
CHANNELS = 1
DTYPE = 'int16'

class VoiceClient:
    def __init__(self):
        self.socket = None
        self.running = False
        self.stream_in = None
        self.stream_out = None
        self.server_addr = None
        self.vad_threshold = 200  # Начальное значение

    def start(self):
        server_ip = input("Введите IP сервера: ")
        server_port_input = input("Введите порт сервера (по умолчанию 5555): ")
        server_port = int(server_port_input) if server_port_input else 5555
        self.server_addr = (server_ip, server_port)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(2.0)
        
        try:
            self.socket.sendto(b"ping", self.server_addr)
            self.running = True
        except Exception as e:
            print(f"Ошибка сокета: {e}")
            return

        try:
            self.stream_in = sd.RawInputStream(
                samplerate=RATE, blocksize=CHUNK, 
                channels=CHANNELS, dtype=DTYPE
            )
            self.stream_out = sd.RawOutputStream(
                samplerate=RATE, blocksize=CHUNK, 
                channels=CHANNELS, dtype=DTYPE
            )
            
            self.stream_in.start()
            self.stream_out.start()

            # 1. Поток для прослушивания сервера
            threading.Thread(target=self.receive_audio, daemon=True).start()
            
            # 2. Поток для изменения порога в реальном времени
            threading.Thread(target=self.change_threshold, daemon=True).start()
            
            print(f"\n[СИСТЕМА] Связь установлена!")
            print(f"[СИСТЕМА] Текущий порог VAD: {self.vad_threshold}")
            print(f"[СИСТЕМА] Чтобы изменить порог, просто введи число (0-1000) и нажми Enter.\n")
            
            self.send_audio()

        except Exception as e:
            print(f"Ошибка аудио-устройств: {e}")
            self.cleanup()

    def change_threshold(self):
        """Метод для изменения чувствительности прямо во время разговора"""
        while self.running:
            try:
                # Используем sys.stdin.readline для корректной работы в потоке
                line = sys.stdin.readline().strip()
                if line.isdigit():
                    new_val = int(line)
                    if 0 <= new_val <= 1000:
                        self.vad_threshold = new_val
                        print(f"---> Порог изменен на: {self.vad_threshold}")
                    else:
                        print("---> Ошибка: введите число от 0 до 1000")
            except:
                break

    def receive_audio(self):
        while self.running:
            try:
                data, _ = self.socket.recvfrom(CHUNK * 8)
                
                # Сначала пробуем декодировать как текст
                try:
                    # Если пакет короткий и содержит текст, пробуем его прочитать
                    if 0 < len(data) < 200: 
                        decoded_msg = data.decode('utf-8')
                        if "[СЕРВЕР]" in decoded_msg:
                            print(decoded_msg)
                            continue # Переходим к следующему пакету, не играем это как звук
                except:
                    # Если это не текст (ошибка декодирования), значит это звук
                    pass

                # Если это звук (пакеты обычно имеют фиксированный размер CHUNK)
                if len(data) > 20: 
                    self.stream_out.write(data)
                    
            except socket.timeout:
                continue
            except:
                break

    def send_audio(self):
        try:
            while self.running:
                data, overflowed = self.stream_in.read(CHUNK)
                if overflowed:
                    continue

                audio_array = np.frombuffer(data, dtype=np.int16)
                
                if audio_array.size > 0:
                    audio_float = audio_array.astype(np.float64)
                    rms = np.sqrt(np.mean(audio_float**2))
                else:
                    rms = 0
                
                # Используем динамически изменяемый порог
                if rms > self.vad_threshold:
                    self.socket.sendto(data, self.server_addr)
                    
        except KeyboardInterrupt:
            print("\nЗавершение работы...")
        finally:
            self.cleanup()

    def cleanup(self):
        if not self.running: return
        self.running = False
        
        try:
            if self.socket and self.server_addr:
                self.socket.sendto(b"bye", self.server_addr)
        except: pass

        if self.stream_in: self.stream_in.stop(); self.stream_in.close()
        if self.stream_out: self.stream_out.stop(); self.stream_out.close()
        if self.socket: self.socket.close()
        print("Сессия завершена.")

if __name__ == "__main__":
    while True:
        client = VoiceClient()
        client.start()
        choice = input("Хотите переподключиться? (y/n): ")
        if choice.lower() != 'y':
            break