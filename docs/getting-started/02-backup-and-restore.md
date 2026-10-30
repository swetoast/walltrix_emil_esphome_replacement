# 2. Back up and restore the original firmware

Take a full image of the flash before writing anything to the clock. With it, going back to the original firmware is one command.

## Find the serial port

Plug the clock into your computer with a micro-USB data cable.

| System | Port name | How to check |
|---|---|---|
| Windows | `COM3`, `COM4`, ... | Device Manager > Ports (COM & LPT), look for USB-SERIAL CH340 |
| Linux | `/dev/ttyUSB0` | `ls /dev/ttyUSB*` before and after plugging in |
| macOS | `/dev/cu.usbserial-*` | `ls /dev/cu.*` before and after plugging in |

The examples below use `COM4`. Replace it with your port.

## Take the backup

```bash
pip install esptool
esptool --port COM4 flash-id
esptool --port COM4 --baud 460800 read-flash 0x0 0x400000 original_full_4MB.bin
```

- `flash-id` should report a 4 MB flash chip.
- `read-flash` copies the whole chip, address `0x0` to `0x400000`.
- The file must be exactly `4194304` bytes.

## Record a checksum

The checksum lets you confirm later that the file has not changed.

| System | Command |
|---|---|
| Windows | `certutil -hashfile original_full_4MB.bin SHA256` |
| Linux | `sha256sum original_full_4MB.bin` |
| macOS | `shasum -a 256 original_full_4MB.bin` |

Save the result next to the file.

## Keep it safe

Store the backup outside this repository, ideally in two places. The repository's `.gitignore` excludes `*.bin`, so it cannot be committed by accident.

## Restore the original firmware

```bash
esptool --port COM4 --baud 460800 write-flash 0x0 original_full_4MB.bin
```

This writes the whole image back and the clock starts exactly as it was. It works as long as the backup is complete, which is why the size and checksum checks above matter.

Next: [First flash](03-first-flash.md)
