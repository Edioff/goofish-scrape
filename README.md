# Goofish Scraping API

Microservicio para extraccion de datos de productos del marketplace Goofish (闲鱼).

## Estructura

```
├── main.py           # FastAPI endpoints
├── scraping.py       # Logica de scraping
├── requirements.txt  # Dependencias
├── goofish_urls.csv  # URLs de entrada (50k)
└── goofish_results.csv  # Datos extraidos
```

## Instalacion

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Editar .env con las credenciales del proxy
```

## Uso

### API (endpoint individual)
```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```
Luego: `GET /scrapePDP?url=https://www.goofish.com/item?id=123456`

### Scraping masivo
```bash
python scraping.py
```
Genera `goofish_results.csv` con los datos extraidos.

## Arquitectura

El scraper usa un enfoque hibrido:

1. **Playwright** abre el navegador una vez para obtener cookies de autenticacion (`_m_h5_tk`, `cookie2`, etc)
2. **curl_cffi** hace las peticiones HTTP directas a la API interna con las cookies capturadas
3. Si detecta bloqueo (5 consecutivos), rota la sesion automaticamente

### Por que este enfoque?

Goofish usa el SDK MTOP de Alibaba que genera cookies via JavaScript. Los clientes HTTP normales (requests, httpx) son bloqueados por fingerprinting TLS.

`curl_cffi` con `impersonate="chrome124"` replica el fingerprint TLS de Chrome, permitiendo requests rapidos (~10/segundo) despues de obtener las cookies del navegador real.

### Calculo del Sign

```
sign = MD5(token + "&" + timestamp + "&" + appKey + "&" + data)
```

Donde:
- `token`: parte antes del `_` en cookie `_m_h5_tk`
- `timestamp`: milisegundos actuales
- `appKey`: `34839810` (constante)
- `data`: `{"itemId":"XXXXX"}`

## Datapoints extraidos

| Campo | Descripcion |
|-------|-------------|
| ITEM_ID | ID del producto |
| CATEGORY_ID | ID de categoria |
| TITLE | Titulo |
| IMAGES | URLs de imagenes (JSON) |
| SOLD_PRICE | Precio |
| BROWSE_COUNT | Visualizaciones |
| WANT_COUNT | "Lo quiero" |
| COLLECT_COUNT | Favoritos |
| QUANTITY | Stock disponible |
| GMT_CREATE | Fecha publicacion |
| SELLER_ID | ID vendedor |

## Proxy

Configurar en `.env`:
```
PROXY_USER=tu-usuario
PROXY_PASS=tu-password
PROXY_HOST=host:puerto
```

La sesion se mantiene con el sufijo `-sid-XXXXXX` en el username para conservar la misma IP.

---
Johan Andres Cruz Forero - Prueba tecnica Iceberg Data
