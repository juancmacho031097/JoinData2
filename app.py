from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
import json
import pdfplumber
import traceback
import requests

app = Flask(__name__)

#===================fotos de flores=============

IMAGENES_PRODUCTOS = {
    "rosas": "https://i.imgur.com/KsfHUfJ.jpeg",
    "girasoles": "https://i.imgur.com/wUile3P.png",
    "tulipanes": "https://i.imgur.com/4wOaKn9.jpeg"
}

URL_CATALOGO = "https://bit.ly/VerCatalogoFlora"


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

def responder_ia_con_estado(nombre, historial, menu, estado_actual):
    prompt = f"""
Eres FloraBot, un asistente de ventas de flores. Estás atendiendo a un cliente llamado {nombre}.
Debes mantener una conversación natural, cálida y guiada para ayudarle a hacer un pedido paso a paso.

No repitas saludos si ya has hablado con el cliente.

Responde con preguntas amigables, y si el cliente ya te dio un dato, no lo repitas.

Ejemplo de respuesta final:

🧾 *Pedido confirmado*:
- Producto: girasoles
- Cantidad: 2
- Modalidad: Domicilio
- Dirección: Calle 118 #43-46
- Total: $50,000

Devuelve un JSON con esta estructura:
{{
"producto": "...",
"cantidad": "...",
"modalidad": "...",
"direccion": "...",
"respuesta": "texto conversacional para mostrar al cliente"
}}

Estado actual del pedido:
{json.dumps(estado_actual, ensure_ascii=False)}

Historial del cliente:
{json.dumps(historial[-6:], ensure_ascii=False)}

Menú disponible:
{json.dumps(menu, ensure_ascii=False)}
"""

    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ustariz-pizza-bot.onrender.com",
            "X-Title": "Bot Flora IA"
        }

        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}]
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}: {response.text}")
            return "No fue posible procesar tu mensaje. Intenta más tarde."

        content = response.json()["choices"][0]["message"]["content"]

        # Extraer solo el JSON sin imprimirlo al cliente
        json_start = content.find('{')
        json_end = content.rfind('}') + 1

        pedido_json = {}
        if json_start != -1 and json_end != -1:
            try:
                pedido_json = json.loads(content[json_start:json_end])
                content = pedido_json.get("respuesta", "Gracias por tu mensaje 🌸")
            except:
                content = "Gracias por tu mensaje 🌸"

        # Actualizar estado del pedido
        for campo in ["producto", "cantidad", "modalidad", "direccion"]:
            if campo in pedido_json and pedido_json[campo]:
                estado_actual[campo] = pedido_json[campo]


        for campo in ["producto", "cantidad", "modalidad", "direccion"]:
            if campo in pedido_json and pedido_json[campo]:
                estado_actual[campo] = pedido_json[campo]

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
        users[user] = {
            "historial": [],
            "estado_pedido": {
                "producto": None,
                "cantidad": None,
                "modalidad": None,
                "direccion": None
            },
            "saludo_enviado": False
        }

    # Guardar historial
    users[user]["historial"].append(msg.lower())

    # Saludo inicial
    if not users[user]["saludo_enviado"]:
        bienvenida = f"¡Hola {nombre}! Bienvenida, mi nombre es Flor 🌸 tu asistente floral. ¿Qué tipo de flores te gustaría hoy? Tenemos ramos de rosas, girasoles y tulipanes."
        users[user]["saludo_enviado"] = True
        message.body(bienvenida)
        return str(resp)

    texto = msg.lower()

    # Mostrar imagen específica si menciona tipo de flor + foto/imagen
    for flor in IMAGENES_PRODUCTOS:
        if flor in texto and any(palabra in texto for palabra in ["foto", "fotos", "imagen", "ver"]):
            message.body(f"Aquí tienes una muestra de nuestros {flor} 🌼")
            message.media(IMAGENES_PRODUCTOS[flor])
            return str(resp)  # 🔴 Esto evita que pase a la IA

    # Mostrar catálogo general si menciona "catálogo", "ver productos", etc.
    if any(palabra in texto for palabra in ["catálogo", "catalogo", "ver productos", "ver catálogo"]):
        message.body(f"Claro 🌸 Aquí puedes ver nuestro catálogo completo de flores y arreglos:\n{URL_CATALOGO}")
        return str(resp)  # 🔴 Esto también evita que siga a la IA


    # Respuesta IA
    respuesta = responder_ia_con_estado(nombre, users[user]["historial"], MENU, users[user]["estado_pedido"])
    message.body(respuesta)
    return str(resp)


@app.route("/", methods=['GET'])
def home():
    return "Bot Flora IA activo ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

 