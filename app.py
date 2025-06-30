from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
import json
import pdfplumber
import traceback
import requests

app = Flask(__name__)

# =================== CONFIG ======================

MENU = {
    "ramos de rosas": {"único": 30000},
    "girasoles": {"único": 25000},
    "tulipanes": {"único": 35000}
}

def cargar_menu_desde_pdf(ruta_pdf):
    global MENU
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            texto = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

        nuevo_menu = {}
        for linea in texto.lower().split("\n"):
            if "$" in linea:
                try:
                    partes = linea.strip().split("$")
                    nombre = partes[0].strip()
                    precio = int(partes[1].replace(",", "").strip())
                    nuevo_menu[nombre] = {"único": precio}
                except:
                    continue

        if nuevo_menu:
            MENU = nuevo_menu
            print("✅ MENÚ CARGADO DESDE PDF:")
            print(json.dumps(MENU, indent=2, ensure_ascii=False))
        else:
            print("⚠️ Menú vacío. Usando valores por defecto.")
    except Exception:
        print("❌ Error cargando el menú desde PDF. Usando menú por defecto.")
        traceback.print_exc()

cargar_menu_desde_pdf("Catalogo_Flora_F.pdf")

# =================== IA ======================
def responder_ia_con_estado(nombre, historial, menu):
    prompt = f"""
    Eres FloraBot, un asistente de ventas de flores. Estás atendiendo a un cliente llamado {nombre}.
    Debes mantener una conversación natural y paso a paso para tomar un pedido.

    Tienes que identificar estos 4 datos:
    1. producto (nombre de flor en el menú)
    2. cantidad (cuántos quiere)
    3. modalidad (recoger o domicilio)
    4. dirección (solo si es domicilio)

    Si el cliente pregunta por el precio de un producto, respóndelo con base en el menú que te paso abajo.

    Cuando recopiles todos los datos, responde así:

    🧾 *Pedido confirmado*:
    - Producto: girasoles
    - Cantidad: 2
    - Modalidad: Domicilio
    - Dirección: Calle 118 #43-46
    - Total: $50,000

    Devuelve un JSON así:
    {{
    "producto": "...",
    "cantidad": "...",
    "modalidad": "...",
    "direccion": "...",
    "respuesta": "texto conversacional para mostrar al cliente"
    }}

    Historial del cliente:
    {json.dumps(historial[-5:])}

    Menú disponible:
    {json.dumps(menu)}
    """


# =================== BOT ======================
users = {}

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    msg = request.form.get('Body')
    user = request.form.get('From')
    nombre = request.form.get('ProfileName')

    resp = MessagingResponse()
    message = resp.message()

    if not msg or not user:
        message.body("No pude leer tu mensaje. ¿Puedes intentarlo de nuevo?")
        return str(resp)

    if user not in users:
        users[user] = {"historial": []}

    users[user]["historial"].append(msg.lower())

    if not MENU:
        message.body("No hay productos disponibles. Intenta más tarde.")
        return str(resp)

    respuesta = responder_ia_con_estado(nombre, users[user]["historial"], MENU)
    message.body(respuesta)
    return str(resp)

@app.route("/", methods=['GET'])
def home():
    return "Bot Flora IA activo ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
