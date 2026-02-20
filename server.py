import socket
import time

IP = '0.0.0.0'
PORT = 5555
CHUNK = 1024
TIMEOUT = 30  # Секунд бездействия до удаления клиента

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        server_socket.bind((IP, PORT))
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        return

    # Храним {адрес: время_последней_активности}
    clients = {} 
    print(f"Сервер VOICE-чат запущен на {PORT}...")

    server_socket.settimeout(0.5)

    while True:
        try:
            try:
                data, addr = server_socket.recvfrom(CHUNK * 8)
            except socket.timeout:
                data, addr = None, None

            current_time = time.time()

            if addr:
                # 1. Регистрация НОВОГО пользователя
                if addr not in clients:
                    # Уведомляем существующих пользователей о новичке
                    text_msg = f"\n[СЕРВЕР] Пользователь {addr} подключился к комнате!"
                    msg = text_msg.encode('utf-8')
                    for client_addr in list(clients.keys()):
                        try:
                            server_socket.sendto(msg, client_addr)
                        except:
                            pass
                    
                    print(f"Подключился: {addr} (Всего: {len(clients) + 1})")
                
                # Обновляем время активности
                clients[addr] = current_time

                # 2. Обработка выхода
                if data == b"bye":
                    if addr in clients:
                        del clients[addr]
                        # Уведомляем остальных об уходе
                        text_exit = f"\n[СЕРВЕР] Пользователь {addr} покинул чат."
                        msg = text_exit.encode('utf-8')
                        for client_addr in list(clients.keys()):
                            try:
                                server_socket.sendto(msg, client_addr)
                            except:
                                pass
                        print(f"Пользователь {addr} покинул чат.")
                    continue

                # 3. Рассылка голоса
                # Если данных много (звук), пересылаем. 
                # Если мало, но это не "bye" и не "ping", возможно это текстовое уведомление
                if len(data) > 20: 
                    for client_addr in list(clients.keys()):
                        if client_addr != addr:
                            try:
                                server_socket.sendto(data, client_addr)
                            except Exception:
                                if client_addr in clients:
                                    del clients[client_addr]
                                    print(f"Пользователь {client_addr} отключился (ошибка сети).")

            # 4. Проверка таймаутов
            for client_addr, last_seen in list(clients.items()):
                if current_time - last_seen > TIMEOUT:
                    del clients[client_addr]
                    print(f"Пользователь {client_addr} отключился по таймауту.")

        except KeyboardInterrupt:
            print("\nСервер остановлен.")
            break
        except Exception as e:
            print(f"Системная ошибка: {e}")

    server_socket.close()

if __name__ == "__main__":
    start_server()