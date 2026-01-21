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
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail/1.0/"
APP_KEY = "34839810"
JSV = "2.7.2"

PROXY_USER = os.getenv("PROXY_USER", "")
PROXY_PASS = os.getenv("PROXY_PASS", "")
PROXY_HOST = os.getenv("PROXY_HOST", "")

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
        headless=True,
        proxy={
            "server": f"http://{PROXY_HOST}",
            "username": username,
            "password": PROXY_PASS
        }
    )
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
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
                return [parse_item_data(result, url)]

            if status == "not_found":
                return [{"ITEM_ID": item_id, "error": "not_found", "url": url}]

            if status == "blocked":
                await rotate_session()
                continue

        except Exception as e:
            if attempt == max_retries - 1:
                return [{"ITEM_ID": item_id, "error": str(e), "url": url}]
            await rotate_session()

    return [{"ITEM_ID": item_id, "error": "max_retries", "url": url}]


# ============== MULTIPROCESSING ==============

import csv
import multiprocessing as mp
from queue import Empty

MP_CONFIG = {
    "INPUT_CSV": "goofish_urls.csv",
    "OUTPUT_CSV": "goofish_results.csv",
    "TARGET": 50000,
    "NUM_WORKERS": 3,
    "CONCURRENT_PER_WORKER": 30
}


def load_scraped_cache(filepath):
    scraped = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item_id = row.get("ITEM_ID", "")
                if item_id:
                    scraped.add(item_id)
        print(f"[CACHE] {len(scraped)} items ya scrapeados")
    except FileNotFoundError:
        print("[CACHE] Sin CSV previo")
    return scraped


def mp_save_results(results, filepath):
    fields = ["URL", "ITEM_ID", "CATEGORY_ID", "TITLE", "IMAGES", "SOLD_PRICE",
              "BROWSE_COUNT", "WANT_COUNT", "COLLECT_COUNT", "QUANTITY", "GMT_CREATE", "SELLER_ID"]

    seen_ids = set()
    unique_data = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item_id = row.get("ITEM_ID", "")
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    unique_data.append(row)
    except FileNotFoundError:
        pass

    for r in results:
        if "error" not in r:
            item_id = r.get("ITEM_ID", "")
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                unique_data.append({
                    "URL": r.get("url", ""),
                    "ITEM_ID": item_id,
                    "CATEGORY_ID": r.get("CATEGORY_ID", ""),
                    "TITLE": r.get("TITLE", ""),
                    "IMAGES": json.dumps(r.get("IMAGES", []), ensure_ascii=False) if isinstance(r.get("IMAGES"), list) else r.get("IMAGES", ""),
                    "SOLD_PRICE": r.get("SOLD_PRICE", ""),
                    "BROWSE_COUNT": r.get("BROWSE_COUNT", 0),
                    "WANT_COUNT": r.get("WANT_COUNT", 0),
                    "COLLECT_COUNT": r.get("COLLECT_COUNT", 0),
                    "QUANTITY": r.get("QUANTITY", 0),
                    "GMT_CREATE": r.get("GMT_CREATE", ""),
                    "SELLER_ID": r.get("SELLER_ID", ""),
                })

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in unique_data:
            w.writerow(row)


async def mp_worker_scrape(worker_id: int, urls: list, result_queue):
    global _cookies, _token, _proxy_url, _session_id

    MAX_RETRIES = 2
    CONCURRENT = MP_CONFIG["CONCURRENT_PER_WORKER"]
    start_time = time.time()

    print(f"[W{worker_id}] Iniciando sesion...", flush=True)
    await init_session()
    print(f"[W{worker_id}] Listo - token: {_token[:16]}... (concurrent={CONCURRENT})", flush=True)

    stats = {"ok": 0, "not_found": 0, "blocked": 0, "rotations": 0}
    pending_urls = list(urls)
    retry_count = {}
    round_num = 1

    while pending_urls:
        print(f"[W{worker_id}] === Ronda {round_num} - {len(pending_urls)} URLs ===", flush=True)
        blocked_urls = []
        round_ok = 0
        round_blocked = 0
        consecutive_blocked = 0
        need_rotate = False

        semaphore = asyncio.Semaphore(CONCURRENT)

        async def fetch_one(session, url, idx):
            nonlocal round_ok, round_blocked, consecutive_blocked, need_rotate
            async with semaphore:
                item_id = extract_item_id(url)
                if not item_id:
                    return {"error": "invalid_url", "url": url}

                try:
                    resp = await fetch_item(session, item_id)
                    status = classify_response(resp.get("ret", []))

                    if status == "success":
                        round_ok += 1
                        stats["ok"] += 1
                        consecutive_blocked = 0
                        return parse_item_data(resp, url)
                    elif status == "not_found":
                        stats["not_found"] += 1
                        return {"error": "not_found", "url": url}
                    elif status == "blocked":
                        round_blocked += 1
                        stats["blocked"] += 1
                        consecutive_blocked += 1
                        if consecutive_blocked >= 10:
                            need_rotate = True
                        retries = retry_count.get(url, 0)
                        if retries < MAX_RETRIES:
                            retry_count[url] = retries + 1
                            return {"blocked_retry": True, "url": url}
                        return {"error": "max_retries", "url": url}
                    else:
                        return {"error": "unknown", "url": url}
                except Exception as e:
                    return {"error": str(e)[:50], "url": url}

        async with AsyncSession() as session:
            for batch_start in range(0, len(pending_urls), CONCURRENT):
                if need_rotate:
                    print(f"[W{worker_id}] Rotando sesion...", flush=True)
                    await rotate_session()
                    stats["rotations"] += 1
                    need_rotate = False
                    consecutive_blocked = 0

                batch = pending_urls[batch_start:batch_start + CONCURRENT]
                tasks = [fetch_one(session, url, i) for i, url in enumerate(batch)]
                results = await asyncio.gather(*tasks)

                for r in results:
                    if r.get("blocked_retry"):
                        blocked_urls.append(r["url"])
                    elif "error" not in r:
                        result_queue.put(r)
                    else:
                        result_queue.put(r)

                processed = min(batch_start + CONCURRENT, len(pending_urls))
                elapsed = time.time() - start_time
                rate = stats["ok"] / elapsed if elapsed > 0 else 0
                print(f"[W{worker_id}] {processed}/{len(pending_urls)} | OK:{round_ok} Blk:{round_blocked} | {rate:.2f}/s", flush=True)

        if blocked_urls:
            print(f"[W{worker_id}] Ronda {round_num}: OK={round_ok}, Blocked={len(blocked_urls)} -> Reintentando", flush=True)
            await rotate_session()
            stats["rotations"] += 1
            pending_urls = blocked_urls
            round_num += 1
        else:
            pending_urls = []

    elapsed = time.time() - start_time
    rate = stats["ok"] / elapsed if elapsed > 0 else 0
    print(f"[W{worker_id}] TERMINADO | OK:{stats['ok']} | Rotaciones:{stats['rotations']} | {rate:.2f}/s", flush=True)


def mp_run_worker(worker_id: int, urls: list, result_queue):
    asyncio.run(mp_worker_scrape(worker_id, urls, result_queue))


if __name__ == "__main__":
    def main():
        cfg = MP_CONFIG
        print(f"=== GOOFISH SCRAPER ===")
        print(f"Workers: {cfg['NUM_WORKERS']}, Concurrent: {cfg['CONCURRENT_PER_WORKER']}, Target: {cfg['TARGET']}\n")

        scraped_cache = load_scraped_cache(cfg["OUTPUT_CSV"])

        with open(cfg["INPUT_CSV"], "r", encoding="utf-8") as f:
            all_urls = [row["URL"] for row in csv.DictReader(f)]

        urls = []
        for url in all_urls:
            item_id = extract_item_id(url)
            if item_id and item_id not in scraped_cache:
                urls.append(url)

        urls = urls[:cfg["TARGET"] + 10000]
        print(f"URLs a procesar: {len(urls)}\n")

        chunk_size = len(urls) // cfg["NUM_WORKERS"]
        url_chunks = [urls[i*chunk_size:(i+1)*chunk_size] for i in range(cfg["NUM_WORKERS"])]

        result_queue = mp.Queue()

        start = time.time()
        workers = []
        for i in range(cfg["NUM_WORKERS"]):
            p = mp.Process(target=mp_run_worker, args=(i, url_chunks[i], result_queue))
            p.start()
            workers.append(p)

        all_results = []
        last_save = 0

        while any(p.is_alive() for p in workers) or not result_queue.empty():
            try:
                while True:
                    r = result_queue.get_nowait()
                    all_results.append(r)
            except Empty:
                pass

            ok_count = len([r for r in all_results if "error" not in r])
            if ok_count - last_save >= 50:
                mp_save_results(all_results, cfg["OUTPUT_CSV"])
                elapsed = time.time() - start
                print(f"[GUARDADO] {ok_count} productos | {ok_count/elapsed:.1f}/s")
                last_save = ok_count

            if ok_count >= cfg["TARGET"]:
                print(f"\n[!] TARGET {cfg['TARGET']} alcanzado!")
                for p in workers:
                    p.terminate()
                break

            time.sleep(0.5)

        for p in workers:
            p.join(timeout=5)

        while not result_queue.empty():
            try:
                all_results.append(result_queue.get_nowait())
            except Empty:
                break

        mp_save_results(all_results, cfg["OUTPUT_CSV"])

        elapsed = time.time() - start
        ok = len([r for r in all_results if "error" not in r])
        errors = len([r for r in all_results if "error" in r])

        print(f"\n{'='*40}")
        print(f"COMPLETADO")
        print(f"OK: {ok} | Errores: {errors}")
        print(f"Tiempo: {elapsed:.0f}s | Rate: {ok/elapsed:.2f}/s")

    main()
