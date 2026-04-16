import uvicorn


def main() -> None:
    uvicorn.run("yggdrasil_agent_runtime.app:app", host="127.0.0.1", port=8010, reload=False)


if __name__ == "__main__":
    main()