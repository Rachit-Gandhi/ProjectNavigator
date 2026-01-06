import uvicorn


def main() -> None:
    # spins up the fastapi server
    uvicorn.run("src.api.routes:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
