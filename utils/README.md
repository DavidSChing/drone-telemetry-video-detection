# 📡 Herramientas de Diagnóstico de Red WiFi

Esta carpeta contiene herramientas especializadas para diagnosticar conexiones WiFi y problemas de red, especialmente enfocadas en optimizar la conexión del ESP32-CAM.

## 📁 Archivos

### 1. `network_analyzer.py` - Analizador WiFi de Laptop
Analiza todas las señales WiFi visibles desde tu laptop.

**Funcionalidades:**
- ✅ Escaneo completo de redes 2.4GHz y 5GHz
- ✅ Medición de intensidad de señal (RSSI en dBm)
- ✅ Análisis de congestión de canales
- ✅ Recomendación de mejores canales
- ✅ Monitoreo en tiempo real de señal
- ✅ Gráficos de uso de canales

**Uso:**
```bash
python utils/network_analyzer.py
```

**Menú de Opciones:**
1. **Análisis completo** - Escanea y muestra todas las redes con análisis de congestión
2. **Gráfico de congestión** - Muestra gráfico visual de uso de canales 2.4GHz
3. **Monitoreo en tiempo real** - Monitorea señal y velocidad por 60 segundos
4. **Info de red conectada** - Muestra detalles de tu red actual
5. **Salir**

**Ejemplo de Salida:**
```
📡 REDES 2.4GHz DETECTADAS
SSID                      Canal   Señal     RSSI       Seguridad
redpucp                      1      86%   -38 dBm     WPA2-Personal
PUCP                         6      65%   -51 dBm     WPA2-Personal

📊 CONGESTIÓN DE CANALES 2.4GHz:
Canal | Redes | Señal Promedio | Estado
   1  |   5.2 |        -45 dBm | 🔴 CONGESTIONADO
   6  |   8.1 |        -52 dBm | 🔴 CONGESTIONADO
  11  |   1.3 |        -75 dBm | 🟢 LIBRE

💡 Mejor canal recomendado: 11
```

---

### 2. `esp32_scanner.py` - Diagnóstico ESP32-CAM
Herramienta especializada para diagnosticar la conexión del ESP32-CAM.

**Funcionalidades:**
- ✅ Ping test al ESP32
- ✅ Test de conexión HTTP al stream
- ✅ Medición de throughput (Mbps)
- ✅ Información de señal WiFi ESP32 ↔ Router
- ✅ Monitoreo de estabilidad de conexión
- ✅ Búsqueda automática de ESP32 en la red
- ✅ Diagnóstico completo automatizado

**Uso:**
```bash
python utils/esp32_scanner.py
```

**Configuración Rápida de IPs:**
- Opción 1: RedPUCP (10.100.224.178)
- Opción 2: iPhone Hotspot (172.20.10.2)
- Opción 3: IP personalizada

**Menú de Opciones:**
1. **Diagnóstico completo** - Ejecuta todos los tests automáticamente (⭐ Recomendado)
2. **Ping al ESP32** - Test básico de conectividad
3. **Test de conexión HTTP** - Verifica que el stream esté disponible
4. **Test de throughput** - Mide velocidad real del stream
5. **Información de señal WiFi** - Calidad de señal ESP32 ↔ Router
6. **Monitoreo en tiempo real** - Monitorea latencia y estabilidad
7. **Buscar ESP32 en la red** - Escanea la red buscando el ESP32 (lento)
8. **Cambiar IP** - Cambiar entre RedPUCP ↔ iPhone
9. **Salir**

**Ejemplo de Salida:**
```
🏥 DIAGNÓSTICO COMPLETO ESP32-CAM
IP: 10.100.224.178

[1/5] Test de Ping...
✅ Respuesta: 10/10 paquetes recibidos
⏱️  Latencia: Min=8ms | Avg=12ms | Max=25ms
💡 Calidad de conexión: 🟢 EXCELENTE

[2/5] Test de Conexión HTTP...
✅ Conexión HTTP exitosa
⏱️  Tiempo de conexión: 85ms
💡 Velocidad de conexión: 🟢 EXCELENTE

[3/5] Información de Señal WiFi...
🔗 INFORMACIÓN DE CONEXIÓN WiFi:
   Red: redpucp
   Banda: 2.4GHz ✅
   Canal: 1
   Señal: 86% (-38 dBm)
   Calidad de señal: 🟢 EXCELENTE
   💡 Señal óptima para streaming

[4/5] Test de Throughput...
📊 RESULTADOS:
   Throughput: 2.34 Mbps
   FPS estimado: 8.2 frames/s
   Calidad: 🟢 EXCELENTE - Stream fluido

[5/5] Monitoreo de Estabilidad...
[Gráfico de latencia en tiempo real]
```

---

## 📊 Interpretación de Resultados

### Señal WiFi (RSSI)
| RSSI (dBm) | Calidad | Descripción |
|------------|---------|-------------|
| -30 a -50 | 🟢 EXCELENTE | Óptimo para streaming HD |
| -50 a -60 | 🟢 BUENA | Adecuado para streaming |
| -60 a -70 | 🟡 REGULAR | Puede tener interrupciones |
| -70 a -80 | 🟠 DÉBIL | Problemas frecuentes |
| -80 a -90 | 🔴 MUY DÉBIL | ¡Crítico! Acercar ESP32 |

### Latencia (Ping)
| Latencia | Calidad | Descripción |
|----------|---------|-------------|
| < 10 ms | 🟢 EXCELENTE | Ideal |
| 10-50 ms | 🟢 BUENA | Aceptable |
| 50-100 ms | 🟡 REGULAR | Tolerable |
| 100-200 ms | 🟠 ALTA | Problemático |
| > 200 ms | 🔴 MUY ALTA | Crítico |

### Throughput
| Throughput | Calidad | Descripción |
|------------|---------|-------------|
| > 2 Mbps | 🟢 EXCELENTE | Stream fluido |
| 1-2 Mbps | 🟢 BUENO | Stream estable |
| 0.5-1 Mbps | 🟡 REGULAR | Posibles interrupciones |
| < 0.5 Mbps | 🔴 BAJO | Stream con problemas |

---

## 🎯 Casos de Uso Prácticos

### Caso 1: Optimizar Canal del Router
```bash
# 1. Analizar congestión
python utils/network_analyzer.py
> Opción 1: Análisis completo

# 2. Ver canal recomendado (ej: canal 11)
# 3. Cambiar router ESP32 o PUCP al canal recomendado
# 4. Repetir análisis para verificar mejora
```

### Caso 2: Diagnosticar Problemas de Latencia
```bash
# 1. Ejecutar diagnóstico completo ESP32
python utils/esp32_scanner.py
> Opción 1: Diagnóstico completo

# 2. Verificar:
#    - ¿Señal WiFi > -70 dBm? → Si no, acercar ESP32
#    - ¿Latencia > 100ms? → Problema de red
#    - ¿Throughput < 1 Mbps? → Revisar configuración ESP32
```

### Caso 3: Comparar Redes (iPhone vs PUCP)
```bash
# Terminal 1: Conectar laptop a iPhone hotspot
python utils/esp32_scanner.py
> IP: 172.20.10.2
> Opción 1: Diagnóstico completo
# [Anotar resultados]

# Terminal 2: Conectar laptop a RedPUCP
python utils/esp32_scanner.py
> IP: 10.100.224.178
> Opción 1: Diagnóstico completo
# [Comparar con iPhone]
```

### Caso 4: Monitoreo Durante Demostración
```bash
# Terminal 1: Sistema principal
cd "D:\PUCP\2025-2\PROYECTO DE DISEÑO MECATRÓNICO\Reconocimiento de personas"
python src/camera_stream.py

# Terminal 2: Monitoreo ESP32
python utils/esp32_scanner.py
> Opción 6: Monitoreo en tiempo real
> Duración: 600 (10 minutos)
# [Ver gráfico de estabilidad]
```

---

## 💡 Solución de Problemas Comunes

### Problema: "Señal 0% en todas las redes"
**Causa:** Problema de codificación de Windows  
**Solución:** Ya corregido en versión actual (usa `%` en lugar de palabra "Señal")

### Problema: "No se encuentra el ESP32"
**Pasos:**
1. Verificar que ESP32 esté encendido
2. Verificar IP correcta: `ipconfig` o ver serial del ESP32
3. Ping manual: `ping 10.100.224.178`
4. Usar opción 7 para buscar automáticamente

### Problema: "Señal débil (-80 dBm)"
**Soluciones:**
1. Acercar ESP32 al router
2. Cambiar a canal menos congestionado
3. Verificar que ESP32 use antena externa (si disponible)
4. Eliminar obstáculos metálicos entre ESP32 y router

### Problema: "Latencia alta (>200ms) pero señal buena"
**Causas posibles:**
1. Congestión de red (muchos dispositivos)
2. Firewall/proxy de universidad
3. QoS priorizando otro tráfico

**Soluciones:**
1. Cambiar canal del router
2. Solicitar puerto dedicado a DTI
3. Usar red de laboratorio en lugar de RedPUCP general

---

## 🔧 Requisitos

```bash
pip install matplotlib numpy requests
```

**Sistemas Operativos:**
- ✅ Windows 10/11 (probado)
- ❌ Linux (requiere adaptación - usar `iwlist`, `iw`)
- ❌ macOS (requiere adaptación - usar `airport`)

---

## 📚 Referencias

- [Optimización de Red](../OPTIMIZACION_RED.md) - Guía completa de optimización
- [ESP32-CAM Documentation](https://randomnerdtutorials.com/esp32-cam-video-streaming-face-recognition-arduino-ide/)
- [WiFi Analyzer Best Practices](https://www.metageek.com/training/resources/wifi-analyzer.html)

---

## 👤 Autor

Proyecto de Diseño Mecatrónico - PUCP 2025-2  
Sistema de Detección de Personas con ESP32-CAM

**Última actualización:** 17 de Octubre, 2025
