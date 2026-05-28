from fastapi.responses import HTMLResponse


def render_playground() -> HTMLResponse:
    return HTMLResponse(
        r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OrionXCore Playground</title>
  <style>
    :root {
      --bg: #f2efe8;
      --panel: rgba(255, 252, 246, 0.9);
      --panel-strong: #fffaf2;
      --ink: #1f1d1a;
      --muted: #6b655c;
      --accent: #0b6e4f;
      --accent-2: #d17b0f;
      --line: rgba(31, 29, 26, 0.12);
      --shadow: 0 18px 50px rgba(43, 34, 21, 0.12);
      --radius: 20px;
      --mono: "SFMono-Regular", "JetBrains Mono", "Menlo", monospace;
      --sans: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, Georgia, serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: var(--sans);
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(11, 110, 79, 0.15), transparent 30%),
        radial-gradient(circle at bottom right, rgba(209, 123, 15, 0.18), transparent 28%),
        linear-gradient(160deg, #f8f2e6 0%, #efe9dd 45%, #ebe5d8 100%);
    }

    .shell {
      max-width: 1400px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }

    .hero {
      display: grid;
      gap: 12px;
      margin-bottom: 24px;
    }

    .eyebrow {
      color: var(--accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 12px;
      font-weight: 700;
    }

    h1 {
      margin: 0;
      font-size: clamp(32px, 5vw, 58px);
      line-height: 0.96;
      font-weight: 700;
    }

    .hero p {
      margin: 0;
      max-width: 860px;
      color: var(--muted);
      font-size: 18px;
      line-height: 1.5;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(320px, 1.1fr) minmax(320px, 0.9fr);
      gap: 18px;
    }

    .card {
      background: var(--panel);
      backdrop-filter: blur(14px);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .card-head {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      padding: 18px 20px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.55), rgba(255,255,255,0.2));
    }

    .card-head h2 {
      margin: 0;
      font-size: 18px;
    }

    .subtle {
      color: var(--muted);
      font-size: 13px;
    }

    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      padding: 18px 20px 8px;
    }

    .segmented {
      display: inline-flex;
      padding: 4px;
      border-radius: 999px;
      background: rgba(31, 29, 26, 0.06);
      gap: 4px;
    }

    .segmented button,
    .ghost,
    .primary {
      border: 0;
      cursor: pointer;
      transition: 160ms ease;
    }

    .segmented button {
      padding: 10px 14px;
      border-radius: 999px;
      background: transparent;
      color: var(--muted);
      font-family: inherit;
      font-size: 14px;
    }

    .segmented button.active {
      background: var(--panel-strong);
      color: var(--ink);
      box-shadow: 0 6px 18px rgba(31, 29, 26, 0.08);
    }

    .field {
      display: grid;
      gap: 8px;
      padding: 10px 20px 0;
    }

    label {
      font-size: 14px;
      color: var(--muted);
    }

    input, textarea {
      width: 100%;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
      color: var(--ink);
      padding: 14px 16px;
      font-size: 14px;
      font-family: var(--mono);
      outline: none;
    }

    textarea {
      min-height: 430px;
      resize: vertical;
      line-height: 1.5;
    }

    input:focus, textarea:focus {
      border-color: rgba(11, 110, 79, 0.55);
      box-shadow: 0 0 0 4px rgba(11, 110, 79, 0.12);
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 18px 20px 22px;
      align-items: center;
    }

    .primary {
      padding: 12px 18px;
      border-radius: 999px;
      background: var(--accent);
      color: #f7f5f0;
      font-weight: 700;
    }

    .primary:hover { transform: translateY(-1px); }

    .ghost {
      padding: 12px 18px;
      border-radius: 999px;
      background: rgba(31, 29, 26, 0.06);
      color: var(--ink);
    }

    .status {
      font-size: 13px;
      color: var(--muted);
    }

    pre {
      margin: 0;
      padding: 20px;
      min-height: 612px;
      overflow: auto;
      background: #171513;
      color: #f9f4ea;
      font-size: 13px;
      line-height: 1.55;
      font-family: var(--mono);
    }

    .hint-list {
      display: grid;
      gap: 8px;
      padding: 0 20px 20px;
      color: var(--muted);
      font-size: 13px;
    }

    .hint-list span {
      padding-left: 14px;
      position: relative;
    }

    .hint-list span::before {
      content: "";
      position: absolute;
      left: 0;
      top: 8px;
      width: 6px;
      height: 6px;
      border-radius: 999px;
      background: var(--accent-2);
    }

    @media (max-width: 980px) {
      .workspace {
        grid-template-columns: 1fr;
      }
      textarea {
        min-height: 320px;
      }
      pre {
        min-height: 380px;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">OrionXCore</div>
      <h1>API Playground</h1>
      <p>
        Test `agent/respond` and OpenAI-compatible `chat/completions` requests without leaving the browser.
        This page is tuned for debugging tools, database traces, and raw payloads.
      </p>
    </section>

    <section class="workspace">
      <article class="card">
        <div class="card-head">
          <div>
            <h2>Request Composer</h2>
            <div class="subtle">Edit endpoint, base URL, and JSON payload, then send the request directly.</div>
          </div>
        </div>

        <div class="controls">
          <div class="segmented" id="modeTabs">
            <button type="button" data-mode="agent" class="active">agent/respond</button>
            <button type="button" data-mode="chat">chat/completions</button>
          </div>
        </div>

        <div class="field">
          <label for="baseUrl">Base URL</label>
          <input id="baseUrl" value="http://127.0.0.1:8080" />
        </div>

        <div class="field">
          <label for="payload">JSON payload</label>
          <textarea id="payload"></textarea>
        </div>

        <div class="actions">
          <button type="button" class="primary" id="sendBtn">Send Request</button>
          <button type="button" class="ghost" id="resetBtn">Reset Payload</button>
          <span class="status" id="status">Ready.</span>
        </div>

        <div class="hint-list">
          <span>`agent/respond` is best for server-driven tool loops and event traces.</span>
          <span>`chat/completions` is best for OpenAI-compatible payload debugging.</span>
          <span>Responses are shown as raw JSON so you can inspect every field.</span>
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <div>
            <h2>Response Inspector</h2>
            <div class="subtle">HTTP result, errors, and structured payload output.</div>
          </div>
        </div>
        <pre id="responsePane">{
  "status": "waiting",
  "message": "Send a request to inspect the response here."
}</pre>
      </article>
    </section>
  </div>

  <script>
    const templates = {
      agent: {
        messages: [
          {
            role: "user",
            content: "Use the database_query tool with operation list_tables for database monitor, then summarize the result briefly."
          }
        ]
      },
      chat: {
        model: "deepseek-v4-flash",
        messages: [
          {
            role: "user",
            content: "List the tables in the monitor database."
          }
        ],
        tools: [
          {
            type: "function",
            function: {
              name: "database_query",
              description: "Run read-only queries and schema introspection against the configured ClickHouse connection.",
              parameters: {
                type: "object",
                properties: {
                  operation: {
                    type: "string",
                    enum: ["query", "list_tables", "describe_table", "text_to_sql"]
                  },
                  database: { type: "string" },
                  table: { type: "string" },
                  question: { type: "string" },
                  tables: { type: "array", items: { type: "string" } },
                  statement: { type: "string" },
                  limit: { type: "integer" }
                },
                additionalProperties: false
              }
            }
          }
        ],
        tool_choice: "auto"
      }
    };

    const endpointMap = {
      agent: "/v1/agent/respond",
      chat: "/v1/chat/completions"
    };

    const payloadInput = document.getElementById("payload");
    const responsePane = document.getElementById("responsePane");
    const statusLabel = document.getElementById("status");
    const baseUrlInput = document.getElementById("baseUrl");
    const sendBtn = document.getElementById("sendBtn");
    const resetBtn = document.getElementById("resetBtn");
    const modeTabs = document.getElementById("modeTabs");

    let currentMode = "agent";

    function setMode(mode) {
      currentMode = mode;
      for (const button of modeTabs.querySelectorAll("button")) {
        button.classList.toggle("active", button.dataset.mode === mode);
      }
      payloadInput.value = JSON.stringify(templates[mode], null, 2);
      statusLabel.textContent = `Ready for ${endpointMap[mode]}.`;
    }

    async function sendRequest() {
      statusLabel.textContent = "Sending request...";
      responsePane.textContent = "Waiting for response...";

      let parsed;
      try {
        parsed = JSON.parse(payloadInput.value);
      } catch (error) {
        statusLabel.textContent = "Payload is not valid JSON.";
        responsePane.textContent = String(error);
        return;
      }

      const url = baseUrlInput.value.replace(/\/$/, "") + endpointMap[currentMode];
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(parsed)
        });

        const text = await response.text();
        let body;
        try {
          body = JSON.parse(text);
        } catch {
          body = text;
        }

        responsePane.textContent = JSON.stringify(
          {
            status: response.status,
            ok: response.ok,
            url,
            body
          },
          null,
          2
        );
        statusLabel.textContent = response.ok
          ? `Completed with HTTP ${response.status}.`
          : `Request failed with HTTP ${response.status}.`;
      } catch (error) {
        responsePane.textContent = JSON.stringify(
          {
            status: "network_error",
            message: String(error)
          },
          null,
          2
        );
        statusLabel.textContent = "Network request failed.";
      }
    }

    modeTabs.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-mode]");
      if (!button) return;
      setMode(button.dataset.mode);
    });

    sendBtn.addEventListener("click", sendRequest);
    resetBtn.addEventListener("click", () => setMode(currentMode));

    setMode("agent");
  </script>
</body>
</html>"""
    )
