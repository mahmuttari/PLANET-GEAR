# -*- coding: utf-8 -*-
"""
sta4fix komut satırı arayüzü.

Kullanım:
    python -m sta4fix cizim.dxf                      # cizim_fixed.dxf üretir
    python -m sta4fix cizim.dwg -o duzgun.dxf        # DWG ise önce DXF'e çevirir
    python -m sta4fix *.dxf --scale 0.8 --margin 2
    python -m sta4fix cizim.dxf --dry-run            # sadece rapor, dosya yazmaz

DWG desteği: sistemde ODA File Converter ("ODAFileConverter") veya LibreDWG
("dwg2dxf") kuruluysa .dwg dosyaları otomatik DXF'e çevrilir. Yoksa Sta4CAD
içinden DXF olarak dışa aktarın ya da ücretsiz ODA File Converter kurun.
Düzeltilen DXF, AutoCAD/BricsCAD ile açılıp DWG olarak kaydedilebilir.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import recover

from .fixer import fix_dxf


def dwg_to_dxf(dwg: Path) -> Path:
    """DWG dosyasını, bulunabilen bir çeviriciyle geçici bir DXF'e çevirir."""
    out_dir = Path(tempfile.mkdtemp(prefix="sta4fix_"))
    if shutil.which("dwg2dxf"):
        out = out_dir / (dwg.stem + ".dxf")
        subprocess.run(["dwg2dxf", "-o", str(out), str(dwg)], check=True)
        return out
    if shutil.which("ODAFileConverter"):
        subprocess.run(
            [
                "ODAFileConverter",
                str(dwg.parent), str(out_dir),
                "ACAD2018", "DXF", "0", "1", dwg.name,
            ],
            check=True,
        )
        return out_dir / (dwg.stem + ".dxf")
    sys.exit(
        "HATA: DWG çevirici bulunamadı (dwg2dxf veya ODAFileConverter).\n"
        "Çözüm: Sta4CAD'den DXF olarak dışa aktarın ya da ücretsiz "
        "ODA File Converter kurun: https://www.opendesign.com/guestfiles/oda_file_converter"
    )


def process(path: Path, args) -> None:
    src = path
    if path.suffix.lower() == ".dwg":
        print(f"[{path.name}] DWG algılandı, DXF'e çevriliyor...")
        src = dwg_to_dxf(path)

    # recover modu; dönüştürücülerin (LibreDWG/ODA) ürettiği kusurlu
    # DXF'leri de onararak okur — temiz dosyalar için de güvenlidir.
    try:
        doc, auditor = recover.readfile(src)
        if auditor.fixes:
            print(f"  ({len(auditor.fixes)} DXF kusuru otomatik onarıldı)")
    except ezdxf.DXFStructureError:
        sys.exit(f"HATA: {src} okunamadı — dosya DXF değil ya da ağır hasarlı.")
    report = fix_dxf(
        doc,
        margin=args.margin,
        scale=args.scale,
        max_shift_factor=args.max_shift,
        add_leader=not args.no_leader,
        layers=set(args.layers) if args.layers else None,
        dry_run=args.dry_run,
    )

    print(
        f"[{path.name}] {report.total_texts} yazı tarandı, "
        f"{report.overlapping} çakışma bulundu, {report.moved} yazı taşındı."
    )
    if report.unresolved:
        print(f"  Uyarı — yer bulunamayan {len(report.unresolved)} yazı:")
        for s in report.unresolved[:10]:
            print(f"    · {s}")

    if args.dry_run:
        return
    out = Path(args.output) if args.output else path.with_name(path.stem + "_fixed.dxf")
    doc.saveas(out)
    print(f"  → {out}")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="sta4fix",
        description="Sta4CAD DWG/DXF çıktılarında iç içe giren yazıları boş alana taşır.",
    )
    ap.add_argument("inputs", nargs="+", help="Girdi DXF/DWG dosyaları")
    ap.add_argument("-o", "--output", help="Çıktı dosyası (tek girdi için)")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="Yazı yüksekliği çarpanı, ör. 0.8 (varsayılan 1.0)")
    ap.add_argument("--margin", type=float, default=1.0,
                    help="Yazı çevresinde bırakılacak pay, çizim birimi (varsayılan 1.0)")
    ap.add_argument("--max-shift", type=float, default=12.0,
                    help="En büyük kaydırma = bu değer × yazı yüksekliği (varsayılan 12)")
    ap.add_argument("--layers", nargs="*",
                    help="Yalnızca bu katmanlardaki yazıları düzelt")
    ap.add_argument("--no-leader", action="store_true",
                    help="Taşınan yazılara kılavuz çizgisi ekleme")
    ap.add_argument("--dry-run", action="store_true",
                    help="Dosya yazmadan yalnızca çakışma raporu ver")
    args = ap.parse_args()

    if args.output and len(args.inputs) > 1:
        ap.error("-o tek girdi dosyasıyla kullanılır")

    for p in args.inputs:
        process(Path(p), args)


if __name__ == "__main__":
    main()
