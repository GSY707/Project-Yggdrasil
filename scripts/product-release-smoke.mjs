#!/usr/bin/env node

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";

const productEnvPath = existsSync("infra/product.env") ? "infra/product.env" : "infra/product.env.template";
const productEnvFileForCompose = productEnvPath.endsWith("product.env") ? "./product.env" : "./product.env.template";
const composePrefix = ["compose", "--env-file", productEnvPath, "-f", "infra/docker-compose.product.yml"];
const composeEnv = {
  ...process.env,
  COMPOSE_BAKE: "false",
  COMPOSE_DOCKER_CLI_BUILD: "0",
  DOCKER_BUILDKIT: "0",
  YGGDRASIL_PRODUCT_ENV_FILE: productEnvFileForCompose,
};

function run(executable, args, { capture = false } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, {
      env: composeEnv,
      stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
    });
    let stdout = "";
    let stderr = "";
    if (capture) {
      child.stdout.on("data", (chunk) => {
        stdout += chunk.toString();
      });
      child.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
      });
    }
    child.on("exit", (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
        return;
      }
      reject(new Error(`${executable} ${args.join(" ")} exited with code ${code ?? 1}\n${stderr || stdout}`));
    });
  });
}

function dockerCompose(args, options) {
  return run("docker", [...composePrefix, ...args], options);
}

async function productSmoke() {
  const result = await run("uv", ["run", "python", "-m", "yggdrasil_sdk.ops_cli", "product-compose-smoke"], { capture: true });
  process.stdout.write(result.stdout);
  const payload = JSON.parse(result.stdout);
  if (payload.status !== "ok") {
    throw new Error(`product-compose-smoke returned ${payload.status}`);
  }
  return payload;
}

async function createBackupSnapshot() {
  const result = await dockerCompose(["exec", "-T", "core-api", "yggdrasil-ops", "backup", "create"], { capture: true });
  process.stdout.write(result.stdout);
  const payload = JSON.parse(result.stdout);
  if (!payload.snapshotDir) {
    throw new Error("Backup did not return snapshotDir.");
  }
  return payload.snapshotDir;
}

async function main() {
  console.log("[release-smoke] docker compose config");
  await dockerCompose(["config"]);

  console.log("[release-smoke] product up");
  await dockerCompose(["up", "-d", "--build"]);

  console.log("[release-smoke] product smoke");
  await productSmoke();

  console.log("[release-smoke] backup before upgrade");
  const rollbackSnapshot = await createBackupSnapshot();

  console.log("[release-smoke] snapshot list");
  await dockerCompose(["run", "--rm", "--no-deps", "core-api", "yggdrasil-ops", "backup", "list"]);

  console.log("[release-smoke] upgrade");
  await run("node", ["scripts/product-compose.mjs", "upgrade"]);

  console.log("[release-smoke] smoke after upgrade");
  await productSmoke();

  console.log(`[release-smoke] rollback to ${rollbackSnapshot}`);
  await run("node", ["scripts/product-compose.mjs", "rollback", "--", "--snapshot", rollbackSnapshot]);

  console.log("[release-smoke] smoke after rollback");
  await productSmoke();
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
