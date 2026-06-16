# BOT XAU/USD ORO - VERSION OPTIMIZADA PARA RENDER
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
import json
import threading
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from io import BytesIO
from flask import Flask

# ---------------- CONFIGURACIÓN ----------------
BOT_TOKEN = ""
CHAT_ID = ""
SIMBOLO = "GC=F"
RIESGO_POR_OPERACION = 1.5
ATR_MULT = 1.8
TP1 = 1.5
TP2 = 2.8
TP3 = 4.0
ATR_MINIMO = 4.0
INTERVALO_REVISION = 1800
HISTORIAL = "historial.json"
ULTIMA_SENAL = {"hora": None, "tipo": None}
# ------------------------------------------------

# Servidor para mantener activo Render
app = Flask(__name__)
@app.route('/')
def index():
    return "Bot activo ✅"

def mantener_activo():
    while True:
        time.sleep(600)  # Cada 10 minutos

def enviar_texto(texto):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown"},
            timeout=10
        )
    except:
        pass

def enviar_grafico(imagen, pie=""):
    try:
        files = {"photo": ("grafico.png", imagen, "image/png")}
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID, "caption": pie, "parse_mode": "Markdown"},
            files=files,
            timeout=15
        )
    except:
        pass

def sesion_activa():
    hora = datetime.utcnow() - timedelta(hours=5)
    return 8 <= hora.hour < 17

def hay_noticia_importante():
    hora = datetime.utcnow() - timedelta(hours=5)
    return (hora.hour == 8 and hora.minute < 60) or (hora.hour == 14 and hora.minute < 60)

def obtener_datos():
    try:
        df = yf.Ticker(SIMBOLO).history(period="20d", interval="1h")
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except:
        return pd.DataFrame()

def calcular_indicadores(df):
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()
    delta = df["Close"].diff()
    ganancia = delta.where(delta > 0, 0).rolling(14).mean()
    perdida = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = ganancia / perdida.replace(0, 1e-9)
    df["RSI"] = 100 - (100 / (1 + rs))
    df["TR"] = np.maximum(df["High"] - df["Low"], np.maximum(abs(df["High"] - df["Close"].shift()), abs(df["Low"] - df["Close"].shift())))
    df["ATR"] = df["TR"].rolling(14).mean()
    df["Volumen_Promedio"] = df["Volume"].rolling(20).mean()
    return df

def crear_grafico(df, entrada, sl, tp1, tp2, tp3, tipo):
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(8,4.5), dpi=80)
    ax.plot(df.index, df["Close"], color="#f7b731", lw=2, label="XAU/USD")
    ax.plot(df.index, df["EMA50"], color="#00a8ff", lw=1.5, label="EMA 50")
    ax.plot(df.index, df["EMA200"], color="#ff4757", lw=1.5, label="EMA 200")
    if tipo == "COMPRA":
        ax.axhline(entrada, color="#2ed573", ls="--", lw=1.5, label=f"Entrada: {entrada:.2f}")
        ax.axhline(sl, color="#ff4757", ls="--", lw=1.2, label=f"SL: {sl:.2f}")
    else:
        ax.axhline(entrada, color="#ffa502", ls="--", lw=1.5, label=f"Entrada: {entrada:.2f}")
        ax.axhline(sl, color="#ff4757", ls="--", lw=1.2, label=f"SL: {sl:.2f}")
    ax.axhline(tp1, color="#1e90ff", ls=":", lw=1)
    ax.axhline(tp2, color="#1e90ff", ls=":", lw=1)
    ax.axhline(tp3, color="#1e90ff", ls=":", lw=1)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.2)
    buffer = BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight")
    buffer.seek(0)
    plt.close(fig)
    return buffer

def guardar_historial(datos):
    try:
        with open(HISTORIAL, "r") as f:
            historial = json.load(f)
    except:
        historial = []
    historial.append(datos)
    with open(HISTORIAL, "w") as f:
        json.dump(historial, f, indent=2)

def analizar():
    global ULTIMA_SENAL
    if not sesion_activa():
        return
    if hay_noticia_importante():
        enviar_texto("⚠️ Noticia económica → pausa temporal")
        return
    df = obtener_datos()
    if len(df) < 150:
        return
    df = calcular_indicadores(df)
    ult = df.iloc[-1]
    ant = df.iloc[-2]
    alcista = ult.EMA50 > ult.EMA200 and ant.EMA50 > ant.EMA200
    bajista = ult.EMA50 < ult.EMA200 and ant.EMA50 < ant.EMA200
    rsi_ok = 35 < ult.RSI < 65
    volatilidad_ok = ult.ATR >= ATR_MINIMO
    volumen_ok = ult.Volume > ult.Volumen_Promedio
    if ULTIMA_SENAL["hora"] and (datetime.now() - ULTIMA_SENAL["hora"]).total_seconds() < 7200:
        return

    if alcista and rsi_ok and volatilidad_ok and volumen_ok:
        ent = round(ult.Close, 2)
        sl = round(ent - ult.ATR * ATR_MULT, 2)
        tp1 = round(ent + ult.ATR * ATR_MULT * TP1, 2)
        tp2 = round(ent + ult.ATR * ATR_MULT * TP2, 2)
        tp3 = round(ent + ult.ATR * ATR_MULT * TP3, 2)
        msg = f"""📈 *SEÑAL COMPRA XAU/USD*
⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}
💲 Entrada: {ent}
🛑 SL: {sl} | Riesgo {RIESGO_POR_OPERACION}%
🎯 TP1: {tp1} | TP2: {tp2} | TP3: {tp3}
✅ EMA50>EMA200 | RSI {ult.RSI:.1f} | ATR {ult.ATR:.2f}"""
        enviar_grafico(crear_grafico(df.tail(40), ent, sl, tp1, tp2, tp3, "COMPRA"), msg)
        guardar_historial({"fecha": datetime.now().strftime('%Y-%m-%d %H:%M'), "tipo": "COMPRA", "ent": ent, "sl": sl, "tp": [tp1, tp2, tp3]})
        ULTIMA_SENAL = {"hora": datetime.now(), "tipo": "COMPRA"}

    elif bajista and rsi_ok and volatilidad_ok and volumen_ok:
        ent = round(ult.Close, 2)
        sl = round(ent + ult.ATR * ATR_MULT, 2)
        tp1 = round(ent - ult.ATR * ATR_MULT * TP1, 2)
        tp2 = round(ent - ult.ATR * ATR_MULT * TP2, 2)
        tp3 = round(ent - ult.ATR * ATR_MULT * TP3, 2)
        msg = f"""📉 *SEÑAL VENTA XAU/USD*
⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}
💲 Entrada: {ent}
🛑 SL: {sl} | Riesgo {RIESGO_POR_OPERACION}%
🎯 TP1: {tp1} | TP2: {tp2} | TP3: {tp3}
✅ EMA50<EMA200 | RSI {ult.RSI:.1f} | ATR {ult.ATR:.2f}"""
        enviar_grafico(crear_grafico(df.tail(40), ent, sl, tp1, tp2, tp3, "VENTA"), msg)
        guardar_historial({"fecha": datetime.now().strftime('%Y-%m-%d %H:%M'), "tipo": "VENTA", "ent": ent, "sl": sl, "tp": [tp1, tp2, tp3]})
        ULTIMA_SENAL = {"hora": datetime.now(), "tipo": "VENTA"}

def ciclo_bot():
    enviar_texto("🤖 *Bot XAU/USD Optimizado INICIADO* ✅")
    while True:
        analizar()
        time.sleep(INTERVALO_REVISION)

if __name__ == "__main__":
    threading.Thread(target=mantener_activo, daemon=True).start()
    threading.Thread(target=ciclo_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
        
