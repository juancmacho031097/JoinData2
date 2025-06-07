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
TWILIO_DESTINO = 'whatsapp:+573001720582'
MENU = {
    "pepperoni": {"small": 20000, "medium": 25000, "large": 30000, "x-large": 35000},
    "hawaiana": {"small": 20000, "medium": 25000, "large": 30000, "x-large": 35000},
    "bbq pollo": {"small": 22000, "medium": 27000, "large": 32000, "x-large": 37000},
    "margarita": {"small": 18000, "medium": 23000, "large": 28000, "x-large": 33000}
}
STEPS = ["sabor", "tamano", "cantidad", "modalidad", "direccion"]

# Google Sheets setup
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), SCOPE)

client = gspread.authorize(CREDS)
sheet = client.open("Pedidos Ustariz Pizza").sheet1

# OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# =================== STATE ======================
users = {}

# =================== FUNCIONES ======================
def calcular_total(sabor, tamano, cantidad):
    return MENU[sabor][tamano] * cantidad

def guardar_pedido(nombre, pedido):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    row = [now, nombre, pedido['sabor'], pedido['tamano'], pedido['cantidad'],
           pedido['modalidad'], pedido.get('direccion', '-'), pedido['total']]
    sheet.append_row(row)

def formatear_pedido(p):
    return f"""🧾 Pedido confirmado:
- {p['cantidad']} Pizza {p['sabor'].capitalize()} ({p['tamano'].capitalize()})
- Modalidad: {p['modalidad']}
- Dirección: {p.get('direccion', 'N/A')}
- Total: ${p['total']:,}"""

def responder_ia(mensaje):
    prompt = f"""Actúa como el asistente virtual de Ustariz Pizza. 
Menú: {MENU}
Horario: Todos los días de 5:30pm a 10:30pm
Cliente: {mensaje}
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message['content']
    except Exception as e:
        return "Lo siento, hubo un error procesando tu solicitud."

# =================== BOT ======================
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    msg = request.form.get('Body').lower()
    user = request.form.get('From')
    nombre = request.form.get('ProfileName')

    if user not in users:
        users[user] = {"step": 0, "pedido": {}}

    step = users[user]["step"]
    pedido = users[user]["pedido"]
    resp = MessagingResponse()
    message = resp.message()

    if step == 0:
        if any(x in msg for x in ["hola", "pizza", "quiero"]):
            message.body("🍕 ¡Bienvenido a Ustariz Pizza! ¿Qué sabor deseas? (pepperoni, hawaiana, bbq pollo, margarita)")
            users[user]["step"] += 1
        else:
            respuesta = responder_ia(msg)
            message.body(respuesta)
    elif step == 1:
        if msg in MENU:
            pedido["sabor"] = msg
            message.body("¿Qué tamaño deseas? (small, medium, large, x-large)")
            users[user]["step"] += 1
        else:
            message.body("Sabor no válido. Prueba: pepperoni, hawaiana, bbq pollo o margarita.")
    elif step == 2:
        if msg in MENU[pedido["sabor"]]:
            pedido["tamano"] = msg
            message.body("¿Cuántas unidades deseas?")
            users[user]["step"] += 1
        else:
            message.body("Tamaño no válido. Prueba: small, medium, large, x-large")
    elif step == 3:
        if msg.isdigit():
            pedido["cantidad"] = int(msg)
            message.body("¿Es para recoger o a domicilio?")
            users[user]["step"] += 1
        else:
            message.body("Por favor, indica un número válido de unidades.")
    elif step == 4:
        if msg in ["recoger", "a domicilio"]:
            pedido["modalidad"] = msg
            if msg == "a domicilio":
                message.body("Por favor, indícame tu dirección completa 🏠")
                users[user]["step"] += 1
            else:
                pedido["direccion"] = "-"
                total = calcular_total(pedido["sabor"], pedido["tamano"], pedido["cantidad"])
                pedido["total"] = total
                guardar_pedido(nombre, pedido)
                resumen = formatear_pedido(pedido)
                message.body(resumen)
                users[user] = {"step": 0, "pedido": {}}
        else:
            message.body("Responde con 'recoger' o 'a domicilio'.")
    elif step == 5:
        pedido["direccion"] = msg
        total = calcular_total(pedido["sabor"], pedido["tamano"], pedido["cantidad"])
        pedido["total"] = total
        guardar_pedido(nombre, pedido)
        resumen = formatear_pedido(pedido)
        message.body(resumen)
        users[user] = {"step": 0, "pedido": {}}

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)
