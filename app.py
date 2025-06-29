from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import openai
import json
import pdfplumber

app = Flask(__name__)

# =================== CONFIG ======================
MENU = {}

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
#creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
#CREDS = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), SCOPE)
CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(CREDS)
sheet = client.open("Pedidos Ustariz Pizza").sheet1

openai.api_key = os.getenv("OPENAI_API_KEY")

# =================== FUNCIONES ======================
def cargar_menu_desde_pdf(ruta_pdf):
    global MENU
    with pdfplumber.open(ruta_pdf) as pdf:
        texto = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    nuevo_menu = {}
    lineas = texto.lower().split("\n")
    for linea in lineas:
        if "$" in linea:
            try:
                partes = linea.strip().split("$")
                nombre = partes[0].strip()
                precio = int(partes[1].replace(",", "").strip())
                nuevo_menu[nombre] = {"único": precio}
            except:
                continue  
    MENU = nuevo_menu

cargar_menu_desde_pdf("Catalogo_Flora.pdf")

def calcular_total(producto, cantidad):
    return MENU[producto]["único"] * int(cantidad)

def guardar_pedido(nombre, pedido):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    row = [now, nombre, pedido['producto'], pedido['cantidad'], pedido['modalidad'], pedido.get('direccion', '-'), pedido['total']]
    sheet.append_row(row)

def responder_ia_con_estado(nombre, historial, menu):
    prompt = f"""
Eres BotUsta, el asistente virtual de Flora. Estás hablando con {nombre}.
Tu tarea es conversar de forma fluida y detectar automáticamente si el cliente ya indicó el producto, cantidad, modalidad (recoger o a domicilio) y dirección. A medida que recopilas estos datos, debes confirmar y preguntar lo siguiente que falta.

Ejemplo:
Cliente: "Hola, quiero 2 ramos de rosas"
Respuesta: "¡Perfecto! 🌹 2 Ramos de Rosas. ¿Es para recoger o a domicilio?"

Si el pedido está completo, genera un resumen como este:
🧾 Pedido confirmado:
- 2 Ramos de Rosas
- Modalidad: A domicilio
- Dirección: Calle 123
- Total: $60,000

Devuelve un JSON con los campos recolectados y la respuesta conversacional.

Historial de mensajes:
{json.dumps(historial[-5:])}
Menú disponible:
{json.dumps(menu)}
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        content = response.choices[0].message['content']
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        pedido_json = json.loads(content[json_start:json_end])
        return content, pedido_json
    except Exception as e:
        print(f"Error IA: {e}")
        return "Ups, tuve un problema procesando tu pedido. ¿Podrías repetirlo?", {}

# =================== BOT ======================
users = {}

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    msg = request.form.get('Body').lower()
    user = request.form.get('From')
    nombre = request.form.get('ProfileName')

    if user not in users:
        users[user] = {"historial": []}

    users[user]["historial"].append(msg)

    resp = MessagingResponse()
    message = resp.message()

    respuesta, pedido = responder_ia_con_estado(nombre, users[user]["historial"], MENU)
    message.body(respuesta)

    if all(k in pedido for k in ["producto", "cantidad", "modalidad", "direccion"]):
        pedido["total"] = calcular_total(pedido["producto"], pedido["cantidad"])
        guardar_pedido(nombre, pedido)
        users[user] = {"historial": []}

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
