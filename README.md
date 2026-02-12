# Goofish Scraper — Alibaba Anti-Bot Bypass

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![curl_cffi](https://img.shields.io/badge/curl__cffi-TLS%20Impersonation-00599C?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

> Scraped **18,000+ products** from Alibaba's Goofish platform by cracking the MTOP SDK cookie signing mechanism. Hybrid Playwright + curl_cffi approach achieving **5-10 products/second**.

## Overview

Goofish (Xianyu) is Alibaba's second-hand marketplace, protected by the MTOP SDK — Alibaba's proprietary anti-bot system that generates dynamic cookies via JavaScript, requires cryptographic request signing, and detects HTTP clients through TLS fingerprinting.

This scraper bypasses all three layers using a hybrid approach: Playwright captures authentication cookies once per session, then `curl_cffi` with Chrome TLS impersonation handles all subsequent API requests at high speed.

## Results

| Metric | Value |
|--------|-------|
| Products scraped | **18,000+** |
| Success rate | **~85%** |
| Speed | **5-10 products/second** |
| Data fields extracted | **11/11 (100%)** |

## How the Bypass Works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Playwright    │────>│  Cookies + Token │────>│   curl_cffi     │
│  (1x per session)│    │   _m_h5_tk       │     │ (all requests)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Cookie Signing (MTOP SDK)

```python
sign = MD5(token + "&" + timestamp + "&" + appKey + "&" + data)
```

Where:
- `token` — First part of `_m_h5_tk` cookie (before `_`)
- `timestamp` — Current time in milliseconds
- `appKey` — `34839810` (Goofish constant)
- `data` — Request payload as JSON string

### Why This Architecture?

| Approach | Speed | Why (not) |
|----------|-------|-----------|
| Playwright for everything | ~0.5 products/sec | Too slow for scale |
| curl_cffi without auth | 0% success | Missing required cookies |
| **Hybrid (this project)** | **5-10/sec** | Best of both worlds |

## Features

- **MTOP SDK bypass** — Cracked cookie signing mechanism
- **TLS impersonation** — `curl_cffi` with Chrome 124 fingerprint
- **Multiprocessing** — 3 parallel workers with independent proxy sessions
- **Concurrency** — 30 simultaneous requests per worker
- **Auto session rotation** — Detects blocks and rotates IP/cookies
- **FastAPI endpoint** — REST API for individual product scraping
- **Docker ready** — Full containerized deployment

## Data Points

| Field | Description | Example |
|-------|-------------|---------|
| ITEM_ID | Unique product ID | `864893386498` |
| CATEGORY_ID | Category | `50025969` |
| TITLE | Product title | `iPhone 14 Pro Max 256GB` |
| IMAGES | Image URLs (JSON array) | `["https://...jpg"]` |
| SOLD_PRICE | Price in CNY | `5999` |
| BROWSE_COUNT | Views | `1234` |
| WANT_COUNT | "I want it" count | `56` |
| COLLECT_COUNT | Favorites | `23` |
| QUANTITY | Available stock | `1` |
| GMT_CREATE | Publication date | `2024-01-15T10:30:00` |
| SELLER_ID | Seller ID | `2208574658321` |

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)

- **curl_cffi** — Chrome TLS fingerprint impersonation
- **Playwright** — One-time cookie capture
- **FastAPI** — REST API wrapper
- **Docker** — Containerized deployment
- **Multiprocessing** — Parallel workers with proxy isolation

## Installation

```bash
git clone https://github.com/Edioff/goofish-scrape.git
cd goofish-scrape
pip install -r requirements.txt
playwright install chromium
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your proxy credentials
```

## Usage

### API (single product)

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
# GET http://localhost:8080/scrapePDP?url=https://www.goofish.com/item?id=123456
```

### Bulk scraping

```bash
python scraping.py
# Outputs: goofish_results.csv
```

### Docker

```bash
docker-compose up --build
```

## Notes

- Requires residential proxy credentials (NetNut or similar)
- For educational and research purposes
- Respect the platform's Terms of Service

## Author

**Johan Cruz** — Data Engineer & Web Scraping Specialist
- GitHub: [@Edioff](https://github.com/Edioff)
- Available for freelance projects

## License

MIT
