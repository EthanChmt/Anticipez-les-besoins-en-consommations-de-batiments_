# fichier: zip_latlon_html.py
import argparse
import io
import os
import re
import tempfile
import webbrowser

import pandas as pd
import folium
from folium.plugins import MarkerCluster


def _clean_zip(z):
    if pd.isna(z):
        return None
    m = re.search(r"\d+", str(z))
    if not m:
        return None
    return m.group(0).zfill(5)


def _autodetect_sep(path):
    for sep in (",", ";", "\t", "|"):
        try:
            df = pd.read_csv(path, sep=sep, nrows=100)
            if {"Latitude", "Longitude", "ZipCode"}.issubset(df.columns):
                return sep
        except Exception:
            continue
    raise ValueError("Séparateur non détecté, indique --sep")


def build_map(df: pd.DataFrame, sample: int | None = None) -> folium.Map:
    req = {"Latitude", "Longitude", "ZipCode"}
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes: {sorted(missing)}")

    data = df[["Latitude", "Longitude", "ZipCode"]].copy()
    data = data[pd.notna(data["Latitude"]) & pd.notna(data["Longitude"])]

    if sample is not None and len(data) > sample:
        data = data.sample(sample, random_state=42)

    data["ZipClean"] = data["ZipCode"].map(_clean_zip)
    data["is_missing"] = data["ZipClean"].isna()

    # centre et zoom
    lat0 = data["Latitude"].astype(float).mean()
    lon0 = data["Longitude"].astype(float).mean()
    m = folium.Map(location=[lat0, lon0], zoom_start=11, control_scale=True)

    # deux calques sélectionnables
    fg_present = folium.FeatureGroup(name="ZipCode présent", show=True)
    fg_missing = folium.FeatureGroup(name="ZipCode manquant", show=True)

    cluster_present = MarkerCluster(name="Présent").add_to(fg_present)
    cluster_missing = MarkerCluster(name="Manquant").add_to(fg_missing)

    bounds = []

    for idx, row in data.iterrows():
        lat = float(row["Latitude"])
        lon = float(row["Longitude"])
        zc = row["ZipClean"]
        miss = pd.isna(zc)

        popup_html = io.StringIO()
        popup_html.write("<b>Index</b> {}<br>".format(idx))
        popup_html.write("<b>Latitude</b> {:.6f}<br>".format(lat))
        popup_html.write("<b>Longitude</b> {:.6f}<br>".format(lon))
        popup_html.write("<b>ZipCode</b> {}<br>".format("(manquant)" if miss else zc))

        marker = folium.CircleMarker(
            location=(lat, lon),
            radius=6 if miss else 5,
            color="#d00" if miss else "#2a5bd7",
            fill=True,
            fill_color="#d00" if miss else "#2a5bd7",
            fill_opacity=0.9 if miss else 0.7,
            weight=1,
            tooltip=f"{'Manquant' if miss else 'Zip'} • {zc if zc else ''}",
            popup=folium.Popup(popup_html.getvalue(), max_width=280),
        )

        if miss:
            marker.add_to(cluster_missing)
        else:
            marker.add_to(cluster_present)

        bounds.append((lat, lon))

    fg_present.add_to(m)
    fg_missing.add_to(m)
    folium.LayerControl(position="topleft").add_to(m)

    # ajuste les bornes si possible
    if bounds:
        m.fit_bounds(bounds, padding=(20, 20))

    return m


def main():
    ap = argparse.ArgumentParser(
        description="Ouvre une carte HTML temporaire avec Latitude Longitude et ZipCode"
    )
    ap.add_argument(
        "--csv",
        default="2016_Building_Energy_Benchmarking.csv",
        help="Chemin du CSV, par défaut 2016_Building_Energy_Benchmarking.csv"
    )
    ap.add_argument(
        "--sep",
        default=None,
        help="Séparateur du CSV, auto si non précisé"
    )
    ap.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Nombre maximum de points à tracer, utile si le fichier est très gros"
    )
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        raise FileNotFoundError(f"Fichier introuvable: {args.csv}")

    sep = args.sep or _autodetect_sep(args.csv)
    df = pd.read_csv(args.csv, sep=sep)

    amap = build_map(df, sample=args.sample)

    # fichier HTML temporaire puis ouverture automatique
    with tempfile.NamedTemporaryFile(prefix="zip_map_", suffix=".html", delete=False) as tmp:
        temp_path = tmp.name
    amap.save(temp_path)
    print(f"Carte ouverte dans le navigateur, fichier temporaire: {temp_path}")
    webbrowser.open("file://" + temp_path)


if __name__ == "__main__":
    main()
