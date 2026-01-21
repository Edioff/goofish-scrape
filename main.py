from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from fastapi.openapi.utils import get_openapi
from scraping import scrape_pdp

YOUR_NAME = "JohanCruz"

app = FastAPI()


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=f"Goofish Scraping API - {YOUR_NAME}",
        version="1.0.0",
        description="Technical Assessment for Backend Engineer at Iceberg Data",
        routes=app.routes
    )

    if "HTTPValidationError" in openapi_schema.get("components", {}).get("schemas", {}):
        del openapi_schema["components"]["schemas"]["HTTPValidationError"]
    if "ValidationError" in openapi_schema.get("components", {}).get("schemas", {}):
        del openapi_schema["components"]["schemas"]["ValidationError"]

    for path in openapi_schema.get("paths", {}).values():
        for method in path.values():
            method.pop("servers", None)
            if "responses" in method and "422" in method["responses"]:
                del method["responses"]["422"]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/", include_in_schema=False, response_class=RedirectResponse)
async def root():
    return "/docs"


@app.get("/scrapePDP", tags=["Scraping"])
async def scrape_pdp_endpoint(
    url: str = Query(..., description="Goofish product URL to scrape")
) -> list:
    return await scrape_pdp(url)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
