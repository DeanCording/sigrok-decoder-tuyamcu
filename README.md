# TuyaMCU Protocol Decoder for Sigrok

A Sigrok protocol decoder for the Tuya MCU serial protocol, developed while reverse engineering a split air conditioner using a Tuya-based WiFi module.

This decoder sits on top of the UART decoder and parses TuyaMCU frames, DPIDs, commands, checksums, and payloads commonly used by Tuya WiFi modules such as the WBWBR1/WBR3 series.

## Installation

Clone this repository:
```bash
git clone https://github.com/jkreucher/sigrok-decoder-tuyamcu.git
```

Then install the decoder manually for the current user:
```bash
mkdir -p ~/.local/share/libsigrokdecode/decoders/
```

```bash
cp -R tuyamcu ~/.local/share/libsigrokdecode/decoders/
```

Or system-wide:

```bash
sudo cp -R tuyamcu /usr/share/libsigrokdecode/decoders/
```

## Disclaimer

This project is not affiliated with or endorsed by Tuya.

All trademarks belong to their respective owners.
