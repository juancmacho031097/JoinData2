from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import openai
import json

app = Flask(__name__)

# =================== CONFIG ======================
MENU = {
    "pepperoni": {"small": 20000, "medium": 25000, "large": 30000, "x-large": 35000},
    "hawaiana": {"small": 20000, "medium": 25000, "large": 30000, "x-large": 35000},
    "bbq pollo": {"small": 22000, "medium": 27000, "large": 32000, "x-large": 37000},
    "margarita": {"small": 18000, "medium": 23000, "large": 28000, "x-large": 33000}
}

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), SCOPE)
#CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)

client = gspread.authorize(CREDS)
sheet = client.open("Pedidos Ustariz Pizza").sheet1

openai.api_key = os.getenv("OPENAI_API_KEY")

# =================== STATE ======================
users = {}

# =================== FUNCIONES ======================
def calcular_total(sabor, tamano, cantidad):
    return MENU[sabor][tamano] * int(cantidad)

def guardar_pedido(nombre, pedido):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    row = [now, nombre, pedido['sabor'], pedido['tamano'], pedido['cantidad'],
           pedido['modalidad'], pedido.get('direccion', '-'), pedido['total']]
    sheet.append_row(row)

def responder_ia_con_estado(nombre, historial, menu):
    prompt = f"""
Eres BotUsta, el asistente virtual de Ustariz Pizza. Estás hablando con {nombre}.
Tu tarea es conversar de forma fluida y detectar automáticamente si el cliente ya indicó el sabor, tamaño, cantidad, modalidad (recoger o a domicilio) y dirección. A medida que recopilas estos datos, debes confirmar y preguntar lo siguiente que falta.

Ejemplo:
Cliente: "Hola, quiero una de pepperoni grande"
Respuesta: "¡Claro que sí! 🍕 Una Pepperoni Large. ¿Cuántas deseas?"

Si el pedido está completo, genera un resumen como este:
🧾 Pedido confirmado:
- 2 Pizza Pepperoni (Large)
- Modalidad: A domicilio
- Dirección: Carrera 52 #80-20
- Total: $60,000

Devuelve un JSON con los campos recolectados y la respuesta conversacional.

Historial de mensajes:
{json.dumps(historial[-5:])}
Menú disponible:
{json.dumps(menu)}
"""
    try:
        response = openai.ChatCompletion.create(
            model="google/gemma-3-4b-it:free",
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

    if all(k in pedido for k in ["sabor", "tamano", "cantidad", "modalidad", "direccion"]):
        pedido["total"] = calcular_total(pedido["sabor"], pedido["tamano"], pedido["cantidad"])
        guardar_pedido(nombre, pedido)
        users[user] = {"historial": []}

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
