#!/usr/bin/env node

import { spawn } from "node:child_process";

const SERVICES_FOR_LOGS = ["core-api", "agent-runtime", "module-host", "worker", "web"];
const APP_SERVICES = ["web", "worker", "agent-runtime", "module-host", "core-api"];

const command = process.argv[2] ?? "status";
const rest = process.argv.slice(3);
const composePrefix = [
  "compose",
  "--env-file",
  "infra/product.env.template",
  "-f",
  "infra/docker-compose.product.yml",
];

const commandArgs = {
  config: ["config"],
  up: ["up", "-d", "--build"],
  down: ["down"],
  status: ["ps"],
  logs: ["logs", "-f", ...SERVICES_FOR_LOGS],
  backup: ["exec", "-T", "core-api", "yggdrasil-ops", "backup", "create"],
};

const composeEnv = {
  ...process.env,
  COMPOSE_BAKE: "false",
  COMPOSE_DOCKER_CLI_BUILD: "0",
  DOCKER_BUILDKIT: "0",
};

function runCompose(args) {
  return new Promise((resolve, reject) => {
    const child = spawn("docker", [...composePrefix, ...args], {
      env: composeEnv,
      stdio: "inherit",
    });

    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`docker compose ${args.join(" ")} exited with code ${code ?? 1}`));
    });
  });
}

async function restoreProductStack() {
  await runCompose(["stop", ...APP_SERVICES]);
  let restoreError = null;
  try {
    await runCompose(["run", "--rm", "--no-deps", "core-api", "yggdrasil-ops", "backup", "restore", ...rest]);
  } catch (error) {
    restoreError = error;
  }
  await runCompose(["up", "-d", ...APP_SERVICES]);
  if (restoreError) {
    throw restoreError;
  }
}

async function main() {
  if (command === "restore") {
    await restoreProductStack();
    return;
  }
  const composeArgs = commandArgs[command] ?? [command, ...rest];
  await runCompose(composeArgs);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
