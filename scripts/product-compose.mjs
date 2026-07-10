#!/usr/bin/env node

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";

const SERVICES_FOR_LOGS = ["core-api", "agent-runtime", "module-host", "worker", "web"];
const APP_SERVICES = ["web", "worker", "agent-runtime", "module-host", "core-api"];

const command = process.argv[2] ?? "status";
const rawRest = process.argv.slice(3);
const rest = rawRest[0] === "--" ? rawRest.slice(1) : rawRest;
const productEnvPath = existsSync("infra/product.env") ? "infra/product.env" : "infra/product.env.template";
const productEnvFileForCompose = productEnvPath.endsWith("product.env") ? "./product.env" : "./product.env.template";
const composePrefix = [
  "compose",
  "--env-file",
  productEnvPath,
  "-f",
  "infra/docker-compose.product.yml",
];

const commandArgs = {
  config: ["config"],
  up: ["up", "-d", "--no-build"],
  down: ["down"],
  status: ["ps"],
  logs: ["logs", "-f", ...SERVICES_FOR_LOGS],
  backup: ["exec", "-T", "core-api", "yggdrasil-ops", "backup", "create"],
  snapshots: ["run", "--rm", "--no-deps", "core-api", "yggdrasil-ops", "backup", "list"],
};

const composeEnv = {
  ...process.env,
  COMPOSE_BAKE: "false",
  YGGDRASIL_PRODUCT_ENV_FILE: productEnvFileForCompose,
};

function runCommand(executable, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, {
      env: composeEnv,
      stdio: "inherit",
    });

    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${executable} ${args.join(" ")} exited with code ${code ?? 1}`));
    });
  });
}

function runCompose(args) {
  return runCommand("docker", [...composePrefix, ...args]);
}

function runProductSmoke() {
  return runCommand("uv", ["run", "python", "-m", "yggdrasil_sdk.ops_cli", "product-compose-smoke"]);
}

async function buildProductImages() {
  const legacyBuildEnv = { ...composeEnv, DOCKER_BUILDKIT: "0" };
  for (const [dockerfile, tag] of [
    ["infra/docker/python-service.Dockerfile", "project-yggdrasil/python-service:local"],
    ["infra/docker/web.Dockerfile", "project-yggdrasil/web:local"],
  ]) {
    await new Promise((resolve, reject) => {
      const child = spawn("docker", ["build", "-f", dockerfile, "-t", tag, "."], {
        env: legacyBuildEnv,
        stdio: "inherit",
      });
      child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`docker build ${dockerfile} exited with code ${code ?? 1}`)));
    });
  }
}

async function restoreProductStack(args) {
  await runCompose(["stop", ...APP_SERVICES]);
  let restoreError = null;
  try {
    await runCompose(["run", "--rm", "--no-deps", "core-api", "yggdrasil-ops", "backup", "restore", ...args]);
  } catch (error) {
    restoreError = error;
  }
  await runCompose(["up", "-d", ...APP_SERVICES]);
  if (restoreError) {
    throw restoreError;
  }
}

async function upgradeProductStack() {
  await runCompose(["exec", "-T", "core-api", "yggdrasil-ops", "backup", "create"]);
  await runCompose(["stop", ...APP_SERVICES]);
  await buildProductImages();
  await runCompose(["up", "-d", "--no-build"]);
  await runProductSmoke();
}

async function tryProtectiveBackup() {
  try {
    await runCompose(["run", "--rm", "--no-deps", "core-api", "yggdrasil-ops", "backup", "create"]);
  } catch (error) {
    console.warn(`Protective pre-rollback backup failed; continuing rollback: ${error.message}`);
  }
}

async function rollbackProductStack() {
  await tryProtectiveBackup();
  await restoreProductStack(rest);
  await runProductSmoke();
}

async function main() {
  if (command === "up") {
    await buildProductImages();
    await runCompose(["up", "-d", "--no-build"]);
    return;
  }
  if (command === "restore") {
    await restoreProductStack(rest);
    return;
  }
  if (command === "upgrade") {
    await upgradeProductStack();
    return;
  }
  if (command === "rollback") {
    await rollbackProductStack();
    return;
  }
  const composeArgs = commandArgs[command] ?? [command, ...rest];
  await runCompose(composeArgs);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
