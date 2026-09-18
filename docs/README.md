# Test Config — Docs (Astro + Starlight)

Interactive documentation site for this repo. Fork-safe: no owner or repo name
is hardcoded — the GitHub Pages base path comes from the `ASTRO_BASE` env var
at build time.

## Commands

```bash
npm install
npm run dev     # local preview (served from /)
npm run build   # static output in dist/
npm run preview # preview the build
```

For a project site (`https://<owner>.github.io/<repo>/`), build with:

```bash
ASTRO_BASE=/<repo>/ npm run build
```

A typical workflow passes `ASTRO_BASE=/${{ github.event.repository.name }}/`
so forks work without editing the config. Optionally set `PAGES_URL`
(e.g. `https://<owner>.github.io`) if you need absolute sitemap/OG URLs.

## Regenerating data

`src/data/*.json` is generated from the bench files — re-run after changing anything
outside `docs/`:

```bash
python3 scripts/extract.py
```

## Deploying (maintainer)

No workflow is committed by design. Publish `dist/` to Pages with your own workflow;
make sure `public/.nojekyll` ships at the publish root.

- Latest Astro 7 + Starlight 0.x, Node ≥ 20 (see `package.json`).
