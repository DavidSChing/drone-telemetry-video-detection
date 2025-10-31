# -*- coding: utf-8 -*- 
# camera_stream.py
import os
import sys

# Configurar variables de entorno ANTES de importar torch/ultralytics
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # Evitar error OpenMP en Windows
os.environ["CUDA_LAUNCH_BLOCKING"] = "0"     # GPU asíncrona para máxima velocidad

# IMPORTANTE: Para usar GPU NVIDIA (no Intel iGPU):
# - Tu sistema: GPU 0 (Task Manager) = Intel Iris Xe (no CUDA)
#               GPU 1 (Task Manager) = NVIDIA MX450 (sí CUDA)
# - PyTorch solo ve GPUs NVIDIA, por lo que tu MX450 es el índice CUDA 0
# - Dejar comentado para usar automáticamente la MX450:
# os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import cv2
import numpy as np
import requests
from requests.exceptions import RequestException
import torch
from ultralytics import YOLO
import time
from datetime import datetime

# Configuración de detección (ajustada para mayor sensibilidad)
CONFIDENCE_THRESHOLD = 0.35  # Umbral base de confianza para detecciones
MIN_BOX_AREA = 400          # Área mínima de caja para filtrar ruido
MAX_BOX_AREA = 500000       # Área máxima aceptada
MAX_NO_DETECT_FRAMES = 10   # Frames consecutivos sin detectar para bajar conf adaptativamente
MAX_FRAMES_HISTORY = 5      # Número de frames para promediar
# PROCESS_EVERY_N_FRAMES se configura dinámicamente según la red (ver más abajo)
TARGET_SIZE = (384, 288)    # Tamaño para procesamiento YOLO
FACE_FALLBACK_ENABLED = True  # Activar fallback de detección de rostro si no hay persona
FACE_FALLBACK_COOLDOWN = 5    # Intentar fallback cada N frames cuando corresponda

# Verificar disponibilidad de CUDA
print("PyTorch versión:", torch.__version__)
print("CUDA disponible:", torch.cuda.is_available())
print("Número de GPUs:", torch.cuda.device_count())
print("CUDA_VISIBLE_DEVICES:", os.environ.get("CUDA_VISIBLE_DEVICES"))
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        try:
            print(f"GPU[{i}]: {torch.cuda.get_device_name(i)}")
        except Exception:
            pass

if torch.cuda.is_available():
    print(f"Usando GPU: {torch.cuda.get_device_name(0)}")
    print("CUDA versión:", torch.version.cuda)
    device = "cuda"
    # Optimización de cuDNN para tamaños fijos
    try:
        torch.backends.cudnn.benchmark = True
    except Exception:
        pass
else:
    print("GPU no disponible, usando CPU")
    print("Razones posibles:")
    print("1. No hay GPU NVIDIA instalada")
    print("2. Drivers NVIDIA no instalados o desactualizados")
    print("3. CUDA Toolkit no instalado o incompatible")
    device = "cpu"

# URLs de la ESP32-CAM y configuración del stream
# Configuración de red - cambiar según la red disponible
USE_NETWORK = "PUCP"  # Opciones: "iPhone" o "PUCP"

if USE_NETWORK == "iPhone":
    ESP32_URL_PROCESSED = "http://172.20.10.2/stream"
    # Parámetros optimizados para red iPhone (baja latencia)
    CHUNK_SIZE = 1024        # Chunks pequeños
    BUFFER_MAX = 32768       # 32KB buffer
    BUFFER_KEEP = 16384      # Mantener 16KB
    PROCESS_SKIP = 2         # Procesar 1 de cada 2 frames
elif USE_NETWORK == "PUCP":
    ESP32_URL_PROCESSED = "http://10.100.224.44/stream"
    # Parámetros optimizados para red PUCP (alta latencia, buffering)
    CHUNK_SIZE = 4096        # Chunks más grandes para reducir overhead
    BUFFER_MAX = 65536       # 64KB buffer (más grande)
    BUFFER_KEEP = 32768      # Mantener 32KB
    PROCESS_SKIP = 1         # Procesar cada frame (no saltar)
else:
    raise ValueError(f"Red desconocida: {USE_NETWORK}")

print(f"[CONFIG] Red seleccionada: {USE_NETWORK}")
print(f"[CONFIG] URL: {ESP32_URL_PROCESSED}")
print(f"[CONFIG] Chunk size: {CHUNK_SIZE} bytes")
print(f"[CONFIG] Buffer max: {BUFFER_MAX} bytes")
print(f"[CONFIG] Procesar 1 de cada {PROCESS_SKIP} frames")

BOUNDARY = b'--1234567890000000000009876543'

# Cargar y configurar modelo YOLO
model = YOLO('../models/yolov8n.pt')  # Modelo pequeño y rápido
model.to(device)
if torch.cuda.is_available():
    model.fuse()  # Fusionar capas para mejor rendimiento en GPU

# Intentar usar FP16 en CUDA
USE_FP16 = False
try:
    if device == "cuda" and hasattr(model, 'model'):
        model.model.half()
        USE_FP16 = True
except Exception:
    USE_FP16 = False

# Reportar dispositivo y dtype reales del modelo
try:
    param = next(model.model.parameters()) if hasattr(model, 'model') else None
    if param is not None:
        print("Modelo en dispositivo:", param.device, "dtype:", param.dtype)
except Exception:
    pass

# Cargador de detección de rostro (fallback)
FACE_CASCADE = None
try:
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    if os.path.exists(cascade_path):
        FACE_CASCADE = cv2.CascadeClassifier(cascade_path)
except Exception:
    FACE_CASCADE = None


# --- Simple Centroid Tracker for Unique Person Counting ---
import math
class DetectionTracker:
    def __init__(self, max_history=MAX_FRAMES_HISTORY, max_lost=8, dist_thresh=200):
        # dist_thresh: distancia máxima (en píxeles) para considerar que una detección es la misma persona entre frames.
        self.max_history = max_history
        self.detection_history = []
        self.last_count = 0
        self.frame_latency_history = []
        self.rtt_history = []
        self.last_frame_time = time.time()
        self.last_request_time = time.time()
        self.start_time = time.time()
        self.frame_count = 0
        self.last_fps_update = time.time()
        self.current_fps = 0
        # Tracker state
        self.next_id = 1
        self.tracks = {}  # id: {'centroid': (x, y), 'box': (x, y, w, h), 'conf': float, 'lost': 0}
        self.max_lost = max_lost  # Frames máximos sin detección antes de eliminar (balance entre estabilidad y reactividad)
        self.dist_thresh = dist_thresh  # Distancia aumentada para tracking más robusto
        self.unique_ids = set()
        # Suavizado de métricas (ventana más grande para estabilidad)
        self.latency_window_size = 30  # 30 frames para latencia
        self.rtt_window_size = 30      # 30 frames para RTT
        # Suavizado de cajas de detección (alpha para EMA - Exponential Moving Average)
        self.box_smoothing_alpha = 0.4  # 0.4 = buen balance entre suavizado y reactividad

    def _centroid(self, box):
        x, y, w, h = box
        return (x + w // 2, y + h // 2)
    
    def _iou(self, box1, box2):
        """Calcular Intersection over Union entre dos cajas"""
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        
        # Calcular coordenadas de intersección
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        # Área de intersección
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # Área de cada caja
        box1_area = w1 * h1
        box2_area = w2 * h2
        
        # IoU
        iou = intersection_area / float(box1_area + box2_area - intersection_area + 1e-6)
        return iou
    
    def update(self, current_detections, is_new_frame=True):
        current_time = time.time()
        if is_new_frame:
            self.frame_count += 1
            time_elapsed = current_time - self.last_fps_update
            if time_elapsed >= 1.0:
                self.current_fps = self.frame_count / time_elapsed
                self.frame_count = 0
                self.last_fps_update = current_time
            frame_latency = current_time - self.last_frame_time
            if frame_latency > 0:
                self.frame_latency_history.append(frame_latency * 1000)
                if len(self.frame_latency_history) > self.latency_window_size:
                    self.frame_latency_history.pop(0)
            self.last_frame_time = current_time
        rtt = current_time - self.last_request_time
        self.last_request_time = current_time
        if rtt > 0:
            self.rtt_history.append(rtt * 1000)
            if len(self.rtt_history) > self.rtt_window_size:
                self.rtt_history.pop(0)

        # --- Centroid tracking logic con suavizado de cajas ---
        detections = [d[0] for d in current_detections]  # [(x, y, w, h), ...]
        confidences = [d[1] for d in current_detections]  # [conf, ...]
        det_centroids = [self._centroid(box) for box in detections]
        assigned = set()
        updated_tracks = {}
        
        # Match detections to existing tracks
        for tid, tinfo in self.tracks.items():
            tcent = tinfo['centroid']
            min_dist = float('inf')
            min_idx = -1
            for idx, cent in enumerate(det_centroids):
                if idx in assigned:
                    continue
                dist = math.hypot(cent[0] - tcent[0], cent[1] - tcent[1])
                if dist < min_dist:
                    min_dist = dist
                    min_idx = idx
            
            if min_idx != -1 and min_dist < self.dist_thresh:
                # Update track con suavizado de caja (EMA)
                new_box = detections[min_idx]
                old_box = tinfo.get('box', new_box)
                
                # Aplicar suavizado exponencial a las coordenadas de la caja
                alpha = self.box_smoothing_alpha
                smoothed_box = (
                    int(alpha * new_box[0] + (1 - alpha) * old_box[0]),  # x
                    int(alpha * new_box[1] + (1 - alpha) * old_box[1]),  # y
                    int(alpha * new_box[2] + (1 - alpha) * old_box[2]),  # w
                    int(alpha * new_box[3] + (1 - alpha) * old_box[3])   # h
                )
                
                updated_tracks[tid] = {
                    'centroid': det_centroids[min_idx],
                    'box': smoothed_box,
                    'conf': confidences[min_idx],
                    'lost': 0
                }
                assigned.add(min_idx)
            else:
                # Mark as lost - mantener última caja conocida
                if tinfo['lost'] + 1 < self.max_lost:
                    updated_tracks[tid] = {
                        'centroid': tcent,
                        'box': tinfo.get('box', (0, 0, 0, 0)),
                        'conf': tinfo.get('conf', None),
                        'lost': tinfo['lost'] + 1
                    }
        
        # Add new tracks for unassigned detections
        for idx, cent in enumerate(det_centroids):
            if idx not in assigned:
                new_box = detections[idx]
                
                # Verificar si esta nueva detección se superpone significativamente con algún track perdido
                overlapping_tracks = []
                for tid, tinfo in updated_tracks.items():
                    if tinfo['lost'] > 0:  # Solo verificar tracks perdidos
                        iou = self._iou(new_box, tinfo['box'])
                        if iou > 0.5:  # Si hay más de 50% de superposición
                            overlapping_tracks.append((tid, iou, tinfo['lost']))
                
                # Si hay superposición, eliminar el track antiguo y crear uno nuevo
                if overlapping_tracks:
                    # Ordenar por IoU descendente y lost ascendente (preferir eliminar los más perdidos)
                    overlapping_tracks.sort(key=lambda x: (-x[2], -x[1]))
                    # Eliminar el track más perdido que se superpone
                    tid_to_remove = overlapping_tracks[0][0]
                    del updated_tracks[tid_to_remove]
                
                # Crear nuevo track
                updated_tracks[self.next_id] = {
                    'centroid': cent,
                    'box': new_box,
                    'conf': confidences[idx],
                    'lost': 0
                }
                self.unique_ids.add(self.next_id)
                self.next_id += 1
        
        # Remove tracks lost for too long
        self.tracks = {tid: tinfo for tid, tinfo in updated_tracks.items() if tinfo['lost'] < self.max_lost}
        # Count current unique persons (active tracks)
        current_ids = list(self.tracks.keys())
        self.last_count = len(current_ids)
        # History for smoothing (not used for unique count)
        self.detection_history.append(current_detections)
        if len(self.detection_history) > self.max_history:
            self.detection_history.pop(0)
        avg_fps = round(self.current_fps, 1)
        avg_frame_latency = round(sum(self.frame_latency_history) / len(self.frame_latency_history), 1) if self.frame_latency_history else 0
        avg_rtt = round(sum(self.rtt_history) / len(self.rtt_history), 1) if self.rtt_history else 0
        stats = {
            'fps': avg_fps,
            'frame_latency': avg_frame_latency,
            'rtt': avg_rtt,
            'tiempo_total': round(current_time - self.start_time, 1),
            'detecciones_totales': len(self.unique_ids),
            'personas_actuales': self.last_count
        }
        return self.last_count, stats
    
    def get_smoothed_detections(self):
        """Retorna las cajas de detección suavizadas de todos los tracks activos"""
        smoothed_dets = []
        for tid, tinfo in self.tracks.items():
            box = tinfo.get('box', None)
            conf = tinfo.get('conf', None)
            if box and box != (0, 0, 0, 0):
                smoothed_dets.append((box, conf))
        return smoothed_dets

# Crear instancia del tracker
tracker = DetectionTracker()

def mostrar_pantalla_inicio():
    # Crear una ventana de inicio con espacio para panel lateral
    window_name = 'ESP32-CAM Stream'
    window_width = 1024  # Ancho total de la ventana
    window_height = 600  # Alto total de la ventana
    img = np.zeros((window_height, window_width, 3), dtype=np.uint8)
    
    # Configuración de texto
    font = cv2.FONT_HERSHEY_SIMPLEX
    color_texto = (0, 255, 0)
    
    # Título
    cv2.putText(img, "Sistema de Deteccion de Personas", 
                (100, 180), font, 1.2, color_texto, 2)
    cv2.putText(img, "PUCP - Proyecto de Diseno Mecatronico", 
                (120, 230), font, 0.8, color_texto, 2)
    
    # Estado
    cv2.putText(img, "Iniciando sistema...", 
                (220, 300), font, 0.7, (0, 255, 255), 1)
    
    # Información del sistema
    info_y = 350
    cv2.putText(img, f"PyTorch: {torch.__version__}", 
                (50, info_y), font, 0.6, (200, 200, 200), 1)
    cv2.putText(img, f"CUDA: {torch.version.cuda if torch.cuda.is_available() else 'No disponible'}", 
                (50, info_y + 30), font, 0.6, (200, 200, 200), 1)
    cv2.putText(img, f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}", 
                (50, info_y + 60), font, 0.6, (200, 200, 200), 1)
    
    cv2.imshow(window_name, img)
    cv2.waitKey(2000)  # Mostrar por 2 segundos
    return window_name

def stream_camera():
    try:
        # Mostrar pantalla de inicio
        window_name = mostrar_pantalla_inicio()
        print(f"Conectando a {ESP32_URL_PROCESSED}...")
        
        # Configurar headers optimizados
        headers = {
            'Accept': 'multipart/x-mixed-replace;boundary=1234567890000000000009876543',
            'Connection': 'keep-alive',  # Mantener conexión abierta
            'Cache-Control': 'no-cache'   # Evitar cache
        }
        
        # Timeout adaptativo según red
        timeout_connect = 10 if USE_NETWORK == "PUCP" else 5
        timeout_read = 30 if USE_NETWORK == "PUCP" else 10
        
        print(f"[CONFIG] Timeout: connect={timeout_connect}s, read={timeout_read}s")
        
        # Iniciar un solo stream (más eficiente)
        response = requests.get(
            ESP32_URL_PROCESSED, 
            stream=True, 
            headers=headers, 
            timeout=(timeout_connect, timeout_read)
        )
        
        if response.status_code != 200:
            raise RequestException(f"Error de conexión: código {response.status_code}")
            
        print("[OK] Conexión establecida")
        
        # Buffer para los datos
        buffer = b''
        
        # Crear ventana para mostrar el video
        cv2.namedWindow('ESP32-CAM Stream', cv2.WINDOW_NORMAL)
        
        # Dimensiones de los videos
        video_width = 400
        video_height = 300
        
        # Usar chunk_size optimizado según la red
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            
            # Limitar el tamaño del buffer según configuración de red
            if len(buffer) > BUFFER_MAX:
                buffer = buffer[-BUFFER_KEEP:]  # Mantener solo los últimos bytes configurados
            
            buffer += chunk
            
            # Buscar el boundary que separa las imágenes
            boundary_pos = buffer.find(BOUNDARY)
            
            while boundary_pos != -1:
                # Encontrar el inicio del JPEG
                jpeg_start = buffer.find(b'\xff\xd8', boundary_pos)
                if jpeg_start == -1:
                    break
                
                # Encontrar el final del JPEG
                jpeg_end = buffer.find(b'\xff\xd9', jpeg_start)
                if jpeg_end == -1:
                    break
                
                # Extraer y decodificar el frame JPEG
                jpg_data = buffer[jpeg_start:jpeg_end + 2]
                buffer = buffer[jpeg_end + 2:]
                
                # Convertir a imagen
                frame = cv2.imdecode(np.frombuffer(jpg_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                
                # Validar dimensiones
                if frame.shape[0] <= 0 or frame.shape[1] <= 0:
                    continue
                
                # Redimensionar una sola vez y crear dos copias en memoria
                frame_display = cv2.resize(frame, (video_width, video_height))
                frame_raw = frame_display.copy()  # Copia para video crudo
                frame_processed = frame_display.copy()  # Copia para procesar
                
                # Crear un canvas más grande para ambos videos y el panel lateral
                canvas_height = 800  # Espacio para dos videos + márgenes
                canvas_width = 1100  # Espacio para videos + panel
                canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                
                # Inicializar atributos de stream_camera si no existen
                if not hasattr(stream_camera, 'frame_count'):
                    stream_camera.frame_count = 0
                    stream_camera.no_detect_frames = 0
                    stream_camera.conf_current = CONFIDENCE_THRESHOLD
                    stream_camera.last_detecciones = []
                
                stream_camera.frame_count += 1
                
                # Posiciones de los videos
                margin_left = 40
                margin_top = 60
                video_spacing = 20  # Espaciado entre videos
                
                # Posición del video procesado (arriba)
                processed_y = margin_top
                processed_x = margin_left
                
                # Posición del video crudo (abajo)
                raw_y = processed_y + video_height + video_spacing
                raw_x = margin_left
                
                # Posición del panel lateral
                panel_x = margin_left + video_width + 40
                panel_width = canvas_width - panel_x - 40
                
                # Procesar solo 1 de cada N frames (según configuración de red)
                personas_detectadas = stream_camera.last_detecciones
                if stream_camera.frame_count % PROCESS_SKIP == 0:
                    # Redimensionar directamente al tamaño objetivo para procesamiento desde el frame display
                    frame_resized = cv2.resize(frame_display, TARGET_SIZE, interpolation=cv2.INTER_AREA)
                else:
                    # Usar últimas detecciones conocidas
                    frame_resized = None

                # Ajuste adaptativo del umbral si pasaron muchos frames sin detecciones
                if stream_camera.no_detect_frames >= MAX_NO_DETECT_FRAMES:
                    threshold_current = max(0.15, CONFIDENCE_THRESHOLD - 0.10)
                else:
                    threshold_current = CONFIDENCE_THRESHOLD
                stream_camera.conf_current = threshold_current

                if frame_resized is not None:
                    # Detectar personas con YOLO
                    try:
                        results = model(frame_resized, verbose=False, half=USE_FP16)
                    except TypeError:
                        # Si la versión no soporta 'half' como argumento
                        results = model(frame_resized, verbose=False)
                    except Exception as e:
                        print(f"Error en inferencia YOLO: {e}")
                        results = None
                    
                    if results is not None:
                        # Filtrar solo detecciones de personas con alta confianza
                        detections = results[0].boxes.data
                        nuevas_detecciones = []
                        
                        # Calcular factor de escala para redimensionar las detecciones al video de visualización
                        scale_x = video_width / TARGET_SIZE[0]
                        scale_y = video_height / TARGET_SIZE[1]
                        
                        for det in detections:
                            try:
                                # Clase 0 es 'person' en COCO
                                if int(det[5]) == 0 and float(det[4]) >= threshold_current:
                                    x1, y1, x2, y2, conf = det[:5]
                                    # Convertir coordenadas al formato (x, y, w, h) y escalar al tamaño del video de visualización
                                    x1, y1 = int(x1 * scale_x), int(y1 * scale_y)
                                    x2, y2 = int(x2 * scale_x), int(y2 * scale_y)
                                    w, h = x2 - x1, y2 - y1
                                    # Solo considerar detecciones con tamaño razonable
                                    area = w * h
                                    if area >= MIN_BOX_AREA and area <= MAX_BOX_AREA and w > 0 and h > 0:
                                        nuevas_detecciones.append(((x1, y1, w, h), conf))
                            except Exception as e:
                                print(f"Error procesando detección: {e}")
                                continue
                        
                        # Actualizar detecciones y persistir últimas válidas
                        personas_detectadas = nuevas_detecciones
                        stream_camera.last_detecciones = personas_detectadas

                # Si no hubo detecciones de persona, intentar fallback de rostro
                if (FACE_FALLBACK_ENABLED and FACE_CASCADE is not None and 
                    len(personas_detectadas) == 0 and 
                    stream_camera.no_detect_frames >= MAX_NO_DETECT_FRAMES and 
                    stream_camera.frame_count % FACE_FALLBACK_COOLDOWN == 0):
                    try:
                        gray = cv2.cvtColor(frame_display, cv2.COLOR_BGR2GRAY)
                        faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                        if len(faces) > 0:
                            personas_detectadas = []
                            for (fx, fy, fw, fh) in faces:
                                # tratar rostro como 1 detección (sin confianza)
                                personas_detectadas.append(((int(fx), int(fy), int(fw), int(fh)), None))
                            stream_camera.last_detecciones = personas_detectadas
                    except Exception as e:
                        print(f"Error en deteccion de rostro: {e}")

                # Actualizar contador de frames sin detecciones
                if len(personas_detectadas) == 0:
                    stream_camera.no_detect_frames += 1
                else:
                    stream_camera.no_detect_frames = 0
                
                # Actualizar tracker ANTES de dibujar
                num_personas, stats = tracker.update(personas_detectadas)
                
                # Obtener cajas suavizadas del tracker para dibujar
                detecciones_a_dibujar = tracker.get_smoothed_detections()
                
                # Dibujar las detecciones suavizadas en el frame procesado
                for (x, y, w, h), conf in detecciones_a_dibujar:
                    try:
                        # Validar que las coordenadas están dentro del frame procesado
                        if x < 0 or y < 0 or x + w > video_width or y + h > video_height:
                            continue
                        
                        # Color base para las detecciones
                        color_box = (0, 255, 0)
                        
                        # Dibujar rectángulo principal
                        cv2.rectangle(frame_processed, (x, y), (x + w, y + h), color_box, 2)
                        
                        # Barra superior con etiqueta y confianza
                        label_bg_color = (40, 40, 40)
                        label_height = 25
                        confianza = f"Persona {conf*100:.0f}%" if conf is not None else "Cara"
                        
                        # Fondo de la etiqueta
                        if y - label_height >= 0:
                            cv2.rectangle(frame_processed, (x, y - label_height), 
                                       (x + w, y), label_bg_color, -1)
                            
                            # Texto de la etiqueta
                            cv2.putText(frame_processed, confianza, (x + 5, y - 7),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        
                        # Indicador de esquina superior izquierda
                        corner_size = min(20, w//4, h//4)
                        cv2.line(frame_processed, (x, y), 
                               (x + corner_size, y), color_box, 2)
                        cv2.line(frame_processed, (x, y), 
                               (x, y + corner_size), color_box, 2)
                        
                        # Indicador de esquina inferior derecha
                        cv2.line(frame_processed, (x + w - corner_size, y + h), 
                               (x + w, y + h), color_box, 2)
                        cv2.line(frame_processed, (x + w, y + h - corner_size), 
                               (x + w, y + h), color_box, 2)
                    except Exception as e:
                        print(f"Error dibujando detección: {e}")
                        continue
                
                # Colocar video procesado (con detecciones) en el canvas - ARRIBA
                try:
                    canvas[processed_y:processed_y+video_height, processed_x:processed_x+video_width] = frame_processed
                except ValueError as e:
                    print(f"Error al copiar frame procesado al canvas: {e}")
                
                # Colocar video crudo (sin detecciones) en el canvas - ABAJO
                try:
                    canvas[raw_y:raw_y+video_height, raw_x:raw_x+video_width] = frame_raw
                except ValueError as e:
                    print(f"Error al copiar frame crudo al canvas: {e}")
                
                # Configuración de la interfaz
                font = cv2.FONT_HERSHEY_SIMPLEX
                color_titulo = (0, 220, 0)  # Verde claro
                color_texto = (200, 200, 200)  # Gris claro
                
                # Título en la parte superior
                cv2.putText(canvas, "Sistema de Deteccion de Personas - PUCP", 
                          (margin_left, 35), font, 0.8, color_titulo, 2)
                
                # Etiquetas para los videos
                cv2.putText(canvas, "Video Procesado (con detecciones)", 
                          (processed_x, processed_y - 8), font, 0.5, color_titulo, 1)
                cv2.putText(canvas, "Video Original (sin procesar)", 
                          (raw_x, raw_y - 8), font, 0.5, (255, 255, 0), 1)
                
                # Bordes de los videos
                cv2.rectangle(canvas, (processed_x-2, processed_y-2), 
                           (processed_x+video_width+2, processed_y+video_height+2), color_titulo, 2)
                cv2.rectangle(canvas, (raw_x-2, raw_y-2), 
                           (raw_x+video_width+2, raw_y+video_height+2), (255, 255, 0), 2)
                
                # Panel de métricas de rendimiento
                y_pos = processed_y + 10  # Alineado con el video procesado
                metrics_height = 200
                
                # Dibujar fondo para métricas
                try:
                    if panel_width > 0 and metrics_height > 0:
                        metrics_bg = np.zeros((metrics_height, panel_width, 3), dtype=np.uint8)
                        metrics_bg[:, :] = (30, 30, 30)  # Fondo gris oscuro
                        canvas[y_pos:y_pos+metrics_height, panel_x:panel_x+panel_width] = metrics_bg
                except ValueError:
                    pass  # Si panel_width es inválido, continuar sin fondo
                
                # Panel de métricas reordenado y renombrado
                y_panel = y_pos + 30
                cv2.putText(canvas, "Personas detectadas:", 
                          (panel_x + 10, y_panel), font, 0.7, color_texto, 1)
                cv2.putText(canvas, str(num_personas), 
                          (panel_x + panel_width - 60, y_panel), font, 0.9, color_titulo, 2)
                y_panel += 35
                
                # FPS
                fps = stats['fps']
                fps_text = f"{fps:.1f} FPS"
                fps_color = (0, 255, 0) if fps >= 30 else (0, 255, 255) if fps >= 20 else (0, 0, 255)
                cv2.putText(canvas, fps_text, (panel_x + 10, y_panel), font, 0.7, fps_color, 2)
                y_panel += 30
                
                # Latencia
                frame_latency = stats['frame_latency']
                latency_text = f"Latencia: {frame_latency:.1f} ms"
                latency_color = (0, 255, 0) if frame_latency <= 30 else (0, 255, 255) if frame_latency <= 50 else (0, 0, 255)
                cv2.putText(canvas, latency_text, (panel_x + 10, y_panel), font, 0.7, latency_color, 2)
                y_panel += 30
                
                # RTT
                rtt = stats['rtt']
                rtt_text = f"RTT: {rtt:.1f} ms"
                rtt_color = (0, 255, 0) if rtt <= 50 else (0, 255, 255) if rtt <= 100 else (0, 0, 255)
                cv2.putText(canvas, rtt_text, (panel_x + 10, y_panel), font, 0.7, rtt_color, 2)
                y_panel += 30
                
                # Confianza actual
                cv2.putText(canvas, f"Confianza actual: {stream_camera.conf_current:.2f}", 
                          (panel_x + 10, y_panel), font, 0.7, color_texto, 1)
                y_panel += 30
                
                # Tiempo de ejecución
                cv2.putText(canvas, f"Tiempo de ejecucion: {stats['tiempo_total']}s", 
                          (panel_x + 10, y_panel), font, 0.7, color_texto, 1)
                y_panel += 30
                
                # Detecciones totales
                cv2.putText(canvas, f"Detecciones totales: {stats['detecciones_totales']}", 
                          (panel_x + 10, y_panel), font, 0.7, color_texto, 1)
                y_panel += 35
                
                # Fecha y hora actual
                tiempo_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(canvas, tiempo_actual, (panel_x + 10, y_panel), font, 0.7, color_texto, 1)
                
                # Mostrar el canvas completo
                cv2.imshow('ESP32-CAM Stream', canvas)
                
                # Salir con ESC o si la ventana se cierra
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or cv2.getWindowProperty('ESP32-CAM Stream', cv2.WND_PROP_VISIBLE) < 1:
                    return
                
                # Buscar el siguiente boundary
                boundary_pos = buffer.find(BOUNDARY)
                
    except RequestException as e:
        print(f"\n[ERROR] Conexión perdida: {e}")
        print("Verifica:")
        print("  - ESP32-CAM está encendida")
        print(f"  - URL correcta: {ESP32_URL_PROCESSED}")
        print(f"  - Red configurada: {USE_NETWORK}")
        print("  - Red WiFi conectada")
    except KeyboardInterrupt:
        print("\n[INFO] Programa interrumpido por el usuario")
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[INFO] Cerrando ventanas...")
        cv2.destroyAllWindows()
        print("[INFO] Programa terminado")
    


if __name__ == "__main__":
    stream_camera()
