#!/usr/bin/env python3
#
"""
Lê KMLs em data/distritos/, normaliza polígonos e grava em web/kml/.
Dependências: simplekml
"""
import warnings
from pathlib import Path
import xml.etree.ElementTree as ET
import simplekml

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
IN_DIR = DATA / "distritos"   # diretório de entrada solicitado
WEB = ROOT / "web"
OUT_DIR = WEB / "kml"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def slugify(value: str) -> str:
    import re
    v = value.strip()
    v = re.sub(r"\s+", "_", v)
    v = re.sub(r"[^a-zA-Z0-9_]+", "_", v)
    v = re.sub(r"_+", "_", v).strip("_")
    return v.lower() or "distrito"

def _parse_coordinates(coord_text: str):
    pts = []
    if not coord_text:
        return pts
    for token in coord_text.strip().replace("\n", " ").replace("\t", " ").split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0]); lat = float(parts[1])
                pts.append((lon, lat))
            except ValueError:
                continue
    return pts

def _findtext(element, path):
    el = element.find(path)
    return (el.text.strip() if el is not None and el.text else None)

def _collect_polygons_from_xml(root: ET.Element):
    ns_any = "{*}"
    polygons = []
    for poly in root.findall(f".//{ns_any}Polygon"):
        outer_coords_el = poly.find(f".//{ns_any}outerBoundaryIs/{ns_any}LinearRing/{ns_any}coordinates")
        if outer_coords_el is None or not (outer_coords_el.text or "").strip():
            outer_coords_el = poly.find(f".//{ns_any}LinearRing/{ns_any}coordinates")
        if outer_coords_el is None:
            continue
        outer = _parse_coordinates(outer_coords_el.text)
        inners = []
        for inner in poly.findall(f".//{ns_any}innerBoundaryIs/{ns_any}LinearRing/{ns_any}coordinates"):
            if inner.text and inner.text.strip():
                inners.append(_parse_coordinates(inner.text))
        if outer:
            polygons.append({"outer": outer, "inners": inners})
    return polygons

def _best_name_from_xml(root: ET.Element, fallback: str) -> str:
    ns_any = "{*}"
    nm = _findtext(root, f".//{ns_any}Placemark/{ns_any}name")
    if nm: return nm
    nm = _findtext(root, f".//{ns_any}Document/{ns_any}name")
    if nm: return nm
    return fallback

def normalize_kml_file(src_path: Path):
    try:
        tree = ET.parse(src_path)
        root = tree.getroot()
    except Exception as e:
        warnings.warn(f"Falha ao parsear {src_path}: {e}")
        return None

    polygons = _collect_polygons_from_xml(root)
    if not polygons:
        warnings.warn(f"Nenhum polígono em {src_path}; ignorando.")
        return None

    name = _best_name_from_xml(root, src_path.stem)
    slug = slugify(name)

    kdoc = simplekml.Kml()
    style = simplekml.Style()
    style.polystyle.color = simplekml.Color.changealphaint(120, simplekml.Color.red)
    style.polystyle.fill = 1
    style.polystyle.outline = 1

    def put_polygon(parent, outer, inners, nm):
        pg = parent.newpolygon(name=nm)
        pg.outerboundaryis = outer
        if inners: pg.innerboundaryis = inners
        pg.style = style

    if len(polygons) == 1:
        put_polygon(kdoc, polygons[0]["outer"], polygons[0]["inners"], name)
    else:
        mg = kdoc.newmultigeometry(name=name)
        for i, p in enumerate(polygons, start=1):
            put_polygon(mg, p["outer"], p["inners"], f"{name} #{i}")

    out_path = OUT_DIR / f"{slug}.kml"
    kdoc.save(str(out_path))
    return out_path

def main():
    if not IN_DIR.exists() or not IN_DIR.is_dir():
        raise SystemExit(f"Diretório de entrada não encontrado: {IN_DIR}")

    found = list(IN_DIR.glob("**/*.kml"))
    if not found:
        raise SystemExit(f"Nenhum KML encontrado em {IN_DIR}")

    ok = 0
    for p in found:
        out = normalize_kml_file(p)
        if out:
            ok += 1
            print(f"Gerado: {out.relative_to(ROOT)}")

    print(f"Concluído. {ok} arquivo(s) KML normalizado(s) gravado(s) em {OUT_DIR.relative_to(ROOT)}.")

if __name__ == "__main__":
    main()