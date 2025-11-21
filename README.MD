# Webhook Chat Watcher 🧟

Este proyecto es una herramienta diseñada para **monitorear en tiempo
real archivos de log** del servidor de *7 Days to Die* y enviar mensajes
automáticamente a un **webhook de Discord**, facilitando el seguimiento
del chat global del juego.

Incluye:

-   GUI profesional en PyQt5 sin botón de maximizar\
-   Monitoreo continuo del archivo (`tail`)\
-   Envío de mensajes a Discord con plantillas personalizables\
-   Detección automática de plataforma: **Xbox / PSN / Steam**\
-   Archivo de configuración `config.ini` auto-generado\
-   Emojis y estilo temático de zombies\
-   Registro interno de actividad

------------------------------------------------------------------------

## 📌 Funcionalidad Principal

El programa analiza líneas como estas dentro del log:

    Chat (from 'Steam_76561198093711528', entity id '1278', to 'Global'): 'Azzlaer': buenas noches xDDD

Y envía un mensaje al webhook con un formato como:

    🧟 Steam — **Azzlaer**: buenas noches xDDD

------------------------------------------------------------------------

## ⚙️ Configuración

Todas las configuraciones se manejan desde un archivo:

    config.ini

Incluye:

-   Ruta del archivo de log\
-   Webhook de Discord\
-   Plantilla de mensaje\
-   Intervalo de vigilancia

------------------------------------------------------------------------

## ▶️ Ejecución

Instala dependencias:

    pip install PyQt5 requests

Ejecuta:

    python monitor_webhook_gui.py

------------------------------------------------------------------------

## 👥 Créditos

Proyecto desarrollado por:

-   **Azzlaer**\
-   **ChatGPT (OpenAI)**

Para la comunidad de **LatinBattle.com**

------------------------------------------------------------------------

## 📄 Licencia

Uso libre para fines personales o comunitarios.
