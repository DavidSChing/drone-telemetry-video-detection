# Drone Telemetry Video Detection
David estubo aquí.
# 🚁 Sistema Integrado de Detección de Personas y Telemetría de Drones

Sistema completo de monitoreo en tiempo real que combina **detección de personas** mediante ESP32-CAM con **telemetría de drones** vía radio MAVLink. Desarrollado como proyecto del curso ** Proyecto de Diseño Mecatrónico** en la Pontificia Universidad Católica del Perú - PUCP.

## ✨ Características Principales

### 🎥 Sistema de Visión
- 🎯 **Detección precisa** de personas usando YOLOv8n (modelo optimizado)
- 📹 **Streaming en tiempo real** desde ESP32-CAM
- 🔢 **Conteo y tracking** de personas con algoritmo de centroides
- ⚡ **Aceleración GPU** (NVIDIA CUDA) con fallback a CPU
- 🔄 **Suavizado de detecciones** para tracking estable

### 📡 Sistema de Telemetría (Próximamente)
- 🚁 **Integración MAVLink** con protocolo ArduPilot
- 📊 **Telemetría en tiempo real** desde radio Holybro 915MHz 100mW
- 🗺️ **Visualización de datos** de vuelo (altitud, velocidad, GPS, batería)
- 📈 **Interfaz unificada** con video y telemetría sincronizados
- 🔌 **Lectura directa** desde puerto serial del receptor de telemetría
- 📱 **Dashboard personalizado** sin depender de Mission Planner

### 🖥️ Interfaz de Usuario
- 📊 **Métricas en tiempo real**: FPS, latencia, RTT
- 🎨 **Visualización dual**: video procesado y original
- 🌐 **Optimización adaptativa** según tipo de red
- 📈 **Panel de telemetría** integrado en la interfaz principal

## 📸 Capturas de Pantalla

> _[Aquí se adjuntan imágenes del sistema funcionando con telemetría]_

## 🛠️ Tecnologías Utilizadas

### Visión por Computadora
- **Python 3.8+**
- **PyTorch** (con soporte CUDA)
- **Ultralytics YOLOv8**
- **OpenCV**
- **NumPy, Matplotlib**

### Telemetría de Drones
- **PyMAVLink** - Comunicación con protocolo MAVLink
- **PySerial** - Lectura de datos del radio receptor
- **ArduPilot/PX4** - Compatible con autopiloto
- **Holybro Telemetry Radio** 915MHz 100mW

### Hardware
- **ESP32-CAM** - Cámara WiFi para detección
- **Holybro Telemetry Radio** - Enlace de telemetría
- **Controladora de vuelo** compatible con MAVLink (Pixhawk, Cube, etc.)

## 🔌 Integración de Telemetría

### ¿Cómo funciona?

El sistema lee los datos de telemetría del dron directamente desde el **receptor Holybro** conectado por USB a la laptop, decodifica los mensajes **MAVLink** y los visualiza en la misma interfaz donde se muestra el video del ESP32-CAM.

↓
→ Dron (con radio TX) → Radio RX Holybro → USB → Python (PyMAVLink) → Interfaz
→ ESP32-CAM → WiFi → Python (OpenCV + YOLO) ─────────→ Interfaz


### Datos de Telemetría Disponibles

- **Posición GPS**: Latitud, Longitud, Altitud
- **Actitud**: Roll, Pitch, Yaw
- **Velocidad**: Ground speed, Airspeed
- **Batería**: Voltaje, Corriente, Porcentaje
- **Estado del sistema**: Modo de vuelo, Armado/Desarmado
- **Sensores**: Presión barométrica, Temperatura
- **Distancia Home**: Distancia y dirección al punto de despegue

## 📋 Requisitos del Sistema

### Hardware
- **ESP32-CAM** con módulo WiFi configurado
- **Radio de telemetría Holybro** 915MHz 100mW (o compatible)
- **Dron con autopiloto** compatible con MAVLink (ArduPilot, PX4)
- (Opcional) **GPU NVIDIA** con soporte CUDA
- **PC con Windows/Linux/Mac**

### Software
- Python 3.8 o superior
- CUDA Toolkit (opcional, para GPU)
- Drivers NVIDIA actualizados (si usas GPU)
- Mission Planner (opcional, para configuración inicial del dron)
