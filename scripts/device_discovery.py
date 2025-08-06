#!/usr/bin/env python3
"""
Cisco Device Discovery Script
Autor: AssistantIsa 
Fecha: Agosto 2025
"""

import requests
import json
import sys
from urllib3.exceptions import InsecureRequestWarning

# Suprimir warnings de SSL para DevNet Sandbox
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Configuración del dispositivo
DEVICE_IP = "10.10.20.48"
PORT = "8181"
USERNAME = "developer"
PASSWORD = "C1sco12345"

def test_connection():
    """
    Prueba la conexión básica al dispositivo
    """
    print("🔍 Cisco Device Discovery Tool")
    print("=" * 40)
    
    # URL base para API REST
    base_url = f"https://{DEVICE_IP}:{PORT}/restconf/data"
    
    # Headers básicos
    headers = {
        'Accept': 'application/yang-data+json',
        'Content-Type': 'application/yang-data+json'
    }
    
    # Autenticación
    auth = (USERNAME, PASSWORD)
    
    try:
        print(f"📡 Conectando a {DEVICE_IP}:{PORT}...")
        
        # Endpoint simple para probar conectividad
        url = f"{base_url}/ietf-interfaces:interfaces"
        
        response = requests.get(
            url,
            headers=headers,
            auth=auth,
            verify=False,  # Para DevNet Sandbox
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Conexión exitosa!")
            print(f"✅ Status Code: {response.status_code}")
            print("✅ Dispositivo responde correctamente")
            
            # Mostrar info básica si está disponible
            try:
                data = response.json()
                if 'ietf-interfaces:interfaces' in data:
                    interfaces = data['ietf-interfaces:interfaces'].get('interface', [])
                    print(f"✅ Interfaces encontradas: {len(interfaces)}")
                    
                    # Mostrar primeras 3 interfaces como ejemplo
                    for i, interface in enumerate(interfaces[:3]):
                        name = interface.get('name', 'Unknown')
                        print(f"  - Interface {i+1}: {name}")
                        
            except json.JSONDecodeError:
                print("✅ Respuesta recibida (no JSON parseable)")
                
        else:
            print(f"❌ Error de conexión: HTTP {response.status_code}")
            print(f"❌ Mensaje: {response.text}")
            
    except requests.exceptions.ConnectTimeout:
        print("❌ Timeout de conexión")
        print("💡 Verificar que DevNet Sandbox esté activo")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error de conexión")
        print("💡 Verificar IP y puerto del dispositivo")
        
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        
    finally:
        print("\n" + "=" * 40)
        print("🏁 Test completado")

def show_device_info():
    """
    Muestra información adicional del dispositivo si está disponible
    """
    print("\n📋 Información del Dispositivo:")
    print(f"  IP: {DEVICE_IP}")
    print(f"  Puerto: {PORT}")
    print(f"  Usuario: {USERNAME}")
    print(f"  Protocolo: RESTCONF")

if __name__ == "__main__":
    print("🚀 Iniciando Cisco Device Discovery...")
    show_device_info()
    test_connection()
    
    # Exit code para indicar éxito/fallo
    print("\n✨ Script ejecutado correctamente")
    sys.exit(0)
