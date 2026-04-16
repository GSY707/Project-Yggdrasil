import { promises as fs } from "node:fs";
import path from "node:path";
import { parse as parseYaml } from "yaml";

type InstallSnapshot = {
  moduleId: string;
  desiredState: string;
  lifecycleState: string;
};

type ModuleCatalogSnapshot = {
  installs: InstallSnapshot[];
};

export type ModuleCard = {
  id: string;
  displayName: string;
  version: string;
  category: string;
  description: string;
  runtimeMode: string;
  desiredState: string;
  lifecycleState: string;
  hooks: string[];
  publishes: string[];
  subscribes: string[];
  permissions: string[];
};

export type SpecDocument = {
  title: string;
  category: string;
  path: string;
  status: string;
  version: string;
  updatedAt: string;
};

export type TodoSnapshot = {
  stubCount: number;
  temporaryCount: number;
  formalCount: number;
  phaseNotes: string[];
  priorities: string[];
};

export type ServiceCard = {
  title: string;
  endpoint: string;
  description: string;
  responsibility: string;
};

export type DashboardData = {
  generatedAt: string;
  modules: ModuleCard[];
  specs: SpecDocument[];
  todo: TodoSnapshot;
  services: ServiceCard[];
};

const WORKSPACE_ROOT = path.resolve(process.cwd(), "../..");
const DOC_TITLE_PATTERN = /^#\s+(.+)$/m;
const DOC_STATUS_PATTERN = /^- (?:文档状态|状态)：(.+)$/m;
const DOC_VERSION_PATTERN = /^- 版本：(.+)$/m;
const DOC_UPDATED_PATTERN = /^- (?:日期|更新时间)：(.+)$/m;

async function readJsonIfExists<T>(filePath: string): Promise<T | null> {
  try {
    const content = await fs.readFile(filePath, "utf8");
    return JSON.parse(content) as T;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return null;
    }
    throw error;
  }
}

async function walkMarkdownFiles(directoryPath: string): Promise<string[]> {
  const entries = await fs.readdir(directoryPath, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map(async (entry) => {
      const entryPath = path.join(directoryPath, entry.name);
      if (entry.isDirectory()) {
        return walkMarkdownFiles(entryPath);
      }
      if (entry.isFile() && entry.name.endsWith(".md")) {
        return [entryPath];
      }
      return [];
    }),
  );
  return nested.flat();
}

function toWorkspacePath(filePath: string): string {
  return path.relative(WORKSPACE_ROOT, filePath).split(path.sep).join("/");
}

function inferDocumentCategory(workspacePath: string): string {
  if (workspacePath.startsWith("docs/specs/")) {
    return "Data Spec";
  }
  if (workspacePath.startsWith("docs/protocols/")) {
    return "Protocol";
  }
  if (workspacePath.startsWith("docs/adr/")) {
    return "ADR";
  }
  return "Product";
}

async function loadSpecDocuments(): Promise<SpecDocument[]> {
  const docsRoot = path.join(WORKSPACE_ROOT, "docs");
  const files = await walkMarkdownFiles(docsRoot);
  const documents = await Promise.all(
    files.map(async (filePath) => {
      const content = await fs.readFile(filePath, "utf8");
      const workspacePath = toWorkspacePath(filePath);
      return {
        title: content.match(DOC_TITLE_PATTERN)?.[1]?.trim() ?? path.basename(filePath, ".md"),
        category: inferDocumentCategory(workspacePath),
        path: workspacePath,
        status: content.match(DOC_STATUS_PATTERN)?.[1]?.trim() ?? "Unspecified",
        version: content.match(DOC_VERSION_PATTERN)?.[1]?.trim() ?? "-",
        updatedAt: content.match(DOC_UPDATED_PATTERN)?.[1]?.trim() ?? "-",
      } satisfies SpecDocument;
    }),
  );

  return documents.sort((left, right) => left.path.localeCompare(right.path, "zh-CN"));
}

async function loadModules(): Promise<ModuleCard[]> {
  const modulesRoot = path.join(WORKSPACE_ROOT, "modules");
  const moduleEntries = await fs.readdir(modulesRoot, { withFileTypes: true });
  const snapshot = await readJsonIfExists<ModuleCatalogSnapshot>(
    path.join(WORKSPACE_ROOT, ".yggdrasil", "state", "module-catalog-snapshot.json"),
  );
  const installByModuleId = new Map(
    (snapshot?.installs ?? []).map((install) => [install.moduleId, install]),
  );

  const manifests = await Promise.all(
    moduleEntries
      .filter((entry) => entry.isDirectory())
      .map(async (entry) => {
        const manifestPath = path.join(modulesRoot, entry.name, "yggdrasil.module.yaml");
        const content = await fs.readFile(manifestPath, "utf8");
        const manifest = parseYaml(content) as {
          metadata?: Record<string, unknown>;
          spec?: {
            runtime?: Record<string, unknown>;
            capabilities?: Record<string, unknown>;
            permissions?: Record<string, unknown>;
          };
        };
        const metadata = manifest.metadata ?? {};
        const spec = manifest.spec ?? {};
        const capabilities = spec.capabilities ?? {};
        const permissions = spec.permissions ?? {};
        const install = installByModuleId.get(String(metadata.id ?? entry.name));
        return {
          id: String(metadata.id ?? entry.name),
          displayName: String(metadata.displayName ?? entry.name),
          version: String(metadata.version ?? "0.0.0"),
          category: String(metadata.category ?? "module"),
          description: String(metadata.description ?? "No description."),
          runtimeMode: String(spec.runtime?.mode ?? "in-process"),
          desiredState: install?.desiredState ?? "enabled",
          lifecycleState: install?.lifecycleState ?? "active",
          hooks: Array.isArray(capabilities.hooks) ? capabilities.hooks.map(String) : [],
          publishes: Array.isArray(capabilities.publishes) ? capabilities.publishes.map(String) : [],
          subscribes: Array.isArray(capabilities.subscribes) ? capabilities.subscribes.map(String) : [],
          permissions: Array.isArray(permissions.requested) ? permissions.requested.map(String) : [],
        } satisfies ModuleCard;
      }),
  );

  return manifests.sort((left, right) => left.id.localeCompare(right.id, "zh-CN"));
}

async function loadTodoSnapshot(): Promise<TodoSnapshot> {
  const todoPath = path.join(WORKSPACE_ROOT, "todo.md");
  const content = await fs.readFile(todoPath, "utf8");
  const phaseSection = content.match(/## 当前阶段([\s\S]*?)(?:\n## |$)/)?.[1] ?? "";
  const prioritiesSection = content.match(/## 当前最该做的 10 件事([\s\S]*?)(?:\n## |$)/)?.[1] ?? "";
  return {
    stubCount: Number(content.match(/占位代码：\s*(\d+)/)?.[1] ?? 0),
    temporaryCount: Number(content.match(/临时代码：\s*(\d+)/)?.[1] ?? 0),
    formalCount: Number(content.match(/正式工程代码：\s*(\d+)/)?.[1] ?? 0),
    phaseNotes: Array.from(phaseSection.matchAll(/^-\s+(.+)$/gm), (match) => match[1].trim()),
    priorities: Array.from(prioritiesSection.matchAll(/^\d+\.\s+(.+)$/gm), (match) => match[1].trim()),
  };
}

function buildServices(): ServiceCard[] {
  return [
    {
      title: "Core API",
      endpoint: "/health  /modules  /specs",
      description: "Expose the formal module catalog and document catalog to operators and the web console.",
      responsibility: "Domain API and integration surface.",
    },
    {
      title: "Agent Runtime",
      endpoint: "/runtime/root-mount/{taskId}  /runtime/pause/{taskId}",
      description: "Preview startup root mounts and pause snapshots using formal runtime objects.",
      responsibility: "Task bootstrapping and safe-stop orchestration.",
    },
    {
      title: "Module Host",
      endpoint: "/health  /modules  /modules/discovered",
      description: "Compute and persist the module catalog snapshot from manifests and local profile state.",
      responsibility: "Module registry and health surface.",
    },
    {
      title: "Worker",
      endpoint: "yggdrasil-worker --json",
      description: "Assemble the worker activity registry from core activities and enabled module contributions.",
      responsibility: "Async activity registry and operator inspection.",
    },
  ];
}

export async function getWorkspaceDashboard(): Promise<DashboardData> {
  const [modules, specs, todo] = await Promise.all([loadModules(), loadSpecDocuments(), loadTodoSnapshot()]);
  return {
    generatedAt: new Date().toISOString(),
    modules,
    specs,
    todo,
    services: buildServices(),
  };
}