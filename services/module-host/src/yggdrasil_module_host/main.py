import uvicorn


def main() -> None:
    uvicorn.run("yggdrasil_module_host.app:app", host="127.0.0.1", port=8020, reload=False)


if __name__ == "__main__":
    main()