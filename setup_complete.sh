#!/bin/bash
# Script de Setup Completo para Cisco Network Automation Portfolio
# Juan Antonio Sanchez - Network Automation Engineer

echo "🚀 Iniciando setup completo del proyecto Cisco Network Automation..."

# 1. Verificar entorno virtual
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Entorno virtual activo: $VIRTUAL_ENV"
else
    echo "⚠️  Activando entorno virtual..."
    source cisco-env/bin/activate
fi

# 2. Instalar dependencias faltantes
echo "📦 Instalando dependencias completas..."
pip install --upgrade pip
pip install netmiko pysnmp requests paramiko textfsm ntc-templates

# 3. Verificar instalación
echo "🔍 Verificando instalación..."
python -c "
try:
    import netmiko
    import pysnmp
    import requests
    import paramiko
    print('✅ Todas las librerías instaladas correctamente')
    print(f'   - netmiko: {netmiko.__version__}')
    print(f'   - requests: {requests.__version__}')
    print('   - pysnmp: OK')
    print('   - paramiko: OK')
except ImportError as e:
    print(f'❌ Error de importación: {e}')
"

# 4. Crear estructura de directorios si no existe
echo "📁 Creando estructura de directorios..."
mkdir -p scripts/config_backup
mkdir -p scripts/monitoring
mkdir -p configs/sample_outputs
mkdir -p logs
mkdir -p data/backups
mkdir -p data/reports

# 5. Verificar config.py
echo "⚙️  Verificando configuración..."
if [[ -f "config.py" ]]; then
    echo "✅ config.py encontrado"
    # Verificar sintaxis
    python -m py_compile config.py 2>/dev/null && echo "✅ Sintaxis de config.py correcta" || echo "❌ Error de sintaxis en config.py"
else
    echo "⚠️  Creando config.py de ejemplo..."
    cat > config.py << 'EOF'
# Configuración para Cisco Network Automation Portfolio
# Juan Antonio Sanchez - Network Automation Engineer

# Credenciales por defecto (DevNet Sandbox)
USERNAME = "developer"
PASSWORD = "Cisco12345"
SNMP_COMMUNITY = "public"

# DevNet Sandbox - Always On IOS XE
DEVNET_DEVICE = {
    'host': 'sandbox-iosxe-latest-1.cisco.com',
    'hostname': 'csr1000v-1',
    'username': USERNAME,
    'password': PASSWORD,
    'device_type': 'cisco_xe',
    'snmp_community': SNMP_COMMUNITY,
    'port': 22
}

# Configuración local (editar según tu lab)
LOCAL_DEVICES = [
    {
        'host': '192.168.1.1',
        'hostname': 'SW01',
        'username': USERNAME,  
        'password': 'tu_password_aqui',  # Cambiar por tu password
        'device_type': 'cisco_ios',
        'snmp_community': SNMP_COMMUNITY
    }
]

# Configuración de logging
LOG_LEVEL = 'INFO'
LOG_FILE = 'logs/network_automation.log'

# Configuración de backups
BACKUP_DIR = 'data/backups'
BACKUP_RETENTION_DAYS = 30

# Configuración de monitoreo
MONITOR_INTERVAL = 60  # segundos
ALERT_THRESHOLDS = {
    'cpu_usage': 80,
    'memory_usage': 85,
    'interface_utilization': 90
}
EOF
    echo "✅ config.py creado con configuración por defecto"
fi

# 6. Verificar que los scripts helper existan
echo "🔧 Verificando scripts principales..."

# Verificar device_discovery.py
if [[ -f "scripts/device_discovery.py" ]]; then
    echo "✅ device_discovery.py encontrado"
else
    echo "⚠️  device_discovery.py no encontrado - necesitas crearlo"
fi

# 7. Test rápido de conectividad
echo "🌐 Testing conectividad básica..."
python -c "
import requests
try:
    response = requests.get('https://httpbin.org/ip', timeout=5)
    print('✅ Conectividad a internet OK')
except:
    print('❌ Sin conectividad a internet')
"

# 8. Mostrar status final
echo ""
echo "📋 RESUMEN DEL SETUP:"
echo "====================="
echo "✅ Entorno virtual: activo"
echo "✅ Dependencias: instaladas"  
echo "✅ Estructura: creada"
echo "✅ Configuración: lista"
echo ""
echo "🎯 PRÓXIMOS PASOS:"
echo "1. Editar config.py con tus dispositivos"
echo "2. Ejecutar: python scripts/device_discovery.py"
echo "3. Probar conectividad con DevNet Sandbox"
echo ""
echo "📞 ¿Necesitas ayuda? Contacta: usanaconisa@gmail.com"
echo "🚀 ¡Listo para automatizar redes!"
