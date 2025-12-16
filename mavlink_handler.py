import pymavlink.mavutil as mavutil
import time
import threading
from datetime import datetime
import math
import csv
import os
import serial.tools.list_ports

class MavlinkHandler:
    def __init__(self, port=None, baud=57600, csv_file="telemetria.csv"):
        self.port = port
        self.baud = baud
        self.master = None
        self.connected = False
        self.latest_data = {}
        self.data_lock = threading.Lock()
        self.csv_file = csv_file

        # Creamos archivo CSV
        self._init_csv()
        self._connect()

    def _init_csv(self):
        #Inicializa archivo CSV con encabezados
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                writer = csv.writer(f)
                # Encabezados básicos
                writer.writerow([
                    "timestamp", "lat", "lon", "altitude",
                    "x", "y", "speed", "battery",
                    "satellites", "gps_fix"
                ])

    def _append_csv(self):
        #Agrega una fila al CSV con los datos actuales
        with self.data_lock:
            data = self.latest_data.copy()

        # Crear fila con valores (usar 0 si falta algún dato)
        row = [
            datetime.now().isoformat(),
            data.get("lat", 0),
            data.get("lon", 0),
            data.get("altitude", 0),
            data.get("x", 0),
            data.get("y", 0),
            data.get("speed", 0),
            data.get("battery", 0),
            data.get("satellites", 0),
            data.get("gps_fix", 0)
        ]
        try:
            with open(self.csv_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            print(f"Error escribiendo CSV: {e}")

    def _connect(self):
        # Establece conexión MAVLink
        try:
            if self.port is None:
                # Buscar automáticamente el puerto
                ports = self._find_serial_ports()
                if not ports:
                    raise Exception("No se encontraron puertos seriales")
                
                # Probar puertos automáticamente
                for port in ports:
                    try:
                        self.master = mavutil.mavlink_connection(port, baud=self.baud)
                        if self._verify_connection():
                            self.port = port
                            self.connected = True
                            print(f"Conectado automáticamente a {port}")
                            return
                    except:
                        continue
                
                raise Exception("No se pudo conectar a ningún puerto")
            else:
                # Conectar al puerto específico
                self.master = mavutil.mavlink_connection(self.port, baud=self.baud)
                if self._verify_connection():
                    self.connected = True
                    print(f"Conectado a {self.port}")
                else:
                    raise Exception("No se pudo verificar la conexión")
                    
            # Iniciar hilo para recibir datos
            self._start_data_thread()
            
        except Exception as e:
            self.connected = False
            raise Exception(f"Error conectando a {self.port}: {str(e)}")
    
    def _find_serial_ports(self):
        # Encuentra puertos seriales disponibles
        ports = serial.tools.list_ports.comports()
        valid_ports = []
        
        for port in ports:
            port_name = port.device
            # Filtrar puertos válidos
            if self._is_valid_port(port_name):
                valid_ports.append(port_name)
                
        return valid_ports
    
    def _is_valid_port(self, port_name):
        # Determina si un puerto es válido
        if port_name.startswith('COM') and len(port_name) > 3:
            try:
                com_num = int(port_name[3:])
                return 1 <= com_num <= 256
            except:
                return False
        elif port_name.startswith('/dev/tty'):
            return True
        return False
    
    def _verify_connection(self):
        # Verifica que la conexión es válida
        try:
            # Esperar por heartbeat
            start_time = time.time()
            while time.time() - start_time < 5:  # Timeout de 5 segundos
                msg = self.master.recv_match(blocking=False)
                if msg and msg.get_type() == 'HEARTBEAT':
                    return True
                time.sleep(0.1)
            return False
        except:
            return False
    
    def _start_data_thread(self):
        # Inicia hilo para recibir datos MAVLink 
        self.data_thread = threading.Thread(target=self._data_loop, daemon=True)
        self.data_thread.start()
    
    def _data_loop(self):
        # Loop principal para recibir datos 
        while self.connected:
            try:
                msg = self.master.recv_match(blocking=False, timeout=1.0)
                if msg:
                    self._process_message(msg)
                time.sleep(0.01)
            except Exception as e:
                print(f"Error en data_loop: {e}")
                time.sleep(1)
    
    def _process_message(self, msg):
        # Procesamiento de mensajes 
        with self.data_lock:
            msg_type = msg.get_type()
            
            if msg_type == 'GLOBAL_POSITION_INT':
                # Obtener lat/lon locales
                lat = msg.lat / 1e7
                lon = msg.lon / 1e7
                self.latest_data['lat'] = lat
                self.latest_data['lon'] = lon
                self.latest_data['altitude'] = msg.alt / 1000.0  # metros
                # Calculo de la velocidad 
                self._calculate_speed_from_position(lat, lon)
                
            elif msg_type == 'SYS_STATUS':
                if hasattr(msg, 'battery_remaining'):
                    self.latest_data['battery'] = msg.battery_remaining
                    
            elif msg_type == 'GPS_RAW_INT':
                self.latest_data['satellites'] = msg.satellites_visible
                self.latest_data['gps_fix'] = msg.fix_type
                
            elif msg_type == 'HEARTBEAT':
                self.latest_data['last_heartbeat'] = time.time()

    def get_latest_data(self):
        # Obtiene los datos más recientes 
        with self.data_lock:
            return self.latest_data.copy()
    
    def is_verified(self):
        # Verifica si la conexión es válida 
        return self.connected and self.master is not None
   

    def save_to_csv(self, filename="mavlink_data.csv"):
        
        fieldnames = list(self.latest_data.keys())

        try:
            # Verificar si el archivo ya existe
            file_exists = False
            try:
                with open(filename, "r", newline="") as f:
                    file_exists = True
            except FileNotFoundError:
                file_exists = False

            # Abrir archivo en modo append
            with open(filename, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                # Si es la primera vez, escribir encabezados
                if not file_exists:
                    writer.writeheader()

                # Escribir fila con los datos actuales
                writer.writerow(self.latest_data)

            print(f"Datos guardados en {filename}")

        except Exception as e:
            print(f"Error guardando CSV: {e}")

    def get_vehicle_info(self):
        # Obtiene información del vehículo
        return {
            'vehicle_type': 'Pixhawk',
            'port': self.port,
            'baud': self.baud,
            'connected': self.connected
        }

    def _calculate_speed_from_position(self, lat, lon):
        # Calcula velocidad estimada desde cambio de coordenadas (m/s) 
        current_time = time.time()
        
        if 'last_pos' in self.latest_data and 'last_time' in self.latest_data:
            lat_prev, lon_prev = self.latest_data['last_pos']
            time_prev = self.latest_data['last_time']
            dt = current_time - time_prev
            
            if dt > 0.1:  # Evitar divisiones por cero
                # Calculos aproximados para una velocidad tentativa
                # 1 grado ≈ 111 km = 111000 metros
                x = (lat - lat_prev) * 111000  # metros
                y = (lon - lon_prev) * 111000 * math.cos(math.radians(lat))  # metros

                distance = math.sqrt(x**2 + y**2)  # metros
                self.latest_data['speed'] = distance / dt  # m/s
            self.latest_data['last_pos'] = (lat, lon)
            self.latest_data['last_time'] = current_time

    def close(self):
        # Cierra la conexión
        self.connected = False
        if self.master:
            try:
                self.master.close()
            except:
                pass
