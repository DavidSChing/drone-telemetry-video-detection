# -*- coding: utf-8 -*-
"""
ESP32-CAM Scanner - Diagnóstico de Conexión y Calidad de Señal
Herramienta especializada para diagnosticar ESP32-CAM en la red WiFi
"""

import subprocess
import re
import time
import requests
import socket
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from collections import deque
import threading

class ESP32Scanner:
    """Escáner y diagnóstico para ESP32-CAM"""
    
    def __init__(self, esp32_ip="10.100.224.178", stream_port=81):
        self.esp32_ip = esp32_ip
        self.stream_url = f"http://{esp32_ip}:{stream_port}/stream"
        self.stream_port = stream_port
        self.monitoring = False
        
    def change_ip(self, new_ip):
        """Cambia la IP del ESP32 a monitorear"""
        self.esp32_ip = new_ip
        self.stream_url = f"http://{new_ip}:{self.stream_port}/stream"
        print(f"✅ IP cambiada a: {new_ip}")
    
    def ping_esp32(self, count=4):
        """Hace ping al ESP32 y retorna estadísticas"""
        print(f"\n📡 Haciendo ping a {self.esp32_ip}...")
        
        try:
            # Comando ping para Windows
            cmd = f"ping -n {count} {self.esp32_ip}"
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='latin-1')
            
            output = result.stdout
            
            # Parsear resultados
            stats = {
                'packets_sent': count,
                'packets_received': 0,
                'packet_loss': 100.0,
                'min_ms': None,
                'max_ms': None,
                'avg_ms': None
            }
            
            # Extraer paquetes recibidos
            received_match = re.search(r'Recibidos = (\d+)|Received = (\d+)', output)
            if received_match:
                stats['packets_received'] = int(received_match.group(1) or received_match.group(2))
            
            # Calcular pérdida
            if stats['packets_sent'] > 0:
                stats['packet_loss'] = ((stats['packets_sent'] - stats['packets_received']) / stats['packets_sent']) * 100
            
            # Extraer tiempos (mínimo, máximo, promedio)
            time_match = re.search(r'Mínimo = (\d+)ms, Máximo = (\d+)ms, Promedio = (\d+)ms|Minimum = (\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms', output)
            if time_match:
                if time_match.group(1):  # Español
                    stats['min_ms'] = int(time_match.group(1))
                    stats['max_ms'] = int(time_match.group(2))
                    stats['avg_ms'] = int(time_match.group(3))
                else:  # Inglés
                    stats['min_ms'] = int(time_match.group(4))
                    stats['max_ms'] = int(time_match.group(5))
                    stats['avg_ms'] = int(time_match.group(6))
            
            # Imprimir resultados
            print("-" * 60)
            if stats['packets_received'] > 0:
                print(f"✅ Respuesta: {stats['packets_received']}/{stats['packets_sent']} paquetes recibidos")
                print(f"📊 Pérdida: {stats['packet_loss']:.1f}%")
                if stats['avg_ms']:
                    print(f"⏱️  Latencia: Min={stats['min_ms']}ms | Avg={stats['avg_ms']}ms | Max={stats['max_ms']}ms")
                    
                    # Evaluación
                    if stats['avg_ms'] < 10:
                        quality = "🟢 EXCELENTE"
                    elif stats['avg_ms'] < 50:
                        quality = "🟢 BUENA"
                    elif stats['avg_ms'] < 100:
                        quality = "🟡 REGULAR"
                    elif stats['avg_ms'] < 200:
                        quality = "🟠 ALTA"
                    else:
                        quality = "🔴 MUY ALTA"
                    
                    print(f"💡 Calidad de conexión: {quality}")
            else:
                print(f"❌ Sin respuesta del ESP32 ({self.esp32_ip})")
                print(f"   Verifica:")
                print(f"   - El ESP32 está encendido")
                print(f"   - La IP es correcta")
                print(f"   - Ambos están en la misma red")
            print("-" * 60)
            
            return stats
            
        except Exception as e:
            print(f"❌ Error en ping: {e}")
            return None
    
    def test_http_connection(self):
        """Prueba la conexión HTTP al stream del ESP32"""
        print(f"\n🌐 Probando conexión HTTP a {self.stream_url}...")
        
        try:
            start_time = time.time()
            response = requests.get(self.stream_url, timeout=10, stream=True)
            connect_time = (time.time() - start_time) * 1000  # ms
            
            print("-" * 60)
            print(f"✅ Conexión HTTP exitosa")
            print(f"📊 Status Code: {response.status_code}")
            print(f"⏱️  Tiempo de conexión: {connect_time:.0f}ms")
            print(f"📄 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            
            # Evaluar tiempo de conexión
            if connect_time < 100:
                quality = "🟢 EXCELENTE"
            elif connect_time < 300:
                quality = "🟢 BUENA"
            elif connect_time < 500:
                quality = "🟡 REGULAR"
            else:
                quality = "🔴 LENTA"
            
            print(f"💡 Velocidad de conexión: {quality}")
            print("-" * 60)
            
            response.close()
            return True
            
        except requests.exceptions.Timeout:
            print("❌ Timeout: El ESP32 no responde en 10 segundos")
            return False
        except requests.exceptions.ConnectionError:
            print(f"❌ Error de conexión: No se puede alcanzar {self.stream_url}")
            print("   Verifica que el ESP32 esté transmitiendo en el puerto correcto")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def measure_throughput(self, duration_sec=10):
        """Mide el throughput del stream del ESP32"""
        print(f"\n📊 Midiendo throughput durante {duration_sec} segundos...")
        
        try:
            response = requests.get(self.stream_url, timeout=5, stream=True)
            
            start_time = time.time()
            total_bytes = 0
            chunk_count = 0
            
            print("Descargando datos...", end='', flush=True)
            
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    total_bytes += len(chunk)
                    chunk_count += 1
                
                elapsed = time.time() - start_time
                if elapsed >= duration_sec:
                    break
                
                # Progress indicator
                if chunk_count % 50 == 0:
                    print(".", end='', flush=True)
            
            response.close()
            elapsed_time = time.time() - start_time
            
            # Calcular métricas
            total_mb = total_bytes / (1024 * 1024)
            throughput_mbps = (total_bytes * 8) / (elapsed_time * 1_000_000)  # Mbps
            throughput_kbps = throughput_mbps * 1000
            fps_estimate = chunk_count / elapsed_time  # Aproximado
            
            print("\n")
            print("-" * 60)
            print("📊 RESULTADOS DEL TEST DE THROUGHPUT:")
            print(f"   Duración: {elapsed_time:.2f} segundos")
            print(f"   Datos descargados: {total_mb:.2f} MB ({total_bytes:,} bytes)")
            print(f"   Chunks recibidos: {chunk_count}")
            print(f"   Throughput: {throughput_mbps:.2f} Mbps ({throughput_kbps:.0f} Kbps)")
            print(f"   FPS estimado: {fps_estimate:.1f} frames/s")
            
            # Evaluación
            if throughput_mbps >= 2.0:
                quality = "🟢 EXCELENTE - Stream fluido"
            elif throughput_mbps >= 1.0:
                quality = "🟢 BUENO - Stream estable"
            elif throughput_mbps >= 0.5:
                quality = "🟡 REGULAR - Posibles interrupciones"
            else:
                quality = "🔴 BAJO - Stream con problemas"
            
            print(f"   Calidad: {quality}")
            print("-" * 60)
            
            return {
                'total_bytes': total_bytes,
                'duration': elapsed_time,
                'throughput_mbps': throughput_mbps,
                'fps_estimate': fps_estimate
            }
            
        except Exception as e:
            print(f"\n❌ Error en test de throughput: {e}")
            return None
    
    def get_wifi_signal_strength(self):
        """
        Obtiene la intensidad de señal WiFi del ESP32
        Nota: Esto requiere que estés conectado a la misma red que el ESP32
        """
        print(f"\n📡 Obteniendo información de señal WiFi...")
        
        try:
            # Obtener info de la red conectada
            cmd = "netsh wlan show interfaces"
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='latin-1')
            
            if result.returncode != 0:
                print("❌ No se pudo obtener información WiFi")
                return None
            
            output = result.stdout
            
            # Extraer información
            info = {}
            
            # SSID
            ssid_match = re.search(r'SSID\s*:\s*(.+)', output)
            if ssid_match:
                info['ssid'] = ssid_match.group(1).strip()
            
            # Señal
            signal_match = re.search(r'(Señal|Signal)\s*:\s*(\d+)%', output)
            if signal_match:
                signal_percent = int(signal_match.group(2))
                rssi_dbm = -90 + (signal_percent * 0.6)
                info['signal_percent'] = signal_percent
                info['rssi_dbm'] = int(rssi_dbm)
            
            # Canal
            channel_match = re.search(r'(Canal|Channel)\s*:\s*(\d+)', output)
            if channel_match:
                info['channel'] = int(channel_match.group(2))
            
            # Velocidad
            rx_match = re.search(r'(Velocidad de recepción|Receive rate)\s*\(Mbps\)\s*:\s*([\d.]+)', output)
            if rx_match:
                info['rx_rate_mbps'] = float(rx_match.group(2))
            
            tx_match = re.search(r'(Velocidad de transmisión|Transmit rate)\s*\(Mbps\)\s*:\s*([\d.]+)', output)
            if tx_match:
                info['tx_rate_mbps'] = float(tx_match.group(2))
            
            # Tipo de radio (banda)
            radio_match = re.search(r'(Tipo de radio|Radio type)\s*:\s*(.+)', output)
            if radio_match:
                radio = radio_match.group(2).strip()
                info['radio_type'] = radio
                
                # Detectar banda basado en canal
                if 'channel' in info:
                    if info['channel'] <= 14:
                        info['band'] = '2.4GHz'
                    else:
                        info['band'] = '5GHz'
            
            if info:
                print("-" * 60)
                print("🔗 INFORMACIÓN DE CONEXIÓN WiFi:")
                print(f"   Red: {info.get('ssid', 'N/A')}")
                print(f"   Banda: {info.get('band', 'N/A')}")
                print(f"   Canal: {info.get('channel', 'N/A')}")
                print(f"   Señal: {info.get('signal_percent', 0)}% ({info.get('rssi_dbm', -90)} dBm)")
                print(f"   Velocidad RX: {info.get('rx_rate_mbps', 0):.1f} Mbps")
                print(f"   Velocidad TX: {info.get('tx_rate_mbps', 0):.1f} Mbps")
                
                # Evaluación
                signal = info.get('rssi_dbm', -90)
                if signal >= -50:
                    quality = "🟢 EXCELENTE"
                    recommendation = "Señal óptima para streaming"
                elif signal >= -60:
                    quality = "🟢 BUENA"
                    recommendation = "Señal adecuada"
                elif signal >= -70:
                    quality = "🟡 REGULAR"
                    recommendation = "Puede tener interrupciones ocasionales"
                elif signal >= -80:
                    quality = "🟠 DÉBIL"
                    recommendation = "Se recomienda acercar ESP32 al router"
                else:
                    quality = "🔴 MUY DÉBIL"
                    recommendation = "¡CRÍTICO! Acercar ESP32 urgentemente"
                
                print(f"\n   Calidad de señal: {quality}")
                print(f"   💡 {recommendation}")
                
                # Advertencias específicas para ESP32
                if info.get('band') == '5GHz':
                    print(f"\n   ⚠️  ADVERTENCIA: Estás en 5GHz")
                    print(f"      El ESP32-CAM solo soporta 2.4GHz")
                    print(f"      Verifica que el ESP32 esté en una red 2.4GHz")
                
                print("-" * 60)
            
            return info
            
        except Exception as e:
            print(f"❌ Error al obtener señal WiFi: {e}")
            return None
    
    def find_esp32_in_network(self, base_ip="10.100.224", start=1, end=254):
        """
        Escanea la red local buscando el ESP32-CAM
        Advertencia: Puede tomar varios minutos
        """
        print(f"\n🔍 Buscando ESP32-CAM en la red {base_ip}.{start}-{end}...")
        print("⚠️  Esto puede tomar varios minutos...\n")
        
        found_devices = []
        
        for i in range(start, end + 1):
            ip = f"{base_ip}.{i}"
            
            # Progress indicator
            if i % 10 == 0:
                print(f"Escaneando: {ip}...", end='\r')
            
            try:
                # Ping rápido (1 segundo timeout)
                cmd = f"ping -n 1 -w 1000 {ip}"
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='latin-1')
                
                if "TTL=" in result.stdout or "TTL =" in result.stdout:
                    # Dispositivo responde, intentar conexión HTTP
                    try:
                        response = requests.get(f"http://{ip}:{self.stream_port}/stream", timeout=2, stream=True)
                        response.close()
                        
                        print(f"✅ ESP32-CAM encontrado en {ip}                    ")
                        found_devices.append(ip)
                        
                    except:
                        pass  # No es un ESP32-CAM
            
            except:
                pass
        
        print("\n" + "-" * 60)
        if found_devices:
            print(f"🎯 {len(found_devices)} ESP32-CAM encontrado(s):")
            for device in found_devices:
                print(f"   - {device}")
        else:
            print("❌ No se encontraron dispositivos ESP32-CAM")
            print("   Verifica:")
            print("   - El rango de IP es correcto")
            print("   - El ESP32 está encendido y conectado a la red")
            print("   - El puerto de stream es el correcto (default: 81)")
        print("-" * 60)
        
        return found_devices
    
    def monitor_connection_realtime(self, duration_sec=60, interval_sec=2):
        """Monitorea la conexión al ESP32 en tiempo real"""
        print(f"\n📊 Monitoreando conexión a ESP32 ({self.esp32_ip}) por {duration_sec} segundos...")
        print("Presiona Ctrl+C para detener\n")
        
        timestamps = []
        ping_times = []
        packet_loss = []
        
        try:
            start_time = time.time()
            iteration = 0
            
            while time.time() - start_time < duration_sec:
                # Ping al ESP32
                cmd = f"ping -n 1 {self.esp32_ip}"
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='latin-1')
                
                current_time = time.time() - start_time
                timestamps.append(current_time)
                
                # Parsear resultado
                time_match = re.search(r'tiempo[<=](\d+)ms|time[<=](\d+)ms', result.stdout)
                if time_match:
                    ping_ms = int(time_match.group(1) or time_match.group(2))
                    ping_times.append(ping_ms)
                    packet_loss.append(0)
                    status = "✅"
                else:
                    ping_times.append(None)
                    packet_loss.append(100)
                    ping_ms = None
                    status = "❌"
                
                # Imprimir estado
                ping_str = f"{ping_ms}ms" if ping_ms else "TIMEOUT"
                print(f"[{current_time:6.1f}s] {status} Ping: {ping_str:>10}")
                
                iteration += 1
                time.sleep(interval_sec)
            
            # Estadísticas finales
            valid_pings = [p for p in ping_times if p is not None]
            total_loss = sum(packet_loss) / len(packet_loss)
            
            print("\n" + "="*60)
            print("📊 ESTADÍSTICAS DEL MONITOREO")
            print("="*60)
            print(f"Duración: {timestamps[-1]:.1f} segundos")
            print(f"Pings enviados: {len(ping_times)}")
            print(f"Pings exitosos: {len(valid_pings)}")
            print(f"Pérdida de paquetes: {total_loss:.1f}%")
            
            if valid_pings:
                print(f"\nLatencia (ms):")
                print(f"  Promedio: {np.mean(valid_pings):.1f} ms")
                print(f"  Mínima: {np.min(valid_pings)} ms")
                print(f"  Máxima: {np.max(valid_pings)} ms")
                print(f"  Desviación: {np.std(valid_pings):.2f} ms")
                
                # Evaluación
                avg_ping = np.mean(valid_pings)
                if avg_ping < 10 and total_loss < 1:
                    quality = "🟢 EXCELENTE - Conexión muy estable"
                elif avg_ping < 50 and total_loss < 5:
                    quality = "🟢 BUENA - Conexión estable"
                elif avg_ping < 100 and total_loss < 10:
                    quality = "🟡 REGULAR - Conexión aceptable"
                elif avg_ping < 200 and total_loss < 20:
                    quality = "🟠 DÉBIL - Conexión inestable"
                else:
                    quality = "🔴 CRÍTICA - Conexión muy inestable"
                
                print(f"\n💡 Calidad de conexión: {quality}")
            
            print("="*60 + "\n")
            
            # Graficar
            self._plot_monitoring_results(timestamps, ping_times, packet_loss)
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Monitoreo interrumpido por el usuario")
            if ping_times:
                self._plot_monitoring_results(timestamps, ping_times, packet_loss)
    
    def _plot_monitoring_results(self, timestamps, ping_times, packet_loss):
        """Grafica los resultados del monitoreo"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # Latencia
        valid_times = [t if t is not None else 0 for t in ping_times]
        colors = ['green' if t is not None else 'red' for t in ping_times]
        
        ax1.scatter(timestamps, valid_times, c=colors, s=50, alpha=0.6)
        ax1.plot(timestamps, valid_times, linewidth=1, alpha=0.3, color='blue')
        ax1.set_ylabel('Latencia (ms)', fontsize=12)
        ax1.set_title('Monitoreo de Latencia al ESP32-CAM', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=100, color='orange', linestyle='--', alpha=0.7, label='Umbral Alto (100ms)')
        ax1.legend()
        
        # Pérdida de paquetes acumulada
        cumulative_loss = np.cumsum(packet_loss) / np.arange(1, len(packet_loss) + 1)
        ax2.plot(timestamps, cumulative_loss, linewidth=2, color='red')
        ax2.fill_between(timestamps, cumulative_loss, 0, alpha=0.3, color='red')
        ax2.set_xlabel('Tiempo (segundos)', fontsize=12)
        ax2.set_ylabel('Pérdida de Paquetes (%)', fontsize=12)
        ax2.set_title('Pérdida de Paquetes Acumulada', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 100)
        
        plt.tight_layout()
        plt.show()
    
    def full_diagnostic(self):
        """Ejecuta un diagnóstico completo del ESP32"""
        print("\n" + "="*70)
        print("🔧 DIAGNÓSTICO COMPLETO ESP32-CAM")
        print("="*70)
        print(f"IP: {self.esp32_ip}")
        print(f"Stream URL: {self.stream_url}")
        print("="*70)
        
        results = {}
        
        # Test 1: Ping
        print("\n[1/5] Test de Ping...")
        results['ping'] = self.ping_esp32(count=10)
        time.sleep(1)
        
        # Test 2: Conexión HTTP
        print("\n[2/5] Test de Conexión HTTP...")
        results['http'] = self.test_http_connection()
        time.sleep(1)
        
        # Test 3: Señal WiFi
        print("\n[3/5] Información de Señal WiFi...")
        results['wifi_signal'] = self.get_wifi_signal_strength()
        time.sleep(1)
        
        # Test 4: Throughput
        print("\n[4/5] Test de Throughput...")
        results['throughput'] = self.measure_throughput(duration_sec=10)
        time.sleep(1)
        
        # Test 5: Monitoreo breve
        print("\n[5/5] Monitoreo de Estabilidad (20 segundos)...")
        self.monitor_connection_realtime(duration_sec=20, interval_sec=1)
        
        # Resumen final
        print("\n" + "="*70)
        print("📋 RESUMEN DEL DIAGNÓSTICO")
        print("="*70)
        
        # Conectividad
        if results['ping'] and results['ping']['packets_received'] > 0:
            print("✅ Conectividad: OK")
        else:
            print("❌ Conectividad: FALLO")
        
        # HTTP
        if results['http']:
            print("✅ Stream HTTP: OK")
        else:
            print("❌ Stream HTTP: FALLO")
        
        # Señal WiFi
        if results['wifi_signal']:
            signal = results['wifi_signal'].get('rssi_dbm', -90)
            if signal >= -70:
                print(f"✅ Señal WiFi: BUENA ({signal} dBm)")
            else:
                print(f"⚠️  Señal WiFi: DÉBIL ({signal} dBm)")
        
        # Throughput
        if results['throughput']:
            mbps = results['throughput']['throughput_mbps']
            if mbps >= 1.0:
                print(f"✅ Throughput: BUENO ({mbps:.2f} Mbps)")
            else:
                print(f"⚠️  Throughput: BAJO ({mbps:.2f} Mbps)")
        
        print("="*70 + "\n")


def main():
    """Función principal con menú interactivo"""
    
    # Configuración inicial
    print("\n" + "="*70)
    print("🔧 ESP32-CAM SCANNER - Diagnóstico de Conexión")
    print("="*70)
    
    # Pedir IP del ESP32
    print("\nIPs comunes:")
    print("  1. RedPUCP: 10.100.224.178")
    print("  2. iPhone Hotspot: 172.20.10.2")
    print("  3. Otra IP")
    
    opcion_ip = input("\nSelecciona la red (1-3): ").strip()
    
    if opcion_ip == '1':
        esp32_ip = "10.100.224.178"
    elif opcion_ip == '2':
        esp32_ip = "172.20.10.2"
    else:
        esp32_ip = input("Ingresa la IP del ESP32-CAM: ").strip()
    
    scanner = ESP32Scanner(esp32_ip)
    
    while True:
        print("\n" + "="*70)
        print(f"🔧 ESP32-CAM SCANNER - IP: {scanner.esp32_ip}")
        print("="*70)
        print("\nOpciones:")
        print("  1. 🏥 Diagnóstico completo (recomendado)")
        print("  2. 📡 Ping al ESP32")
        print("  3. 🌐 Test de conexión HTTP")
        print("  4. 📊 Test de throughput")
        print("  5. 📶 Información de señal WiFi")
        print("  6. 📈 Monitoreo en tiempo real")
        print("  7. 🔍 Buscar ESP32 en la red (lento)")
        print("  8. 🔄 Cambiar IP del ESP32")
        print("  9. ❌ Salir")
        print("-"*70)
        
        opcion = input("\nSelecciona una opción (1-9): ").strip()
        
        if opcion == '1':
            scanner.full_diagnostic()
        
        elif opcion == '2':
            count = input("Número de pings (default: 4): ").strip()
            count = int(count) if count else 4
            scanner.ping_esp32(count)
        
        elif opcion == '3':
            scanner.test_http_connection()
        
        elif opcion == '4':
            duration = input("Duración del test en segundos (default: 10): ").strip()
            duration = int(duration) if duration else 10
            scanner.measure_throughput(duration)
        
        elif opcion == '5':
            scanner.get_wifi_signal_strength()
        
        elif opcion == '6':
            duration = input("Duración del monitoreo en segundos (default: 60): ").strip()
            duration = int(duration) if duration else 60
            interval = input("Intervalo entre muestras en segundos (default: 2): ").strip()
            interval = int(interval) if interval else 2
            scanner.monitor_connection_realtime(duration, interval)
        
        elif opcion == '7':
            base = input("Base de IP (default: 10.100.224): ").strip()
            base = base if base else "10.100.224"
            scanner.find_esp32_in_network(base)
        
        elif opcion == '8':
            new_ip = input("Nueva IP del ESP32: ").strip()
            scanner.change_ip(new_ip)
        
        elif opcion == '9':
            print("\n👋 ¡Hasta luego!\n")
            break
        
        else:
            print("\n❌ Opción inválida. Intenta de nuevo.")


if __name__ == "__main__":
    main()
