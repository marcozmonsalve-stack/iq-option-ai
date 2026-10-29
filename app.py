
import os
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="IQ OPTION AI")

API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IQ OPTION AI</title>
<style>
body{margin:0;background:#080d18;color:#eef4ff;font-family:Arial,sans-serif;padding:20px}
main{max-width:700px;margin:auto}
h1{color:#36d6ad}
.card{background:#141e30;padding:18px;border-radius:15px;margin:14px 0}
select,button{width:100%;padding:14px;margin-top:10px;border-radius:9px;font-size:16px}
button{background:#36d6ad;border:0;font-weight:bold}
#signal{font-size:27px;font-weight:bold}
small{color:#aab7cc}
</style>
</head>
<body><main>
<h1>IQ OPTION AI</h1>
<p>Análisis técnico del mercado</p>
<div class="card">
<label>Par de divisas</label>
<select id="symbol">
<option>EUR/USD</option><option>GBP/USD</option>
<option>USD/JPY</option><option>AUD/USD</option>
<option>USD/CAD</option><option>EUR/JPY</option>
</select>
<label>Intervalo</label>
<select id="interval">
<option>1min</option><option selected>5min</option>
<option>15min</option><option>30min</option>
<option>1h</option>
</select>
<button onclick="analyze()">ANALIZAR MERCADO</button>
</div>
<div class="card">
<small>SEÑAL DEL SISTEMA</small>
<div id="signal">ESPERANDO ANÁLISIS</div>
<p id="detail">Selecciona un par y pulsa analizar.</p>
<p id="price"></p>
</div>
<small>Señales informativas, no garantizan resultados. Verifica los datos antes de operar.</small>
</main>
<script>
async function analyze(){
const s=document.getElementById('symbol').value;
const i=document.getElementById('interval').value;
document.getElementById('signal').textContent='ANALIZANDO...';
document.getElementById('detail').textContent='';
document.getElementById('price').textContent='';
try{
const r=await fetch('/api/analyze?symbol='+encodeURIComponent(s)+'&interval='+i);
const d=await r.json();
if(!r.ok)throw Error(d.detail||'No se pudo obtener información');
document.getElementById('signal').textContent=d.signal;
document.getElementById('detail').textContent=d.reason;
document.getElementById('price').textContent='Precio: '+d.price;
}catch(e){
document.getElementById('signal').textContent='SIN DATOS';
document.getElementById('detail').textContent=e.message;
}
}
</script>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

@app.get("/api/analyze")
def analyze(symbol: str = "EUR/USD", interval: str = "5min"):
    if not API_KEY:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Falta configurar TWELVE_DATA_API_KEY en el servidor."
        )

    response = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": symbol,
            "interval": interval,
            "outputsize": 100,
            "apikey": API_KEY
        },
        timeout=20
    )
    data = response.json()

    if response.status_code != 200 or "values" not in data:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=502,
            detail=data.get("message", "Error del proveedor de datos.")
        )

    values = data["values"]
    closes = [float(v["close"]) for v in reversed(values)]

    if len(closes) < 30:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=502,
            detail="No hay suficientes velas para analizar."
        )

    def ema(series, period):
        alpha = 2 / (period + 1)
        result = series[0]
        for value in series[1:]:
            result = alpha * value + (1 - alpha) * result
        return result

    fast = ema(closes, 9)
    slow = ema(closes, 21)

    changes = [closes[n] - closes[n-1] for n in range(1, len(closes))]
    gains = [max(x, 0) for x in changes[-14:]]
    losses = [max(-x, 0) for x in changes[-14:]]
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14

    rsi = 100 if avg_loss == 0 else 100 - (
        100 / (1 + avg_gain / avg_loss)
    )

    if fast > slow and rsi >= 55 and rsi < 70:
        signal = "COMPRA"
        reason = "Tendencia alcista y RSI favorable."
    elif fast < slow and rsi <= 45 and rsi > 30:
        signal = "VENTA"
        reason = "Tendencia bajista y RSI favorable."
    else:
        signal = "ESPERAR"
        reason = "Las condiciones no coinciden claramente."

    return {
        "symbol": symbol,
        "price": closes[-1],
        "signal": signal,
        "reason": reason,
        "rsi": round(rsi, 2),
        "ema9": round(fast, 6),
        "ema21": round(slow, 6)
    }
