#!/usr/bin/env python3
"""
PLANET-GEAR — Tek kademeli planet dişli kutusu hesap aracı (QDD aktüatör için)
=============================================================================

Bu betik bir QDD (Quasi-Direct Drive) aktüatörün planet redüktörünü
parametrik olarak boyutlandırır ve üretilebilirlik için gerekli tüm
kinematik koşulları doğrular:

  - Çevrim oranı (güneş giriş, taşıyıcı çıkış, halka sabit)
  - Diş sayısı uyumu (Zring = Zsun + 2*Zplanet)
  - Montaj koşulu (assembly condition):  (Zsun + Zring) / p tam sayı olmalı
  - Komşuluk koşulu (neighbor / tip clearance): planetler çarpışmamalı
  - Geometri: bölüm daireleri, eksenler arası mesafe, dış çap
  - Tork ve devir dönüşümü (motor <-> çıkış)

Kullanım:
    python3 planetary_gear_calc.py
    python3 planetary_gear_calc.py --zsun 14 --zplanet 28 --planets 3 --module 1.0
"""

from __future__ import annotations
import argparse
import math
from dataclasses import dataclass


@dataclass
class PlanetaryDesign:
    z_sun: int          # güneş dişli diş sayısı
    z_planet: int       # planet dişli diş sayısı
    n_planets: int      # planet sayısı
    module: float       # modül [mm]
    pressure_angle: float = 20.0  # basınç açısı [derece]
    addendum_factor: float = 1.0  # ha* (standart = 1.0)

    @property
    def z_ring(self) -> int:
        # İç (halka) dişlinin diş sayısı
        return self.z_sun + 2 * self.z_planet

    @property
    def ratio(self) -> float:
        # Halka sabit, güneş giriş, taşıyıcı çıkış: i = 1 + Zring/Zsun
        return 1.0 + self.z_ring / self.z_sun

    # ---- Geometri ----
    @property
    def d_sun(self) -> float:
        return self.module * self.z_sun

    @property
    def d_planet(self) -> float:
        return self.module * self.z_planet

    @property
    def d_ring(self) -> float:
        return self.module * self.z_ring

    @property
    def center_distance(self) -> float:
        # Güneş–planet eksenleri arası mesafe
        return self.module * (self.z_sun + self.z_planet) / 2.0

    # ---- Doğrulama koşulları ----
    def check_tooth_count(self) -> tuple[bool, str]:
        ok = self.z_ring == self.z_sun + 2 * self.z_planet
        return ok, f"Zring = Zsun + 2*Zplanet => {self.z_ring} == {self.z_sun + 2*self.z_planet}"

    def check_assembly(self) -> tuple[bool, str]:
        # Eşit aralıklı planetlerin monte edilebilmesi için
        total = self.z_sun + self.z_ring
        ok = total % self.n_planets == 0
        return ok, f"(Zsun + Zring)/p = ({self.z_sun}+{self.z_ring})/{self.n_planets} = {total/self.n_planets:.3f}"

    def check_neighbor(self) -> tuple[bool, str]:
        # Komşu planetlerin uç dairelerinin çarpışmaması koşulu
        # (Zsun + Zplanet) * sin(pi/p) > Zplanet + 2*ha*
        lhs = (self.z_sun + self.z_planet) * math.sin(math.pi / self.n_planets)
        rhs = self.z_planet + 2 * self.addendum_factor
        ok = lhs > rhs
        return ok, f"(Zs+Zp)*sin(pi/p) = {lhs:.2f}  >  Zp+2 = {rhs:.2f}"

    def check_coaxial(self) -> tuple[bool, str]:
        # Güneş ve halkanın eş eksenli olması için modüller eşit olmalı
        # (tek modül kullandığımız için her zaman sağlanır — bilgi amaçlı)
        ok = True
        return ok, "Güneş/planet/halka aynı modül -> eş eksenlilik sağlanır"

    def all_checks(self) -> list[tuple[str, bool, str]]:
        return [
            ("Diş sayısı uyumu", *self.check_tooth_count()),
            ("Montaj koşulu", *self.check_assembly()),
            ("Komşuluk koşulu", *self.check_neighbor()),
            ("Eş eksenlilik", *self.check_coaxial()),
        ]


def torque_speed(design: PlanetaryDesign,
                 motor_torque_cont: float,
                 motor_torque_peak: float,
                 motor_speed_rpm: float,
                 efficiency: float = 0.90) -> dict:
    i = design.ratio
    return {
        "out_torque_cont": motor_torque_cont * i * efficiency,
        "out_torque_peak": motor_torque_peak * i * efficiency,
        "out_speed_rpm": motor_speed_rpm / i,
        "out_speed_rad_s": motor_speed_rpm / i * 2 * math.pi / 60.0,
    }


def print_report(design: PlanetaryDesign,
                 motor_torque_cont: float,
                 motor_torque_peak: float,
                 motor_speed_rpm: float,
                 efficiency: float) -> bool:
    line = "=" * 64
    print(line)
    print(" PLANET-GEAR — QDD Aktüatör Redüktör Raporu")
    print(line)
    print(f" Modül (m)              : {design.module:.2f} mm")
    print(f" Basınç açısı           : {design.pressure_angle:.0f} derece")
    print(f" Güneş diş sayısı  (Zs) : {design.z_sun}")
    print(f" Planet diş sayısı (Zp) : {design.z_planet}")
    print(f" Halka diş sayısı  (Zr) : {design.z_ring}")
    print(f" Planet sayısı     (p)  : {design.n_planets}")
    print(line)
    print(" KİNEMATİK")
    print(f"   Çevrim oranı i       : {design.ratio:.3f} : 1")
    print(line)
    print(" GEOMETRİ (bölüm daireleri)")
    print(f"   Güneş çapı           : {design.d_sun:.2f} mm")
    print(f"   Planet çapı          : {design.d_planet:.2f} mm")
    print(f"   Halka çapı (iç)      : {design.d_ring:.2f} mm")
    print(f"   Eksenler arası (a)   : {design.center_distance:.2f} mm")
    print(line)
    print(" DOĞRULAMA KOŞULLARI")
    all_ok = True
    for name, ok, detail in design.all_checks():
        flag = "GECTI" if ok else "KALDI"
        all_ok = all_ok and ok
        print(f"   [{flag}] {name:<18}: {detail}")
    print(line)
    ts = torque_speed(design, motor_torque_cont, motor_torque_peak,
                      motor_speed_rpm, efficiency)
    print(f" TORK / DEVİR (verim = %{efficiency*100:.0f})")
    print(f"   Motor sürekli tork   : {motor_torque_cont:.2f} Nm")
    print(f"   Motor tepe tork      : {motor_torque_peak:.2f} Nm")
    print(f"   Motor devri          : {motor_speed_rpm:.0f} rpm")
    print(f"   --> Çıkış sürekli    : {ts['out_torque_cont']:.2f} Nm")
    print(f"   --> Çıkış tepe       : {ts['out_torque_peak']:.2f} Nm")
    print(f"   --> Çıkış devri      : {ts['out_speed_rpm']:.0f} rpm "
          f"({ts['out_speed_rad_s']:.1f} rad/s)")
    print(line)
    print(f" SONUÇ: {'TÜM KOŞULLAR SAĞLANDI ✓' if all_ok else 'BAZI KOŞULLAR SAĞLANMADI ✗'}")
    print(line)
    return all_ok


def main():
    p = argparse.ArgumentParser(description="QDD planet redüktör hesap aracı")
    p.add_argument("--zsun", type=int, default=14)
    p.add_argument("--zplanet", type=int, default=28)
    p.add_argument("--planets", type=int, default=3)
    p.add_argument("--module", type=float, default=1.0)
    p.add_argument("--pressure-angle", type=float, default=20.0)
    p.add_argument("--motor-cont", type=float, default=3.0, help="Motor sürekli torku [Nm]")
    p.add_argument("--motor-peak", type=float, default=6.5, help="Motor tepe torku [Nm]")
    p.add_argument("--motor-rpm", type=float, default=2400.0, help="Motor devri [rpm]")
    p.add_argument("--efficiency", type=float, default=0.90)
    args = p.parse_args()

    design = PlanetaryDesign(
        z_sun=args.zsun,
        z_planet=args.zplanet,
        n_planets=args.planets,
        module=args.module,
        pressure_angle=args.pressure_angle,
    )
    ok = print_report(design, args.motor_cont, args.motor_peak,
                      args.motor_rpm, args.efficiency)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
