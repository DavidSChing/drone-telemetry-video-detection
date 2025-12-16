import sys
import os
from PyQt5.QtWidgets import QFrame, QTextEdit
import serial.tools.list_ports
import webbrowser
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QGroupBox,
                             QProgressBar, QMessageBox, QTabWidget)
from PyQt5.QtCore import QTimer, Qt
from datetime import datetime
import time
import folium
from folium import plugins
import tempfile

# Importar con manejo de errores
try:
    from mavlink_handler import MavlinkHandler
except ImportError as e:
    print(f"Error importando MavlinkHandler: {e}")
    MavlinkHandler = None

class DroneControllerComplete(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mavlink = None
        self.connected = False
        self.positions_history = []
        self.home_position = None
        self.map_file = None
        
        # Inicializar atributos
        self.alt_value = None
        self.speed_value = None
        self.batt_value = None
        self.batt_bar = None
        self.gps_value = None
        self.gps_fix = None
        self.lat_value = None
        self.lon_value = None
        self.console = None
        
        self.setup_ui()
        self.setup_timers()
        self.setup_map()

    def setup_ui(self):
        # Interfaz principal
        self.setWindowTitle("Control Dron - Pixhawk 2.4.8")
        self.setGeometry(100, 100, 1200, 800)

        # Estilo de presentación
        self.setStyleSheet(""" 
            QMainWindow {
                background-color: #2b2b2b;
                color: white;
            }
            QGroupBox {
                color: #00ff00;
                font-weight: bold;
                border: 2px solid #00ff00;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #00ff00;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #666;
                padding: 8px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #606060;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
            QLabel {
                color: white;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #404040;
                color: white;
                padding: 8px 16px;
                border: 1px solid #444;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #505050;
                border-color: #00ff00;
            }
            QTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                border: 1px solid #444;
                font-family: monospace;
                font-size: 10px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Barra de conexión
        self.setup_connection_bar(layout)

        # Tabs principales
        self.setup_tabs(layout)

    def setup_connection_bar(self, layout):
        # Barra de conexión
        conn_group = QGroupBox("CONEXIÓN DRON")
        conn_layout = QHBoxLayout()

        self.conn_status = QLabel("DESCONECTADO")
        self.conn_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #ff4444;")
        conn_layout.addWidget(self.conn_status)

        self.conn_info = QLabel("Conecta telemetría Holybro USB y enciende Pixhawk")
        self.conn_info.setStyleSheet("color: #cccccc;")
        conn_layout.addWidget(self.conn_info)

        conn_layout.addStretch()

        self.connect_btn = QPushButton("CONECTAR DRON")
        self.connect_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.connect_btn)

        self.map_btn = QPushButton("ABRIR MAPA GPS")
        self.map_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; }")
        self.map_btn.clicked.connect(self.open_map)
        self.map_btn.setEnabled(False)
        conn_layout.addWidget(self.map_btn)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

    def setup_tabs(self, layout):
        # Tabs principales: Control y Mapa
        self.tabs = QTabWidget()

        # Tab 1: Control principal
        self.control_tab = self.setup_control_tab()
        self.tabs.addTab(self.control_tab, "CONTROL PRINCIPAL")

        # Tab 2: Mapa GPS
        self.map_tab = self.setup_map_tab()
        self.tabs.addTab(self.map_tab, "MAPA GPS")

        layout.addWidget(self.tabs)

    def setup_control_tab(self):
        # Tab de control principal con datos en tiempo real
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Columna izquierda: Datos y controles
        left_column = QVBoxLayout()
        self.setup_data_display(left_column)
        
        # Agregar consola de logs
        self.setup_console(left_column)
        
        layout.addLayout(left_column)

        return widget

    def setup_data_display(self, layout):
        # Display de datos del dron (GPS, batería, posición)
        data_group = QGroupBox("DATOS EN TIEMPO REAL")
        data_layout = QVBoxLayout()

        # Fila 1: Altura y Velocidad
        row1 = QHBoxLayout()

        # Altura Frame
        alt_frame = QFrame()
        alt_frame.setFrameStyle(QFrame.Box)
        alt_frame.setStyleSheet("border: 1px solid #444; padding: 5px;")
        alt_layout = QVBoxLayout(alt_frame)

        alt_label = QLabel("ALTURA")
        alt_label.setStyleSheet("color: #00ffff; font-size: 10px;")
        alt_layout.addWidget(alt_label)

        self.alt_value = QLabel("-- m")
        self.alt_value.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ffff;")
        alt_layout.addWidget(self.alt_value)

        row1.addWidget(alt_frame)

        # Velocidad Frame
        speed_frame = QFrame()
        speed_frame.setFrameStyle(QFrame.Box)
        speed_frame.setStyleSheet("border: 1px solid #444; padding: 5px;")
        speed_layout = QVBoxLayout(speed_frame)

        speed_label = QLabel("VELOCIDAD")
        speed_label.setStyleSheet("color: #ffff00; font-size: 10px;")
        speed_layout.addWidget(speed_label)

        self.speed_value = QLabel("-- m/s")
        self.speed_value.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffff00;")
        speed_layout.addWidget(self.speed_value)

        row1.addWidget(speed_frame)

        data_layout.addLayout(row1)

        # Fila 2: Batería y GPS
        row2 = QHBoxLayout()

        # Batería Frame
        batt_frame = QFrame()
        batt_frame.setFrameStyle(QFrame.Box)
        batt_frame.setStyleSheet("border: 1px solid #444; padding: 5px;")
        batt_layout = QVBoxLayout(batt_frame)

        batt_label = QLabel("BATERÍA")
        batt_label.setStyleSheet("color: #ff4444; font-size: 10px;")
        batt_layout.addWidget(batt_label)

        self.batt_value = QLabel("-- %")
        self.batt_value.setStyleSheet("font-size: 18px; font-weight: bold; color: #ff4444;")
        batt_layout.addWidget(self.batt_value)

        self.batt_bar = QProgressBar()
        self.batt_bar.setRange(0, 100)
        self.batt_bar.setValue(0)
        self.batt_bar.setStyleSheet(""" 
            QProgressBar {
                border: 1px solid #444;
                border-radius: 3px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #ff4444;
            }
        """)
        batt_layout.addWidget(self.batt_bar)

        row2.addWidget(batt_frame)

        # GPS Frame
        gps_frame = QFrame()
        gps_frame.setFrameStyle(QFrame.Box)
        gps_frame.setStyleSheet("border: 1px solid #444; padding: 5px;")
        gps_layout = QVBoxLayout(gps_frame)

        gps_label = QLabel("GPS")
        gps_label.setStyleSheet("color: #00ff00; font-size: 10px;")
        gps_layout.addWidget(gps_label)

        self.gps_value = QLabel("-- sats")
        self.gps_value.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff00;")
        gps_layout.addWidget(self.gps_value)

        self.gps_fix = QLabel("NO FIX")
        self.gps_fix.setStyleSheet("font-size: 12px; color: #ff4444;")
        gps_layout.addWidget(self.gps_fix)

        row2.addWidget(gps_frame)

        data_layout.addLayout(row2)

        # Fila 3: Ubicación GPS
        loc_frame = QFrame()
        loc_frame.setFrameStyle(QFrame.Box)
        loc_frame.setStyleSheet("border: 1px solid #444; padding: 5px;")
        loc_layout = QVBoxLayout(loc_frame)

        loc_label = QLabel("UBICACIÓN GPS")
        loc_label.setStyleSheet("color: #ff00ff; font-size: 10px;")
        loc_layout.addWidget(loc_label)

        self.lat_value = QLabel("Lat: --")
        self.lat_value.setStyleSheet("font-size: 11px; font-family: monospace;")
        loc_layout.addWidget(self.lat_value)

        self.lon_value = QLabel("Lon: --")
        self.lon_value.setStyleSheet("font-size: 11px; font-family: monospace;")
        loc_layout.addWidget(self.lon_value)

        data_layout.addWidget(loc_frame)

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

    def setup_console(self, layout):
        """Agrega una consola para mostrar logs"""
        console_group = QGroupBox("CONSOLA")
        console_layout = QVBoxLayout()
        
        self.console = QTextEdit()
        self.console.setMaximumHeight(150)
        self.console.setReadOnly(True)
        console_layout.addWidget(self.console)
        
        console_group.setLayout(console_layout)
        layout.addWidget(console_group)

    def setup_map_tab(self):
        # Tab del mapa GPS
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Controles del mapa
        map_controls = QHBoxLayout()

        map_title = QLabel("MAPA GPS EN TIEMPO REAL")
        map_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00ffff;")
        map_controls.addWidget(map_title)

        map_controls.addStretch()

        self.center_map_btn = QPushButton("Centrar en Dron")
        self.center_map_btn.clicked.connect(self.center_map_on_drone)
        self.center_map_btn.setEnabled(False)
        map_controls.addWidget(self.center_map_btn)

        layout.addLayout(map_controls)

        # Información del mapa
        map_info = QLabel("El mapa se ha abierto en tu navegador")
        map_info.setStyleSheet("color: #cccccc; font-size: 10px;")
        layout.addWidget(map_info)

        return widget

    def setup_timers(self):
        """Configura los timers para actualización de datos"""
        # Timer para actualizar datos de la interfaz
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.update_ui_data)
        self.data_timer.start(1000)  # Actualizar cada 1 segundo

    def update_ui_data(self):
        # Actualiza los datos
        if self.connected and self.mavlink:
            try:
                # Obtener datos del handler MAVLink
                data = self.mavlink.get_latest_data()
                
                # Actualizar altitud
                if 'altitude' in data and data['altitude'] is not None:
                    self.alt_value.setText(f"{data['altitude']:.1f} m")
                
                # Actualizar velocidad
                if 'speed' in data and data['speed'] is not None:
                    self.speed_value.setText(f"{data['speed']:.1f} m/s")
                
                # Actualizar batería
                if 'battery' in data and data['battery'] is not None:
                    batt_percent = data['battery']
                    self.batt_value.setText(f"{batt_percent:.0f} %")
                    self.batt_bar.setValue(int(batt_percent))
                
                # Actualizar GPS
                if 'satellites' in data and data['satellites'] is not None:
                    self.gps_value.setText(f"{data['satellites']} sats")
                
                # Actualizar fix de GPS
                if 'gps_fix' in data and data['gps_fix'] is not None:
                    fix_type = data['gps_fix']
                    fix_text = self.get_fix_type_text(fix_type)
                    self.gps_fix.setText(fix_text)
                    color = "#00ff00" if fix_type >= 3 else "#ff4444"
                    self.gps_fix.setStyleSheet(f"font-size: 12px; color: {color};")
                
                # Actualizar posición
                if 'lat' in data and 'lon' in data and data['lat'] is not None and data['lon'] is not None:
                    lat = data['lat']
                    lon = data['lon']
                    self.lat_value.setText(f"Lat: {lat:.6f}")
                    self.lon_value.setText(f"Lon: {lon:.6f}")
                    
                    # Guardar posición en el historial
                    self.positions_history.append((lat, lon))
                    
                    # Actualizar mapa cada 10 posiciones
                    if len(self.positions_history) % 10 == 0:
                        self.update_map()
                    
                    # Habilitar botón de centrar mapa
                    self.center_map_btn.setEnabled(True)
                    
            except Exception as e:
                self.log(f"Error actualizando UI: {e}")

    def get_fix_type_text(self, fix_type):
        """Convierte el tipo de fix GPS a texto legible"""
        fix_types = {
            0: "NO GPS",
            1: "NO FIX", 
            2: "2D FIX",
            3: "3D FIX",
            4: "DGPS",
            5: "RTK FLOAT",
            6: "RTK FIX"
        }
        return fix_types.get(fix_type, f"FIX {fix_type}")

    def center_map_on_drone(self):
        # Centrar el mapa en la posición del dron
        if self.positions_history:
            self.update_map()
            self.log("Centrando mapa en la posición del dron")

    def setup_map(self):
        # Inicializar mapa Folium
        self.update_map()

    def update_map(self):
        # Actualizar mapa con nueva posición
        if not self.positions_history:
            # Usar posición por defecto si no hay historial
            lat, lon = -12.0464, -77.0428
        else:
            lat, lon = self.positions_history[-1]

        self.map = folium.Map(
            location=[lat, lon],
            zoom_start=16,
            tiles='OpenStreetMap'
        )

        # Agregar marcador de posición actual
        folium.Marker(
            [lat, lon],
            popup=f'<b>DRON</b><br>Lat: {lat:.6f}<br>Lon: {lon:.6f}',
            tooltip='Posición actual del dron',
            icon=folium.Icon(color='red', icon='plane', prefix='fa')
        ).add_to(self.map)

        # Agregar línea de ruta si hay suficientes puntos
        if len(self.positions_history) > 1:
            folium.PolyLine(
                self.positions_history,
                color='blue',
                weight=4,
                opacity=0.7,
                popup='Ruta del dron'
            ).add_to(self.map)

        # Agregar home position si está definida
        if self.home_position:
            home_lat, home_lon = self.home_position
            folium.Marker(
                [home_lat, home_lon],
                popup='<b>HOME</b><br>Posición inicial',
                tooltip='HOME',
                icon=folium.Icon(color='green', icon='home', prefix='fa')
            ).add_to(self.map)

        # Agregar plugins
        plugins.Fullscreen().add_to(self.map)
        plugins.MousePosition().add_to(self.map)

        # Guardar y actualizar archivo
        if self.map_file is None:
            self.map_file = tempfile.NamedTemporaryFile(suffix='.html', delete=False)
        
        self.map.save(self.map_file.name)
        self.log("Mapa actualizado con nueva posición")

    def open_map(self):
        # Abrir mapa en el navegador
        try:
            webbrowser.open('file://' + os.path.abspath(self.map_file.name))
            self.log("Mapa abierto en navegador")
        except Exception as e:
            self.log(f"Error abriendo mapa: {e}")

    def toggle_connection(self):
        # Conectar o desconectar
        if not self.connected:
            self.connect_to_drone()
        else:
            self.disconnect_from_drone()

    def connect_to_drone(self):
        # Verificar si MavlinkHandler está disponible
        if MavlinkHandler is None:
            self.log("ERROR: MavlinkHandler no está disponible")
            QMessageBox.critical(self, "Error", "No se pudo importar MavlinkHandler. Verifica la instalación.")
            return
            
        # Conectar al dron
        self.conn_info.setText("Buscando dron...")
        self.connect_btn.setEnabled(False)

        threading.Thread(target=self._auto_connect, daemon=True).start()

    def _auto_connect(self):
        # Buscar y conectar automáticamente
        try:
            ports = serial.tools.list_ports.comports()
            
            # Mostrar puertos disponibles
            available_ports = [port.device for port in ports]
            self.log(f"Puertos disponibles: {available_ports}")
            
            if not available_ports:
                self._update_conn_info("No se encontraron puertos COM")
                self._update_conn_status("DESCONECTADO", "#ff4444")
                self.connect_btn.setEnabled(True)
                return

            found = False

            for port in ports:
                # Filtrar puertos que no son COM (en Windows) o tienen nombres específicos
                port_name = port.device
                if not self.is_valid_port(port_name):
                    continue
                    
                for baud in [57600]:
                    try:
                        self._update_conn_info(f"Probando {port_name} @ {baud}...")
                        self.log(f"Intentando conectar a {port_name} a {baud} bauds")

                        mav = MavlinkHandler(port=port_name, baud=baud)
                        time.sleep(2)

                        if mav.is_verified():
                            self.mavlink = mav
                            self.connected = True

                            vehicle_info = mav.get_vehicle_info()
                            info_text = f"Conectado: {vehicle_info.get('vehicle_type', 'Unknown')}"
                            self._update_conn_info(info_text)
                            self._update_conn_status("CONECTADO", "#00ff00")

                            # Habilitar controles
                            self.map_btn.setEnabled(True)
                            self.connect_btn.setText("DESCONECTAR")
                            self.connect_btn.setEnabled(True)
                            
                            self.log(f"Conexión exitosa: {port_name} @ {baud}")
                            found = True
                            return
                        else:
                            mav.close()
                    except Exception as e:
                        self.log(f"Error probando {port_name} @ {baud}: {e}")
                        continue

            if not found:
                self._update_conn_info("No se encontró el dron")
                self._update_conn_status("DESCONECTADO", "#ff4444")
                self.connect_btn.setEnabled(True)
                self.log("No se pudo encontrar ningún dron conectado")

        except Exception as e:
            self._update_conn_info(f"Error: {str(e)}")
            self._update_conn_status("DESCONECTADO", "#ff4444")
            self.connect_btn.setEnabled(True)
            self.log(f"Error en conexión: {e}")

    def is_valid_port(self, port_name):
        """Verifica si el puerto es válido para conexión"""
        # En Windows, los puertos válidos son COM1-COM255
        if sys.platform.startswith('win'):
            return port_name.startswith('COM') and len(port_name) > 3
        # En Linux/Mac, los puertos válidos son /dev/tty*
        else:
            return port_name.startswith('/dev/tty')
    
    def _update_conn_info(self, message):
        # Actualizar info de conexión desde hilo
        def update():
            self.conn_info.setText(message)
        QTimer.singleShot(0, update)

    def _update_conn_status(self, status, color):
        # Actualizar estado de conexión desde hilo
        def update():
            self.conn_status.setText(status)
            self.conn_status.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
        QTimer.singleShot(0, update)

    def disconnect_from_drone(self):
        # Desconectar del dron
        self.connected = False
        if self.mavlink:
            self.mavlink.close()
            self.mavlink = None

        self._update_conn_status("DESCONECTADO", "#ff4444")
        self.conn_info.setText("Desconectado")
        self.connect_btn.setText("CONECTAR DRON")

        self.map_btn.setEnabled(False)
        self.center_map_btn.setEnabled(False)
        self.log("Desconectado del dron")

    def log(self, message):
        # Agregar a consola
        timestamp = datetime.now().strftime("%H:%M:%S")
        if self.console:
            self.console.append(f"[{timestamp}] {message}")
            # Auto-scroll
            scrollbar = self.console.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        else:
            print(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """Manejar cierre de la aplicación"""
        self.disconnect_from_drone()
        if self.map_file:
            try:
                os.unlink(self.map_file.name)
            except:
                pass
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DroneControllerComplete()
    window.show()
    sys.exit(app.exec_())