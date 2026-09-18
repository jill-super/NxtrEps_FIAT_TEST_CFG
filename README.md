# FIASA Test Configuration

Test bench configuration for the **FIASA electric power steering (EPS)** program (Fiat / Nexteer, P3271/P3272) —
a complete **Vector CANoe 8.5.98** setup to simulate the vehicle, stimulate the EPS ECU, run diagnostics,
measure/calibrate via XCP, and operate the bench from CANoe panels.

📖 **Interactive documentation:** built from [`docs/`](docs/) (Astro + Starlight) with
searchable signal / service / measurement explorers. Preview locally with `npm run dev`
in `docs/`, or publish `docs/dist/` to GitHub Pages with your own workflow (none is
committed by design — see [`docs/README.md`](docs/README.md)).
New here? Start with [`docs/src/content/docs/getting-started.mdx`](docs/src/content/docs/getting-started.mdx).

## Repository layout

| Directory | Contains | Docs source |
| --------- | -------- | ----------- |
| [`Canoe Config/`](Canoe%20Config/) | `Fiasa.cfg` hub config, 4 operator panels (`.xvp`), 2 VT System configs (`.vtcfg`), 2 test setups (`.tse`), `CANape.INI`, `Trace.blf` recording, logs | [`canoe-config`](docs/src/content/docs/canoe-config.mdx), [`panels`](docs/src/content/docs/panels.mdx), [`vt-system`](docs/src/content/docs/vt-system.mdx), [`test-execution`](docs/src/content/docs/test-execution.mdx), [`traces-logs`](docs/src/content/docs/traces-logs.mdx) |
| [`DBC/`](DBC/) | C-CAN database — **77 messages / 595 signals** across 9 ECUs — plus 4-message DSS bench DB and viewer layout | [`dbc`](docs/src/content/docs/dbc.mdx) |
| [`CDD/`](CDD/) | EPS diagnostics (**22 classes / 206 instances / 263 services**) + bench CDD (19 services) + CANdela migration log | [`cdd`](docs/src/content/docs/cdd.mdx) |
| [`A2L/`](A2L/) | RTE 4.00.00 ASAP2 description (**422 measurements**), CANape map INI, bus-load sysvar | [`a2l`](docs/src/content/docs/a2l.mdx) |
| [`Capl/`](Capl/) | 8 CAPL sources (ECU stubs, VT sim, XCP tests) + 6 compiled `.cbf` + test report (`pass`, 2016-03-21) + diagnostic trace | [`capl`](docs/src/content/docs/capl.mdx) |
| [`system_variables/`](system_variables/) | `sys.vsysvar` — 52 bench sysvars (message disables, NTC injection, Tx-rate probes); `SIGNALS.vsysvar` placeholder | [`system-variables`](docs/src/content/docs/system-variables.mdx) |
| [`docs/`](docs/) | Documentation site (Astro + Starlight, GitHub Pages ready, fork-safe) | [`file-formats`](docs/src/content/docs/file-formats.mdx), [`glossary`](docs/src/content/docs/glossary.mdx), [`repo-overview`](docs/src/content/docs/repo-overview.mdx) |

Every file format in the repo (`.dbc`, `.cdd`, `.a2l`, `.can`/`.CAN`, `.cbf`, `.cfg`,
`.vtcfg`, `.xvp`, `.tse`, `.vsysvar`, `.blf`, `.ini`, `.log`, `.txt`, `.xml`, `.html`,
`.dmp`) is explained in the [file-format guide](docs/src/content/docs/file-formats.mdx)
and explorable in its own docs page. Binary files (`.cbf`, `.blf`, `.dmp`) are documented
by purpose + how to open them; everything text-based is parsed and searchable.

## Quick start

1. Keep the top-level folder names as-is — `Fiasa.cfg` references siblings via relative paths (`..\DBC\…`, `..\CDD\…`, `..\Capl\…`, `..\system_variables\…`).
2. Open `Canoe Config/Fiasa.cfg` in **CANoe 8.5.98 SP4 (32-bit PRO)** with the VT System connected.
3. Start measurement, open `Canoe Config/Fiasa326.xvp`, attach XCP via `A2L/Rte_4.00.00.a2l`.

Full bring-up order, tool versions and re-run instructions:
[`getting-started`](docs/src/content/docs/getting-started.mdx).

## Docs development

```bash
cd docs
npm install
npm run dev      # preview
npm run build    # static site in docs/dist/
python3 scripts/extract.py  # regenerate src/data/*.json after bench changes
```

For a project Pages site build with `ASTRO_BASE=/<repo>/ npm run build`
so forks work without editing the config. No Pages workflow is committed —
add your own to publish `docs/dist/`.

## Contributing

Issues and pull requests are welcome. If you change bench files, please also re-run
`python3 scripts/extract.py` in `docs/` and rebuild the docs so the explorers stay in sync.
