import { NextRequest, NextResponse } from "next/server";

const CORE_API_BASE_URL = process.env.YGGDRASIL_CORE_API_BASE_URL ?? "http://127.0.0.1:8000";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

async function forwardRequest(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const baseUrl = new URL(CORE_API_BASE_URL);
  const pathname = path.join("/");
  const targetUrl = new URL(`${baseUrl.pathname.replace(/\/$/, "")}/${pathname}`, baseUrl);
  targetUrl.search = request.nextUrl.search;

  try {
    const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.text();
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: {
        "content-type": request.headers.get("content-type") ?? "application/json",
      },
      body,
      cache: "no-store",
    });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json; charset=utf-8",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: `Unable to reach core API at ${targetUrl.toString()}.`,
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 502 },
    );
  }
}

export async function GET(request: NextRequest, context: RouteContext) {
  return forwardRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return forwardRequest(request, context);
}