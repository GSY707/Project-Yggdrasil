import uvicorn

from yggdrasil_sdk.support import load_workspace_dotenv


def main() -> None:
    load_workspace_dotenv()
    uvicorn.run("yggdrasil_agent_runtime.app:app", host="0.0.0.0", port=5001, reload=False)


if __name__ == "__main__":
    main()