"""
Mercedes DSM Reader v2.0 with GUI
Graphical interface for reading EEPROM from Mercedes DSM module via OpenPort 2.0
Author: AI Assistant
Date: 2024
"""

import sys
import json
import serial
import struct
import threading
import time
import binascii
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class DSMReaderGUI(QMainWindow):
    """Основное окно программы"""
    
    def __init__(self):
        super().__init__()
        self.com_port = None
        self.serial_conn = None
        self.is_connected = False
        self.scanning = False
        self.init_ui()
        
    def init_ui(self):
        """Инициализация графического интерфейса"""
        self.setWindowTitle("Mercedes DSM Reader v2.0")
        self.setGeometry(100, 100, 900, 700)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        
        # Панель подключения
        connection_group = QGroupBox("Подключение")
        connection_layout = QHBoxLayout()
        
        self.port_combo = QComboBox()
        self.port_combo.setFixedWidth(150)
        self.refresh_ports()
        
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["500000", "250000", "125000", "1000000"])
        self.baud_combo.setCurrentText("500000")
        self.baud_combo.setFixedWidth(100)
        
        self.connect_btn = QPushButton("🔌 Подключиться")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setFixedWidth(120)
        
        self.status_label = QLabel("Статус: Не подключено")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.refresh_ports)
        refresh_btn.setFixedWidth(100)
        
        connection_layout.addWidget(QLabel("COM порт:"))
        connection_layout.addWidget(self.port_combo)
        connection_layout.addWidget(refresh_btn)
        connection_layout.addWidget(QLabel("CAN скорость:"))
        connection_layout.addWidget(self.baud_combo)
        connection_layout.addWidget(self.connect_btn)
        connection_layout.addWidget(self.status_label)
        connection_layout.addStretch()
        
        connection_group.setLayout(connection_layout)
        layout.addWidget(connection_group)
        
        # Панель управления
        control_group = QGroupBox("Управление чтением")
        control_layout = QHBoxLayout()
        
        self.scan_btn = QPushButton("▶ Начать сканирование DSM")
        self.scan_btn.clicked.connect(self.toggle_scan)
        self.scan_btn.setEnabled(False)
        self.scan_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        
        self.stop_btn = QPushButton("⏹ Остановить")
        self.stop_btn.clicked.connect(self.stop_scan)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px;")
        
        self.save_btn = QPushButton("💾 Сохранить дамп")
        self.save_btn.clicked.connect(self.save_dump)
        self.save_btn.setEnabled(False)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        control_layout.addWidget(self.scan_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.save_btn)
        control_layout.addWidget(self.progress_bar)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Панель информации
        info_group = QGroupBox("Информация")
        info_layout = QGridLayout()
        
        self.segments_label = QLabel("Найдено сегментов: 0")
        self.bytes_label = QLabel("Прочитано байт: 0")
        self.time_label = QLabel("Время: 00:00")
        self.module_label = QLabel("Модуль: Не определен")
        
        info_layout.addWidget(self.segments_label, 0, 0)
        info_layout.addWidget(self.bytes_label, 0, 1)
        info_layout.addWidget(self.time_label, 1, 0)
        info_layout.addWidget(self.module_label, 1, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # HEX просмотрщик
        hex_group = QGroupBox("HEX просмотрщик")
        hex_layout = QVBoxLayout()
        
        self.hex_text = QTextEdit()
        self.hex_text.setReadOnly(True)
        self.hex_text.setFont(QFont("Courier", 10))
        self.hex_text.setPlaceholderText("Данные появятся здесь после чтения...")
        
        hex_layout.addWidget(self.hex_text)
        hex_group.setLayout(hex_layout)
        layout.addWidget(hex_group)
        
        # Лог
        log_group = QGroupBox("Лог программы")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        central_widget.setLayout(layout)
        
        # Таймер обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(1000)
        
        self.log("Программа запущена. Выберите COM порт OpenPort и подключитесь.")
        
    def refresh_ports(self):
        """Обновить список COM портов"""
        self.port_combo.clear()
        ports = []
        
        # Попытка автоматического поиска портов
        for i in range(1, 21):
            port_name = f"COM{i}"
            try:
                ser = serial.Serial(port_name)
                ser.close()
                ports.append(port_name)
            except:
                pass
                
        if ports:
            self.port_combo.addItems(ports)
            self.log(f"Найдены порты: {', '.join(ports)}")
        else:
            self.port_combo.addItem("COM3")
            self.log("Порты не найдены. Используется COM3 по умолчанию.")
    
    def toggle_connection(self):
        """Подключение/отключение от OpenPort"""
        if not self.is_connected:
            self.connect_to_port()
        else:
            self.disconnect_port()
    
    def connect_to_port(self):
        """Подключиться к выбранному COM порту"""
        port = self.port_combo.currentText()
        baudrate = int(self.baud_combo.currentText())
        
        try:
            self.log(f"Подключаюсь к {port}...")
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=115200,  # OpenPort работает на 115200
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=1
            )
            
            # Инициализация CAN
            self.send_openport_command('C')  # Close if open
            time.sleep(0.1)
            self.send_openport_command('O')  # Open CAN
            time.sleep(0.1)
            self.send_openport_command(f'S{baudrate}')
            time.sleep(0.1)
            
            self.is_connected = True
            self.connect_btn.setText("🔌 Отключиться")
            self.status_label.setText("Статус: Подключено")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.scan_btn.setEnabled(True)
            
            self.log(f"✓ Успешно подключено к {port}")
            self.log("Теперь подключите OpenPort к автомобилю и включите зажигание.")
            
        except Exception as e:
            self.log(f"✗ Ошибка подключения: {str(e)}")
            self.status_label.setText("Статус: Ошибка подключения")
    
    def disconnect_port(self):
        """Отключиться от порта"""
        if self.serial_conn:
            try:
                self.serial_conn.close()
                self.log("Соединение закрыто")
            except:
                pass
        
        self.is_connected = False
        self.connect_btn.setText("🔌 Подключиться")
        self.status_label.setText("Статус: Не подключено")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
    
    def send_openport_command(self, cmd):
        """Отправить команду OpenPort"""
        if self.serial_conn:
            self.serial_conn.write(f"{cmd}\r".encode())
            time.sleep(0.05)
            response = self.serial_conn.read(100)
            return response.decode().strip()
        return ""
    
    def toggle_scan(self):
        """Начать/остановить сканирование"""
        if not self.scanning:
            self.start_scanning()
        else:
            self.stop_scan()
    
    def start_scanning(self):
        """Запуск сканирования в отдельном потоке"""
        if not self.is_connected:
            self.log("Сначала подключитесь к OpenPort!")
            return
        
        self.scanning = True
        self.scan_btn.setText("⏸ Пауза")
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        
        # Запуск в отдельном потоке
        self.scan_thread = threading.Thread(target=self.scan_dsm_thread)
        self.scan_thread.daemon = True
        self.scan_thread.start()
        
        self.log("Начато сканирование DSM...")
    
    def scan_dsm_thread(self):
        """Поток сканирования DSM"""
        try:
            # Имитация сканирования (замените реальной логикой)
            segments = []
            total_bytes = 0
            
            # Сканирование сегментов EEPROM
            for seg_id in range(0xF100, 0xF110):
                if not self.scanning:
                    break
                    
                # Имитация чтения данных
                data = self.read_dsm_segment(seg_id)
                if data:
                    segments.append((seg_id, data))
                    total_bytes += len(data)
                    
                    # Обновление UI через сигналы
                    self.update_progress_signal.emit(seg_id, len(data), total_bytes)
                
                # Прогресс
                progress = ((seg_id - 0xF100) / 16) * 100
                self.progress_bar.setValue(int(progress))
                
                time.sleep(0.1)
            
            if segments:
                self.dump_data = segments
                self.save_btn.setEnabled(True)
                self.log(f"Сканирование завершено. Найдено {len(segments)} сегментов, {total_bytes} байт")
            else:
                self.log("Данные не найдены. Проверьте подключение к автомобилю.")
                
        except Exception as e:
            self.log(f"Ошибка при сканировании: {str(e)}")
        
        self.scanning = False
        self.scan_btn.setText("▶ Начать сканирование DSM")
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(100)
    
    def read_dsm_segment(self, segment_id):
        """Чтение сегмента данных из DSM (заглушка - замените реальной логикой)"""
        # В реальной программе здесь будет UDS протокол
        # 0x22 - ReadDataByIdentifier
        cmd = bytes([0x22, (segment_id >> 8) & 0xFF, segment_id & 0xFF])
        
        try:
            if self.serial_conn:
                # Отправка CAN команды через OpenPort
                can_id = 0x7E0
                can_cmd = f't{can_id:03X}{cmd.hex()}'
                self.serial_conn.write(f"{can_cmd}\r".encode())
                
                # Чтение ответа (упрощённо)
                time.sleep(0.1)
                response = self.serial_conn.read(100)
                
                if response:
                    # Парсинг ответа (упрощённо)
                    return bytes([0x00, 0x01, 0x02, 0x03, 0x04])  # Тестовые данные
        except:
            pass
        
        return None
    
    def stop_scan(self):
        """Остановить сканирование"""
        self.scanning = False
        self.log("Сканирование остановлено пользователем")
    
    def save_dump(self):
        """Сохранить дамп в файл"""
        if not hasattr(self, 'dump_data'):
            self.log("Нет данных для сохранения")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить дамп", f"dsm_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}", "BIN files (*.bin);;HEX files (*.hex);;All files (*.*)"
        )
        
        if filename:
            try:
                with open(filename, 'wb') as f:
                    for seg_id, data in self.dump_data:
                        f.write(data)
                
                self.log(f"Дамп сохранён в {filename}")
                
                # Также создаём HEX версию
                if not filename.endswith('.hex'):
                    hex_filename = filename.rsplit('.', 1)[0] + '.hex'
                    self.create_hex_dump(hex_filename)
                    
            except Exception as e:
                self.log(f"Ошибка при сохранении: {str(e)}")
    
    def create_hex_dump(self, filename):
        """Создать HEX представление дампа"""
        try:
            all_data = bytearray()
            for _, data in self.dump_data:
                all_data.extend(data)
            
            with open(filename, 'w') as f:
                f.write("Адрес:  00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F  Текст\n")
                f.write("=" * 70 + "\n")
                
                for i in range(0, len(all_data), 16):
                    chunk = all_data[i:i+16]
                    hex_str = ' '.join(f'{b:02X}' for b in chunk)
                    hex_str = hex_str.ljust(47)
                    
                    # ASCII представление
                    ascii_str = ''
                    for b in chunk:
                        if 32 <= b <= 126:
                            ascii_str += chr(b)
                        else:
                            ascii_str += '.'
                    
                    f.write(f"{i:04X}:  {hex_str}  {ascii_str}\n")
            
            self.log(f"HEX версия создана: {filename}")
            
            # Показать первые строки в просмотрщике
            self.display_hex_data(all_data[:512])
            
        except Exception as e:
            self.log(f"Ошибка при создании HEX дампа: {str(e)}")
    
    def display_hex_data(self, data):
        """Отобразить HEX данные в просмотрщике"""
        hex_text = ""
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            hex_str = hex_str.ljust(47)
            
            # ASCII представление
            ascii_str = ''
            for b in chunk:
                if 32 <= b <= 126:
                    ascii_str += chr(b)
                else:
                    ascii_str += '.'
            
            hex_text += f"{i:04X}:  {hex_str}  {ascii_str}\n"
        
        self.hex_text.setText(hex_text)
    
    def update_ui(self):
        """Обновление информации в UI"""
        if self.scanning:
            current_time = time.strftime("%H:%M:%S")
            self.time_label.setText(f"Время: {current_time}")
    
    def log(self, message):
        """Добавить сообщение в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        self.log_text.append(log_message)
        # Автопрокрутка
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        print(log_message)  # Также в консоль
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.scanning:
            self.stop_scan()
        
        if self.is_connected:
            self.disconnect_port()
        
        event.accept()

# Сигналы для обновления UI из потока
class DSMReaderApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = DSMReaderGUI()
    
    def run(self):
        self.window.show()
        return self.app.exec_()

def main():
    """Точка входа в программу"""
    app = DSMReaderApp()
    sys.exit(app.run())

if __name__ == "__main__":
    main()
