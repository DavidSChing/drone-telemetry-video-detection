# -*- coding: utf-8 -*-
"""
Network Analyzer - Análisis de Señales WiFi
Analiza todas las redes WiFi visibles desde la laptop
Detecta congestión, interferencias y calidad de señal
"""

import subprocess
import re
import time
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

class WiFiAnalyzer:
    """Analizador de señales WiFi para Windows"""
    
    def __init__(self):
        self.networks = {}
        self.channel_usage = defaultdict(list)
        self.scan_history = []
        
    def scan_networks(self):
        """Escanea todas las redes WiFi disponibles usando netsh"""
        try:
            # Ejecutar comando netsh para escanear redes
            cmd = "netsh wlan show networks mode=bssid"
            # Usar cp850 (DOS Latin 1) que es la codificación de cmd en español
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='cp850')
            
            if result.returncode != 0:
                print("❌ Error al escanear redes WiFi")
                return []
            
            return self._parse_netsh_output(result.stdout)
            
        except Exception as e:
            print(f"❌ Error en scan_networks: {e}")
            return []
    
    def _parse_netsh_output(self, output):
        """Parsea la salida de netsh wlan show networks"""
        networks = []
        current_ssid = None
        current_bssid_data = None
        
        lines = output.split('\n')
        
        for line in lines:
            original_line = line
            line = line.strip()
            
            # SSID - Inicio de nueva red
            if line.startswith('SSID'):
                ssid_match = re.search(r'SSID \d+ : (.+)', line)
                if ssid_match:
                    # Guardar BSSID anterior si existe
                    if current_bssid_data and 'bssid' in current_bssid_data and current_ssid:
                        network_entry = {'ssid': current_ssid}
                        network_entry.update(current_bssid_data)
                        networks.append(network_entry)
                    
                    current_ssid = ssid_match.group(1).strip()
                    current_bssid_data = None  # Reset para nueva red
            
            # Tipo de red
            elif ('Tipo de red' in line or 'Network type' in line) and current_bssid_data is not None:
                match = re.search(r':\s*(.+)', line)
                if match:
                    current_bssid_data['type'] = match.group(1).strip()
            
            # Autenticación
            elif ('Autenticación' in line or 'Authentication' in line) and current_bssid_data is not None:
                match = re.search(r':\s*(.+)', line)
                if match:
                    current_bssid_data['auth'] = match.group(1).strip()
            
            # Cifrado
            elif ('Cifrado' in line or 'Encryption' in line) and current_bssid_data is not None:
                match = re.search(r':\s*(.+)', line)
                if match:
                    current_bssid_data['encryption'] = match.group(1).strip()
            
            # BSSID - Inicio de nuevo punto de acceso
            elif 'BSSID' in line:
                # Guardar BSSID anterior si existe
                if current_bssid_data and 'bssid' in current_bssid_data and current_ssid:
                    network_entry = {'ssid': current_ssid}
                    network_entry.update(current_bssid_data)
                    networks.append(network_entry)
                
                # Iniciar nuevo BSSID
                match = re.search(r'BSSID \d+\s*:\s*(.+)', line)
                if match:
                    current_bssid_data = {'bssid': match.group(1).strip()}
            
            # Señal - buscar líneas con % que no sean "Uso del canal" ni "Mbps"
            elif '%' in line and 'Uso del canal' not in line and 'Mbps' not in line and current_bssid_data is not None:
                # La línea puede ser "         Señal             : 20%" o "         Se├▒al             : 20%"
                match = re.search(r'(\d+)\s*%', line)
                if match:
                    signal_percent = int(match.group(1))
                    # Convertir % a dBm aproximado
                    # 100% ≈ -30dBm, 0% ≈ -90dBm
                    rssi_dbm = -90 + (signal_percent * 0.6)
                    current_bssid_data['signal_percent'] = signal_percent
                    current_bssid_data['rssi_dbm'] = int(rssi_dbm)
            
            # Banda - Extraer 2.4 o 5 GHz
            elif ('Banda' in line or 'Band' in line) and current_bssid_data is not None:
                if '2,4 GHz' in line or '2.4 GHz' in line:
                    current_bssid_data['band'] = '2.4GHz'
                elif '5 GHz' in line:
                    current_bssid_data['band'] = '5GHz'
            
            # Canal
            elif ('Canal' in line or 'Channel' in line) and current_bssid_data is not None:
                # Evitar líneas de "Uso del canal"
                if 'Uso del canal' not in line and 'channel usage' not in line.lower():
                    match = re.search(r':\s*(\d+)', line)
                    if match:
                        current_bssid_data['channel'] = int(match.group(1))
        
        # Agregar el último BSSID si existe
        if current_bssid_data and 'bssid' in current_bssid_data and current_ssid:
            network_entry = {'ssid': current_ssid}
            network_entry.update(current_bssid_data)
            networks.append(network_entry)
        
        # Post-procesamiento: inferir banda del canal si no está presente
        for net in networks:
            if 'band' not in net and 'channel' in net:
                ch = net['channel']
                if 1 <= ch <= 14:
                    net['band'] = '2.4GHz'
                elif ch >= 36:
                    net['band'] = '5GHz'
        
        return networks
    
    def get_connected_network_info(self):
        """Obtiene información detallada de la red WiFi conectada actualmente"""
        try:
            cmd = "netsh wlan show interfaces"
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='cp850')
            
            if result.returncode != 0:
                return None
            
            info = {}
            for line in result.stdout.split('\n'):
                line = line.strip()
                
                # SSID (evitar BSSID)
                if ('SSID' in line or 'ssid' in line.lower()) and 'BSSID' not in line and 'bssid' not in line.lower():
                    match = re.search(r':\s*(.+)', line)
                    if match:
                        ssid = match.group(1).strip()
                        if ssid:  # Evitar SSIDs vacíos
                            info['ssid'] = ssid
                
                # BSSID
                elif 'BSSID' in line:
                    match = re.search(r':\s*(.+)', line)
                    if match:
                        info['bssid'] = match.group(1).strip()
                
                # Canal
                elif 'Canal' in line or 'Channel' in line:
                    match = re.search(r':\s*(\d+)', line)
                    if match:
                        info['channel'] = int(match.group(1))
                
                # Señal - con espacios variables
                elif 'Señal' in line or 'Signal' in line:
                    match = re.search(r'(\d+)\s*%', line)
                    if match:
                        signal_percent = int(match.group(1))
                        rssi_dbm = -90 + (signal_percent * 0.6)
                        info['signal_percent'] = signal_percent
                        info['rssi_dbm'] = int(rssi_dbm)
                
                # Velocidad de recepción
                elif 'Velocidad de recepción' in line or 'Receive rate' in line:
                    match = re.search(r':\s*([\d.]+)', line)
                    if match:
                        info['rx_rate_mbps'] = float(match.group(1))
                
                # Velocidad de transmisión
                elif 'Velocidad de transmisión' in line or 'Transmit rate' in line:
                    match = re.search(r':\s*([\d.]+)', line)
                    if match:
                        info['tx_rate_mbps'] = float(match.group(1))
                
                # Tipo de radio
                elif 'Tipo de radio' in line or 'Radio type' in line:
                    match = re.search(r':\s*(.+)', line)
                    if match:
                        radio = match.group(1).strip()
                        info['radio_type'] = radio
                        # Detectar banda
                        if '802.11a' in radio or '802.11ac' in radio or '802.11ax' in radio:
                            # 802.11ax puede ser dual-band, usar canal
                            if 'channel' in info:
                                info['band'] = '2.4GHz' if info['channel'] <= 14 else '5GHz'
                            else:
                                info['band'] = '5GHz'
                        elif '802.11n' in radio or '802.11g' in radio or '802.11b' in radio:
                            # 802.11n puede ser 2.4 o 5GHz, usar canal
                            if 'channel' in info:
                                info['band'] = '2.4GHz' if info['channel'] <= 14 else '5GHz'
                            else:
                                info['band'] = '2.4GHz'
                        else:
                            info['band'] = 'Desconocida'
            
            return info if info else None
            
        except Exception as e:
            print(f"❌ Error al obtener info de red conectada: {e}")
            return None
    
    def analyze_24ghz_congestion(self, networks):
        """Analiza la congestión en canales 2.4GHz"""
        channel_count = defaultdict(int)
        channel_signals = defaultdict(list)
        
        for net in networks:
            if 'channel' in net and net['channel'] <= 14:  # 2.4GHz
                ch = net['channel']
                channel_count[ch] += 1
                if 'rssi_dbm' in net:
                    channel_signals[ch].append(net['rssi_dbm'])
        
        # Calcular congestión considerando solapamiento de canales
        # En 2.4GHz, cada canal afecta ±2 canales
        congestion = {}
        for ch in range(1, 14):
            total_networks = 0
            avg_signal = []
            
            for offset in range(-2, 3):  # Canales adyacentes
                neighbor_ch = ch + offset
                if neighbor_ch in channel_count:
                    # Peso mayor para canal exacto
                    weight = 1.0 if offset == 0 else 0.3
                    total_networks += channel_count[neighbor_ch] * weight
                    if neighbor_ch in channel_signals:
                        avg_signal.extend(channel_signals[neighbor_ch])
            
            congestion[ch] = {
                'networks': total_networks,
                'avg_rssi': int(np.mean(avg_signal)) if avg_signal else -90
            }
        
        return congestion
    
    def print_summary(self):
        """Imprime un resumen del análisis de redes"""
        print("\n" + "="*70)
        print("📡 ANÁLISIS DE SEÑALES WiFi - LAPTOP")
        print("="*70)
        
        # Red conectada actualmente
        connected = self.get_connected_network_info()
        if connected:
            print("\n🔗 RED CONECTADA ACTUALMENTE:")
            print(f"   SSID: {connected.get('ssid', 'N/A')}")
            print(f"   Canal: {connected.get('channel', 'N/A')}")
            print(f"   Banda: {connected.get('band', 'N/A')}")
            print(f"   Señal: {connected.get('signal_percent', 0)}% ({connected.get('rssi_dbm', -90)} dBm)")
            print(f"   RX: {connected.get('rx_rate_mbps', 0):.1f} Mbps | TX: {connected.get('tx_rate_mbps', 0):.1f} Mbps")
            
            # Evaluación de calidad
            signal = connected.get('rssi_dbm', -90)
            if signal >= -50:
                quality = "🟢 EXCELENTE"
            elif signal >= -60:
                quality = "🟢 BUENA"
            elif signal >= -70:
                quality = "🟡 REGULAR"
            elif signal >= -80:
                quality = "🟠 DÉBIL"
            else:
                quality = "🔴 MUY DÉBIL"
            
            print(f"   Calidad: {quality}")
        
        # Escanear todas las redes
        print("\n🔍 Escaneando redes WiFi...")
        networks = self.scan_networks()
        
        if not networks:
            print("❌ No se detectaron redes WiFi")
            return
        
        print(f"✅ {len(networks)} redes detectadas\n")
        
        # Separar por banda
        networks_24 = [n for n in networks if 'channel' in n and n['channel'] <= 14]
        networks_5 = [n for n in networks if 'channel' in n and n['channel'] > 14]
        
        print(f"📊 2.4GHz: {len(networks_24)} redes | 5GHz: {len(networks_5)} redes")
        
        # Análisis 2.4GHz
        if networks_24:
            print("\n" + "-"*70)
            print("📡 REDES 2.4GHz DETECTADAS (Ordenadas por señal)")
            print("-"*70)
            print(f"{'SSID':<25} {'Canal':>6} {'Señal':>8} {'RSSI':>8} {'Seguridad':<15}")
            print("-"*70)
            
            networks_24_sorted = sorted(networks_24, key=lambda x: x.get('signal_percent', 0), reverse=True)
            for net in networks_24_sorted[:15]:  # Top 15
                ssid = net.get('ssid', 'Oculta')[:24]
                channel = net.get('channel', '?')
                signal = net.get('signal_percent', 0)
                rssi = net.get('rssi_dbm', -90)
                auth = net.get('auth', 'N/A')[:14]
                
                print(f"{ssid:<25} {channel:>6} {signal:>7}% {rssi:>7} dBm {auth:<15}")
            
            # Análisis de congestión
            congestion = self.analyze_24ghz_congestion(networks_24)
            print("\n📊 CONGESTIÓN DE CANALES 2.4GHz:")
            print("-"*70)
            print("Canal | Redes | Señal Promedio | Estado")
            print("-"*70)
            
            # Canales recomendados: 1, 6, 11 (no se solapan)
            recommended = [1, 6, 11]
            for ch in recommended:
                if ch in congestion:
                    networks_count = congestion[ch]['networks']
                    avg_rssi = congestion[ch]['avg_rssi']
                    
                    if networks_count < 2:
                        status = "🟢 LIBRE"
                    elif networks_count < 4:
                        status = "🟡 MEDIO"
                    else:
                        status = "🔴 CONGESTIONADO"
                    
                    print(f"  {ch:>2}  | {networks_count:>5.1f} | {avg_rssi:>10} dBm    | {status}")
            
            # Mejor canal
            best_ch = min(recommended, key=lambda x: congestion.get(x, {'networks': 999})['networks'])
            print(f"\n💡 Mejor canal recomendado: {best_ch}")
        
        # Análisis 5GHz
        if networks_5:
            print("\n" + "-"*70)
            print("📡 REDES 5GHz DETECTADAS (Ordenadas por señal)")
            print("-"*70)
            print(f"{'SSID':<25} {'Canal':>6} {'Señal':>8} {'RSSI':>8}")
            print("-"*70)
            
            networks_5_sorted = sorted(networks_5, key=lambda x: x.get('signal_percent', 0), reverse=True)
            for net in networks_5_sorted[:10]:  # Top 10
                ssid = net.get('ssid', 'Oculta')[:24]
                channel = net.get('channel', '?')
                signal = net.get('signal_percent', 0)
                rssi = net.get('rssi_dbm', -90)
                
                print(f"{ssid:<25} {channel:>6} {signal:>7}% {rssi:>7} dBm")
        
        print("\n" + "="*70 + "\n")
    
    def plot_channel_usage(self):
        """Genera gráfico de uso de canales 2.4GHz"""
        networks = self.scan_networks()
        networks_24 = [n for n in networks if 'channel' in n and n['channel'] <= 14]
        
        if not networks_24:
            print("❌ No hay redes 2.4GHz para graficar")
            return
        
        congestion = self.analyze_24ghz_congestion(networks_24)
        
        channels = list(range(1, 14))
        networks_count = [congestion.get(ch, {'networks': 0})['networks'] for ch in channels]
        avg_signals = [congestion.get(ch, {'avg_rssi': -90})['avg_rssi'] for ch in channels]
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))
        
        # Gráfico 1: Número de redes por canal
        colors = ['green' if ch in [1, 6, 11] else 'orange' for ch in channels]
        bars = ax1.bar(channels, networks_count, color=colors, alpha=0.7, edgecolor='black')
        ax1.set_xlabel('Canal', fontsize=12)
        ax1.set_ylabel('Número de Redes (ponderado)', fontsize=12)
        ax1.set_title('Congestión de Canales 2.4GHz', fontsize=14, fontweight='bold')
        ax1.grid(axis='y', alpha=0.3)
        ax1.set_xticks(channels)
        
        # Destacar canales recomendados
        for i, ch in enumerate(channels):
            if ch in [1, 6, 11]:
                ax1.text(ch, networks_count[i] + 0.2, '★', ha='center', fontsize=16, color='green')
        
        # Gráfico 2: Señal promedio por canal
        ax2.plot(channels, avg_signals, marker='o', linewidth=2, markersize=8, color='blue')
        ax2.fill_between(channels, avg_signals, -90, alpha=0.3, color='blue')
        ax2.set_xlabel('Canal', fontsize=12)
        ax2.set_ylabel('Señal Promedio (dBm)', fontsize=12)
        ax2.set_title('Intensidad de Señal por Canal', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.set_xticks(channels)
        ax2.axhline(y=-70, color='orange', linestyle='--', label='Umbral Regular')
        ax2.axhline(y=-80, color='red', linestyle='--', label='Umbral Débil')
        ax2.legend()
        
        plt.tight_layout()
        plt.show()
    
    def monitor_signal_realtime(self, duration_sec=60, interval_sec=2):
        """Monitorea la señal de la red conectada en tiempo real"""
        print(f"\n📊 Monitoreando señal WiFi por {duration_sec} segundos...")
        print("Presiona Ctrl+C para detener\n")
        
        timestamps = []
        signals = []
        rx_rates = []
        tx_rates = []
        
        try:
            start_time = time.time()
            while time.time() - start_time < duration_sec:
                info = self.get_connected_network_info()
                
                if info:
                    current_time = time.time() - start_time
                    timestamps.append(current_time)
                    signals.append(info.get('rssi_dbm', -90))
                    rx_rates.append(info.get('rx_rate_mbps', 0))
                    tx_rates.append(info.get('tx_rate_mbps', 0))
                    
                    print(f"[{current_time:6.1f}s] "
                          f"Señal: {info.get('signal_percent', 0):>3}% ({info.get('rssi_dbm', -90):>3} dBm) | "
                          f"RX: {info.get('rx_rate_mbps', 0):>6.1f} Mbps | "
                          f"TX: {info.get('tx_rate_mbps', 0):>6.1f} Mbps")
                
                time.sleep(interval_sec)
            
            # Estadísticas finales
            if signals:
                print("\n" + "="*70)
                print("📊 ESTADÍSTICAS DEL MONITOREO")
                print("="*70)
                print(f"Duración: {timestamps[-1]:.1f} segundos")
                print(f"Muestras: {len(signals)}")
                print(f"\nSeñal (dBm):")
                print(f"  Promedio: {np.mean(signals):.1f} dBm")
                print(f"  Mínima: {np.min(signals)} dBm")
                print(f"  Máxima: {np.max(signals)} dBm")
                print(f"  Desviación: {np.std(signals):.2f} dBm")
                print(f"\nVelocidad RX (Mbps):")
                print(f"  Promedio: {np.mean(rx_rates):.1f} Mbps")
                print(f"  Mínima: {np.min(rx_rates):.1f} Mbps")
                print(f"  Máxima: {np.max(rx_rates):.1f} Mbps")
                print("="*70 + "\n")
                
                # Graficar
                self._plot_monitoring_results(timestamps, signals, rx_rates, tx_rates)
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Monitoreo interrumpido por el usuario")
            if signals:
                self._plot_monitoring_results(timestamps, signals, rx_rates, tx_rates)
    
    def _plot_monitoring_results(self, timestamps, signals, rx_rates, tx_rates):
        """Grafica los resultados del monitoreo"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # Señal
        ax1.plot(timestamps, signals, linewidth=2, color='blue', marker='o', markersize=4)
        ax1.fill_between(timestamps, signals, -90, alpha=0.3, color='blue')
        ax1.set_ylabel('Señal (dBm)', fontsize=12)
        ax1.set_title('Monitoreo de Señal WiFi en Tiempo Real', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=-70, color='orange', linestyle='--', alpha=0.7, label='Regular')
        ax1.axhline(y=-80, color='red', linestyle='--', alpha=0.7, label='Débil')
        ax1.legend()
        
        # Velocidades
        ax2.plot(timestamps, rx_rates, linewidth=2, color='green', marker='s', markersize=4, label='RX (Recepción)')
        ax2.plot(timestamps, tx_rates, linewidth=2, color='orange', marker='^', markersize=4, label='TX (Transmisión)')
        ax2.set_xlabel('Tiempo (segundos)', fontsize=12)
        ax2.set_ylabel('Velocidad (Mbps)', fontsize=12)
        ax2.set_title('Velocidad de Conexión', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        plt.show()


def main():
    """Función principal con menú interactivo"""
    analyzer = WiFiAnalyzer()
    
    while True:
        print("\n" + "="*70)
        print("🌐 ANALIZADOR DE SEÑALES WiFi - LAPTOP")
        print("="*70)
        print("\nOpciones:")
        print("  1. 📊 Análisis completo de redes WiFi")
        print("  2. 📈 Gráfico de congestión de canales 2.4GHz")
        print("  3. 📡 Monitoreo de señal en tiempo real (60s)")
        print("  4. 🔍 Info de red conectada")
        print("  5. ❌ Salir")
        print("-"*70)
        
        opcion = input("\nSelecciona una opción (1-5): ").strip()
        
        if opcion == '1':
            analyzer.print_summary()
        
        elif opcion == '2':
            analyzer.plot_channel_usage()
        
        elif opcion == '3':
            try:
                duration = input("Duración del monitoreo en segundos (default: 60): ").strip()
                duration = int(duration) if duration else 60
                interval = input("Intervalo entre muestras en segundos (default: 2): ").strip()
                interval = int(interval) if interval else 2
                analyzer.monitor_signal_realtime(duration, interval)
            except ValueError:
                print("❌ Valores inválidos, usando defaults (60s, intervalo 2s)")
                analyzer.monitor_signal_realtime(60, 2)
        
        elif opcion == '4':
            info = analyzer.get_connected_network_info()
            if info:
                print("\n🔗 RED CONECTADA:")
                for key, value in info.items():
                    print(f"   {key}: {value}")
            else:
                print("\n❌ No se pudo obtener información de la red conectada")
        
        elif opcion == '5':
            print("\n👋 ¡Hasta luego!\n")
            break
        
        else:
            print("\n❌ Opción inválida. Intenta de nuevo.")


if __name__ == "__main__":
    main()
