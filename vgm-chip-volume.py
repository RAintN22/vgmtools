#!/usr/bin/env python3
# VGM v1.70 Chip Clock/Volume Header insertion tool
# Valley Bell, 2024-08-12
#
# Usage:
#   1. set the ChipClockHeaders and ChipVolumeHeaders structures to the settings you want
#   2. run the tool on the respective VGM(s)
# Notes:
#   - ChipVolumeHeaders accepts the following sorts of numbers as "volume" value:
#     - floating point with 1.0 = 100%
#     - integer (8.8 fixed) with 0x100 = 100%
#     - negative float/int will be turned into relative adjustments (i.e. -0.5 = 50% of the default volume)

import sys
import os
import gzip
import struct

if len(sys.argv) < 3:
    print("Usage: {} [--mono] input.vgm output.vgm".format(sys.argv[0]))
    sys.exit(0)

mono_mode = True
args = sys.argv[1:]
if '--mono' in args:
    mono_mode = True
    args.remove('--mono')
if len(args) < 2:
    print("Usage: {} [--mono] input.vgm output.vgm".format(sys.argv[0]))
    sys.exit(0)
input_file, output_file = args[0], args[1]

CHIPID_SN76496	= 0x00
CHIPID_YM2413	= 0x01
CHIPID_YM2612	= 0x02
CHIPID_YM2151	= 0x03
CHIPID_SEGAPCM	= 0x04
CHIPID_RF5C68	= 0x05
CHIPID_RF5C68	= 0x05
CHIPID_YM2203	= 0x06
CHIPID_YM2608	= 0x07
CHIPID_YM2610	= 0x08
CHIPID_YM3812	= 0x09
CHIPID_YM3526	= 0x0A
CHIPID_Y8950	= 0x0B
CHIPID_YMF262	= 0x0C
CHIPID_YMF278B	= 0x0D
CHIPID_YMF271	= 0x0E
CHIPID_YMZ280B	= 0x0F
CHIPID_RF5C164	= 0x10
CHIPID_32X_PWM	= 0x11
CHIPID_AY8910	= 0x12
CHIPID_GB_DMG	= 0x13
CHIPID_NES_APU	= 0x14
CHIPID_YMW258	= 0x15
CHIPID_uPD7759	= 0x16
CHIPID_OKIM6258	= 0x17
CHIPID_OKIM6295	= 0x18
CHIPID_K051649	= 0x19
CHIPID_K054539	= 0x1A
CHIPID_C6280	= 0x1B
CHIPID_C140		= 0x1C
CHIPID_K053260	= 0x1D
CHIPID_POKEY	= 0x1E
CHIPID_QSOUND	= 0x1F
CHIPID_SCSP		= 0x20
CHIPID_WSWAN	= 0x21
CHIPID_VBOY_VSU	= 0x22
CHIPID_SAA1099	= 0x23
CHIPID_ES5503	= 0x24
CHIPID_ES5506	= 0x25
CHIPID_X1_010	= 0x26
CHIPID_C352		= 0x27
CHIPID_GA20		= 0x28
CHIPID_MIKEY	= 0x29
CHIPID_K007232  = 0x2A
CHIPID_YM2203_SSG	= 0x80 | CHIPID_YM2203
CHIPID_YM2608_SSG	= 0x80 | CHIPID_YM2608
CHIPID_YMF278B_FM	= 0x80 | CHIPID_YMF278B


ChipClockHeaders = [
	# chip type, instance, clock
#	(CHIPID_SN76496, 0, 3579545),
#	(CHIPID_SN76496, 1, 3579545/2),
]

ChipVolumeHeaders = [   
	# chip type, instance, volume
   # (CHIPID_YM3812, 0, 5.0),
#	(CHIPID_YM2203,     0,  1.0),
#	(CHIPID_YM2203_SSG, 0, -0.5),
#	(CHIPID_YM2608,     1,  0xC2),
#	(CHIPID_YM2608_SSG, 1, -0x41),
]


def ReadRelOfs(buffer, bufofs: int) -> int:
	val = struct.unpack_from("<I", buffer, bufofs)[0]
	return 0 if val == 0 else (bufofs + val)

def WriteRelOfs(buffer, bufofs: int, value: int) -> None:
	if value != 0:
		value -= bufofs
	struct.pack_into("<I", buffer, bufofs, value)
	return

def GenerateExtraHeader(clkHdr, volHdr) -> bytearray:
	ccData = GenerateChipClockHeader(clkHdr)
	cvData = GenerateChipVolHeader(volHdr)
	subHdrData = [ccData, cvData]
	
	# calculate sub-header offsets
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
	
	# assemble all data
	xData = struct.pack("<III", xhSize, *shOfsList)[0:xhSize]
	for shData in subHdrData:
		xData += shData
	return xData

def GenerateChipClockHeader(hdr) -> bytearray:
	ccData = bytearray()
	if len(hdr) == 0:
		return ccData
	# entry count
	ccData += struct.pack("<B", len(hdr))
	for clkEntry in hdr:
		chipClk = clkEntry[2]
		if type(chipClk) is float:
			chipClk = int(chipClk + 0.5)
		# chip type/ID (bit 7 = 2nd instance), chip clock
		ccData += struct.pack("<BI", (clkEntry[1] << 7) | clkEntry[0], chipClk)
	return ccData

def GenerateChipVolHeader(hdr) -> bytearray:
	cvData = bytearray()
	if len(hdr) == 0:
		return cvData
	# entry count
	cvData += struct.pack("<B", len(hdr))
	for clkEntry in hdr:
		chipVol = clkEntry[2]
		if type(chipVol) is float:
			# convert float -> 8.8 fixed-point integer
			if chipVol >= 0:
				chipVol = int(chipVol * 0x100 + 0.5)
			else:
				chipVol = int(chipVol * 0x100 - 0.5)
		if chipVol < 0:
			# convert negative values to relative
			chipVol = 0x8000 | (-chipVol)
		# chip type, chip instance, chip volume
		cvData += struct.pack("<BBH", clkEntry[0], clkEntry[1], chipVol)
	return cvData

def OpenVGMFile(filename: str):
	f = open(filename, "rb")
	sig = f.read(2)
	if sig == b'\x1F\x8B':
		f.close()
		return gzip.open(filename, "rb")
	else:
		f.seek(0)
		return f

with OpenVGMFile(sys.argv[1]) as f:
	isVGZ = (type(f) == gzip.GzipFile)
	sig = f.read(4)
	if sig != b"Vgm ":
		print("Not a VGM file!")
		sys.exit(1)
	f.seek(0)
	indata = bytearray(f.read())

# parse header
vgmVer = struct.unpack_from("<I", indata, 0x08)[0]
if vgmVer < 0x150:
	print("Can not work with VGMs whose version is <1.50!")
	sys.exit(1)
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

# generate extra header
xHdrData = GenerateExtraHeader(ChipClockHeaders, ChipVolumeHeaders)
xhPad = (0x00 - len(xHdrData)) & 0x0F
xHdrData += b'\x00' * xhPad	# not required, but I like alignment

# add extra header to the VGM
if xDataOfs == 0:
	# not extra header exists yet
	xDataOfs = max(0xC0, hdrSize)
	if xDataOfs > hdrSize:
		hdrPadding = xDataOfs - hdrSize
		# pad header and insert extra header
		indata = indata[:hdrSize] + (b'\x00' * hdrPadding) + xHdrData + indata[hdrSize:]
		ofsMove = hdrPadding + len(xHdrData)
	else:
		# insert extra header
		indata = indata[:hdrSize] + xHdrData + indata[hdrSize:]
		ofsMove = len(xHdrData)
	WriteRelOfs(indata, 0xBC, xDataOfs)
else:
	# replace existing extra header
	xDataEndOfs = hdrSize + xDataSize
	if xDataSize > len(xHdrData):
		# pad the new extra header so that the full old data gets dummied out
		xhPad = len(xHdrData) - xDataSize
		xHdrData += b'\x00' * xhPad
	# remove old extra header and insert extra header
	indata = indata[:hdrSize] + xHdrData + indata[xDataEndOfs:]
	ofsMove = len(xHdrData) - (xDataEndOfs - hdrSize)

# move all offsets
dataOfs += ofsMove
if loopOfs != 0:
	loopOfs += ofsMove
if gd3Ofs != 0:
	gd3Ofs += ofsMove

# update VGM version
if vgmVer < 0x170:
	vgmVer = 0x170
	struct.pack_into("<I", indata, 0x08, vgmVer)
# rewrite offsets
WriteRelOfs(indata, 0x34, dataOfs)	# data offset
if loopOfs != 0:
	WriteRelOfs(indata, 0x1C, loopOfs)	# loop offset
if gd3Ofs != 0:
	WriteRelOfs(indata, 0x14, gd3Ofs)	# GD3 offset
WriteRelOfs(indata, 0x04, len(indata))	# EOF offset


if mono_mode:
    dataOfs = ReadRelOfs(indata, 0x34)
    cmd_stream = indata[dataOfs:]
    processed_cmds = bytearray()
    i = 0

    cmd_lengths = {
        0x40: 1, 0x41: 3, 0x42: 3, 0x43: 3, 0x44: 3, 0x45: 3, 0x46: 3, 0x47: 3, 0x48: 3,
        0x49: 3, 0x4A: 3, 0x4B: 3, 0x4C: 3, 0x4D: 3, 0x4E: 3, 0x4F: 3, 0x50: 1,
        0x51: 3, 0x52: 3, 0x53: 3, 0x54: 3, 0x55: 3, 0x56: 3, 0x57: 3, 0x58: 3,
        0x59: 3, 0x5A: 3, 0x5B: 3, 0x5C: 3, 0x5D: 3, 0x5E: 3, 0x5F: 3,
        0x61: 2, 0x62: 1, 0x63: 1, 0x66: 1, 0x67: 0, 0x68: 1,
        0x70: 1, 0x71: 1, 0x72: 1, 0x73: 1, 0x74: 1, 0x75: 1, 0x76: 1, 0x77: 1,
        0x78: 1, 0x79: 1, 0x7A: 1, 0x7B: 1, 0x7C: 1, 0x7D: 1, 0x7E: 1, 0x7F: 1,
        0x80: 1, 0x81: 1, 0x82: 1, 0x83: 1, 0x84: 1, 0x85: 1, 0x86: 1, 0x87: 1,
        0x88: 1, 0x89: 1, 0x8A: 1, 0x8B: 1, 0x8C: 1, 0x8D: 1, 0x8E: 1, 0x8F: 1,
        0x90: 4, 0x91: 4, 0x92: 6, 0x93: 2, 0x94: 2, 0x95: 3, 0xE0: 4,
    }

    while i < len(cmd_stream):
        cmd = cmd_stream[i]
        length = cmd_lengths.get(cmd, 1)
        
        # Handle PCM data block (0x67)
        if cmd == 0x67:
            if i + 7 > len(cmd_stream):
                break
            data_size = struct.unpack_from("<I", cmd_stream, i + 3)[0]
            length = 7 + data_size
        
        if i + length > len(cmd_stream):
            break
        
        current_cmd = cmd_stream[i:i+length]
        if cmd == 0x41 and length >= 3:
            reg = current_cmd[1]
            val = current_cmd[2]
            if reg == 0x10:  # Ch0 Left
                processed_cmds.extend(current_cmd)
                processed_cmds.extend([0x41, 0x11, val])  # Mirror to Ch0 Right
            elif reg == 0x13:  # Ch1 Right
                processed_cmds.extend(current_cmd)
                processed_cmds.extend([0x41, 0x12, val])  # Mirror to Ch1 Left
            elif reg in (0x11, 0x12):  # Skip existing Right/Left writes
                pass
            else:
                processed_cmds.extend(current_cmd)
        else:
            processed_cmds.extend(current_cmd)
        i += length
    indata = indata[:dataOfs] + processed_cmds
    WriteRelOfs(indata, 0x04, len(indata))
# write VGM, with optional GZip compression
if isVGZ:
	with open(sys.argv[2], "wb") as f:
		with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=f, mtime=None) as zf:
			zf.write(indata)
else:
	with open(sys.argv[2], "wb") as f:
		f.write(indata) 
        
        

