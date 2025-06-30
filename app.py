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
    prompt = f"""Tu tarea es conversar de forma fluida y detectar automáticamente si el cliente ya indicó el producto, cantidad, modalidad (recoger o a domicilio) y dirección. A medida que recopilas estos datos, debes confirmar y preguntar lo siguiente que falta.


Historial:
{json.dumps(historial[-5:])}

Menú:
{json.dumps(menu)}
"""

    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ustariz-pizza-bot.onrender.com",
            "X-Title": "Bot Flora IA"
        }

        data = {
            "model": "google/gemma-3-4b-it:free",
            "messages": [{"role": "user", "content": prompt}]
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}: {response.text}")
            return "No fue posible procesar tu mensaje. Intenta más tarde."

        content = response.json()["choices"][0]["message"]["content"]

        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        pedido_json = {}
        if json_start != -1 and json_end != -1:
            try:
                pedido_json = json.loads(content[json_start:json_end])
            except:
                pass

        return pedido_json.get("respuesta", content)

    except Exception:
        print("=========== ERROR GPT ===========")
        traceback.print_exc()
        return "Ups, hubo un problema técnico. Estamos trabajando para solucionarlo. 🙏"

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
