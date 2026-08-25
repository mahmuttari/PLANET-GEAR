#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QDD (Quasi-Direct Drive) Aktüatör Boyutlandırma ve Doğrulama Hesapları
======================================================================
Tek kademeli planet redüktörlü, dış rotorlu BLDC motorlu QDD aktüatör.
Tüm birimler SI (m, N, W, kg), açılar derece olarak girilir.

Çalıştır:  python3 calc/qdd_hesap.py
Script; dişli geometrisini, montaj koşullarını, kavrama oranını,
Lewis eğilme gerilmesini, motor/termal büyüklükleri ve yansıyan
ataleti hesaplar; tasarım kurallarını assert ile doğrular.
"""

import math

# ----------------------------------------------------------------------
# 1) HEDEF SPESİFİKASYONLAR (bacaklı robot eklemi, Mini-Cheetah sınıfı)
# ----------------------------------------------------------------------
T_PEAK_OUT   = 24.0      # N·m  — tepe çıkış torku
T_CONT_OUT   = 8.0       # N·m  — sürekli çıkış torku
W_MAX_OUT    = 40.0      # rad/s — tepe çıkış hızı (~382 rpm)
V_BUS        = 48.0      # V    — bara gerilimi
MASS_TARGET  = 0.550     # kg   — kütle hedefi

# ----------------------------------------------------------------------
# 2) MOTOR (dış rotorlu BLDC, 8108/8112 sınıfı, 36N42P)
# ----------------------------------------------------------------------
KV           = 100.0     # rpm/V
R_PH         = 0.055     # ohm  — faz direnci (hat-nötr)
J_ROTOR      = 1.2e-4    # kg·m² — rotor ataleti
I_PEAK       = 45.0      # A    — tepe q-ekseni akımı (sürücü limiti)
R_TH         = 1.9       # K/W  — stator→ortam ısıl direnç (gövdeye montajlı)
DT_MAX       = 80.0      # K    — izinli sargı sıcaklık artışı

KT = 60.0 / (2.0 * math.pi * KV)          # N·m/A  (Kt = 60/(2π·Kv))

# ----------------------------------------------------------------------
# 3) PLANET DİŞLİ (tek kademe, 3 planet)
# ----------------------------------------------------------------------
Z_SUN, Z_PLANET, Z_RING = 18, 36, 90
N_PLANET     = 3
MODULE       = 0.8e-3    # m — modül
ALPHA        = 20.0      # derece — kavrama açısı
FACE_W       = 8.0e-3    # m — diş genişliği
ETA_GEAR     = 0.97      # tek kademe planet verimi
K_SHARE      = 1.25      # planetler arası yük paylaşım dengesizliği
Y_LEWIS_SUN  = 0.309     # Lewis form faktörü (z=18, 20° tam derinlik)
SIGMA_ALLOW  = 380e6     # Pa — sertleştirilmiş çelik izinli eğilme gerilmesi

RATIO = 1.0 + Z_RING / Z_SUN              # sabit halka, güneş giriş → taşıyıcı çıkış


def main():
    # ---- dişli geometrisi ----
    d_sun    = MODULE * Z_SUN
    d_planet = MODULE * Z_PLANET
    d_ring   = MODULE * Z_RING
    a_carrier = 0.5 * MODULE * (Z_SUN + Z_PLANET)   # taşıyıcı yörünge yarıçapı

    # Diş uyum ve montaj koşulları
    assert Z_SUN + 2 * Z_PLANET == Z_RING, "Eş çalışma koşulu: zs + 2zp = zr"
    assert (Z_SUN + Z_RING) % N_PLANET == 0, "Montaj koşulu: (zs+zr)/N tam sayı"

    # Komşu planet çarpışma kontrolü (uç dairesi çapı < planet merkez aralığı)
    d_tip_planet = d_planet + 2.0 * MODULE
    planet_pitch = 2.0 * a_carrier * math.sin(math.pi / N_PLANET)
    assert d_tip_planet < planet_pitch, "Komşu planetler çarpışıyor!"

    # Kavrama oranı (güneş-planet dış kavraması)
    alpha = math.radians(ALPHA)
    def base_r(d): return 0.5 * d * math.cos(alpha)
    def tip_r(d):  return 0.5 * d + MODULE
    la = (math.sqrt(tip_r(d_sun)**2    - base_r(d_sun)**2)
        + math.sqrt(tip_r(d_planet)**2 - base_r(d_planet)**2)
        - (0.5 * d_sun + 0.5 * d_planet) * math.sin(alpha))
    contact_ratio = la / (math.pi * MODULE * math.cos(alpha))
    assert contact_ratio > 1.2, "Kavrama oranı yetersiz"

    # ---- tork zinciri ----
    t_sun_peak = T_PEAK_OUT / (RATIO * ETA_GEAR)      # motora düşen tepe tork
    i_peak_req = t_sun_peak / KT                      # gereken tepe akım
    assert i_peak_req <= I_PEAK, "Sürücü akım limiti aşılıyor"

    # Diş kuvveti ve Lewis eğilme gerilmesi (güneş dişi, en kritik)
    ft_total  = 2.0 * t_sun_peak / d_sun
    ft_planet = ft_total / N_PLANET * K_SHARE
    sigma_lewis = ft_planet / (FACE_W * MODULE * Y_LEWIS_SUN)
    sf_bending = SIGMA_ALLOW / sigma_lewis
    assert sf_bending > 1.5, "Eğilme emniyet katsayısı düşük"

    # ---- hız / gerilim kontrolü ----
    w_motor_max = W_MAX_OUT * RATIO                   # rad/s
    rpm_motor   = w_motor_max * 60.0 / (2.0 * math.pi)
    bemf_ll     = rpm_motor / KV                      # V (yaklaşık, hat-hat tepe)
    v_margin    = V_BUS - bemf_ll
    assert v_margin > 0.25 * V_BUS, "Gerilim marjı yetersiz (alan zayıflatma gerekir)"

    # ---- termal: sürekli tork ----
    t_sun_cont = T_CONT_OUT / (RATIO * ETA_GEAR)
    i_cont     = t_sun_cont / KT
    p_cu_cont  = 1.5 * R_PH * i_cont**2               # FOC: P = 3/2·R·Iq²
    dt_cont    = p_cu_cont * R_TH
    assert dt_cont < DT_MAX, "Sürekli torkta sargı aşırı ısınıyor"

    # ---- yansıyan atalet ve geri sürülebilirlik ----
    j_reflected = J_ROTOR * RATIO**2                  # çıkışa yansıyan rotor ataleti
    # kaba geri sürme torku tahmini: dişli sürtünmesi + rulman (deneysel ~%2 kayıp)
    t_backdrive = 0.02 * T_PEAK_OUT + 0.15

    rows = [
        ("Redüksiyon oranı (i = 1 + zr/zs)", f"{RATIO:.1f} : 1"),
        ("Güneş / Planet / Halka diş sayısı", f"{Z_SUN} / {Z_PLANET} / {Z_RING}"),
        ("Modül · diş genişliği", f"{MODULE*1e3:.1f} mm · {FACE_W*1e3:.0f} mm"),
        ("Bölüm daireleri (güneş/planet/halka)",
         f"{d_sun*1e3:.1f} / {d_planet*1e3:.1f} / {d_ring*1e3:.1f} mm"),
        ("Taşıyıcı yörünge yarıçapı", f"{a_carrier*1e3:.1f} mm"),
        ("Kavrama oranı (güneş-planet)", f"{contact_ratio:.2f}"),
        ("Kt / Kv", f"{KT*1e3:.1f} mN·m/A  /  {KV:.0f} rpm/V"),
        ("Tepe çıkış torku → motor torku", f"{T_PEAK_OUT:.0f} N·m → {t_sun_peak:.2f} N·m"),
        ("Gereken tepe akım", f"{i_peak_req:.1f} A  (limit {I_PEAK:.0f} A)"),
        ("Diş kuvveti (planet başına, K=1.25)", f"{ft_planet:.0f} N"),
        ("Lewis eğilme gerilmesi / emniyet", f"{sigma_lewis/1e6:.0f} MPa  /  SF={sf_bending:.1f}"),
        ("Tepe hızda motor devri / BEMF", f"{rpm_motor:.0f} rpm  /  {bemf_ll:.1f} V"),
        ("Gerilim marjı", f"{v_margin:.1f} V ({100*v_margin/V_BUS:.0f} %)"),
        ("Sürekli tork akımı / bakır kaybı", f"{i_cont:.1f} A  /  {p_cu_cont:.1f} W"),
        ("Sürekli torkta sıcaklık artışı", f"{dt_cont:.0f} K  (izin {DT_MAX:.0f} K)"),
        ("Çıkışa yansıyan rotor ataleti", f"{j_reflected*1e3:.2f} ×10⁻³ kg·m²"),
        ("Tahmini geri sürme torku", f"{t_backdrive:.2f} N·m"),
    ]

    w = max(len(r[0]) for r in rows)
    print("=" * (w + 30))
    print("QDD AKTÜATÖR — HESAP ÖZETİ (tüm doğrulamalar GEÇTİ)")
    print("=" * (w + 30))
    for k, v in rows:
        print(f"{k:<{w}}  {v}")
    print("=" * (w + 30))


if __name__ == "__main__":
    main()
