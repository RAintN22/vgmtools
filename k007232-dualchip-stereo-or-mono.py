#!/usr/bin/env python3
# VGM v1.70 Chip Clock/Volume Header insertion tool with Multi-Chip Mono Support
# Valley Bell, 2024-08-12
# Modified for K007232 Mono Support
# Enhanced by Copilot for strict K007232 dual-chip mono conversion as described by user

import sys
import os
import gzip
import struct
import argparse

# Chip configuration structure
k007232_config = {
    0: {'reg_base': 0x10, 'mode': 'mono'},
    1: {'reg_base': 0x90, 'mode': 'mono'}
}

# ----- Original Constants (Keep intact) -----
CHIPID_SN76496   = 0x00
CHIPID_YM2413    = 0x01
CHIPID_YM2612    = 0x02
CHIPID_YM2151    = 0x03
CHIPID_SEGAPCM   = 0x04
CHIPID_RF5C68    = 0x05
CHIPID_YM2203    = 0x06
CHIPID_YM2608    = 0x07
CHIPID_YM2610    = 0x08
CHIPID_YM3812    = 0x09
CHIPID_YM3526    = 0x0A
CHIPID_Y8950     = 0x0B
CHIPID_YMF262    = 0x0C
CHIPID_YMF278B   = 0x0D
CHIPID_YMF271    = 0x0E
CHIPID_YMZ280B   = 0x0F
CHIPID_RF5C164   = 0x10
CHIPID_32X_PWM   = 0x11
CHIPID_AY8910    = 0x12
CHIPID_GB_DMG    = 0x13
CHIPID_NES_APU   = 0x14
CHIPID_YMW258    = 0x15
CHIPID_uPD7759   = 0x16
CHIPID_OKIM6258  = 0x17
CHIPID_OKIM6295  = 0x18
CHIPID_K051649   = 0x19
CHIPID_K054539   = 0x1A
CHIPID_C6280     = 0x1B
CHIPID_C140      = 0x1C
CHIPID_K053260   = 0x1D
CHIPID_POKEY     = 0x1E
CHIPID_QSOUND    = 0x1F
CHIPID_SCSP      = 0x20
CHIPID_WSWAN     = 0x21
CHIPID_VBOY_VSU  = 0x22
CHIPID_SAA1099   = 0x23
CHIPID_ES5503    = 0x24
CHIPID_ES5506    = 0x25
CHIPID_X1_010    = 0x26
CHIPID_C352      = 0x27
CHIPID_GA20      = 0x28
CHIPID_MIKE      = 0x29
CHIPID_K007232   = 0x2A
CHIPID_YM2203_SSG    = 0x80 | CHIPID_YM2203
CHIPID_YM2608_SSG    = 0x80 | CHIPID_YM2608
CHIPID_YMF278B_FM    = 0x80 | CHIPID_YMF278B

ChipClockHeaders = []
ChipVolumeHeaders = []

# ----- Argument Parsing -----
def parse_arguments():
    parser = argparse.ArgumentParser(description='VGM Chip Volume Processor')
    parser.add_argument('--k007232-0', choices=['stereo', 'mono'], default='stereo',
                      help='Mode for K007232 chip 0 (registers 0x10-0x13)')
    parser.add_argument('--k007232-1', choices=['stereo', 'mono'], default='stereo',
                      help='Mode for K007232 chip 1 (registers 0x90-0x93)')
    parser.add_argument('input', help='Input VGM file')
    parser.add_argument('output', help='Output VGM file')
    args = vars(parser.parse_args())
    
    # Update chip configuration
    k007232_config[0]['mode'] = args['k007232_0']
    k007232_config[1]['mode'] = args['k007232_1']
    return args['input'], args['output']

# ----- Original Core Functions -----
def ReadRelOfs(buffer, bufofs: int) -> int:
    val = struct.unpack_from("<I", buffer, bufofs)[0]
    return 0 if val == 0 else (bufofs + val)

def WriteRelOfs(buffer, bufofs: int, value: int) -> None:
    if value != 0:
        value -= bufofs
    struct.pack_into("<I", buffer, bufofs, value)

def GenerateExtraHeader(clkHdr, volHdr):
    ccData = GenerateChipClockHeader(clkHdr)
    cvData = GenerateChipVolHeader(volHdr)
    subHdrData = [ccData, cvData]
    
    # Calculate sub-header offsets
    shOfsList = []
    subHdrCnt = 0
    subHdrOfs = 0x00
    for (subIdx, shData) in enumerate(subHdrData):
        if len(shData) > 0:
            shOfsList.append(subHdrOfs)
            subHdrOfs += len(shData)
            subHdrCnt = subIdx + 1
        else:
            shOfsList.append(0)
    xhSize = (1 + subHdrCnt) * 0x04
    for (subIdx, shOfs) in enumerate(shOfsList):
        if len(subHdrData[subIdx]) > 0:
            shOfsDistance = (subHdrCnt - subIdx) * 0x04
            shOfsList[subIdx] += shOfsDistance
    
    # Assemble all data
    xData = struct.pack("<III", xhSize, *shOfsList)[0:xhSize]
    for shData in subHdrData:
        xData += shData
    return xData

def GenerateChipClockHeader(hdr):
    ccData = bytearray()
    if len(hdr) == 0:
        return ccData
    ccData += struct.pack("<B", len(hdr))
    for clkEntry in hdr:
        chipClk = clkEntry[2]
        if type(chipClk) is float:
            chipClk = int(chipClk + 0.5)
        ccData += struct.pack("<BI", (clkEntry[1] << 7) | clkEntry[0], chipClk)
    return ccData

def GenerateChipVolHeader(hdr):
    cvData = bytearray()
    if len(hdr) == 0:
        return cvData
    cvData += struct.pack("<B", len(hdr))
    for clkEntry in hdr:
        chipVol = clkEntry[2]
        if type(chipVol) is float:
            if chipVol >= 0:
                chipVol = int(chipVol * 0x100 + 0.5)
            else:
                chipVol = int(chipVol * 0x100 - 0.5)
        if chipVol < 0:
            chipVol = 0x8000 | (-chipVol)
        cvData += struct.pack("<BBH", clkEntry[0], clkEntry[1], chipVol)
    return cvData

def OpenVGMFile(filename: str):
    try:
        f = open(filename, "rb")
        sig = f.read(2)
        f.seek(0)
        if sig == b'\x1F\x8B':
            f.close()
            return gzip.open(filename, "rb")
        return f
    except FileNotFoundError:
        print(f"Error: Input file '{filename}' not found!")
        sys.exit(1)

# ----- K007232 Mono Processing -----
def process_k007232_mono(cmd_stream, chip_num, reg_base):
    """
    For a given chip (chip_num: 0 or 1, reg_base: 0x10 or 0x90), 
    find sets of 4 consecutive 0x41 commands for volume (reg_base + 0 to +3).
    Rewrite as:
      - right vol ch0 = left vol ch0
      - left vol ch1 = right vol ch1
    """
    i = 0
    out = bytearray()
    cmds = cmd_stream
    length = len(cmds)

    while i < length:
        # Look for the sequence: 41 XX YY (where XX in reg_base+0..reg_base+3)
        # Need to find all four - in any order, but typically grouped.
        # We'll scan up to 8 bytes ahead to allow for the 4 commands together.
        # Only process if all four found within 12 bytes (conservative).
        lookahead = cmds[i:i+12]
        indices = {}
        for off in range(0, len(lookahead), 3):
            if i + off + 3 > length:
                break
            if lookahead[off] == 0x41:
                reg = lookahead[off+1]
                val = lookahead[off+2]
                if reg in (reg_base+0, reg_base+1, reg_base+2, reg_base+3):
                    indices[reg] = (i+off, val)
        if len(indices) == 4:
            # extract the values for each reg
            vals = {}
            for r in range(4):
                reg = reg_base + r
                idx, val = indices[reg]
                vals[reg] = val
            # Compose mono set:
            # right vol ch0 = left vol ch0
            # left vol ch1 = right vol ch1
            out.extend([0x41, reg_base+0, vals[reg_base+0]])  # left ch0
            out.extend([0x41, reg_base+1, vals[reg_base+0]])  # right ch0 = left ch0
            out.extend([0x41, reg_base+2, vals[reg_base+3]])  # left ch1 = right ch1
            out.extend([0x41, reg_base+3, vals[reg_base+3]])  # right ch1
            # skip these 4 commands
            i = max(idx for idx,_ in indices.values()) + 3
            continue
        # If not a full block, just copy the command as-is
        out.append(cmds[i])
        i += 1
    return out

# ----- Improved Command Processor -----
def process_mono_commands(cmd_stream):
    """
    Improved mono processor for K007232:
    - If mono mode is set for chip 0, process 0x41 10..13
    - If mono mode is set for chip 1, process 0x41 90..93
    - Other chips or stereo: leave untouched
    """
    # First, copy input to allow index-based manipulation.
    cmds = bytearray(cmd_stream)
    length = len(cmds)
    i = 0
    out = bytearray()

    while i < length:
        # Check for start of a K007232 volume block for either chip
        for chip_id, config in k007232_config.items():
            base = config['reg_base']
            if config['mode'] == 'mono':
                # Look for a set of 4 consecutive 0x41 commands for this chip:
                if i+12 <= length and all(
                    cmds[i+off*3] == 0x41 and
                    cmds[i+off*3+1] == base+off and
                    0 <= cmds[i+off*3+2] <= 0xFF
                    for off in range(4)
                ):
                    # Block found: apply mono fix
                    left_ch0 = cmds[i+2]
                    right_ch1 = cmds[i+11]
                    out.extend([0x41, base+0, left_ch0])      # left ch0
                    out.extend([0x41, base+1, left_ch0])      # right ch0 = left ch0
                    out.extend([0x41, base+2, right_ch1])     # left ch1 = right ch1
                    out.extend([0x41, base+3, right_ch1])     # right ch1
                    i += 12
                    break
        else:
            # Not a mono block, copy command as-is
            out.append(cmds[i])
            i += 1
    return out

# ----- Main Program Flow -----
def main():
    input_file, output_file = parse_arguments()

    # Load input file
    with OpenVGMFile(input_file) as f:
        isVGZ = isinstance(f, gzip.GzipFile)
        indata = bytearray(f.read())

    # Verify VGM version
    vgmVer = struct.unpack_from("<I", indata, 0x08)[0]
    if vgmVer < 0x150:
        print("Cannot process VGMs with version <1.50!")
        sys.exit(1)

    # Original header processing
    eofOfs = ReadRelOfs(indata, 0x04)
    gd3Ofs = ReadRelOfs(indata, 0x14)
    loopOfs = ReadRelOfs(indata, 0x1C)
    dataOfs = ReadRelOfs(indata, 0x34)
    if dataOfs == 0:
        dataOfs = 0x40
    if eofOfs == 0:
        eofOfs = len(indata)

    hdrSize = min([ofs for ofs in [dataOfs, gd3Ofs] if ofs != 0])
    xDataOfs = ReadRelOfs(indata, 0xBC) if hdrSize >= 0xC0 else 0x00
    xDataSize = 0
    if xDataOfs != 0:
        xDataSize = hdrSize - xDataOfs
        hdrSize = min([hdrSize, xDataOfs])

    # Generate and insert extra headers
    xHdrData = GenerateExtraHeader(ChipClockHeaders, ChipVolumeHeaders)
    xhPad = (0x00 - len(xHdrData)) & 0x0F
    xHdrData += b'\x00' * xhPad

    if xDataOfs == 0:
        xDataOfs = max(0xC0, hdrSize)
        if xDataOfs > hdrSize:
            hdrPadding = xDataOfs - hdrSize
            indata = indata[:hdrSize] + (b'\x00' * hdrPadding) + xHdrData + indata[hdrSize:]
            ofsMove = hdrPadding + len(xHdrData)
        else:
            indata = indata[:hdrSize] + xHdrData + indata[hdrSize:]
            ofsMove = len(xHdrData)
        WriteRelOfs(indata, 0xBC, xDataOfs)
    else:
        xDataEndOfs = hdrSize + xDataSize
        if xDataSize > len(xHdrData):
            xhPad = len(xHdrData) - xDataSize
            xHdrData += b'\x00' * xhPad
        indata = indata[:hdrSize] + xHdrData + indata[xDataEndOfs:]
        ofsMove = len(xHdrData) - (xDataEndOfs - hdrSize)

    # Update offsets
    dataOfs += ofsMove
    if loopOfs != 0:
        loopOfs += ofsMove
    if gd3Ofs != 0:
        gd3Ofs += ofsMove

    # Update VGM version
    if vgmVer < 0x170:
        vgmVer = 0x170
        struct.pack_into("<I", indata, 0x08, vgmVer)
    
    WriteRelOfs(indata, 0x34, dataOfs)
    if loopOfs != 0:
        WriteRelOfs(indata, 0x1C, loopOfs)
    if gd3Ofs != 0:
        WriteRelOfs(indata, 0x14, gd3Ofs)
    WriteRelOfs(indata, 0x04, len(indata))

    # Mono processing
    if any(cfg['mode'] == 'mono' for cfg in k007232_config.values()):
        cmd_stream = indata[dataOfs:]
        processed_cmds = process_mono_commands(cmd_stream)
        indata = indata[:dataOfs] + processed_cmds
        WriteRelOfs(indata, 0x04, len(indata))

    # Write output
    if isVGZ:
        with open(output_file, "wb") as f:
            with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=f, mtime=None) as zf:
                zf.write(indata)
    else:
        with open(output_file, "wb") as f:
            f.write(indata)

if __name__ == "__main__":
    main()