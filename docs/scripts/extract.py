#!/usr/bin/env python3
"""Extract structured data from the repo root into docs JSON.

Run from docs/:  python3 scripts/extract.py
Reads repo root (..), writes src/data/*.json
"""
import os, re, json, xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # docs/scripts/extract.py -> repo root
OUT = Path(__file__).resolve().parents[1] / "src" / "data"
OUT.mkdir(parents=True, exist_ok=True)

def w(name, obj):
    p = OUT / name
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {p} ({p.stat().st_size} B)")

# ---------------------------------------------------------------- inventory
inventory = []
for dirpath, _, files in os.walk(REPO):
    if ".git" in dirpath or "/docs" in dirpath or dirpath.endswith("/docs"):
        continue
    # skip docs output itself
    if Path(dirpath).resolve().is_relative_to((REPO / "docs").resolve()):
        continue
    for f in files:
        p = Path(dirpath) / f
        rel = p.relative_to(REPO).as_posix()
        inventory.append({
            "path": rel,
            "dir": Path(rel).parent.as_posix(),
            "name": f,
            "ext": p.suffix.lower(),
            "size": p.stat().st_size,
        })
inventory.sort(key=lambda r: (r["dir"], r["name"]))
w("inventory.json", inventory)

EXT_DESC = {
    ".dbc": "CAN database — messages, signals, ECUs, value tables",
    ".cdd": "CANdela diagnostics description — ECU, sessions, services, DIDs/DTCs",
    ".a2l": "ASAP2 measurement & calibration description (XCP/CANape)",
    ".can": "CAPL source — simulation / test node",
    ".cbf": "Compiled CAPL branch file (binary, built from .can)",
    ".cfg": "CANoe configuration (v8.5.98) — buses, DBs, nodes, windows",
    ".vtcfg": "VT System configuration — modules, channels, stimulus values",
    ".xvp": "CANoe panel file — controls bound to signals / sysvars",
    ".tse": "CANoe test setup / test environment",
    ".vsysvar": "CANoe system variables definition (XML)",
    ".ini": "Tool INI — CANape / DBC-viewer settings",
    ".blf": "Vector Binary Logging Format — CAN trace recording",
    ".log": "Tool log (migration / fault history)",
    ".dmp": "CANape crash dump (binary, diagnostic only)",
    ".txt": "Plain-text log",
    ".html": "CAPL test execution report (rendered)",
    ".xml": "CAPL test execution report (machine readable)",
    ".md": "Markdown documentation (repo README)",
}
by_ext = {}
for r in inventory:
    by_ext.setdefault(r["ext"] or "(none)", []).append(r["path"])
w("extensions.json", {k: {"count": len(v), "files": v, "about": EXT_DESC.get(k, "")} for k, v in sorted(by_ext.items())})

# ---------------------------------------------------------------- DBC
def parse_dbc(path: Path):
    txt = path.read_text(encoding="utf-8", errors="ignore")
    bus = (re.search(r"^BU_:(.*)$", txt, flags=re.M).group(1).strip() if re.search(r"^BU_:", txt, flags=re.M) else "")
    nodes = bus.split() if bus else []
    bos = []
    # split BO blocks
    parts = re.split(r"(?=^BO_\s)", txt, flags=re.M)
    for b in parts:
        m = re.match(r"BO_\s+(\d+)\s+(\S+):\s*(\d+)\s+(\S+)", b)
        if not m: continue
        can_id, name, dlc, tx = m.groups()
        sigs = []
        for sm in re.finditer(r"^\s*SG_\s+(\S+)\s*:\s*(\d+)\|(\d+)@([01])([+-])\s*\(([^,]+),([^)]+)\)\s*\[([^|]+)\|([^\]]+)\]\s*\"([^\"]*)\"\s*(.*)$", b, flags=re.M):
            (sname, start, length, byteorder, sign, factor, offset, minimum, maximum, unit, receivers) = sm.groups()
            sigs.append({
                "name": sname, "start": int(start), "len": int(length),
                "byteOrder": "Motorola" if byteorder == "0" else "Intel",
                "signed": sign == "-",
                "factor": factor.strip(), "offset": offset.strip(),
                "min": minimum.strip(), "max": maximum.strip(),
                "unit": unit, "receivers": receivers.strip().split() if receivers.strip() else [],
            })
        # comments CM_ BO_
        cm = re.search(rf"^CM_\s+BO_\s+{can_id}\s+\"(.*?)\"\s*;", b, flags=re.M | re.S)
        bos.append({"id": int(can_id), "idHex": hex(int(can_id)), "name": name,
                    "dlc": int(dlc), "tx": tx, "signals": sigs,
                    "comment": (cm.group(1) if cm else "")})
    vals = re.findall(r"^VAL_\s+(\d+)\s+(\S+)\s+(.*?);", txt, flags=re.M)
    val_tables = re.findall(r"^VAL_TABLE_\s+(\S+)\s+(.*?);", txt, flags=re.M)
    # message comments global
    cm_sg = len(re.findall(r"^CM_\s+SG_", txt, flags=re.M))
    return {"file": path.name, "nodes": nodes, "messageCount": len(bos),
            "signalCount": sum(len(m["signals"]) for m in bos),
            "messages": sorted(bos, key=lambda m: m["id"]),
            "valueDescriptions": [{"id": int(a), "signal": b, "map": c.strip()[:400]} for a, b, c in vals],
            "valueTables": [{"name": a, "map": b.strip()[:400]} for a, b in val_tables],
            "commentedSignals": cm_sg}

for f in ["DSS.dbc", "P3271_C-CAN [07339]_6A_R1_CR1664.dbc"]:
    p = REPO / "DBC" / f
    if p.exists():
        key = "dbc_dss.json" if f.startswith("DSS") else "dbc_ccan.json"
        w(key, parse_dbc(p))

# ---------------------------------------------------------------- CAPL (.can text)
def parse_capl(path: Path):
    txt = path.read_text(encoding="utf-8", errors="ignore")
    lines = txt.splitlines()
    handlers = []
    for pat, kind in [(r"^\s*on\s+start\b", "on start"), (r"^\s*on\s+preStart\b", "on preStart"),
                      (r"^\s*on\s+stopMeasurement\b", "on stopMeasurement"),
                      (r"^\s*on\s+message\b", "on message"), (r"^\s*on\s+message\s+(\S+)", "on message"),
                      (r"^\s*on\s+sysvar\b", "on sysvar"), (r"^\s*on\s+timer\b", "on timer"),
                      (r"^\s*on\s+key\b", "on key"), (r"^\s*on\s+envVar\b", "on envVar"),
                      (r"^\s*testcase\s+(\S+)", "testcase"), (r"^\s*(?:dword|long|int|float|double|char|byte|word|void)\s+(\w+)\s*\(", "function")]:
        for i, ln in enumerate(lines, 1):
            m = re.match(pat, ln)
            if m:
                handlers.append({"kind": kind, "line": i, "code": ln.strip()[:160]})
                if len(handlers) > 400: break
    includes = re.findall(r"^\s*#include\s+[\"<]([^\">]+)[\">]", txt, flags=re.M)
    # variables block excerpt
    var_block = ""
    m = re.search(r"variables\s*\{(.*?)\n\}", txt, flags=re.S)
    if m: var_block = m.group(1)[:2000]
    return {"file": path.name, "size": path.stat().st_size, "lines": len(lines),
            "handlers": handlers[:200], "handlerCount": len(handlers),
            "includes": includes, "variablesExcerpt": var_block,
            "source": txt}

capl = []
capl_dir = REPO / "Capl"
for f in sorted(os.listdir(capl_dir)):
    p = capl_dir / f
    if f.lower().endswith((".can",)):
        try: capl.append(parse_capl(p))
        except Exception as e: capl.append({"file": f, "error": str(e)})
    elif f.lower().endswith(".cbf"):
        head = p.read_bytes()[:16]
        capl.append({"file": f, "size": p.stat().st_size, "binary": True,
                     "magic": head[:4].decode("ascii", errors="replace"),
                     "note": "Compiled CAPL (.cbf). Open the same-named .can source for logic; this binary is produced by the CANoe CAPL compiler.",
                     "source": None, "handlers": [], "handlerCount": 0, "lines": 0})
    elif f.lower().endswith((".html", ".xml", ".txt")):
        capl.append({"file": f, "size": p.stat().st_size, "lines": len(p.read_text(encoding='utf-8', errors='ignore').splitlines()),
                     "note": "Report/log — see Traces & logs page for detail.", "handlers": []})
w("capl.json", capl)

# -- Init VT7001 report xml detail
try:
    import xml.etree.ElementTree as ET
    rp = REPO / "Capl" / "Init VT7001_report.xml"
    if rp.exists():
        r = ET.parse(str(rp)).getroot()
        info = {"tag": r.tag, "attrib": dict(r.attrib)}
        tcs = []
        for tc in r.findall(".//testcase")[:50]:
            tcs.append({"attrib": dict(tc.attrib),
                        "title": (tc.findtext("title") or "")[:160],
                        "verdict": (tc.findtext("verdict") or (tc.find("verdict").attrib.get("result") if tc.find("verdict") is not None else ""))[:40]})
        seq = [{"tag": c.tag, "attrib": dict(list(c.attrib.items())[:8]),
                "text": ((c.text or "").strip()[:200])} for c in list(r)[:20]]
        setup = [{"name": (x.findtext("name") or ""), "desc": (x.findtext("description") or "")[:200]} for x in r.findall(".//xinfo")][:20]
        w("capl_report.json", {"file": "Init VT7001_report.xml", "root": info, "setup": setup, "testcases": tcs, "children": seq})
except Exception as e:
    w("capl_report.json", {"error": str(e)})

# ---------------------------------------------------------------- A2L
def parse_a2l(path: Path):
    txt = path.read_text(encoding="utf-8", errors="ignore")
    meas = []
    for m in re.finditer(r"/begin\s+MEASUREMENT\s+(\S+)\s+\"([^\"]*)\"\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+([^\s]+)\s+([^\s]+)", txt):
        name, desc, dtype, conv, res, acc, lo, hi = m.groups()
        # ECU_ADDRESS + following lines for context
        meas.append({"name": name, "desc": desc[:160], "datatype": dtype, "conversion": conv,
                     "resolution": res, "accuracy": acc, "lower": lo, "upper": hi})
    groups = re.findall(r"/begin\s+GROUP\s+(\S+)\s+\"([^\"]*)\"", txt)
    compu = re.findall(r"/begin\s+COMPU_METHOD\s+(\S+)\s+\"([^\"]*)\"\s+(\S+)\s+(\S+)\s+(\S+)", txt)
    layouts = re.findall(r"/begin\s+RECORD_LAYOUT\s+(\S+)", txt)
    proj = re.search(r"/begin\s+PROJECT\s+(\S+)\s+\"([^\"]*)\"", txt)
    mod = re.search(r"/begin\s+MODULE\s+(\S+)\s+\"([^\"]*)\"", txt)
    header = re.search(r"/begin\s+MOD_COMMON.*?BYTE_ORDER\s+(\S+)", txt, flags=re.S)
    return {"file": path.name, "size": path.stat().st_size,
            "project": (proj.group(1) if proj else ""), "module": (mod.group(1) if mod else ""),
            "byteOrder": (header.group(1) if header else ""),
            "measurementCount": len(meas), "measurements": meas,
            "groups": [{"name": a, "desc": b[:120]} for a, b in groups],
            "compuMethods": [{"name": a, "desc": b[:120], "type": c, "format": d, "unit": e} for a, b, c, d, e in compu],
            "recordLayouts": layouts}

a2l_p = REPO / "A2L" / "Rte_4.00.00.a2l"
if a2l_p.exists():
    w("a2l.json", parse_a2l(a2l_p))

# ---------------------------------------------------------------- CDD
def parse_cdd(path: Path):
    raw = path.read_text(encoding="utf-8", errors="ignore")
    txt = re.sub(r"<!DOCTYPE[^>]*>", "", raw)
    root = ET.fromstring(txt)
    ecudoc = root.find("ECUDOC")
    ecu_info = []
    for ecu in root.findall(".//ECU"):
        name = ""
        n = ecu.find("NAME")
        if n is not None:
            for t in n.findall("TUV"):
                if t.text and t.text.strip():
                    name = t.text.strip(); break
        ecu_info.append({"id": ecu.attrib.get("id"), "name": name})
    classes = []
    for dc in root.findall(".//DIAGCLASS"):
        nm = ""; q = ""
        n = dc.find("NAME")
        if n is not None:
            for t in n.findall("TUV"):
                if (t.text or "").strip(): nm = t.text.strip(); break
        qq = dc.find("QUAL")
        if qq is not None and qq.text: q = qq.text.strip()
        insts = []
        for di in dc.findall("./DIAGINST"):
            din = ""
            dn = di.find("NAME")
            if dn is not None:
                for t in dn.findall("TUV"):
                    if (t.text or "").strip(): din = t.text.strip(); break
            svcs = []
            for s in di.findall("./SERVICE"):
                sn = ""
                snn = s.find("NAME")
                if snn is not None:
                    for t in snn.findall("TUV"):
                        if (t.text or "").strip(): sn = t.text.strip(); break
                short = ""
                sh = s.find("SHORTCUTNAME")
                if sh is not None:
                    for t in sh.findall("TUV"):
                        if (t.text or "").strip(): short = t.text.strip(); break
                qual = s.findtext("QUAL") or ""
                svcs.append({"name": sn, "qual": (qual or "").strip()[:80], "shortcut": short[:120],
                             "func": s.attrib.get("func"), "phys": s.attrib.get("phys")})
            dq = di.find("QUAL")
            insts.append({"name": din, "qual": ((dq.text.strip() if dq is not None and dq.text else "")[:80]), "services": svcs})
        classes.append({"name": nm, "qual": q, "instances": insts})
    # counts
    total_inst = sum(len(c["instances"]) for c in classes)
    total_svc = sum(len(i["services"]) for c in classes for i in c["instances"])
    dataobjs = len(re.findall(r"<DATAOBJ\b", raw))
    return {"file": path.name, "size": path.stat().st_size,
            "dtd": root.attrib.get("dtdvers"),
            "manufacturer": ecudoc.attrib.get("manufacturer") if ecudoc is not None else "",
            "languages": ecudoc.attrib.get("languages") if ecudoc is not None else "",
            "ecus": ecu_info,
            "diagClasses": classes,
            "counts": {"diagClasses": len(classes), "diagInstances": total_inst,
                       "services": total_svc, "dataObjects": dataobjs,
                       "dtcs": raw.count("<DTC"), "envvars": raw.count("<ENVVAR")}}

for f, key in [("Fiasa_326_327_4.00.00.cdd", "cdd_fiasa.json"), ("DSS.cdd", "cdd_dss.json")]:
    p = REPO / "CDD" / f
    if p.exists():
        w(key, parse_cdd(p))

# migration log excerpt
ml = REPO / "CDD" / "Load_migration_7.5.2101_to_8.2.106_Fiasa_326_327_4.00.00.log"
if ml.exists():
    lines = ml.read_text(encoding="utf-8", errors="ignore").splitlines()
    w("cdd_migration.json", {"file": ml.name, "lines": len(lines), "excerpt": lines[:80]})

# ---------------------------------------------------------------- vsysvar
def parse_vsysvar(path: Path):
    try:
        r = ET.parse(str(path)).getroot()
    except Exception as e:
        return {"file": path.name, "error": str(e), "variables": []}
    out = []
    def walk(ns, prefix):
        name = ns.attrib.get("name", "")
        pre = f"{prefix}{name}::" if name else prefix
        for v in ns.findall("variable"):
            out.append({"namespace": pre.rstrip(":"), "name": v.attrib.get("name"),
                        "full": f"{pre}{v.attrib.get('name')}",
                        "type": v.attrib.get("type"), "unit": v.attrib.get("unit", ""),
                        "min": v.attrib.get("minValue", ""), "max": v.attrib.get("maxValue", ""),
                        "start": v.attrib.get("startValue", "")})
        for child in ns.findall("namespace"):
            walk(child, pre)
    for ns in r.findall("namespace"):
        walk(ns, "")
    return {"file": path.name, "size": path.stat().st_size, "variables": out}

sysvars = []
for f in ["sys.vsysvar", "SIGNALS.vsysvar", "bl.vsysvar"]:
    for base in [REPO / "system_variables" / f, REPO / "A2L" / f]:
        if base.exists():
            d = parse_vsysvar(base)
            d["location"] = base.relative_to(REPO).as_posix()
            sysvars.append(d)
w("sysvars.json", sysvars)

# ---------------------------------------------------------------- CANoe cfg references
def canoe_versions(txt: str):
    """Return (human, raw) CANoe version.

    Fiasa.cfg / *.tse carry two lines:
      ;CANoe Version |4|8|3|38693 Fiasa   <- pipe-encoded, not human readable
      Version: 8.5.98 Build 98            <- human readable, what docs should show
    """
    human = ""
    m = re.search(r"^Version:\s*(.+?)\s*$", txt, flags=re.M)
    if m:
        human = m.group(1).strip()
    raw = ""
    m2 = re.search(r"^;CANoe Version\s*(.+?)\s*$", txt, flags=re.M)
    if m2:
        raw = m2.group(1).strip()
    return human, raw


cfg = REPO / "Canoe Config" / "Fiasa.cfg"
if cfg.exists():
    txt = cfg.read_text(encoding="utf-8", errors="ignore")
    refs = re.findall(r"<VFileName V4 QL> 1 \"([^\"]+)\"", txt)
    # networks
    nets = re.findall(r"ILConfiguration::VNetwork 4 Begin_Of_Object\s*\n2\s*\n(\S+)", txt)
    dbs = re.findall(r"ILConfiguration::VDatabase 4 Begin_Of_Object\s*\n2\s*\n([^\n]+)", txt)
    # simulation nodes: .can / .cbf mentions
    nodes = sorted(set(re.findall(r"\.\.\\Capl\\([^\"]+\.(?:can|cbf))", txt, flags=re.I)))
    human_ver, raw_ver = canoe_versions(txt)
    w("canoe_cfg.json", {"file": "Fiasa.cfg", "size": cfg.stat().st_size,
                         "referencedFiles": refs[:60], "referencedCount": len(refs),
                         "networks": nets, "databases": [d.strip() for d in dbs],
                         "caplNodes": nodes,
                         "canoeVersion": human_ver, "canoeVersionRaw": raw_ver})

# ---------------------------------------------------------------- vtcfg
def parse_vtcfg(path: Path):
    r = ET.parse(str(path)).getroot()
    mods = []
    for m in r.findall(".//module"):
        chs = [{"name": c.attrib.get("name")} for c in m.findall(".//channel")]
        vals = len(m.findall(".//value"))
        mods.append({"productCode": m.attrib.get("productCode"), "interface": m.attrib.get("interface"),
                     "serial": m.attrib.get("serialNo"), "channels": chs, "channelCount": len(chs), "valueCount": vals})
    return {"file": path.name, "modules": mods,
            "channelCount": sum(m["channelCount"] for m in mods),
            "valueCount": sum(m["valueCount"] for m in mods)}

for f, key in [("Fiasa.vtcfg", "vt_fiasa.json"), ("Fiasa_VTsys.vtcfg", "vt_fiasa_vtsys.json")]:
    p = REPO / "Canoe Config" / f
    if p.exists():
        w(key, parse_vtcfg(p))

# ---------------------------------------------------------------- xvp panels
def parse_xvp(path: Path):
    txt = path.read_text(encoding="utf-8", errors="ignore")
    ctrls = re.findall(r"Panels\.(?:Design|Runtime)\.(\w+)", txt)
    from collections import Counter
    c = Counter(ctrls)
    syms = sorted(set(re.findall(r"SymbolConfiguration\">([^<]+)</Property>", txt)))
    # control names
    names = re.findall(r'<Property Name="Name">([^<]+)</Property>', txt)
    return {"file": path.name, "size": path.stat().st_size, "controlCount": len(re.findall(r"<Object Type", txt)),
            "controlTypes": [{"type": k, "count": v} for k, v in c.most_common()],
            "controlNames": names[:80], "symbols": syms[:120], "symbolCount": len(syms)}

panels = []
for f in sorted(os.listdir(REPO / "Canoe Config")):
    if f.lower().endswith(".xvp"):
        panels.append(parse_xvp(REPO / "Canoe Config" / f))
w("panels.json", panels)

# ---------------------------------------------------------------- TSE
def parse_tse(path: Path):
    txt = path.read_text(encoding="utf-8", errors="ignore")
    can = re.findall(r"\"([^\"]+\.can)\"", txt, flags=re.I)
    cbf = re.findall(r"\"([^\"]+\.cbf)\"", txt, flags=re.I)
    human_ver, raw_ver = canoe_versions(txt)
    return {"file": path.name, "size": path.stat().st_size,
            "canoeVersion": human_ver, "canoeVersionRaw": raw_ver,
            "caplSource": can, "caplBinary": cbf,
            "lines": txt.count("\n") + 1}
w("tse.json", [parse_tse(REPO / "Canoe Config" / f) for f in ["Test_FIASA.tse", "Test_FIASA_ver81.tse"] if (REPO / "Canoe Config" / f).exists()])

# ---------------------------------------------------------------- CANape INI (sections)
ini_p = REPO / "Canoe Config" / "CANape.INI"
if ini_p.exists():
    txt = ini_p.read_text(encoding="utf-8", errors="ignore")
    sections = re.findall(r"^\[(.+)\]$", txt, flags=re.M)
    keys = len(re.findall(r"^[A-Z0-9_]+\s*=", txt, flags=re.M))
    # keep curated important keys
    keep = {}
    for k in ["MDF_FORMAT", "MDF_TIME_FORMAT", "FILTER_FROM_FILE", "MIN_DISK_SPACE", "FREE_MEMORY_LIMIT"]:
        m = re.search(rf"^{k}=(.*)$", txt, flags=re.M)
        if m: keep[k] = m.group(1).strip()
    w("canape_ini.json", {"file": "CANape.INI", "size": ini_p.stat().st_size,
                          "sections": sections, "keyCount": keys, "highlights": keep})

# A2L helper INI
a2l_ini = REPO / "A2L" / "Rte_4.00.00.INI"
if a2l_ini.exists():
    w("a2l_ini.json", {"file": a2l_ini.name, "lines": a2l_ini.read_text(encoding="utf-8", errors="ignore").splitlines()})

# ---------------------------------------------------------------- logs / traces
logs = []
for rel in ["Canoe Config/DumpStartWrite.log", "Canoe Config/FaultHistory.log",
            "Canoe Config/traceLog.txt", "Capl/traceLog.txt",
            "Canoe Config/CANapeFault.dmp", "Canoe Config/Trace.blf"]:
    p = REPO / rel
    if not p.exists(): continue
    if p.suffix.lower() in (".log", ".txt"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        # splitlines() is the canonical line count (matches capl.json + tracelog_capl.json).
        # (count("\n")+1 over-counts by one when the file ends with a newline.)
        nlines = len(t.splitlines())
        logs.append({"file": rel, "size": p.stat().st_size, "lines": nlines,
                     "head": t.splitlines()[:40]})
    else:
        head = p.read_bytes()[:64]
        logs.append({"file": rel, "size": p.stat().st_size,
                     "magic": head[:4].decode("ascii", errors="replace"),
                     "hexHead": head.hex(" ")[:160],
                     "note": "Binary file — open in Vector CANoe/CANape; documented, not rendered inline."})
w("logs.json", logs)

# capl traceLog structured sample (diag lines)
tl = REPO / "Capl" / "traceLog.txt"
if tl.exists():
    lines = tl.read_text(encoding="utf-8", errors="ignore").splitlines()
    w("tracelog_capl.json", {"file": "Capl/traceLog.txt", "lines": len(lines), "all": lines})

print("done.")
