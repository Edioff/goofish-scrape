# Goofish Scraping API

**Prueba Tecnica - Backend Engineer @ Iceberg Data**
**Candidato:** Johan Andres Cruz Forero

---

## Resultados

| Metrica | Valor |
|---------|-------|
| Productos scrapeados | **18,000+** |
| Tasa de exito | ~85% |
| Velocidad promedio | 5-10 productos/segundo |
| Campos extraidos | 11/11 (100%) |

---

## Solucion Implementada

### El Problema

Goofish (闲鱼) utiliza el SDK MTOP de Alibaba que:
- Genera cookies dinamicas via JavaScript
- Requiere firma digital (`sign`) en cada request
- Detecta y bloquea clientes HTTP por fingerprinting TLS

### Mi Solucion: Enfoque Hibrido

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Playwright    │────>│  Cookies + Token │────>│   curl_cffi     │
│  (1 vez/sesion) │     │   _m_h5_tk       │     │ (requests API)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

1. **Playwright** abre el navegador UNA vez para capturar cookies de autenticacion
2. **curl_cffi** con `impersonate="chrome124"` replica el fingerprint TLS de Chrome
3. Requests directos a la API interna: `h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail`

### Calculo del Sign

```python
sign = MD5(token + "&" + timestamp + "&" + appKey + "&" + data)
```

Donde:
- `token`: primera parte de cookie `_m_h5_tk` (antes del `_`)
- `timestamp`: milisegundos actuales
- `appKey`: `34839810` (constante de Goofish)
- `data`: `{"itemId":"XXXXX"}`

### Optimizaciones

- **Cache de URLs scrapeadas**: evita requests duplicados
- **Multiprocessing**: 3 workers paralelos
- **Concurrencia**: 30 requests simultaneos por worker
- **Rotacion de sesion**: detecta bloqueos y rota IP/cookies automaticamente
- **Manejo de errores**: no reintenta productos eliminados (404)

---

## Estructura del Proyecto

```
├── main.py              # FastAPI - endpoint /scrapePDP
├── scraping.py          # Logica de scraping + multiprocessing
├── requirements.txt     # Dependencias
├── Dockerfile           # Imagen Docker
├── docker-compose.yml   # Orquestacion
├── .env.example         # Template de configuracion
└── README.md
```

---

## Instalacion y Uso

### Requisitos
- Python 3.10+
- Credenciales de proxy NetNut

### Setup

```bash
# Clonar e instalar
git clone <repo>
cd goofish-scraper
pip install -r requirements.txt
playwright install chromium

# Configurar proxy
cp .env.example .env
# Editar .env con credenciales
```

### Ejecutar API (endpoint individual)

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

Luego visitar: `http://localhost:8080/scrapePDP?url=https://www.goofish.com/item?id=123456`

### Ejecutar Scraping Masivo

```bash
python scraping.py
```

Genera `goofish_results.csv` con los datos extraidos.

### Docker

```bash
docker-compose up --build
```

---

## Datapoints Extraidos

| Campo | Descripcion | Ejemplo |
|-------|-------------|---------|
| ITEM_ID | ID unico del producto | `864893386498` |
| CATEGORY_ID | Categoria | `50025969` |
| TITLE | Titulo del producto | `iPhone 14 Pro Max 256GB` |
| IMAGES | URLs de imagenes (JSON array) | `["https://...jpg"]` |
| SOLD_PRICE | Precio en CNY | `5999` |
| BROWSE_COUNT | Visualizaciones | `1234` |
| WANT_COUNT | "Lo quiero" | `56` |
| COLLECT_COUNT | Favoritos | `23` |
| QUANTITY | Stock disponible | `1` |
| GMT_CREATE | Fecha publicacion (ISO) | `2024-01-15T10:30:00` |
| SELLER_ID | ID del vendedor | `2208574658321` |

---

## Configuracion del Proxy

```env
PROXY_USER=tu-usuario
PROXY_PASS=tu-password
PROXY_HOST=gw.netnut.net:5959
```

La sesion se mantiene agregando `-sid-XXXXXX` al username para conservar la misma IP entre requests.

---

## Decisiones Tecnicas

### Por que curl_cffi en lugar de requests/httpx?
Goofish detecta el fingerprint TLS. `curl_cffi` puede imitar exactamente el fingerprint de Chrome, evitando bloqueos.

### Por que Playwright solo para cookies?
Usar Playwright para cada request seria lento (~2s/producto). Capturando cookies una vez y usando curl_cffi para requests, logramos ~10 productos/segundo.

### Por que multiprocessing en lugar de asyncio puro?
Cada worker necesita su propia sesion de proxy (IP diferente). Multiprocessing aisla completamente cada worker, evitando conflictos de estado global.

---

Johan Andres Cruz Forero
Enero 2025
