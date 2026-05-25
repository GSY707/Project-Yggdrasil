import uvicorn

from yggdrasil_sdk.support import load_workspace_dotenv


def main() -> None:
    load_workspace_dotenv()
    uvicorn.run("yggdrasil_module_host.app:app", host="0.0.0.0", port=5002, reload=False)


if __name__ == "__main__":
    main()