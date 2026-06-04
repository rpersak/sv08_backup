# SV08 Mainline Klipper — Setup postopek

## Korak 1: Sovol extras (OBVEZNO)

Prek SFTP (WinSCP, FileZilla) kopiraj v `/home/sovol/klipper/klippy/extras/`:
- `probe_pressure.py`
- `z_offset_calibration.py`

Prenesi iz: https://github.com/Rappetor/Sovol-SV08-Mainline/tree/main/files-used/sovol-addons

Nato restaraj Klipper:
```
sudo systemctl restart klipper
```

## Korak 2: pid_calibrate.py patch (za PID profile)

Kopiraj patched verzijo v `/home/sovol/klipper/klippy/extras/pid_calibrate.py`
(iz klipper-pid-profiles repo — patch doda SET_HEATER_PID command)

Nato zbriši .pyc cache in restaraj:
```
rm -f /home/sovol/klipper/klippy/extras/__pycache__/pid_calibrate*.pyc
sudo systemctl restart klipper
```

## Korak 3: Konfiguracijske datoteke

Kopiraj vse datoteke iz tega folderja v `/home/sovol/printer_data/config/` prek SFTP.

POZOR: `mainsail.cfg` in `timelapse.cfg` NE kopiraj — ti nastanejo avtomatsko z KIAUH.

## Korak 4: MCU seriali

Preveri MCU seriale prek SSH:
```
ls /dev/serial/by-path/
```

Če vidita oba serija iz `printer.cfg` (`platform-5200400...` in `platform-5101400...`) — OK, ni treba ničesar spremeniti.

Če sta seriali drugačni (po MCU firmware flashu):
```
ls /dev/serial/by-id/
```
In posodobi `printer.cfg` v sekcijah `[mcu]` in `[mcu extra_mcu]`.

## Korak 5: MCU firmware (če ni že narejeno)

Klipper host in MCU firmware MORATA biti iste verzije. Preveri z:
- Klipper bo javil "MCU mcu Version mismatch" ob startu

Če je mismatch, je treba flashat MCU firmware prek Katapult/USB.
Glej: https://github.com/Rappetor/Sovol-SV08-Mainline (README sekcija za MCU flash)

## Korak 6: Zagon in Z kalibracija

1. Odpri Mainsail v brskalniku
2. Home printer: `G28`
3. Zaženi Z kalibracijo: `Z_OFFSET_CALIBRATION`
4. Preveri Z offset z babystepping med testnim printom
5. Nastavi `internalendstopoffset` v `printer.cfg` ([z_offset_calibration] sekcija)

## Korak 7: KAMP (opcijsko)

Če si KAMP namestil prek KIAUH:
1. Odkomentiraj `[include KAMP_Settings.cfg]` v printer.cfg
2. Uredi `KAMP_Settings.cfg` po potrebi

## Spremembe glede na staro konfiguracijo

| Staro | Novo | Razlog |
|-------|------|--------|
| `fan_generic fan0/fan1` | `[fan]` z multi_pin | Mainline standard, M106 deluje native |
| `fan_generic fan3` | `fan_generic exhaust_fan` | Jasnejše ime |
| `M106/M107` makri | odstranjeni | Z `[fan]` niso več potrebni |
| `RUN_PROBE_VIR_CONTACT` | odstranjeno | Sovol-specifično, ni v mainline |
| `Z_OFFSET_CALIBRATION METHOD=force_overlay` | `Z_OFFSET_CALIBRATION` | Novi extra brez parametra |
| `max_accel_to_decel` | `minimum_cruise_ratio: 0.5` | Deprecated v mainline |
| `vir_contact_speed` v probe | odstranjeno | Sovol-specifičen parameter |
| run_current X/Y: 1.5A | 1.1A | Rappetor priporočilo za mainline |
| run_current Z: 0.58A | 0.55A | Rappetor priporočilo |
| `controller_fan MCU_fan` | dodano | Krmili mainboard cooling fan (PA1) |

## Konfigi ki so enaki

- Vse pin definicije (stepper, heater, fan pini)
- Thermistorji
- Bed mesh kalibracija (vključno v SAVE_CONFIG)
- Eddy current probe kalibracija (SAVE_CONFIG)
- Homing override
- PID profili
- Vsi makri (SUSENJE, AUTO_POWEROFF, PAUSE/RESUME, itd.)
- PLR (power loss recovery)
- Crowsnest (kamera)
- Obico integracija
