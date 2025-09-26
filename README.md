

# Network Emulation API (NetJem)

Una API REST basada en FastAPI que permite emular condiciones de red mediante Linux Traffic Control (tc) para pruebas y simulación de redes.

## Funcionalidades

- **Emulación de latencia**: Añade retardos configurables a los paquetes
- **Pérdida de paquetes**: Simula pérdida aleatoria de paquetes (0-100%)
- **Corrupción de datos**: Introduce errores aleatorios en paquetes
- **Duplicación de paquetes**: Simula duplicación aleatoria de paquetes
- **Control de ancho de banda**: Limita la velocidad de transmisión
- **Filtrado por IP**: Aplica emulación solo a direcciones IP específicas
- **Escaneo ARP**: Descubre dispositivos activos en la red
- **Gestión de interfaces**: Manejo de múltiples interfaces de red

## Requisitos del Sistema

### Hardware
- Arquitectura x86_64 o ARM64
- Mínimo 512MB RAM disponible
- Acceso a interfaces de red del host

### Software
- **Linux**: Ubuntu 18.04+, Debian 9+, CentOS 7+, o distribuciones compatibles
- **Docker**: Versión 20.10 o superior
- **Permisos**: Acceso de superusuario (root/sudo)

### Compatibilidad por Plataforma
- ✅ **Linux nativo**: Funcionalidad completa
- ⚠️ **Windows con WSL2**: Funcionalidad limitada, dado que tc solo afecta al subsistema WSL2
- ⚠️ **macOS**: Funcionalidad limitada, dado que tc solo afecta al contenedor Docker
- ❌ **Windows nativo**: No compatible con traffic control

## Instalación y Ejecución

### Paso 1: Obtener el código
```bash
git clone <repositorio>
cd TrafficShaping
```

### Paso 2: Construir la imagen Docker
```bash
# Opción recomendada (imagen optimizada)
docker build -f Dockerfile.multistage -t netjem-api .

# Opción alternativa (imagen simple)
docker build -t netjem-api .
```

### Paso 3: Ejecutar el contenedor
```bash
# Ejecución con acceso completo a la red del host
docker run --privileged --network host netjem-api
```

### Paso 4: Verificar funcionamiento
- API disponible en: http://localhost:11111/docs

## Parámetros de Ejecución

### Flags de Docker requeridos

**`--privileged`**
- **Propósito**: Otorga capacidades administrativas al contenedor
- **Necesario para**: Ejecutar comandos tc (traffic control)
- **Riesgo**: Acceso completo al sistema host

**`--network host`**
- **Propósito**: Comparte el stack de red del host con el contenedor
- **Necesario para**: Que las modificaciones tc afecten las interfaces reales del host
- **Efecto**: El contenedor ve y modifica directamente las interfaces del sistema

### Configuración avanzada
```bash
# Ejecutar en segundo plano
docker run -d --privileged --network host --name netjem netjem-api

# Ejecutar con logs visibles
docker run --privileged --network host --rm netjem-api

# Ejecutar con reinicio automático
docker run -d --restart unless-stopped --privileged --network host netjem-api
```

## Advertencias de Seguridad

### ⚠️ CRÍTICO
- **Permisos privilegiados**: El contenedor tiene acceso completo al sistema host
- **Modificación de red**: Puede alterar significativamente el comportamiento de red
- **Interrupciones de servicio**: Las configuraciones incorrectas pueden causar pérdida de conectividad

### ⚠️ IMPORTANTE
- **Solo desarrollo/testing**: No recomendado para entornos de producción sin supervisión
- **Respaldos de configuración**: Asegúrese de poder restaurar la configuración de red original
- **Monitoreo**: Supervise el impacto en el rendimiento de red durante las pruebas

### ⚠️ OPERACIONAL
- **Persistencia**: Las configuraciones tc se pierden al reiniciar el sistema
- **Conflictos**: Puede interferir con otras herramientas de gestión de red (NetworkManager, systemd-networkd)
- **Recursos**: Traffic Shaping puede afectar de forma muy agresiva a las comunicaciones de red. Se recomienda siempre ejecutar un borrado cuando se haya finalizado la experimentación

## Validación de Instalación

### Verificar capacidades del sistema
```bash
# Comprobar que tc está disponible
docker run --privileged --network host --rm netjem-api tc qdisc show

# Verificar interfaces de red disponibles
docker run --privileged --network host --rm netjem-api ip link show

# Probar conectividad de la API
curl http://localhost:11111/interfaces_info
```

## Ejecución Nativa (Alternativa)

Para sistemas Linux sin Docker:

### Instalar dependencias
```bash
sudo apt update
sudo apt install python3 python3-pip iproute2
```

### Configurar entorno Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Ejecutar aplicación
```bash
sudo python -m uvicorn NetJemAPI:app --host 0.0.0.0 --port 11111
```

## Solución de Problemas

### Error: "tc: command not found"
```bash
# Reconstruir imagen sin caché
docker build -f Dockerfile.multistage -t netjem-api --no-cache .
```

### Error: "Permission denied"
```bash
# Verificar que Docker tiene permisos sudo
sudo docker run --privileged --network host netjem-api
```

### Error: "Cannot bind to port 11111"
```bash
# Verificar que el puerto no esté en uso
sudo netstat -tulpn | grep 11111
# O usar un puerto diferente
docker run --privileged --network host -e PORT=8080 netjem-api
```

## Uso de la API

Una vez en funcionamiento, acceda a:
- **Documentación interactiva**: http://localhost:11111/docs
- **Especificación OpenAPI**: http://localhost:11111/openapi.json

## Limitaciones Técnicas

1. **Plataforma**: Requiere kernel Linux con soporte para tc
2. **Permisos**: Necesita privilegios administrativos
3. **Red**: Las modificaciones afectan todo el tráfico del sistema
4. **Persistencia**: Configuraciones temporales (se pierden al reiniciar)
5. **Concurrencia**: Un solo punto de control por interfaz de red
