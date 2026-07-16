# Registry submissions — vehicle-safety-mcp

Where to list this server and what each destination needs. Do these **after** the
v0.2.0 tag/release exists on GitHub.

The single highest-leverage target is the **Official MCP Registry** — mcp.so, PulseMCP,
and others increasingly sync from it, so publishing there once seeds the rest.

---

## Prerequisites (one-time, before the Official Registry)

The Official Registry only lists servers that resolve to a real package or remote, and
it verifies you own both the GitHub namespace *and* the package. For this Python server:

- [ ] **Publish `vehicle-safety-mcp` to PyPI** at version `0.2.0` (so `uvx vehicle-safety-mcp`
      works and `server.json`'s `packages[0]` resolves).
      - `uv build` then `uv publish` (needs a PyPI account + API token).
      - PyPI project page will live at: https://pypi.org/project/vehicle-safety-mcp/
- [ ] **Add the ownership marker** so the registry can link the PyPI package to the
      `io.github.basit-khan-abdul/*` namespace. Include this exact line in the package's
      long description (the README shipped in the wheel), then re-publish:
      ```
      mcp-name: io.github.basit-khan-abdul/vehicle-safety-mcp
      ```
- [ ] Confirm `server.json` `version` and `packages[0].version` match the published
      PyPI version (currently both `0.2.0`).

> Not publishing to PyPI yet? Then the Official Registry step must wait, but mcp.so,
> Smithery, and PulseMCP can all list the server directly from the GitHub repo.

---

## 1. Official MCP Registry

- **Registry (live):** https://registry.modelcontextprotocol.io
- **Repo + publisher CLI:** https://github.com/modelcontextprotocol/registry
- **server.json reference:** https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/generic-server-json.md
- **Needs:** the `server.json` at repo root (already prepared), the PyPI package +
  ownership marker (see Prerequisites), and a GitHub login to authenticate the
  `io.github.basit-khan-abdul` namespace.
- **Steps:**
  - [ ] Get the CLI — download a `mcp-publisher` release binary, or from the registry
        repo: `make publisher` → `./bin/mcp-publisher`.
  - [ ] `mcp-publisher login github` (opens GitHub OAuth; must be the **basit-khan-abdul**
        account, which owns the namespace).
  - [ ] From the repo root: `mcp-publisher publish` (reads `./server.json`).
  - [ ] Verify: `curl "https://registry.modelcontextprotocol.io/v0/servers?search=vehicle-safety-mcp"`
- **Note:** `mcp-publisher init` can regenerate `server.json` and auto-fill
  `repository.id`; the hand-written file here is a ready template if you prefer to publish as-is.

## 2. mcp.so

- **Submit:** https://mcp.so/submit
- **Directory:** https://mcp.so
- **Needs:** the public GitHub repo URL, name, short description, category/tags.
  (mcp.so currently supports **public GitHub** MCP servers only.)
- **Steps:**
  - [ ] Sign in, click **Submit** (nav bar) or open a submission issue on their GitHub.
  - [ ] Paste `https://github.com/basit-khan-abdul/vehicle-safety-mcp`, fill name +
        description (reuse the README one-liner), pick a category.
  - [ ] Save — saving publishes the draft automatically.

## 3. Smithery

- **Add a server:** https://smithery.ai/new
- **Docs:** https://smithery.ai/docs
- **Needs:** connect the GitHub repo, plus a **`smithery.yaml`** in the repo root that
  declares how to start the server (a `stdio` start command for this local Python server).
- **Steps:**
  - [ ] Sign in to Smithery with the **basit-khan-abdul** GitHub account.
  - [ ] Add `smithery.yaml` to the repo (follow current docs for the stdio start-command
        shape), commit, and push.
  - [ ] Go to https://smithery.ai/new, select the `vehicle-safety-mcp` repo, and deploy/list it.
- **Note:** Smithery leans toward hosted (Docker) servers; a local stdio server is listed
  via its `smithery.yaml` start command — check the docs for the latest required fields
  before writing the YAML.

## 4. PulseMCP

- **Submit:** https://www.pulsemcp.com/submit
- **Directory:** https://www.pulsemcp.com/servers
- **Needs:** the public GitHub repo URL (PulseMCP scrapes metadata from the repo).
- **Steps:**
  - [ ] Open the submit form, paste `https://github.com/basit-khan-abdul/vehicle-safety-mcp`,
        add name/description if prompted.
  - [ ] Submit. PulseMCP also auto-indexes from the Official MCP Registry, so completing
        step 1 may list it here automatically over time.

---

## Quick reference

| Destination | Entry point | Package needed? | Key input |
|---|---|---|---|
| Official MCP Registry | https://registry.modelcontextprotocol.io | **Yes** (PyPI + marker) | `server.json` + GitHub OAuth |
| mcp.so | https://mcp.so/submit | No | GitHub repo URL |
| Smithery | https://smithery.ai/new | No (needs `smithery.yaml`) | GitHub repo + YAML |
| PulseMCP | https://www.pulsemcp.com/submit | No | GitHub repo URL |
