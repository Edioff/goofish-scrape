import os
import re
import json
import random
import hashlib
import time
import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import quote
from curl_cffi.requests import AsyncSession
from playwright.async_api import async_playwright, Browser, BrowserContext
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail/1.0/"
APP_KEY = "34839810"
JSV = "2.7.2"

PROXY_USER = os.getenv("PROXY_USER", "codify-dc-any")
PROXY_PASS = os.getenv("PROXY_PASS", "58ADAB79s03h8TJ")
PROXY_HOST = os.getenv("PROXY_HOST", "gw.netnut.net:5959")

scraped_urls: set[str] = set()
_cookies: dict[str, str] = {}
_token: str = ""
_proxy_url: str = ""
_session_id: str = ""


def generate_session_id() -> str:
    return str(random.randint(100000, 999999))


def extract_item_id(url: str) -> str | None:
    match = re.search(r'[?&]id=(\d+)', url)
    return match.group(1) if match else None


def calc_sign(token: str, timestamp: str, data: str) -> str:
    raw = f"{token}&{timestamp}&{APP_KEY}&{data}"
    return hashlib.md5(raw.encode()).hexdigest()


def classify_response(ret: list) -> str:
    ret_str = str(ret)
    if "SUCCESS" in ret_str:
        return "success"
    if any(x in ret_str for x in ["RGV587_ERROR", "mini_login"]):
        return "blocked"
    if any(x in ret_str for x in ["NOT_FOUND", "DEL"]):
        return "not_found"
    return "error"


def parse_item_data(api_response: dict[str, Any], url: str) -> dict[str, Any]:
    data = api_response.get("data", {})
    item = data.get("itemDO", {})
    seller = data.get("sellerDO", {})

    images = [img.get("url", "") for img in item.get("imageInfos", []) if img.get("url")]

    gmt_raw = item.get("gmtCreate")
    gmt_formatted = None
    if gmt_raw:
        try:
            gmt_formatted = datetime.fromtimestamp(gmt_raw / 1000).isoformat()
        except:
            gmt_formatted = str(gmt_raw)

    return {
        "ITEM_ID": str(item.get("itemId", "")),
        "CATEGORY_ID": str(item.get("categoryId", "")),
        "TITLE": item.get("title", ""),
        "IMAGES": images,
        "SOLD_PRICE": item.get("soldPrice", ""),
        "BROWSE_COUNT": item.get("browseCnt", 0),
        "WANT_COUNT": item.get("wantCnt", 0),
        "COLLECT_COUNT": item.get("collectCnt", 0),
        "QUANTITY": item.get("quantity", 0),
        "GMT_CREATE": gmt_formatted,
        "SELLER_ID": str(seller.get("sellerId", "")),
        "url": url
    }


async def init_session() -> None:
    global _cookies, _token, _proxy_url, _session_id

    _session_id = generate_session_id()
    username = f"{PROXY_USER}-sid-{_session_id}"
    _proxy_url = f"http://{username}:{PROXY_PASS}@{PROXY_HOST}"

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=False,
        proxy={
            "server": f"http://{PROXY_HOST}",
            "username": username,
            "password": PROXY_PASS
        }
    )
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN"
    )

    page = await context.new_page()
    await page.goto(
        "https://www.goofish.com/item?id=995598771021",
        wait_until="domcontentloaded",
        timeout=120000
    )
    await page.wait_for_timeout(8000)

    cookies = await context.cookies()
    _cookies = {c["name"]: c["value"] for c in cookies}

    h5_tk = _cookies.get("_m_h5_tk", "")
    if "_" in h5_tk:
        _token = h5_tk.split("_")[0]

    await browser.close()
    await playwright.stop()


async def rotate_session() -> None:
    await init_session()


async def fetch_item(session: AsyncSession, item_id: str) -> dict[str, Any]:
    timestamp = str(int(time.time() * 1000))
    data = json.dumps({"itemId": item_id}, separators=(',', ':'))
    sign = calc_sign(_token, timestamp, data)

    url = (
        f"{API_URL}?jsv={JSV}&appKey={APP_KEY}&t={timestamp}&sign={sign}"
        f"&v=1.0&type=originaljson&accountSite=xianyu&dataType=json"
        f"&timeout=20000&api=mtop.taobao.idle.pc.detail&sessionOption=AutoLoginOnly"
        f"&spm_cnt=a21ybx.item.0.0"
    )

    headers = {
        "accept": "application/json",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "es-419,es;q=0.6",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.goofish.com",
        "priority": "u=1, i",
        "referer": "https://www.goofish.com/",
        "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Brave";v="144"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "sec-gpc": "1",
        "cookie": "; ".join(f"{k}={v}" for k, v in _cookies.items())
    }

    body = f"data={quote(data)}"

    resp = await session.post(
        url,
        headers=headers,
        data=body,
        proxy=_proxy_url,
        timeout=30,
        impersonate="chrome124"
    )
    return resp.json()


async def scrape_pdp(url: str, max_retries: int = 2) -> list[dict[str, Any]]:
    if url in scraped_urls:
        return [{"error": "duplicate", "url": url}]

    item_id = extract_item_id(url)
    if not item_id:
        return [{"error": "invalid_url", "url": url}]

    if not _token:
        await init_session()

    for attempt in range(max_retries):
        try:
            async with AsyncSession() as session:
                result = await fetch_item(session, item_id)

            ret = result.get("ret", [])
            status = classify_response(ret)

            if status == "success":
                scraped_urls.add(url)
                return [parse_item_data(result, url)]

            if status == "not_found":
                scraped_urls.add(url)
                return [{"ITEM_ID": item_id, "error": "not_found", "url": url}]

            if status == "blocked":
                await rotate_session()
                continue

        except Exception as e:
            if attempt == max_retries - 1:
                return [{"ITEM_ID": item_id, "error": str(e), "url": url}]
            await rotate_session()

    return [{"ITEM_ID": item_id, "error": "max_retries", "url": url}]


async def scrape_batch(urls: list[str], batch_size: int = 50) -> list[dict[str, Any]]:
    if not _token:
        await init_session()

    results = []
    blocked_count = 0

    async with AsyncSession() as session:
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]

            for url in batch:
                if url in scraped_urls:
                    results.append({"error": "duplicate", "url": url})
                    continue

                item_id = extract_item_id(url)
                if not item_id:
                    results.append({"error": "invalid_url", "url": url})
                    continue

                try:
                    api_result = await fetch_item(session, item_id)
                    ret = api_result.get("ret", [])
                    status = classify_response(ret)

                    if status == "success":
                        scraped_urls.add(url)
                        results.append(parse_item_data(api_result, url))
                        blocked_count = 0
                    elif status == "not_found":
                        scraped_urls.add(url)
                        results.append({"ITEM_ID": item_id, "error": "not_found", "url": url})
                    elif status == "blocked":
                        blocked_count += 1
                        results.append({"ITEM_ID": item_id, "error": "blocked", "url": url})
                        if blocked_count >= 3:
                            await rotate_session()
                            blocked_count = 0
                    else:
                        results.append({"ITEM_ID": item_id, "error": "unknown", "url": url})

                except Exception as e:
                    results.append({"ITEM_ID": item_id, "error": str(e)[:100], "url": url})

    return results


async def close_session() -> None:
    global _cookies, _token, _proxy_url, _session_id
    _cookies = {}
    _token = ""
    _proxy_url = ""
    _session_id = ""


if __name__ == "__main__":
    import csv

    INPUT_CSV = "goofish_urls.csv"
    OUTPUT_CSV = "goofish_results.csv"
    TARGET = 10000

    def load_urls():
        with open(INPUT_CSV, "r", encoding="utf-8") as f:
            return [row["URL"] for row in csv.DictReader(f)]

    def save_results(results):
        fields = ["URL", "ITEM_ID", "CATEGORY_ID", "TITLE", "IMAGES", "SOLD_PRICE",
                  "BROWSE_COUNT", "WANT_COUNT", "COLLECT_COUNT", "QUANTITY", "GMT_CREATE", "SELLER_ID"]
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in results:
                if "error" not in r:
                    w.writerow({
                        "URL": r.get("url", ""),
                        "ITEM_ID": r.get("ITEM_ID", ""),
                        "CATEGORY_ID": r.get("CATEGORY_ID", ""),
                        "TITLE": r.get("TITLE", ""),
                        "IMAGES": json.dumps(r.get("IMAGES", []), ensure_ascii=False),
                        "SOLD_PRICE": r.get("SOLD_PRICE", ""),
                        "BROWSE_COUNT": r.get("BROWSE_COUNT", 0),
                        "WANT_COUNT": r.get("WANT_COUNT", 0),
                        "COLLECT_COUNT": r.get("COLLECT_COUNT", 0),
                        "QUANTITY": r.get("QUANTITY", 0),
                        "GMT_CREATE": r.get("GMT_CREATE", ""),
                        "SELLER_ID": r.get("SELLER_ID", ""),
                    })

    async def run_batch():
        urls = load_urls()
        print(f"Loaded {len(urls)} URLs. Target: {TARGET}")

        await init_session()
        print("Session ready\n")

        results = []
        done = set()
        blocked = 0
        start = time.time()

        async with AsyncSession() as session:
            for i, url in enumerate(urls):
                success_count = len([r for r in results if "error" not in r])
                if success_count >= TARGET:
                    break

                item_id = extract_item_id(url)
                if not item_id or url in done:
                    continue

                try:
                    resp = await fetch_item(session, item_id)
                    status = classify_response(resp.get("ret", []))

                    if status == "success":
                        results.append(parse_item_data(resp, url))
                        done.add(url)
                        blocked = 0
                    elif status == "not_found":
                        results.append({"error": "not_found", "url": url})
                        done.add(url)
                    elif status == "blocked":
                        blocked += 1
                        if blocked >= 5:
                            print(f"[{i}] Rotating session...")
                            await rotate_session()
                            blocked = 0

                    if (i + 1) % 100 == 0:
                        ok = len([r for r in results if "error" not in r])
                        elapsed = time.time() - start
                        print(f"[{i+1}] OK: {ok} | {ok/elapsed:.1f}/s")
                        save_results(results)

                except Exception as e:
                    print(f"[{i}] Error: {str(e)[:40]}")

        await close_session()
        save_results(results)

        elapsed = time.time() - start
        ok = len([r for r in results if "error" not in r])
        print(f"\nDone! {ok} products in {elapsed:.0f}s ({ok/elapsed:.1f}/s)")
        print(f"Output: {OUTPUT_CSV}")

    asyncio.run(run_batch())
