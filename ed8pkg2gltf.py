# ED8 PKG to GLTF, forked from uyjulian/ed8pkg2glb.  This is also configured to dumped meshes,
# textures, shaders, metadata (materials, shader parameters, locators, etc) and the asset XML.
# HUGE thank you to uyjulian for writing the original program!
#
# For command line options, run:
# /path/to/python3 ed8pkg2gltf.py --help
#
# GitHub eArmada8/ed8pkg2gltf

import os, gc, sys, io, struct, array, glob
from lib_fmtibvb import *

# This script outputs non-empty vgmaps by default, change the following line to True to change
partial_vgmaps_default = False

try:
    import zstandard
except:
    pass

def read_null_ending_string(f):
    import itertools
    import functools
    toeof = iter(functools.partial(f.read, 1), b'')
    return sys.intern(b''.join(itertools.takewhile(b'\x00'.__ne__, toeof)).decode('ASCII'))

def bytearray_byteswap(p, itemsize):
    if itemsize == 1:
        pass
    elif itemsize == 2:
        for i in range(0, len(p), itemsize):
            p0 = p[i + 0]
            p[i + 0] = p[i + 1]
            p[i + 1] = p0
    elif itemsize == 4:
        for i in range(0, len(p), itemsize):
            p0 = p[i + 0]
            p1 = p[i + 1]
            p[i + 0] = p[i + 3]
            p[i + 1] = p[i + 2]
            p[i + 2] = p1
            p[i + 3] = p0
    elif itemsize == 8:
        for i in range(0, len(p), itemsize):
            p0 = p[i + 0]
            p1 = p[i + 1]
            p2 = p[i + 2]
            p3 = p[i + 3]
            p[i + 0] = p[i + 7]
            p[i + 1] = p[i + 6]
            p[i + 2] = p[i + 5]
            p[i + 3] = p[i + 4]
            p[i + 4] = p3
            p[i + 5] = p2
            p[i + 6] = p1
            p[i + 7] = p0
    else:
        raise Exception("don't know how to byteswap this array type")

def cast_memoryview(mv, t):
    return mv.cast(t)

def read_integer(f, size, unsigned, endian='<'):
    typemap = {1: 'b', 2: 'h', 4: 'i', 8: 'q'}
    inttype = typemap[size]
    if unsigned == True:
        inttype = inttype.upper()
    ba = bytearray(f.read(size))
    if endian == '>':
        bytearray_byteswap(ba, size)
    return cast_memoryview(memoryview(ba), inttype)[0]

def imageUntilePS4(buffer, width, height, bpb, pitch=0):
    Tile = (0, 1, 8, 9, 2, 3, 10, 11, 16, 17, 24, 25, 18, 19, 26, 27, 4, 5, 12, 13, 6, 7, 14, 15, 20, 21, 28, 29, 22, 23, 30, 31, 32, 33, 40, 41, 34, 35, 42, 43, 48, 49, 56, 57, 50, 51, 58, 59, 36, 37, 44, 45, 38, 39, 46, 47, 52, 53, 60, 61, 54, 55, 62, 63)
    tileWidth = 8
    tileHeight = 8
    out = bytearray(len(buffer))
    usingPitch = False
    if pitch > 0 and pitch != width:
        width_bak = width
        width = pitch
        usingPitch = True
    if width % tileWidth or height % tileHeight:
        width_show = width
        height_show = height
        width = width_real = (width + (tileWidth - 1)) // tileWidth * tileWidth
        height = height_real = (height + (tileHeight - 1)) // tileHeight * tileHeight
    else:
        width_show = width_real = width
        height_show = height_real = height
    for InY in range(height):
        for InX in range(width):
            Z = InY * width + InX
            globalX = Z // (tileWidth * tileHeight) * tileWidth
            globalY = globalX // width * tileHeight
            globalX %= width
            inTileX = Z % tileWidth
            inTileY = Z // tileWidth % tileHeight
            inTile = inTileY * tileHeight + inTileX
            inTile = Tile[inTile]
            inTileX = inTile % tileWidth
            inTileY = inTile // tileHeight
            OutX = globalX + inTileX
            OutY = globalY + inTileY
            OffsetIn = InX * bpb + InY * bpb * width
            OffsetOut = OutX * bpb + OutY * bpb * width
            out[OffsetOut:OffsetOut + bpb] = buffer[OffsetIn:OffsetIn + bpb]
    if usingPitch:
        width_show = width_bak
    if width_show != width_real or height_show != height_real:
        crop = bytearray(width_show * height_show * bpb)
        for Y in range(height_show):
            OffsetIn = Y * width_real * bpb
            OffsetOut = Y * width_show * bpb
            crop[OffsetOut:OffsetOut + width_show * bpb] = out[OffsetIn:OffsetIn + width_show * bpb]
        out = crop
    return out

def imageUntileMorton(buffer, width, height, bpb, pitch=0):
    Tile = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63)
    tileWidth = 8
    tileHeight = 8
    out = bytearray(len(buffer))
    usingPitch = False
    if pitch > 0 and pitch != width:
        width_bak = width
        width = pitch
        usingPitch = True
    if width % tileWidth or height % tileHeight:
        width_show = width
        height_show = height
        width = width_real = (width + (tileWidth - 1)) // tileWidth * tileWidth
        height = height_real = (height + (tileHeight - 1)) // tileHeight * tileHeight
    else:
        width_show = width_real = width
        height_show = height_real = height
    for InY in range(height):
        for InX in range(width):
            Z = InY * width + InX
            globalX = Z // (tileWidth * tileHeight) * tileWidth
            globalY = globalX // width * tileHeight
            globalX %= width
            inTileX = Z % tileWidth
            inTileY = Z // tileWidth % tileHeight
            inTile = inTileY * tileHeight + inTileX
            inTile = Tile[inTile]
            inTileX = inTile % tileWidth
            inTileY = inTile // tileHeight
            OutX = globalX + inTileX
            OutY = globalY + inTileY
            OffsetIn = InX * bpb + InY * bpb * width
            OffsetOut = OutX * bpb + OutY * bpb * width
            out[OffsetOut:OffsetOut + bpb] = buffer[OffsetIn:OffsetIn + bpb]
    if usingPitch:
        width_show = width_bak
    if width_show != width_real or height_show != height_real:
        crop = bytearray(width_show * height_show * bpb)
        for Y in range(height_show):
            OffsetIn = Y * width_real * bpb
            OffsetOut = Y * width_show * bpb
            crop[OffsetOut:OffsetOut + width_show * bpb] = out[OffsetIn:OffsetIn + width_show * bpb]
        out = crop
    return out

def Compact1By1(x):
    x &= 1431655765
    x = (x ^ x >> 1) & 858993459
    x = (x ^ x >> 2) & 252645135
    x = (x ^ x >> 4) & 16711935
    x = (x ^ x >> 8) & 65535
    return x

def DecodeMorton2X(code):
    return Compact1By1(code >> 0)

def DecodeMorton2Y(code):
    return Compact1By1(code >> 1)

def imageUntileVita(buffer, width, height, bpb, pitch=0):
    import math
    tileWidth = 8
    tileHeight = 8
    out = bytearray(len(buffer))
    usingPitch = False
    if pitch > 0 and pitch != width:
        width_bak = width
        width = pitch
        usingPitch = True
    if width % tileWidth or height % tileHeight:
        width_show = width
        height_show = height
        width = width_real = (width + (tileWidth - 1)) // tileWidth * tileWidth
        height = height_real = (height + (tileHeight - 1)) // tileHeight * tileHeight
    else:
        width_show = width_real = width
        height_show = height_real = height
    for InY in range(height):
        for InX in range(width):
            Z = InY * width + InX
            mmin = width if width < height else height
            k = int(math.log(mmin, 2))
            if height < width:
                j = Z >> 2 * k << 2 * k | (DecodeMorton2Y(Z) & mmin - 1) << k | (DecodeMorton2X(Z) & mmin - 1) << 0
                OutX = j // height
                OutY = j % height
            else:
                j = Z >> 2 * k << 2 * k | (DecodeMorton2X(Z) & mmin - 1) << k | (DecodeMorton2Y(Z) & mmin - 1) << 0
                OutX = j % width
                OutY = j // width
            OffsetIn = InX * bpb + InY * bpb * width
            OffsetOut = OutX * bpb + OutY * bpb * width
            out[OffsetOut:OffsetOut + bpb] = buffer[OffsetIn:OffsetIn + bpb]
    if usingPitch:
        width_show = width_bak
    if width_show != width_real or height_show != height_real:
        crop = bytearray(width_show * height_show * bpb)
        for Y in range(height_show):
            OffsetIn = Y * width_real * bpb
            OffsetOut = Y * width_show * bpb
            crop[OffsetOut:OffsetOut + width_show * bpb] = out[OffsetIn:OffsetIn + width_show * bpb]
        out = crop
    return out

def Unswizzle(data, width, height, imgFmt, IsSwizzled, platform_id, pitch=0):
    TexParams = (('DXT1', 1, 8), ('DXT3', 1, 16), ('DXT5', 1, 16), ('BC5', 1, 16), ('BC7', 1, 16), ('RGBA8', 0, 4), ('ARGB8', 0, 4), ('L8', 0, 1), ('A8', 0, 1), ('LA88', 0, 2), ('RGBA16F', 0, 8), ('ARGB1555', 0, 2), ('ARGB4444', 0, 2), ('RGB565', 0, 2), ('ARGB8_SRGB', 0, 4))
    TexParams = tuple((tuple((TexParams[j][i] for j in range(len(TexParams)))) for i in range(len(TexParams[0]))))
    IsBlockCompressed = TexParams[1][TexParams[0].index(imgFmt)]
    BytesPerBlock = TexParams[2][TexParams[0].index(imgFmt)]
    if IsBlockCompressed:
        width >>= 2
        height >>= 2
        pitch >>= 2
    if platform_id == GNM_PLATFORM:
        data = imageUntilePS4(data, width, height, BytesPerBlock, pitch)
    elif platform_id == GXM_PLATFORM:
        data = imageUntileVita(data, width, height, BytesPerBlock, pitch)
    else:
        data = imageUntileMorton(data, width, height, BytesPerBlock, pitch)
    return data

def GetInfo(val, sh1, sh2):
    val &= 4294967295
    val <<= 31 - sh1
    val &= 4294967295
    val >>= 31 - sh1 + sh2
    val &= 4294967295
    return val

def decode_bc7_block(src):

    def get_bits(src, bit, count):
        v = 0
        x = 0
        by = bit >> 3
        bit &= 7
        if count == 0:
            return 0
        if bit + count <= 8:
            v = src[by] >> bit & (1 << count) - 1
        else:
            x = src[by] | src[by + 1] << 8
            v = x >> bit & (1 << count) - 1
        return v & 255
    bc7_modes = [[3, 4, 0, 0, 4, 0, 1, 0, 3, 0], [2, 6, 0, 0, 6, 0, 0, 1, 3, 0], [3, 6, 0, 0, 5, 0, 0, 0, 2, 0], [2, 6, 0, 0, 7, 0, 1, 0, 2, 0], [1, 0, 2, 1, 5, 6, 0, 0, 2, 3], [1, 0, 2, 0, 7, 8, 0, 0, 2, 2], [1, 0, 0, 0, 7, 7, 1, 0, 4, 0], [2, 6, 0, 0, 5, 5, 1, 0, 2, 0]]

    def bc7_mode_to_dict(mode_arr):
        return {'ns': mode_arr[0], 'pb': mode_arr[1], 'rb': mode_arr[2], 'isb': mode_arr[3], 'cb': mode_arr[4], 'ab': mode_arr[5], 'epb': mode_arr[6], 'spb': mode_arr[7], 'ib': mode_arr[8], 'ib2': mode_arr[9]}
    bc7_modes[:] = [bc7_mode_to_dict(x) for x in bc7_modes]
    bc7_si2 = [52428, 34952, 61166, 60616, 51328, 65260, 65224, 60544, 51200, 65516, 65152, 59392, 65512, 65280, 65520, 61440, 63248, 142, 28928, 2254, 140, 29456, 12544, 36046, 2188, 12560, 26214, 13932, 6120, 4080, 29070, 14748, 43690, 61680, 23130, 13260, 15420, 21930, 38550, 42330, 29646, 5064, 12876, 15324, 27030, 49980, 39270, 1632, 626, 1252, 20032, 10016, 51510, 37740, 14790, 25500, 37686, 40134, 33150, 59160, 52464, 4044, 30532, 60962]
    bc7_si3 = [2858963024, 1784303680, 1515864576, 1414570152, 2779054080, 2694860880, 1431675040, 1515868240, 2857697280, 2857719040, 2863289600, 2425393296, 2492765332, 2762253476, 2846200912, 705315408, 2777960512, 172118100, 2779096320, 1436590240, 2829603924, 1785348160, 2762231808, 437912832, 5285028, 2862977168, 342452500, 1768494080, 2693105056, 2860651540, 1352967248, 1784283648, 2846195712, 1351655592, 2829094992, 606348324, 11162880, 613566756, 608801316, 1352993360, 1342874960, 2863285316, 1717960704, 2778768800, 1352683680, 1764256040, 1152035396, 1717986816, 2856600644, 1420317864, 2508232064, 2526451200, 2824098984, 2157286784, 2853442580, 2526412800, 2863272980, 2689618080, 2695210400, 2516582400, 1082146944, 2846402984, 2863311428, 709513812]
    bc7_ai0 = [15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2, 2, 15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6, 6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2, 2, 15]
    bc7_ai1 = [3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3, 3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15, 8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15, 3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12, 3, 3]
    bc7_ai2 = [15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8, 15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15, 15, 10, 8, 15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8, 15, 3, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 3, 15, 15, 8]
    bc7_weights2 = [0, 21, 43, 64]
    bc7_weights3 = [0, 9, 18, 27, 37, 46, 55, 64]
    bc7_weights4 = [0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64]

    def bc7_get_weights(n):
        if n == 2:
            return bc7_weights2
        if n == 3:
            return bc7_weights3
        return bc7_weights4

    def bc7_get_subset(ns, partition, n):
        if ns == 2:
            return 1 & bc7_si2[partition] >> n
        if ns == 3:
            return 3 & bc7_si3[partition] >> 2 * n
        return 0

    def expand_quantized(v, bits):
        v = v << 8 - bits
        return (v | v >> bits) & 255

    def bc7_lerp(dst, dst_offset, e, e_offset, s0, s1):
        t0 = 64 - s0
        t1 = 64 - s1
        dst_write_offset = dst_offset * 4
        e_read_offset_0 = (e_offset + 0) * 4
        e_read_offset_1 = (e_offset + 1) * 4
        dst[dst_write_offset + 0] = t0 * e[e_read_offset_0 + 0] + s0 * e[e_read_offset_1 + 0] + 32 >> 6 & 255
        dst[dst_write_offset + 1] = t0 * e[e_read_offset_0 + 1] + s0 * e[e_read_offset_1 + 1] + 32 >> 6 & 255
        dst[dst_write_offset + 2] = t0 * e[e_read_offset_0 + 2] + s0 * e[e_read_offset_1 + 2] + 32 >> 6 & 255
        dst[dst_write_offset + 3] = t1 * e[e_read_offset_0 + 3] + s1 * e[e_read_offset_1 + 3] + 32 >> 6 & 255
    col = bytearray(4 * 4 * 4)
    endpoints = bytearray(6 * 4)
    bit = 0
    mode = src[0]
    if mode == 0:
        for i in range(16):
            col[i * 4 + 0] = 0
            col[i * 4 + 1] = 0
            col[i * 4 + 2] = 0
            col[i * 4 + 3] = 255
        return col
    while True:
        cond = mode & 1 << bit != 0
        bit += 1
        if cond:
            break
    mode = bit - 1
    info = bc7_modes[mode]
    cb = info['cb']
    ab = info['ab']
    cw = bc7_get_weights(info['ib'])
    aw = bc7_get_weights(info['ib2'] if ab != 0 and info['ib2'] != 0 else info['ib'])
    partition = get_bits(src, bit, info['pb'])
    bit += info['pb']
    rotation = get_bits(src, bit, info['rb'])
    bit += info['rb']
    index_sel = get_bits(src, bit, info['isb'])
    bit += info['isb']
    numep = info['ns'] << 1
    for i in range(numep):
        val = get_bits(src, bit, cb)
        bit += cb
        endpoints[i * 4 + 0] = val
    for i in range(numep):
        val = get_bits(src, bit, cb)
        bit += cb
        endpoints[i * 4 + 1] = val
    for i in range(numep):
        val = get_bits(src, bit, cb)
        bit += cb
        endpoints[i * 4 + 2] = val
    for i in range(numep):
        val = 255
        if ab != 0:
            val = get_bits(src, bit, ab)
            bit += ab
        endpoints[i * 4 + 3] = val
    if info['epb'] != 0:
        cb += 1
        if ab != 0:
            ab += 1
        for i in range(numep):
            endpoint_write_offset = i * 4
            val = get_bits(src, bit, 1)
            bit += 1
            endpoints[endpoint_write_offset + 0] = endpoints[endpoint_write_offset + 0] << 1 | val
            endpoints[endpoint_write_offset + 1] = endpoints[endpoint_write_offset + 1] << 1 | val
            endpoints[endpoint_write_offset + 2] = endpoints[endpoint_write_offset + 2] << 1 | val
            if ab != 0:
                endpoints[endpoint_write_offset + 3] = endpoints[endpoint_write_offset + 3] << 1 | val
    if info['spb'] != 0:
        cb += 1
        if ab != 0:
            ab += 1
        for i in range(0, numep, 2):
            val = get_bits(src, bit, 1)
            bit += 1
            for j in range(2):
                endpoint_write_offset = (i + j) * 4
                endpoints[endpoint_write_offset + 0] = endpoints[endpoint_write_offset + 0] << 1 | val
                endpoints[endpoint_write_offset + 1] = endpoints[endpoint_write_offset + 1] << 1 | val
                endpoints[endpoint_write_offset + 2] = endpoints[endpoint_write_offset + 2] << 1 | val
                if ab != 0:
                    endpoints[endpoint_write_offset + 3] = endpoints[endpoint_write_offset + 3] << 1 | val
    for i in range(numep):
        endpoint_write_offset = i * 4
        endpoints[endpoint_write_offset + 0] = expand_quantized(endpoints[endpoint_write_offset + 0], cb)
        endpoints[endpoint_write_offset + 1] = expand_quantized(endpoints[endpoint_write_offset + 1], cb)
        endpoints[endpoint_write_offset + 2] = expand_quantized(endpoints[endpoint_write_offset + 2], cb)
        if ab != 0:
            endpoints[endpoint_write_offset + 3] = expand_quantized(endpoints[endpoint_write_offset + 3], ab)
    cibit = bit
    aibit = cibit + 16 * info['ib'] - info['ns']
    for i in range(16):
        s = bc7_get_subset(info['ns'], partition, i) << 1
        ib = info['ib']
        if i == 0:
            ib -= 1
        elif info['ns'] == 2:
            if i == bc7_ai0[partition]:
                ib -= 1
        elif info['ns'] == 3:
            if i == bc7_ai1[partition]:
                ib -= 1
            elif i == bc7_ai2[partition]:
                ib -= 1
        i0 = get_bits(src, cibit, ib)
        cibit += ib
        if ab != 0 and info['ib2'] != 0:
            ib2 = info['ib2']
            if ib2 != 0 and i == 0:
                ib2 -= 1
            i1 = get_bits(src, aibit, ib2)
            aibit += ib2
            if index_sel != 0:
                bc7_lerp(col, i, endpoints, s, aw[i1], cw[i0])
            else:
                bc7_lerp(col, i, endpoints, s, cw[i0], aw[i1])
        else:
            bc7_lerp(col, i, endpoints, s, cw[i0], cw[i0])
        if rotation == 1:
            val = col[i * 4 + 0]
            col[i * 4 + 0] = col[i * 4 + 3]
            col[i * 4 + 3] = val
        elif rotation == 2:
            val = col[i * 4 + 1]
            col[i * 4 + 1] = col[i * 4 + 3]
            col[i * 4 + 3] = val
        elif rotation == 3:
            val = col[i * 4 + 2]
            col[i * 4 + 2] = col[i * 4 + 3]
            col[i * 4 + 3] = val
    return col

def decode_bc5(data):

    def decode_bc3_alpha(dst, dst_offset, src, src_offset, stride, o, sign):
        a0 = 0
        a1 = 0
        a = bytearray(8)
        lut1 = 0
        lut2 = 0
        if sign == 1:
            raise Exception('Signed bc5 not implemented!')
        else:
            a0 = src[src_offset + 0]
            a1 = src[src_offset + 1]
        src_lut_offset = src_offset + 2
        lut1 = src[src_lut_offset + 0] | src[src_lut_offset + 1] << 8 | src[src_lut_offset + 2] << 16
        lut2 = src[src_lut_offset + 3] | src[src_lut_offset + 4] << 8 | src[src_lut_offset + 5] << 16
        a[0] = a0 & 255
        a[1] = a1 & 255
        if a0 > a1:
            a[2] = (6 * a0 + 1 * a1) // 7
            a[3] = (5 * a0 + 2 * a1) // 7
            a[4] = (4 * a0 + 3 * a1) // 7
            a[5] = (3 * a0 + 4 * a1) // 7
            a[6] = (2 * a0 + 5 * a1) // 7
            a[7] = (1 * a0 + 6 * a1) // 7
        else:
            a[2] = (4 * a0 + 1 * a1) // 5
            a[3] = (3 * a0 + 2 * a1) // 5
            a[4] = (2 * a0 + 3 * a1) // 5
            a[5] = (1 * a0 + 4 * a1) // 5
            a[6] = 0
            a[7] = 255
        for n in range(8):
            aw = 7 & lut1 >> 3 * n
            dst[dst_offset + (stride * n + o)] = a[aw]
        for n in range(8):
            aw = 7 & lut2 >> 3 * n
            dst[dst_offset + (stride * (8 + n) + o)] = a[aw]
    finalColor = bytearray(4 * 4 * 4)
    block = data[:16]
    decode_bc3_alpha(finalColor, 0, block, 0, 4, 0, 0)
    decode_bc3_alpha(finalColor, 0, block, 8, 4, 1, 0)
    return finalColor
import struct

def decode_dxt1(data):
    finalColor = bytearray(4 * 4 * 4)
    (color0, color1, bits) = struct.unpack('<HHI', data[:8])
    r0 = (color0 >> 11 & 31) << 3
    g0 = (color0 >> 5 & 63) << 2
    b0 = (color0 & 31) << 3
    r1 = (color1 >> 11 & 31) << 3
    g1 = (color1 >> 5 & 63) << 2
    b1 = (color1 & 31) << 3
    for j in range(4):
        j_offset = j * 4 * 4
        for i in range(4):
            i_offset = i * 4
            control = bits & 3
            bits = bits >> 2
            if control == 0:
                finalColor[j_offset + i_offset + 0] = r0
                finalColor[j_offset + i_offset + 1] = g0
                finalColor[j_offset + i_offset + 2] = b0
                finalColor[j_offset + i_offset + 3] = 255
            elif control == 1:
                finalColor[j_offset + i_offset + 0] = r1
                finalColor[j_offset + i_offset + 1] = g1
                finalColor[j_offset + i_offset + 2] = b1
                finalColor[j_offset + i_offset + 3] = 255
            elif control == 2:
                if color0 > color1:
                    finalColor[j_offset + i_offset + 0] = (2 * r0 + r1) // 3
                    finalColor[j_offset + i_offset + 1] = (2 * g0 + g1) // 3
                    finalColor[j_offset + i_offset + 2] = (2 * b0 + b1) // 3
                    finalColor[j_offset + i_offset + 3] = 255
                else:
                    finalColor[j_offset + i_offset + 0] = (r0 + r1) // 2
                    finalColor[j_offset + i_offset + 1] = (g0 + g1) // 2
                    finalColor[j_offset + i_offset + 2] = (b0 + b1) // 2
                    finalColor[j_offset + i_offset + 3] = 255
            elif control == 3:
                if color0 > color1:
                    finalColor[j_offset + i_offset + 0] = (2 * r1 + r0) // 3
                    finalColor[j_offset + i_offset + 1] = (2 * g1 + g0) // 3
                    finalColor[j_offset + i_offset + 2] = (2 * b1 + b0) // 3
                    finalColor[j_offset + i_offset + 3] = 255
                else:
                    finalColor[j_offset + i_offset + 0] = 0
                    finalColor[j_offset + i_offset + 1] = 0
                    finalColor[j_offset + i_offset + 2] = 0
                    finalColor[j_offset + i_offset + 3] = 0
    return bytes(finalColor)

def decode_dxt3(data):
    finalColor = bytearray(4 * 4 * 4)
    block = data[:16]
    bits = struct.unpack(b'<8B', block[:8])
    (color0, color1) = struct.unpack(b'<HH', block[8:12])
    (code,) = struct.unpack(b'<I', block[12:])
    r0 = (color0 >> 11 & 31) << 3
    g0 = (color0 >> 5 & 63) << 2
    b0 = (color0 & 31) << 3
    r1 = (color1 >> 11 & 31) << 3
    g1 = (color1 >> 5 & 63) << 2
    b1 = (color1 & 31) << 3
    for j in range(4):
        j_offset = j * 4 * 4
        high = False
        for i in range(4):
            i_offset = i * 4
            if high:
                high = False
            else:
                high = True
            alphaCodeIndex = (4 * j + i) // 2
            finalAlpha = bits[alphaCodeIndex]
            if high:
                finalAlpha &= 15
            else:
                finalAlpha >>= 4
            finalAlpha *= 17
            colorCode = code >> 2 * (4 * j + i) & 3
            if colorCode == 0:
                finalColor[j_offset + i_offset + 0] = r0
                finalColor[j_offset + i_offset + 1] = g0
                finalColor[j_offset + i_offset + 2] = b0
            elif colorCode == 1:
                finalColor[j_offset + i_offset + 0] = r1
                finalColor[j_offset + i_offset + 1] = g1
                finalColor[j_offset + i_offset + 2] = b1
            elif colorCode == 2:
                finalColor[j_offset + i_offset + 0] = (2 * r0 + r1) // 3
                finalColor[j_offset + i_offset + 1] = (2 * g0 + g1) // 3
                finalColor[j_offset + i_offset + 2] = (2 * b0 + b1) // 3
            elif colorCode == 3:
                finalColor[j_offset + i_offset + 0] = (r0 + 2 * r1) // 3
                finalColor[j_offset + i_offset + 1] = (g0 + 2 * g1) // 3
                finalColor[j_offset + i_offset + 2] = (b0 + 2 * b1) // 3
            finalColor[j_offset + i_offset + 3] = finalAlpha
    return bytes(finalColor)

def decode_dxt5(data):
    finalColor = bytearray(4 * 4 * 4)
    block = data[:16]
    (alpha0, alpha1) = struct.unpack(b'<BB', block[:2])
    bits = struct.unpack(b'<6B', block[2:8])
    alphaCode1 = bits[2] | bits[3] << 8 | bits[4] << 16 | bits[5] << 24
    alphaCode2 = bits[0] | bits[1] << 8
    (color0, color1) = struct.unpack(b'<HH', block[8:12])
    (code,) = struct.unpack(b'<I', block[12:])
    r0 = (color0 >> 11 & 31) << 3
    g0 = (color0 >> 5 & 63) << 2
    b0 = (color0 & 31) << 3
    r1 = (color1 >> 11 & 31) << 3
    g1 = (color1 >> 5 & 63) << 2
    b1 = (color1 & 31) << 3
    for j in range(4):
        j_offset = j * 4 * 4
        for i in range(4):
            i_offset = i * 4
            alphaCodeIndex = 3 * (4 * j + i)
            if alphaCodeIndex <= 12:
                alphaCode = alphaCode2 >> alphaCodeIndex & 7
            elif alphaCodeIndex == 15:
                alphaCode = alphaCode2 >> 15 | alphaCode1 << 1 & 6
            else:
                alphaCode = alphaCode1 >> alphaCodeIndex - 16 & 7
            if alphaCode == 0:
                finalAlpha = alpha0
            elif alphaCode == 1:
                finalAlpha = alpha1
            elif alpha0 > alpha1:
                finalAlpha = ((8 - alphaCode) * alpha0 + (alphaCode - 1) * alpha1) // 7
            elif alphaCode == 6:
                finalAlpha = 0
            elif alphaCode == 7:
                finalAlpha = 255
            else:
                finalAlpha = ((6 - alphaCode) * alpha0 + (alphaCode - 1) * alpha1) // 5
            colorCode = code >> 2 * (4 * j + i) & 3
            if colorCode == 0:
                finalColor[j_offset + i_offset + 0] = r0
                finalColor[j_offset + i_offset + 1] = g0
                finalColor[j_offset + i_offset + 2] = b0
            elif colorCode == 1:
                finalColor[j_offset + i_offset + 0] = r1
                finalColor[j_offset + i_offset + 1] = g1
                finalColor[j_offset + i_offset + 2] = b1
            elif colorCode == 2:
                finalColor[j_offset + i_offset + 0] = (2 * r0 + r1) // 3
                finalColor[j_offset + i_offset + 1] = (2 * g0 + g1) // 3
                finalColor[j_offset + i_offset + 2] = (2 * b0 + b1) // 3
            elif colorCode == 3:
                finalColor[j_offset + i_offset + 0] = (r0 + 2 * r1) // 3
                finalColor[j_offset + i_offset + 1] = (g0 + 2 * g1) // 3
                finalColor[j_offset + i_offset + 2] = (b0 + 2 * b1) // 3
            finalColor[j_offset + i_offset + 3] = finalAlpha
    return bytes(finalColor)

def decode_block_into_abgr8(f, dwWidth, dwHeight, dxgiFormat):
    if dwWidth % 4 != 0:
        raise Exception('Width is not multiple of 4')
    if dwHeight % 4 != 0:
        raise Exception('Height is not multiple of 4')
    block_size = 8 if dxgiFormat == 71 else 16
    blocks_height = (dwHeight + 3) // 4
    blocks_width = (dwWidth + 3) // 4
    line_pitch = blocks_width * block_size
    size_in_bytes = line_pitch * blocks_height
    in_data = f.read(size_in_bytes)
    if len(in_data) != size_in_bytes:
        raise Exception('Data read incomplete')
    decode_callback = None
    if dxgiFormat == 71:
        decode_callback = decode_dxt1
    elif dxgiFormat == 74:
        decode_callback = decode_dxt3
    elif dxgiFormat == 77:
        decode_callback = decode_dxt5
    elif dxgiFormat == 83:
        decode_callback = decode_bc5
    elif dxgiFormat == 98:
        decode_callback = decode_bc7_block
    else:
        raise Exception('Not supported format ' + str(dxgiFormat))
    pixel_size_in_bytes = 4
    block_width_size_in_bytes = 4 * pixel_size_in_bytes
    single_row_size_in_bytes = blocks_width * block_width_size_in_bytes
    out_data = bytearray(single_row_size_in_bytes * dwHeight)
    for row in range(0, dwHeight, 4):
        offs = row // 4 * line_pitch
        block_line_data = in_data[offs:offs + line_pitch]
        blocks = len(block_line_data) // block_size
        blocks_line_width = blocks * block_size
        for block_offset in range(0, blocks_line_width, block_size):
            block = block_line_data[block_offset:block_offset + block_size]
            decoded = decode_callback(block)
            for i in range(4):
                start_write_offset = block_offset // block_size * block_width_size_in_bytes + (row + i) * single_row_size_in_bytes
                start_read_offset = 4 * 4 * i
                out_data[start_write_offset:start_write_offset + block_width_size_in_bytes] = decoded[start_read_offset:start_read_offset + block_width_size_in_bytes]
    return bytes(out_data)

def decode_l8_into_abgr8(f, dwWidth, dwHeight, dxgiFormat):
    size_in_bytes = dwWidth * dwHeight * 1
    in_data = f.read(size_in_bytes)
    if len(in_data) != size_in_bytes:
        raise Exception('Data read incomplete')
    out_data = bytearray(dwWidth * dwHeight * 4)
    for row in range(dwHeight):
        for col in range(dwWidth):
            out_offset = (row * dwWidth + col) * 4
            in_offset = (row * dwWidth + col) * 1
            (color,) = struct.unpack(b'<B', in_data[in_offset:in_offset + 1])
            out_data[out_offset + 0] = color & 255
            out_data[out_offset + 1] = color & 255
            out_data[out_offset + 2] = color & 255
            out_data[out_offset + 3] = 255
    return bytes(out_data)

def decode_la8_into_abgr8(f, dwWidth, dwHeight, dxgiFormat):
    size_in_bytes = dwWidth * dwHeight * 2
    in_data = f.read(size_in_bytes)
    if len(in_data) != size_in_bytes:
        raise Exception('Data read incomplete')
    out_data = bytearray(dwWidth * dwHeight * 4)
    for row in range(dwHeight):
        for col in range(dwWidth):
            out_offset = (row * dwWidth + col) * 4
            in_offset = (row * dwWidth + col) * 2
            (color,) = struct.unpack(b'<H', in_data[in_offset:in_offset + 2])
            out_data[out_offset + 0] = color >> 8 & 255
            out_data[out_offset + 1] = color >> 8 & 255
            out_data[out_offset + 2] = color >> 8 & 255
            out_data[out_offset + 3] = color >> 0 & 255
    return bytes(out_data)

def decode_rgb565_into_abgr8(f, dwWidth, dwHeight, dxgiFormat):
    size_in_bytes = dwWidth * dwHeight * 2
    in_data = f.read(size_in_bytes)
    if len(in_data) != size_in_bytes:
        raise Exception('Data read incomplete')
    out_data = bytearray(dwWidth * dwHeight * 4)
    for row in range(dwHeight):
        for col in range(dwWidth):
            out_offset = (row * dwWidth + col) * 4
            in_offset = (row * dwWidth + col) * 2
            (color,) = struct.unpack(b'<H', in_data[in_offset:in_offset + 2])
            out_data[out_offset + 0] = (color >> 11 & 31) << 3
            out_data[out_offset + 1] = (color >> 5 & 63) << 2
            out_data[out_offset + 2] = (color & 31) << 3
            out_data[out_offset + 3] = 255
    return bytes(out_data)

def decode_argb4444_into_abgr8(f, dwWidth, dwHeight, dxgiFormat):
    size_in_bytes = dwWidth * dwHeight * 2
    in_data = f.read(size_in_bytes)
    if len(in_data) != size_in_bytes:
        raise Exception('Data read incomplete')
    out_data = bytearray(dwWidth * dwHeight * 4)
    for row in range(dwHeight):
        for col in range(dwWidth):
            out_offset = (row * dwWidth + col) * 4
            in_offset = (row * dwWidth + col) * 2
            (color,) = struct.unpack(b'<H', in_data[in_offset:in_offset + 2])
            out_data[out_offset + 0] = (color >> 8 & 15) * 17
            out_data[out_offset + 1] = (color >> 4 & 15) * 17
            out_data[out_offset + 2] = (color >> 0 & 15) * 17
            out_data[out_offset + 3] = (color >> 12 & 15) * 17
    return bytes(out_data)

def decode_rgba8_into_abgr8(f, dwWidth, dwHeight, dxgiFormat):
    size_in_bytes = dwWidth * dwHeight * 4
    in_data = f.read(size_in_bytes)
    if len(in_data) != size_in_bytes:
        raise Exception('Data read incomplete')
    out_data = bytearray(dwWidth * dwHeight * 4)
    for row in range(dwHeight):
        for col in range(dwWidth):
            out_offset = (row * dwWidth + col) * 4
            in_offset = out_offset
            (color,) = struct.unpack(b'<I', in_data[in_offset:in_offset + 4])
            out_data[out_offset + 0] = color >> 0 & 255
            out_data[out_offset + 1] = color >> 8 & 255
            out_data[out_offset + 2] = color >> 16 & 255
            out_data[out_offset + 3] = color >> 24 & 255
    return bytes(out_data)

def decode_argb8_into_agbr8(f, dwWidth, dwHeight, dxgiFormat):
    size_in_bytes = dwWidth * dwHeight * 4
    in_data = f.read(size_in_bytes)
    if len(in_data) != size_in_bytes:
        raise Exception('Data read incomplete')
    out_data = bytearray(dwWidth * dwHeight * 4)
    for row in range(dwHeight):
        for col in range(dwWidth):
            out_offset = (row * dwWidth + col) * 4
            in_offset = out_offset
            (color,) = struct.unpack(b'<I', in_data[in_offset:in_offset + 4])
            out_data[out_offset + 0] = color >> 16 & 255
            out_data[out_offset + 1] = color >> 8 & 255
            out_data[out_offset + 2] = color >> 0 & 255
            out_data[out_offset + 3] = color >> 24 & 255
    return bytes(out_data)

def get_dds_header(fmt, width, height, mipmap_levels, is_cube_map):
    dwMagic = b'DDS '
    dwSize = 124
    dwFlags = 1 | 2 | 4 | 4096
    dwHeight = height
    dwWidth = width
    dwPitchOrLinearSize = 0
    dwDepth = 0
    dwMipMapCount = 0
    ddspf_dwSize = 32
    ddspf_dwFlags = 0
    ddspf_dwFourCC = b''
    ddspf_dwRGBBitCount = 0
    ddspf_dwRBitMask = 0
    ddspf_dwGBitMask = 0
    ddspf_dwBBitMask = 0
    ddspf_dwABitMask = 0
    dwCaps = 4096
    dwCaps2 = 0
    dwCaps3 = 0
    dwCaps4 = 0
    dxgiFormat = 0
    resourceDimension = 3
    miscFlag = 0
    arraySize = 1
    miscFlags2 = 0
    if True:
        if fmt == 'LA8':
            (ddspf_dwRBitMask, ddspf_dwGBitMask, ddspf_dwBBitMask, ddspf_dwABitMask) = (255, 255, 255, 65280)
            dwFlags |= 8
        elif fmt == 'L8':
            (ddspf_dwRBitMask, ddspf_dwGBitMask, ddspf_dwBBitMask, ddspf_dwABitMask) = (255, 255, 255, 0)
            dwFlags |= 8
        elif fmt == 'ARGB8' or fmt == 'ARGB8_SRGB':
            (ddspf_dwRBitMask, ddspf_dwGBitMask, ddspf_dwBBitMask, ddspf_dwABitMask) = (16711680, 65280, 255, 4278190080)
            dwFlags |= 8
        elif fmt == 'RGBA8':
            (ddspf_dwRBitMask, ddspf_dwGBitMask, ddspf_dwBBitMask, ddspf_dwABitMask) = (255, 65280, 16711680, 4278190080)
            dwFlags |= 8
        elif fmt == 'RGB565':
            (ddspf_dwRBitMask, ddspf_dwGBitMask, ddspf_dwBBitMask, ddspf_dwABitMask) = (63488, 2016, 31, 0)
            dwFlags |= 8
        elif fmt == 'ARGB4444':
            (ddspf_dwRBitMask, ddspf_dwGBitMask, ddspf_dwBBitMask, ddspf_dwABitMask) = (3840, 240, 15, 61440)
            dwFlags |= 8
        elif fmt == 'BC5':
            dwFlags |= 524288
            dxgiFormat = 83
        elif fmt == 'BC7':
            dwFlags |= 524288
            dxgiFormat = 98
        elif fmt == 'DXT1':
            dwFlags |= 524288
        elif fmt == 'DXT3':
            dwFlags |= 524288
        elif fmt == 'DXT5':
            dwFlags |= 524288
    if dwFlags & 8 != 0:
        ddspf_dwFlags = 64
        if ddspf_dwABitMask != 0:
            ddspf_dwFlags |= 1
        all_bit_mask = ddspf_dwRBitMask | ddspf_dwGBitMask | ddspf_dwBBitMask | ddspf_dwABitMask
        if all_bit_mask & 4278190080 != 0:
            ddspf_dwRGBBitCount = 32
        elif all_bit_mask & 16711680 != 0:
            ddspf_dwRGBBitCount = 24
        elif all_bit_mask & 65280 != 0:
            ddspf_dwRGBBitCount = 16
        elif all_bit_mask & 255 != 0:
            ddspf_dwRGBBitCount = 8
        dwPitchOrLinearSize = (width * ddspf_dwRGBBitCount + 7) // 8
    if dwFlags & 524288 != 0:
        ddspf_dwFlags = 4
        if dxgiFormat != 0:
            ddspf_dwFourCC = b'DX10'
        else:
            ddspf_dwFourCC = fmt.encode('ASCII')
        dwPitchOrLinearSize = (width + 3) // 4 * (8 if fmt == 'DXT1' else 16)
    if mipmap_levels != None:
        dwFlags |= 131072
        dwMipMapCount = mipmap_levels
        dwCaps |= 4194304
    if mipmap_levels != None or is_cube_map:
        dwCaps |= 8
    if is_cube_map:
        dwCaps2 = 512 | 1024 | 2048 | 4096 | 8192 | 16384 | 32768
    if ddspf_dwFourCC == b'DX10':
        return struct.pack('<4s20I4s10I5I', dwMagic, dwSize, dwFlags, dwHeight, dwWidth, dwPitchOrLinearSize, dwDepth, dwMipMapCount, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ddspf_dwSize, ddspf_dwFlags, ddspf_dwFourCC, ddspf_dwRGBBitCount, ddspf_dwRBitMask, ddspf_dwGBitMask, ddspf_dwBBitMask, ddspf_dwABitMask, dwCaps, dwCaps2, dwCaps3, dwCaps4, 0, dxgiFormat, resourceDimension, miscFlag, arraySize, miscFlags2)
    else:
        return struct.pack('<4s20I4s10I', dwMagic, dwSize, dwFlags, dwHeight, dwWidth, dwPitchOrLinearSize, dwDepth, dwMipMapCount, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ddspf_dwSize, ddspf_dwFlags, ddspf_dwFourCC, ddspf_dwRGBBitCount, ddspf_dwRBitMask, ddspf_dwGBitMask, ddspf_dwBBitMask, ddspf_dwABitMask, dwCaps, dwCaps2, dwCaps3, dwCaps4, 0)

def uncompress_nislzss(src, decompressed_size, compressed_size):
    des = int.from_bytes(src.read(4), byteorder='little')
    if des != decompressed_size:
        des = des if des > decompressed_size else decompressed_size
    cms = int.from_bytes(src.read(4), byteorder='little')
    if cms != compressed_size and compressed_size - cms != 4:
        raise Exception("compression size in header and stream don't match")
    num3 = int.from_bytes(src.read(4), byteorder='little')
    fin = src.tell() + cms - 13
    cd = bytearray(des)
    num4 = 0
    while src.tell() <= fin:
        b = src.read(1)[0]
        if b == num3:
            b2 = src.read(1)[0]
            if b2 != num3:
                if b2 >= num3:
                    b2 -= 1
                b3 = src.read(1)[0]
                if b2 < b3:
                    for _ in range(b3):
                        cd[num4] = cd[num4 - b2]
                        num4 += 1
                else:
                    sliding_window_pos = num4 - b2
                    cd[num4:num4 + b3] = cd[sliding_window_pos:sliding_window_pos + b3]
                    num4 += b3
            else:
                cd[num4] = b2
                num4 += 1
        else:
            cd[num4] = b
            num4 += 1
    return cd

def uncompress_lz4(src, decompressed_size, compressed_size):
    dst = bytearray(decompressed_size)
    min_match_len = 4
    num4 = 0
    fin = src.tell() + compressed_size

    def get_length(src, length):
        if length != 15:
            return length
        while True:
            read_buf = src.read(1)
            if len(read_buf) != 1:
                raise Exception('EOF at length read')
            len_part = read_buf[0]
            length += len_part
            if len_part != 255:
                break
        return length
    while src.tell() <= fin:
        read_buf = src.read(1)
        if not read_buf:
            raise Exception('EOF at reading literal-len')
        token = read_buf[0]
        literal_len = get_length(src, token >> 4 & 15)
        read_buf = src.read(literal_len)
        if len(read_buf) != literal_len:
            raise Exception('not literal data')
        dst[num4:num4 + literal_len] = read_buf[:literal_len]
        num4 += literal_len
        read_buf = src.read(2)
        if not read_buf or src.tell() > fin:
            if token & 15 != 0:
                raise Exception('EOF, but match-len > 0: %u' % (token % 15,))
            break
        if len(read_buf) != 2:
            raise Exception('premature EOF')
        offset = read_buf[0] | read_buf[1] << 8
        if offset == 0:
            raise Exception("offset can't be 0")
        match_len = get_length(src, token >> 0 & 15)
        match_len += min_match_len
        if offset < match_len:
            for _ in range(match_len):
                dst[num4] = dst[num4 - offset]
                num4 += 1
        else:
            sliding_window_pos = num4 - offset
            dst[num4:num4 + match_len] = dst[sliding_window_pos:sliding_window_pos + match_len]
            num4 += match_len
    return dst

def uncompress_zstd(src, decompressed_size, compressed_size):
    dctx = zstandard.ZstdDecompressor()
    uncompressed = dctx.decompress(src.read(compressed_size), max_output_size=decompressed_size)
    return uncompressed
NOEPY_HEADER_BE = 1381582928
NOEPY_HEADER_LE = 1346918738
GCM_PLATFORM = 1195592960
GXM_PLATFORM = 1196969217
GNM_PLATFORM = 1196313858
DX11_PLATFORM = 1146630449

def get_type(id_, type_strings, class_descriptors):
    total_types = len(type_strings) + 1
    if id_ < total_types:
        return type_strings[id_]
    else:
        id_ -= total_types
        return class_descriptors[id_].name

def get_class_from_type(id_, type_strings):
    total_types = len(type_strings) + 1
    if id_ < total_types:
        return None
    else:
        return id_ - total_types + 1

def get_reference_from_class_descriptor_index(cluster_info, class_name, index):
    if class_name in cluster_info.list_for_class_descriptors and len(cluster_info.list_for_class_descriptors[class_name]) > index:
        return cluster_info.list_for_class_descriptors[class_name][index].split('#', 1)
    return None

def get_class_name(cluster_info, id_):
    return cluster_info.class_descriptors[id_ - 1].name

def get_class_size(cluster_info, id_):
    return cluster_info.class_descriptors[id_ - 1].get_size_in_bytes()

def get_member_id_to_pointer_info(g, class_descriptor, cluster_info, pointer_fixup_count, class_element):
    member_id_to_pointer_info = {}
    for m in range(class_descriptor.class_data_member_count):
        member_id = class_descriptor.member_offset + m
        data_member = cluster_info.data_members[member_id]
        value_offset = data_member.value_offset
        member_id_to_pointer_info[member_id] = []
        for b in range(pointer_fixup_count):
            pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
            if pointer_info.source_object_id == class_element:
                if (pointer_info.som == value_offset + 4 or pointer_info.som + 4 == value_offset or pointer_info.som == value_offset) and (not pointer_info.is_class_data_member()) or (pointer_info.som == member_id and pointer_info.is_class_data_member()):
                    member_id_to_pointer_info[member_id].append(pointer_info)
    return member_id_to_pointer_info

def map_object_member_from_value_offset_recursive(cluster_info, class_id, offset_from_parent, object_value_offset_to_member_id, object_member_to_fixup_map):
    class_descriptor = cluster_info.class_descriptors[class_id - 1]
    for m in range(class_descriptor.class_data_member_count):
        member_id = class_descriptor.member_offset + m
        data_member = cluster_info.data_members[member_id]
        value_offset = offset_from_parent + data_member.value_offset
        object_value_offset_to_member_id[value_offset] = member_id
        for i in object_member_to_fixup_map:
            if member_id not in object_member_to_fixup_map[i]:
                object_member_to_fixup_map[i][member_id] = []
    if class_descriptor.super_class_id > 0:
        map_object_member_from_value_offset_recursive(cluster_info, class_descriptor.super_class_id, offset_from_parent, object_value_offset_to_member_id, object_member_to_fixup_map)

def get_object_member_pointer_info_map(cluster_info, cluster_instance_list_header):
    if cluster_instance_list_header.class_id <= 0:
        return {}
    object_member_to_fixup_map = {}
    for i in range(cluster_instance_list_header.count):
        object_member_to_fixup_map[i] = {}
    object_value_offset_to_member_id = {}
    map_object_member_from_value_offset_recursive(cluster_info, cluster_instance_list_header.class_id, 0, object_value_offset_to_member_id, object_member_to_fixup_map)
    object_value_offset_to_member_id_sorted_keys = sorted(object_value_offset_to_member_id.keys())
    class_size_one = get_class_size(cluster_info, cluster_instance_list_header.class_id)
    class_size_total = class_size_one * cluster_instance_list_header.count
    for b in range(cluster_instance_list_header.pointer_fixup_count):
        pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
        if not pointer_info.source_object_id in object_member_to_fixup_map:
            object_member_to_fixup_map[pointer_info.source_object_id] = {}
        obj_source_object_id = object_member_to_fixup_map[pointer_info.source_object_id]
        member_id = None
        if pointer_info.is_class_data_member():
            member_id = pointer_info.som
        elif not pointer_info.is_class_data_member():
            for x in object_value_offset_to_member_id_sorted_keys:
                if x > pointer_info.som:
                    break
                member_id = object_value_offset_to_member_id[x]
        if member_id != None:
            if not member_id in obj_source_object_id:
                obj_source_object_id[member_id] = []
            obj_source_object_id[member_id].append(pointer_info)
    return object_member_to_fixup_map

def get_object_member_array_info_map(cluster_info, cluster_instance_list_header):
    if cluster_instance_list_header.class_id <= 0:
        return {}
    object_member_to_fixup_map = {}
    for i in range(cluster_instance_list_header.count):
        object_member_to_fixup_map[i] = {}
    object_value_offset_to_member_id = {}
    map_object_member_from_value_offset_recursive(cluster_info, cluster_instance_list_header.class_id, 0, object_value_offset_to_member_id, object_member_to_fixup_map)
    object_value_offset_to_member_id_sorted_keys = sorted(object_value_offset_to_member_id.keys())
    class_size_one = get_class_size(cluster_info, cluster_instance_list_header.class_id)
    class_size_total = class_size_one * cluster_instance_list_header.count
    for b in range(cluster_instance_list_header.array_fixup_count):
        array_info = cluster_info.array_info[b + cluster_info.array_fixup_offset]
        if not array_info.source_object_id in object_member_to_fixup_map:
            object_member_to_fixup_map[array_info.source_object_id] = {}
        obj_source_object_id = object_member_to_fixup_map[array_info.source_object_id]
        member_id = None
        if array_info.is_class_data_member():
            member_id = array_info.som
        elif not array_info.is_class_data_member():
            for x in object_value_offset_to_member_id_sorted_keys:
                if x > array_info.som:
                    break
                member_id = object_value_offset_to_member_id[x]
        if member_id != None:
            if not member_id in obj_source_object_id:
                obj_source_object_id[member_id] = []
            if array_info not in obj_source_object_id[member_id]:
                obj_source_object_id[member_id].append(array_info)
        if array_info.is_class_data_member():
            member_id = array_info.som
        elif not array_info.is_class_data_member():
            for x in object_value_offset_to_member_id_sorted_keys:
                if x > array_info.som + 4:
                    break
                member_id = object_value_offset_to_member_id[x]
        if member_id != None:
            if not member_id in obj_source_object_id:
                obj_source_object_id[member_id] = []
            if array_info not in obj_source_object_id[member_id]:
                obj_source_object_id[member_id].append(array_info)
    return object_member_to_fixup_map
pythonStructTypeToDataSizeMapping = {'c': 1, 'b': 1, 'B': 1, '?': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4, 'l': 4, 'L': 4, 'q': 8, 'Q': 8, 'e': 2, 'f': 4, 'd': 8}
clusterPrimitiveToPythonStructTypeMapping = {'PUInt8': 'B', 'PInt8': 'b', 'PUInt16': 'H', 'PInt16': 'h', 'PUInt32': 'I', 'PInt32': 'i', 'PUInt64': 'Q', 'PInt64': 'q', 'float': 'f'}

def process_data_members(g, cluster_info, id_, member_location, array_location, class_element, cluster_mesh_info, class_name, should_print_class, dict_data, cluster_header, data_instances_by_class, offset_from_parent, array_fixup_count, pointer_fixup_count, object_member_pointer_info_map, object_member_array_info_map, root_member_id):
    if id_ > 0:
        class_id = id_ - 1
        class_descriptor = cluster_info.class_descriptors[class_id]
        member_id_to_pointer_info = {}
        if object_member_pointer_info_map != None and class_element in object_member_pointer_info_map:
            member_id_to_pointer_info = object_member_pointer_info_map[class_element]
        else:
            member_id_to_pointer_info = get_member_id_to_pointer_info(g, class_descriptor, cluster_info, pointer_fixup_count, class_element)
        member_id_to_array_info = {}
        if object_member_array_info_map != None and class_element in object_member_array_info_map:
            member_id_to_array_info = object_member_array_info_map[class_element]
        for m in range(class_descriptor.class_data_member_count):
            member_id = class_descriptor.member_offset + m
            data_member = cluster_info.data_members[member_id]
            info_for_id = member_id
            if root_member_id != None:
                info_for_id = root_member_id
            pointer_infos = []
            if info_for_id in member_id_to_pointer_info:
                pointer_infos = member_id_to_pointer_info[info_for_id]
            array_infos = []
            if info_for_id in member_id_to_array_info:
                array_infos = member_id_to_array_info[info_for_id]
            type_id = data_member.type_id
            variable_text = data_member.name
            type_text = get_type(type_id, cluster_info.type_strings, cluster_info.class_descriptors)
            class_type_id = get_class_from_type(type_id, cluster_info.type_strings)
            val = None
            value_offset = data_member.value_offset
            data_offset = member_location + value_offset
            expected_offset = data_member.fixed_array_size
            if expected_offset == 0:
                expected_offset = 1
            expected_size = data_member.size_in_bytes * expected_offset
            g.seek(data_offset)
            if data_instances_by_class != None:
                if type_text in clusterPrimitiveToPythonStructTypeMapping and (class_name.startswith('PArray<') or class_name.startswith('PSharray<')) and (variable_text in ['m_els', 'm_u']):
                    datatype_pystructtype = clusterPrimitiveToPythonStructTypeMapping[type_text]
                    datatype_size_single = pythonStructTypeToDataSizeMapping[datatype_pystructtype]
                    val = []
                    if 'm_count' in dict_data:
                        array_count = dict_data['m_count']
                        for array_info in array_infos:
                            if array_info.som == offset_from_parent + value_offset or array_info.som == offset_from_parent + value_offset + 4:
                                old_position = g.tell()
                                if array_info.count != array_count and array_count >= 65535:
                                    array_count = 0
                                g.seek(array_location + array_info.offset)
                                val = bytearray(g.read(array_count * datatype_size_single))
                                if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                                    bytearray_byteswap(val, datatype_size_single)
                                val = cast_memoryview(memoryview(val), datatype_pystructtype)
                                g.seek(old_position)
                                break
                elif type_text[0:7] == 'PArray<' and type_text[-1:] == '>' and (type(dict_data[variable_text]) == dict) and (type_text not in ['PArray<PUInt32>', 'PArray<PInt32>', 'PArray<float>', 'PArray<PUInt8>', 'PArray<PUInt8,4>']):
                    array_count = dict_data[variable_text]['m_count']
                    current_count = 0
                    type_value = type_text[7:-1]
                    is_pointer = False
                    if not type_value in data_instances_by_class:
                        if type_value[0:10] == 'PDataBlock':
                            type_value = type_value[0:10]
                        if type_value[-2:] == ' *':
                            type_value = type_value[:-2]
                            is_pointer = True
                    arr = None
                    if array_count == 0:
                        arr = []
                    elif type_value in data_instances_by_class:
                        for pointer_info in pointer_infos:
                            if (is_pointer == True or (is_pointer == False and pointer_info.som == value_offset + 4)) and (not pointer_info.is_class_data_member()) and (len(cluster_info.classes_strings) > pointer_info.destination_object.object_list) and (cluster_info.classes_strings[pointer_info.destination_object.object_list] == type_value) and (pointer_info.destination_object.object_list in data_instances_by_class):
                                data_instances_by_class_this = data_instances_by_class[pointer_info.destination_object.object_list]
                                if is_pointer == True:
                                    if current_count == 0:
                                        arr = [None] * array_count
                                    offset_calculation = pointer_info.destination_object.object_id
                                    if len(data_instances_by_class_this) > offset_calculation:
                                        arr[pointer_info.array_index] = data_instances_by_class_this[offset_calculation]
                                    current_count += 1
                                else:
                                    arr = [data_instances_by_class_this[pointer_info.destination_object.object_id + i] for i in range(pointer_info.array_index)]
                    else:
                        for pointer_info in pointer_infos:
                            if pointer_info.som == value_offset + 4 and (not pointer_info.is_class_data_member()):
                                user_fix_id = pointer_info.user_fixup_id
                                if user_fix_id != None and user_fix_id < len(cluster_info.user_fixes) and (type(cluster_info.user_fixes[user_fix_id].data) == str):
                                    if current_count == 0:
                                        arr = [None] * array_count
                                    arr[pointer_info.array_index] = cluster_info.user_fixes[user_fix_id].data
                                    current_count += 1
                    val = {'m_els': arr, 'm_count': array_count}
                    if type_value in ['PShaderParameterDefinition'] and arr != None:
                        shader_object_dict = {}
                        for pointer_info in pointer_infos:
                            if not pointer_info.is_class_data_member():
                                for x in range(len(arr)):
                                    value_this = arr[x]
                                    pointer_info_offset_needed = pointer_info.som
                                    if value_this['m_parameterType'] == 71:
                                        pointer_info_offset_needed -= 8
                                        if value_this['m_bufferLoc']['m_offset'] == pointer_info_offset_needed:
                                            if len(cluster_info.classes_strings) > pointer_info.destination_object.object_list and pointer_info.destination_object.object_list in data_instances_by_class:
                                                shader_object_dict[value_this['m_name']] = data_instances_by_class[pointer_info.destination_object.object_list][pointer_info.destination_object.object_id]
                                    elif value_this['m_parameterType'] == 66 or value_this['m_parameterType'] == 68:
                                        if value_this['m_bufferLoc']['m_size'] == 24:
                                            pointer_info_offset_needed -= 16
                                        else:
                                            pointer_info_offset_needed -= 12
                                        if value_this['m_bufferLoc']['m_offset'] == pointer_info_offset_needed:
                                            user_fix_id = pointer_info.user_fixup_id
                                            if user_fix_id != None and user_fix_id < len(cluster_info.user_fixes) and ('PAssetReferenceImport' in data_instances_by_class) and (type(cluster_info.user_fixes[user_fix_id].data) == int) and (cluster_info.user_fixes[user_fix_id].data < len(data_instances_by_class['PAssetReferenceImport'])):
                                                shader_object_dict[value_this['m_name']] = data_instances_by_class['PAssetReferenceImport'][cluster_info.user_fixes[user_fix_id].data]
                        dict_data['mu_tweakableShaderParameterDefinitionsObjectReferences'] = shader_object_dict
                elif (class_name[0:9] == 'PSharray<' and class_name[-1:] == '>') and variable_text == 'm_u' and (type_text not in ['PSharray<PUInt32>', 'PSharray<PInt32>', 'PSharray<float>', 'PSharray<PUInt8>']):
                    array_count = dict_data['m_count']
                    current_count = 0
                    val = [None] * array_count
                    for b in range(pointer_fixup_count):
                        if current_count >= array_count:
                            break
                        pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
                        if pointer_info.source_object_id == class_element and pointer_info.som == offset_from_parent + 4 and (not pointer_info.is_class_data_member()) and (pointer_info.destination_object.object_list in data_instances_by_class):
                            offset_calculation = pointer_info.destination_object.object_id
                            data_instances_by_class_this = data_instances_by_class[pointer_info.destination_object.object_list]
                            if len(data_instances_by_class_this) > offset_calculation:
                                val[pointer_info.array_index] = data_instances_by_class_this[offset_calculation]
                            current_count += 1
                elif type_text in data_instances_by_class or type_text in ['PBase']:
                    for pointer_info in pointer_infos:
                        if pointer_info.is_class_data_member():
                            user_fix_id = pointer_info.user_fixup_id
                            object_id = pointer_info.destination_object.object_id
                            object_list = pointer_info.destination_object.object_list
                            if object_list in data_instances_by_class:
                                data_instances_by_class_this = data_instances_by_class[object_list]
                                if len(data_instances_by_class_this) > object_id:
                                    val = data_instances_by_class_this[object_id]
                                    break
                elif type_text in cluster_info.import_classes_strings:
                    for pointer_info in pointer_infos:
                        if pointer_info.is_class_data_member():
                            user_fix_id = pointer_info.user_fixup_id
                            if user_fix_id != None and user_fix_id < len(cluster_info.user_fixes) and ('PAssetReferenceImport' in data_instances_by_class) and (type(cluster_info.user_fixes[user_fix_id].data) == int) and (cluster_info.user_fixes[user_fix_id].data < len(data_instances_by_class['PAssetReferenceImport'])):
                                val = data_instances_by_class['PAssetReferenceImport'][cluster_info.user_fixes[user_fix_id].data]
                                break
                elif class_type_id != None and type(dict_data[variable_text]) == dict and (cluster_info.class_descriptors[class_type_id - 1].get_size_in_bytes() * (1 if data_member.fixed_array_size == 0 else data_member.fixed_array_size) == expected_size):
                    if data_member.fixed_array_size > 0:
                        val = dict_data[variable_text]
                        structsize = cluster_info.class_descriptors[class_type_id - 1].get_size_in_bytes()
                        for i in range(data_member.fixed_array_size):
                            val2 = val[i]
                            process_data_members(g, cluster_info, class_type_id, data_offset + structsize * i, array_location, class_element, cluster_mesh_info, type_text, should_print_class, val2, cluster_header, data_instances_by_class, offset_from_parent + value_offset + structsize * i, array_fixup_count, pointer_fixup_count, object_member_pointer_info_map, object_member_array_info_map, member_id)
                    else:
                        val = dict_data[variable_text]
                        process_data_members(g, cluster_info, class_type_id, data_offset, array_location, class_element, cluster_mesh_info, type_text, should_print_class, val, cluster_header, data_instances_by_class, offset_from_parent + value_offset, array_fixup_count, pointer_fixup_count, object_member_pointer_info_map, object_member_array_info_map, member_id)
            elif type_text in clusterPrimitiveToPythonStructTypeMapping:
                datatype_pystructtype = clusterPrimitiveToPythonStructTypeMapping[type_text]
                datatype_size_single = pythonStructTypeToDataSizeMapping[datatype_pystructtype]
                if (class_name.startswith('PArray<') or class_name.startswith('PSharray<')) and variable_text in ['m_els', 'm_u']:
                    val = []
                elif data_member.fixed_array_size != 0:
                    val = bytearray(g.read(data_member.fixed_array_size * datatype_size_single))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        bytearray_byteswap(val, datatype_size_single)
                    val = cast_memoryview(memoryview(val), datatype_pystructtype)
                elif type_text in ['float']:
                    ba = bytearray(g.read(datatype_size_single))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        bytearray_byteswap(ba, datatype_size_single)
                    val = cast_memoryview(memoryview(ba), datatype_pystructtype)[0]
                else:
                    val = read_integer(g, datatype_size_single, type_text.startswith('PU'), '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text in ['bool']:
                val = read_integer(g, 1, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<') > 0
            elif type_text in ['PChar']:
                val = ''
                for array_info in array_infos:
                    if True:
                        old_position = g.tell()
                        g.seek(array_location + array_info.offset)
                        try:
                            val = read_null_ending_string(g)
                        except:
                            val = ''
                        g.seek(old_position)
                        break
                if expected_size == 4:
                    g.seek(4, io.SEEK_CUR)
                elif expected_size == 1:
                    g.seek(1, io.SEEK_CUR)
            elif type_text in ['PString'] and class_name in ['PNode']:
                val = ''
                for array_info in array_infos:
                    if array_info.som + 4 == value_offset or array_info.som == value_offset:
                        old_position = g.tell()
                        g.seek(array_location + array_info.offset)
                        try:
                            val = read_null_ending_string(g)
                        except:
                            val = ''
                        g.seek(old_position)
                        break
                if expected_size == 4:
                    g.seek(4, io.SEEK_CUR)
                elif expected_size == 1:
                    g.seek(1, io.SEEK_CUR)
            elif type_text in ['PString']:
                val = ''
                for array_info in array_infos:
                    if array_info.som == value_offset:
                        old_position = g.tell()
                        g.seek(array_location + array_info.offset)
                        try:
                            val = read_null_ending_string(g)
                        except:
                            val = ''
                        g.seek(old_position)
                        break
                if expected_size == 4:
                    g.seek(4, io.SEEK_CUR)
                elif expected_size == 1:
                    g.seek(1, io.SEEK_CUR)
            elif type_text in ['PTextureStateGNM']:
                val = g.read(expected_size)
            elif type_text in ['PCgParameterInfoGCM', 'PCgCodebookGCM', 'PCgBindingParameterInfoGXM', 'PCgBindingSceneConstantsGXM']:
                val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text in ['Vector4'] and expected_size == 4:
                val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text in ['PLightType', 'PRenderDataType', 'PAnimationKeyDataType', 'PTextureFormatBase', 'PSceneRenderPassType']:
                val = None
                for pointer_info in pointer_infos:
                    if pointer_info.is_class_data_member():
                        user_fix_id = pointer_info.user_fixup_id
                        if user_fix_id != None and user_fix_id < len(cluster_info.user_fixes):
                            val = cluster_info.user_fixes[user_fix_id].data
                        else:
                            val = pointer_info.destination_object.object_list
            elif type_text in ['PClassDescriptor']:
                val = None
                for pointer_info in pointer_infos:
                    if pointer_info.is_class_data_member():
                        user_fix_id = pointer_info.user_fixup_id
                        if user_fix_id != None and user_fix_id < len(cluster_info.user_fixes):
                            val = cluster_info.user_fixes[user_fix_id].data
                        else:
                            val = pointer_info.destination_object.object_list
                        break
            elif class_type_id != None and (cluster_info.class_descriptors[class_type_id - 1].get_size_in_bytes() * (1 if data_member.fixed_array_size == 0 else data_member.fixed_array_size) == expected_size or (type_text[0:7] == 'PArray<' and type_text[-1:] == '>') or (type_text[0:9] == 'PSharray<' and type_text[-1:] == '>')):
                if data_member.fixed_array_size > 0:
                    val = []
                    structsize = cluster_info.class_descriptors[class_type_id - 1].get_size_in_bytes()
                    for i in range(data_member.fixed_array_size):
                        val2 = {}
                        process_data_members(g, cluster_info, class_type_id, data_offset + structsize * i, array_location, class_element, cluster_mesh_info, type_text, should_print_class, val2, cluster_header, data_instances_by_class, offset_from_parent + value_offset + structsize * i, array_fixup_count, pointer_fixup_count, object_member_pointer_info_map, object_member_array_info_map, member_id)
                        val.append(val2)
                else:
                    val = {}
                    process_data_members(g, cluster_info, class_type_id, data_offset, array_location, class_element, cluster_mesh_info, type_text, should_print_class, val, cluster_header, data_instances_by_class, offset_from_parent + value_offset, array_fixup_count, pointer_fixup_count, object_member_pointer_info_map, object_member_array_info_map, member_id)
            if data_instances_by_class != None and val != None or data_instances_by_class == None:
                dict_data[variable_text] = val
        process_data_members(g, cluster_info, class_descriptor.super_class_id, member_location, array_location, class_element, cluster_mesh_info, class_name, should_print_class, dict_data, cluster_header, data_instances_by_class, offset_from_parent, array_fixup_count, pointer_fixup_count, object_member_pointer_info_map, object_member_array_info_map, None)
cluster_classes_to_handle = ['PAnimationChannel', 'PAnimationChannelTimes', 'PAnimationClip', 'PAnimationConstantChannel', 'PAnimationSet', 'PAssetReference', 'PAssetReferenceImport', 'PCgParameterInfoGCM', 'PContextVariantFoldingTable', 'PDataBlock', 'PDataBlockD3D11', 'PDataBlockGCM', 'PDataBlockGNM', 'PDataBlockGXM', 'PEffect', 'PEffectVariant', 'PLight', 'PLocator', 'PMaterial', 'PMaterialSwitch', 'PMatrix4', 'PMesh', 'PMeshInstance', 'PMeshInstanceBounds', 'PMeshInstanceSegmentContext', 'PMeshInstanceSegmentStreamBinding', 'PMeshSegment', 'PNode', 'PNodeContext', 'PParameterBuffer', 'PPhysicsMaterial', 'PPhysicsMesh', 'PPhysicsModel', 'PPhysicsRigidBody', 'PSamplerState', 'PSceneRenderPass', 'PShader', 'PShaderComputeProgram', 'PShaderFragmentProgram', 'PShaderGeometryProgram', 'PShaderParameterCaptureBufferLocation', 'PShaderParameterCaptureBufferLocationTypeConstantBuffer', 'PShaderParameterDefinition', 'PShaderPass', 'PShaderPassInfo', 'PShaderStreamDefinition', 'PShaderVertexProgram', 'PShape', 'PSkeletonJointBounds', 'PSkinBoneRemap', 'PString', 'PTexture2D', 'PTextureCubeMap', 'PVertexStream', 'PWorldMatrix']

def process_cluster_instance_list_header(cluster_instance_list_header, g, count_list, cluster_info, cluster_mesh_info, cluster_header, filename, data_instances_by_class):
    member_location = g.tell()
    array_location = g.tell() + cluster_instance_list_header.objects_size
    should_print_class = ''
    class_name = get_class_name(cluster_info, cluster_instance_list_header.class_id)
    class_size = get_class_size(cluster_info, cluster_instance_list_header.class_id)
    should_print_class = class_name == should_print_class
    should_handle_class = should_print_class or class_name in cluster_classes_to_handle
    data_instances = None
    if data_instances_by_class == None:
        cluster_info.classes_strings.append(class_name)
        data_instances = []
    elif count_list in data_instances_by_class:
        data_instances = data_instances_by_class[count_list]
    else:
        should_handle_class = False
    if should_handle_class:
        object_member_pointer_info_map = get_object_member_pointer_info_map(cluster_info, cluster_instance_list_header)
        object_member_array_info_map = get_object_member_array_info_map(cluster_info, cluster_instance_list_header)
        for i in range(cluster_instance_list_header.count):
            dict_data = None
            if data_instances_by_class == None:
                dict_data = {}
                data_instances.append(dict_data)
            else:
                dict_data = data_instances[i]
            g.seek(member_location)
            process_data_members(g, cluster_info, cluster_instance_list_header.class_id, member_location, array_location, i, cluster_mesh_info, class_name, should_print_class, dict_data, cluster_header, data_instances_by_class, 0, cluster_instance_list_header.array_fixup_count, cluster_instance_list_header.pointer_fixup_count, object_member_pointer_info_map, object_member_array_info_map, None)
            if data_instances_by_class == None:
                dict_data['mu_memberLoc'] = member_location
                dict_data['mu_memberClass'] = class_name
            else:
                reference_from_class_descriptor_index = get_reference_from_class_descriptor_index(cluster_info, class_name, i)
                if reference_from_class_descriptor_index != None and len(list(reference_from_class_descriptor_index)) > 1:
                    dict_data['mu_name'] = reference_from_class_descriptor_index[1]
            member_location += class_size
    cluster_info.pointer_array_fixup_offset += cluster_instance_list_header.pointer_array_fixup_count
    cluster_info.pointer_fixup_offset += cluster_instance_list_header.pointer_fixup_count
    cluster_info.array_fixup_offset += cluster_instance_list_header.array_fixup_count
    if data_instances_by_class != None:
        return None
    if class_name == 'PAssetReference':
        for v in data_instances:
            if not v['m_assetType'] in cluster_info.list_for_class_descriptors:
                cluster_info.list_for_class_descriptors[v['m_assetType']] = []
            cluster_info.list_for_class_descriptors[v['m_assetType']].append(v['m_id'])
    if class_name == 'PAssetReferenceImport':
        for v in data_instances:
            cluster_info.import_classes_strings.append(v['m_targetAssetType'])
    if should_handle_class:
        return data_instances
    else:
        return None

class ClusterClusterHeader:

    def __init__(self, g):
        self.cluster_marker = read_integer(g, 4, False, '<')
        self.size = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.packed_namespace_size = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.platform_id = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.instance_list_count = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.array_fixup_size = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.array_fixup_count = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.pointer_fixup_size = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.pointer_fixup_count = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.pointer_array_fixup_size = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.pointer_array_fixup_count = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.pointers_in_arrays_count = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.user_fixup_count = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.user_fixup_data_size = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.total_data_size = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.header_class_instance_count = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')
        self.header_class_child_count = read_integer(g, 4, False, '>' if self.cluster_marker == NOEPY_HEADER_BE else '<')

class ClusterPackedNamespace:

    def __init__(self, g, cluster_header):
        self.header = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.size = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.type_count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.class_count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.class_data_member_count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.string_table_size = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.default_buffer_count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.default_buffer_size = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')

class ClusterPackedDataMember:

    def __init__(self, g, cluster_header, label_offset):
        self.name_offset = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.type_id = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.value_offset = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.size_in_bytes = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.flags = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.fixed_array_size = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        old_position = g.tell()
        g.seek(label_offset + self.name_offset)
        self.name = read_null_ending_string(g)
        g.seek(old_position)

class ClusterPackedClassDescriptor:

    def __init__(self, g, cluster_header, label_offset):
        self.super_class_id = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.size_in_bytes_and_alignment = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.name_offset = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.class_data_member_count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.offset_from_parent = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.offset_to_base = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.offset_to_base_in_allocated_block = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.flags = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.default_buffer_offset = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        old_position = g.tell()
        g.seek(label_offset + self.name_offset)
        self.name = read_null_ending_string(g)
        g.seek(old_position)

    def get_size_in_bytes(self):
        return self.size_in_bytes_and_alignment & 268435455

    def get_alignment(self):
        return 1 << ((self.size_in_bytes_and_alignment & 4026531840) >> 28)

class ClusterInstanceListHeader:

    def __init__(self, g, cluster_header):
        self.class_id = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.size = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.objects_size = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.arrays_size = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.pointers_in_arrays_count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.array_fixup_count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.pointer_fixup_count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.pointer_array_fixup_count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')

class ClusterHeaderClassChildArray:

    def __init__(self, g, cluster_header, type_strings, class_descriptors):
        self.type_id = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.offset = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.flags = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')

class ClusterUserFixup:

    def __init__(self, g, cluster_header):
        self.type_id = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.size = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.offset = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')

class ClusterUserFixupResult:

    def __init__(self, g, fixup, type_strings, class_descriptors, Loc):
        self.data_type = get_type(fixup.type_id, type_strings, class_descriptors)
        self.defer = False
        old_position = g.tell()
        g.seek(Loc + fixup.offset)
        if self.data_type == 'PAssetReferenceImport':
            self.user_fixup_type = self.data_type
            self.user_fixup_target_offset = None
            self.defer = True
            self.data_offset = fixup.offset
            self.data_size = fixup.size
            self.refer_type = None
            self.data = read_integer(g, self.data_size, True, '>')
        else:
            self.user_fixup_type = None
            self.user_fixup_target_offset = fixup.offset
            self.data_offset = 0
            self.data_size = 0
            self.refer_type = self.data_type
            self.data = read_null_ending_string(g)
        g.seek(old_position)

class ClusterObjectID:

    def __init__(self):
        self.object_id = 0
        self.object_list = 0

class ClusterBaseFixup:

    def __init__(self):
        self.source_offset_or_member = 0
        self.source_object_id = 0
        self.som = 0

    def unpack_source(self, fixup_buffer):
        som = cluster_variable_length_quantity_unpack(fixup_buffer)
        self.som = som >> 1
        if som & 1 != 0:
            self.source_offset_or_member = som >> 1 | 1 << 31
        else:
            self.source_offset_or_member = som >> 1

    def is_class_data_member(self):
        return self.source_offset_or_member & 1 << 31 == 0

    def unpack(self, fixup_buffer, mask):
        if mask & 1 == 0:
            self.unpack_source(fixup_buffer)
        if mask & 2 == 0:
            self.source_object_id = cluster_variable_length_quantity_unpack(fixup_buffer)

    def set_source_object_id(self, fixup_buffer, sourceObjectID):
        self.source_object_id = sourceObjectID

class ClusterArrayFixup(ClusterBaseFixup):

    def __init__(self):
        super(ClusterArrayFixup, self).__init__()
        self.source_offset_or_member = 0
        self.source_object_id = 0
        self.count = 0
        self.offset = 0
        self.fixup_type = 'Array'

    def unpack_fixup(self, fixup_buffer, mask):
        if mask & 8 == 0:
            self.count = cluster_variable_length_quantity_unpack(fixup_buffer)
        self.offset = cluster_variable_length_quantity_unpack(fixup_buffer)

    def unpack(self, fixup_buffer, mask):
        super(ClusterArrayFixup, self).unpack(fixup_buffer, mask)
        self.unpack_fixup(fixup_buffer, mask)

class ClusterPointerFixup(ClusterBaseFixup):

    def __init__(self):
        super(ClusterPointerFixup, self).__init__()
        self.source_offset_or_member = 0
        self.source_object_id = 0
        self.destination_object = ClusterObjectID()
        self.destination_offset = 0
        self.array_index = 0
        self.user_fixup_id = None
        self.fixup_type = 'Pointer'

    def unpack_fixup(self, fixup_buffer, mask):
        is_user_fixup = False
        if mask & 16 == 0:
            user_fixup_id = cluster_variable_length_quantity_unpack(fixup_buffer)
            is_user_fixup = user_fixup_id != 0
            if is_user_fixup:
                self.user_fixup_id = user_fixup_id - 1
            else:
                self.user_fixup_id = None
        if is_user_fixup != True:
            self.destination_object.object_id = cluster_variable_length_quantity_unpack(fixup_buffer)
            if mask & 32 == 0:
                self.destination_object.object_list = cluster_variable_length_quantity_unpack(fixup_buffer)
            if mask & 64 == 0:
                self.destination_offset = cluster_variable_length_quantity_unpack(fixup_buffer)
        if mask & 8 == 0:
            self.array_index = cluster_variable_length_quantity_unpack(fixup_buffer)

    def unpack(self, fixup_buffer, mask):
        super(ClusterPointerFixup, self).unpack(fixup_buffer, mask)
        self.unpack_fixup(fixup_buffer, mask)

class ClusterFixupUnpacker:

    def __init__(self, unpack_mask, object_count):
        self.unpack_mask = unpack_mask
        self.object_count = object_count

    def unpack_strided(self, template_fixup, fixup_buffer, use_unpack_id):
        object_id = cluster_variable_length_quantity_unpack(fixup_buffer)
        stride = cluster_variable_length_quantity_unpack(fixup_buffer)
        stridedSeriesLength = cluster_variable_length_quantity_unpack(fixup_buffer)
        for i in range(stridedSeriesLength):
            fixup_buffer.set_fixup(template_fixup)
            if use_unpack_id:
                unpack_id(fixup_buffer, object_id, self.unpack_mask)
            else:
                unpack_with_fixup(fixup_buffer, object_id, self.unpack_mask)
            fixup_buffer.next_fixup()
            object_id += stride

    def unpack_all(self, template_fixup, fixup_buffer):
        for i in range(self.object_count):
            fixup_buffer.set_fixup(template_fixup)
            unpack_with_fixup(fixup_buffer, i, self.unpack_mask)
            fixup_buffer.next_fixup()

    def unpack_inclusive(self, template_fixup, fixup_buffer):
        patching_count = cluster_variable_length_quantity_unpack(fixup_buffer)
        for i in range(patching_count):
            next_ = 0
            if self.object_count < 256:
                next_ = fixup_buffer.read()
            else:
                next_ = cluster_variable_length_quantity_unpack(fixup_buffer)
            fixup_buffer.set_fixup(template_fixup)
            unpack_id(fixup_buffer, next_, self.unpack_mask)
            fixup_buffer.next_fixup()
        return patching_count

    def unpack_exclusive(self, template_fixup, fixup_buffer):
        patching_count = cluster_variable_length_quantity_unpack(fixup_buffer)
        last = 0
        for i in range(patching_count):
            next_ = 0
            if self.object_count < 256:
                next_ = fixup_buffer.read()
            else:
                next_ = cluster_variable_length_quantity_unpack(fixup_buffer)
            for o in range(last, next_):
                fixup_buffer.set_fixup(template_fixup)
                unpack_id(fixup_buffer, o, self.unpack_mask)
                fixup_buffer.next_fixup()
            last = next_ + 1
        for o in range(last, self.object_count):
            fixup_buffer.set_fixup(template_fixup)
            unpack_id(fixup_buffer, o, self.unpack_mask)
            fixup_buffer.next_fixup()
        return patching_count

    def unpack_bitmasked(self, template_fixup, fixup_buffer, use_unpack_id):
        bytes_required_as_bit_mask = self.object_count >> 3
        if self.object_count & 7 != 0:
            bytes_required_as_bit_mask += 1
        bit_mask_offset = fixup_buffer.offset
        fixup_buffer.offset += bytes_required_as_bit_mask
        current_bit = 1
        object_id = 0
        while object_id < self.object_count:
            if object_id & 7 == 0:
                current_bit = 1
            bit_mask = fixup_buffer.get_value_at(bit_mask_offset)
            if bit_mask & current_bit != 0:
                fixup_buffer.set_fixup(template_fixup)
                if use_unpack_id:
                    unpack_id(fixup_buffer, object_id, self.unpack_mask)
                else:
                    unpack_with_fixup(fixup_buffer, object_id, self.unpack_mask)
                fixup_buffer.next_fixup()
            if object_id & 7 == 7:
                bit_mask_offset += 1
            else:
                current_bit = current_bit << 1
            object_id += 1

class ClusterProcessInfo:

    def __init__(self, pointer_array, pointer, array, class_descriptor, data_members, type_strings, user_fixes, list_for_class_descriptors, classes_strings, import_classes_strings):
        self.pointer_array_fixup_offset = 0
        self.pointer_fixup_offset = 0
        self.array_fixup_offset = 0
        self.pointer_array_info = pointer_array
        self.pointer_info = pointer
        self.array_info = array
        self.class_descriptors = class_descriptor
        self.data_members = data_members
        self.type_strings = type_strings
        self.user_fixes = user_fixes
        self.list_for_class_descriptors = list_for_class_descriptors
        self.classes_strings = classes_strings
        self.import_classes_strings = import_classes_strings

    def reset_offset(self):
        self.pointer_array_fixup_offset = 0
        self.pointer_fixup_offset = 0
        self.array_fixup_offset = 0

class FixUpBuffer:

    def __init__(self, g, size, decompressed):
        self.pointer_index = 0
        self.offset = 0
        self.size = size
        self.fixup_buffer = g.read(self.size)
        self.decompressed = decompressed

    def read(self):
        val = self.fixup_buffer[self.offset]
        self.offset += 1
        return val

    def get_value_at(self, index):
        return self.fixup_buffer[index]

    def get_fixup(self):
        return self.decompressed[self.pointer_index]

    def set_fixup(self, fixup):
        self.decompressed[self.pointer_index].source_offset_or_member = fixup.source_offset_or_member
        self.decompressed[self.pointer_index].source_object_id = fixup.source_object_id
        self.decompressed[self.pointer_index].som = fixup.som
        if fixup.fixup_type == 'Array':
            self.decompressed[self.pointer_index].count = fixup.count
            self.decompressed[self.pointer_index].offset = fixup.offset
        elif fixup.fixup_type == 'Pointer':
            if self.decompressed[self.pointer_index].destination_object == None:
                self.decompressed[self.pointer_index].destination_object = ClusterObjectID()
            self.decompressed[self.pointer_index].destination_object.object_id = fixup.destination_object.object_id
            self.decompressed[self.pointer_index].destination_object.object_list = fixup.destination_object.object_list
            self.decompressed[self.pointer_index].destination_offset = fixup.destination_offset
            self.decompressed[self.pointer_index].array_index = fixup.array_index
            self.decompressed[self.pointer_index].user_fixup_id = fixup.user_fixup_id

    def next_fixup(self):
        self.pointer_index += 1

def unpack_with_fixup(fixup_buffer, ID, mask):
    fixup_buffer.get_fixup().set_source_object_id(fixup_buffer, ID)
    fixup_buffer.get_fixup().unpack_fixup(fixup_buffer, mask)

def unpack_id(fixup_buffer, ID, mask):
    fixup_buffer.get_fixup().set_source_object_id(fixup_buffer, ID)

def initialize_fixup_as_template(template_fixup, fixup_buffer, mask):
    if mask & 32 != 0:
        template_fixup.destination_object.object_list = cluster_variable_length_quantity_unpack(fixup_buffer)
    return template_fixup

def cluster_variable_length_quantity_unpack(fixup_buffer):
    by_pass = True
    result = 0
    next_ = 0
    shift = 0
    while next_ & 128 != 0 or by_pass:
        by_pass = False
        next_ = fixup_buffer.read()
        result |= (next_ & 127) << shift
        shift += 7
    return result

def decompress(fixup_buffer, fixup_count, object_count, is_pointer):
    pointer_end = fixup_buffer.pointer_index + fixup_count
    while fixup_buffer.pointer_index < pointer_end:
        pack_type_with_mask = fixup_buffer.read()
        pack_type = pack_type_with_mask & 7
        mask = pack_type_with_mask & ~7
        mask_for_fixups = mask | 1
        if object_count == 1:
            mask_for_fixups |= 2
        template_fixup = None
        if is_pointer:
            template_fixup = ClusterPointerFixup()
        else:
            template_fixup = ClusterArrayFixup()
        template_fixup.unpack_source(fixup_buffer)
        if is_pointer:
            template_fixup = initialize_fixup_as_template(template_fixup, fixup_buffer, mask_for_fixups)
        unpacker = ClusterFixupUnpacker(mask_for_fixups, object_count)
        if pack_type == 0:
            unpacker.unpack_all(template_fixup, fixup_buffer)
        elif pack_type == 2:
            decompressed_with_id_pointer = fixup_buffer.pointer_index
            patching_count = unpacker.unpack_inclusive(template_fixup, fixup_buffer)
            save_pointer = fixup_buffer.pointer_index
            for i in range(patching_count):
                fixup_buffer.pointer_index = decompressed_with_id_pointer
                fixup_buffer.get_fixup().unpack_fixup(fixup_buffer, mask_for_fixups)
                decompressed_with_id_pointer += 1
            fixup_buffer.pointer_index = save_pointer
        elif pack_type == 3:
            decompressed_with_id_pointer = fixup_buffer.pointer_index
            patching_count = unpacker.unpack_exclusive(template_fixup, fixup_buffer)
            inclusive_count = object_count - patching_count
            save_pointer = fixup_buffer.pointer_index
            for i in range(inclusive_count):
                fixup_buffer.pointer_index = decompressed_with_id_pointer
                fixup_buffer.get_fixup().unpack_fixup(fixup_buffer, mask_for_fixups)
                decompressed_with_id_pointer += 1
            fixup_buffer.pointer_index = save_pointer
        elif pack_type == 4:
            unpacker.unpack_bitmasked(template_fixup, fixup_buffer, False)
        elif pack_type == 5:
            patching_count = cluster_variable_length_quantity_unpack(fixup_buffer)
            for i in range(patching_count):
                fixup_buffer.set_fixup(template_fixup)
                fixup_buffer.get_fixup().unpack(fixup_buffer, mask_for_fixups)
                fixup_buffer.next_fixup()
        elif pack_type == 6:
            unpacker.unpack_strided(template_fixup, fixup_buffer, False)
        elif pack_type == 1:
            decompressed_group_end_pointer = fixup_buffer.pointer_index + object_count
            template_fixup_for_target = template_fixup
            while fixup_buffer.pointer_index < decompressed_group_end_pointer:
                pack_type_for_groups = fixup_buffer.read()
                template_fixup_for_target.unpack_fixup(fixup_buffer, mask_for_fixups)
                if pack_type_for_groups == 2:
                    unpacker.unpack_inclusive(template_fixup_for_target, fixup_buffer)
                elif pack_type_for_groups == 3:
                    unpacker.unpack_exclusive(template_fixup_for_target, fixup_buffer)
                elif pack_type_for_groups == 4:
                    unpacker.unpack_bitmasked(template_fixup_for_target, fixup_buffer, True)
                elif pack_type_for_groups == 6:
                    unpacker.unpack_strided(template_fixup_for_target, fixup_buffer, True)

def decompress_fixups(fixup_buffer, instance_list, is_pointer_array, is_pointer):
    for i in range(len(instance_list)):
        fixup_count = 0
        if is_pointer:
            fixup_count = instance_list[i].pointer_fixup_count
        else:
            fixup_count = instance_list[i].array_fixup_count
            if is_pointer_array:
                fixup_count = instance_list[i].pointer_array_fixup_count
        decompress(fixup_buffer, fixup_count, instance_list[i].count, is_pointer)
    return fixup_buffer.decompressed

def parse_cluster(filename='', noesis_model=None, storage_media=None, pkg_name='', partialmaps = False, allbuffers = False, gltf_nonbinary = False, item_num = 0):
    type_list = []
    list_for_class_descriptors = {}
    classes_strings = []
    import_classes_strings = []
    cluster_mesh_info = None
    g = storage_media.open(filename, 'rb')
    g.seek(0)
    cluster_header = ClusterClusterHeader(g)
    g.seek(cluster_header.size)
    name_spaces = ClusterPackedNamespace(g, cluster_header)
    type_ids = memoryview(bytearray(g.read(name_spaces.type_count * 4)))
    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
        bytearray_byteswap(type_ids, 4)
    type_ids = cast_memoryview(memoryview(type_ids), 'i')
    label_offset = g.tell() + name_spaces.class_count * 36 + name_spaces.class_data_member_count * 24
    old_position = g.tell()
    for i in range(len(type_ids)):
        g.seek(label_offset + type_ids[i])
        type_list.append(read_null_ending_string(g))
    g.seek(old_position)
    class_member_count = 0
    class_descriptors = [ClusterPackedClassDescriptor(g, cluster_header, label_offset) for i in range(name_spaces.class_count)]
    for class_descriptor in class_descriptors:
        class_descriptor.member_offset = class_member_count
        class_member_count += class_descriptor.class_data_member_count
    class_data_members = [ClusterPackedDataMember(g, cluster_header, label_offset) for i in range(name_spaces.class_data_member_count)]
    g.seek(g.tell() + name_spaces.string_table_size)
    instance_list = [ClusterInstanceListHeader(g, cluster_header) for i in range(cluster_header.instance_list_count)]
    object_data_offset = g.tell()
    g.seek(object_data_offset + cluster_header.total_data_size)
    user_fixup_data_offset = g.tell()
    g.seek(user_fixup_data_offset + cluster_header.user_fixup_data_size)
    user_fixups = [ClusterUserFixup(g, cluster_header) for i in range(cluster_header.user_fixup_count)]
    user_fixup_results = [ClusterUserFixupResult(g, fixup, type_list, class_descriptors, user_fixup_data_offset) for fixup in user_fixups]
    header_class_ids = bytearray(g.read(cluster_header.header_class_instance_count * 4))
    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
        bytearray_byteswap(header_class_ids, 4)
    header_class_ids = cast_memoryview(memoryview(header_class_ids), 'i')
    header_class_children = [ClusterHeaderClassChildArray(g, cluster_header, type_list, class_descriptors) for i in range(cluster_header.header_class_child_count)]
    pointer_fixup_total = 0
    array_fixup_total = 0
    array_pointer_fixup_total = 0
    for i in range(len(instance_list)):
        pointer_fixup_total += instance_list[i].pointer_fixup_count
        array_fixup_total += instance_list[i].array_fixup_count
        array_pointer_fixup_total += instance_list[i].pointer_array_fixup_count
    pointer_array_fixup_offset = g.tell()
    pointer_array_fixups = [ClusterArrayFixup() for i in range(array_pointer_fixup_total)]
    pointer_array_fixups = decompress_fixups(FixUpBuffer(g, cluster_header.pointer_array_fixup_size, pointer_array_fixups), instance_list, True, False)
    g.seek(pointer_array_fixup_offset + cluster_header.pointer_array_fixup_size)
    pointer_fixup_offset = g.tell()
    pointer_fixups = [ClusterPointerFixup() for i in range(pointer_fixup_total)]
    pointer_fixups = decompress_fixups(FixUpBuffer(g, cluster_header.pointer_fixup_size, pointer_fixups), instance_list, False, True)
    g.seek(pointer_fixup_offset + cluster_header.pointer_fixup_size)
    array_fixup_offset = g.tell()
    array_fixups = [ClusterArrayFixup() for i in range(array_fixup_total)]
    array_fixups = decompress_fixups(FixUpBuffer(g, cluster_header.array_fixup_size, array_fixups), instance_list, False, False)
    g.seek(array_fixup_offset + cluster_header.array_fixup_size)
    cluster_mesh_info = MeshInfo()
    cluster_mesh_info.storage_media = storage_media
    cluster_mesh_info.filename = filename
    cluster_mesh_info.vram_model_data_offset = g.tell()
    header_processor = ClusterProcessInfo(pointer_array_fixups, pointer_fixups, array_fixups, class_descriptors, class_data_members, type_list, user_fixup_results, list_for_class_descriptors, classes_strings, import_classes_strings)
    for i in range(len(class_descriptors)):
        class_descriptor = class_descriptors[i]
        if class_descriptor.name == 'PClusterHeader':
            dict_data = cluster_mesh_info.cluster_header
            g.seek(0)
            process_data_members(g, header_processor, i + 1, 0, 0, 0, cluster_mesh_info, class_descriptor.name, False, dict_data, cluster_header, None, 0, 0, 0, None, None, None)
            break
    g.seek(object_data_offset)
    class_location = g.tell()
    count_list = 0
    data_instances_by_class = {}
    for instance_list_header in instance_list:
        g.seek(class_location)
        data_instances = process_cluster_instance_list_header(instance_list_header, g, count_list, header_processor, cluster_mesh_info, cluster_header, filename, None)
        if data_instances != None:
            data_instances_by_class[get_class_name(header_processor, instance_list_header.class_id)] = data_instances
            data_instances_by_class[count_list] = data_instances
        class_location += instance_list_header.size
        count_list += 1
    cluster_mesh_info.data_instances_by_class = data_instances_by_class
    header_processor.reset_offset()
    class_location = object_data_offset
    count_list = 0
    for instance_list_header in instance_list:
        g.seek(class_location)
        process_cluster_instance_list_header(instance_list_header, g, count_list, header_processor, cluster_mesh_info, cluster_header, filename, data_instances_by_class)
        class_location += instance_list_header.size
        count_list += 1
    render_mesh(g, cluster_mesh_info, header_processor, cluster_header, pkg_name, partialmaps = partialmaps, allbuffers = allbuffers, gltf_nonbinary = gltf_nonbinary, item_num = item_num)
    return cluster_mesh_info

def file_is_ed8_pkg(path):
    path = os.path.realpath(path)
    if not os.path.isfile(path):
        return False
    max_offset = 0
    with open(path, 'rb') as f:
        f.seek(0, 2)
        length = f.tell()
        f.seek(0, 0)
        if length <= 4:
            return False
        f.seek(4, io.SEEK_CUR)
        (total_file_entries,) = struct.unpack('<I', f.read(4))
        if length < 8 + (64 + 4 + 4 + 4 + 4) * total_file_entries:
            return False
        for i in range(total_file_entries):
            (file_entry_name, file_entry_uncompressed_size, file_entry_compressed_size, file_entry_offset, file_entry_flags) = struct.unpack('<64sIIII', f.read(64 + 4 + 4 + 4 + 4))
            cur_offset = file_entry_offset + file_entry_compressed_size
            if cur_offset > max_offset:
                max_offset = cur_offset
        if length < max_offset:
            return False
    return True

class MeshInfo:

    def __init__(self):
        self.cluster_header = {}
        self.data_instances_by_class = {}
        self.gltf_data = {}
        self.filename = ''
        self.storage_media = None
        self.vram_model_data_offset = 0
        self.bone_names = []

class IStorageMedia:

    def normalize_path_name(self, name):
        raise Exception('This member needs to be overrided')

    def check_existent_storage(self, name):
        raise Exception('This member needs to be overrided')

    def open(self, name, flags):
        raise Exception('This member needs to be overrided')

    def get_list_at(self, name, list_callback):
        raise Exception('This member needs to be overrided')

class TFileMedia(IStorageMedia):

    def __init__(self, basepath):
        basepath = os.path.realpath(basepath)
        if not os.path.isdir(basepath):
            raise Exception('Passed in basepath is not directory')
        self.basepath = basepath

    def normalize_path_name(self, name):
        return os.path.normpath(name)

    def check_existent_storage(self, name):
        return os.path.isfile(self.basepath + os.sep + name)

    def open(self, name, flags='rb', **kwargs):
        if 'w' in flags:
            return open(name, flags, **kwargs)
        else:
            input_data = None
            with open(self.basepath + os.sep + name, 'rb') as f:
                input_data = f.read()
            if 'b' in flags:
                return io.BytesIO(input_data, **kwargs)
            else:
                return io.TextIOWrapper(io.BytesIO(input_data), **kwargs)

    def get_list_at(self, name, list_callback):
        llist = sorted(os.listdir(self.basepath))
        for item in llist:
            if list_callback(item):
                break

class TED8PkgMedia(IStorageMedia):

    def __init__(self, path):
        path = os.path.realpath(path)
        if not os.path.isfile(path):
            raise Exception('Passed in path is not file')
        self.path = path
        basepath = os.path.dirname(path)
        if not os.path.isdir(basepath):
            raise Exception('Parent path is not directory')
        self.basepath = basepath
        f = open(path, 'rb')
        self.f = f
        f.seek(4, io.SEEK_CUR)
        package_file_entries = {}
        (total_file_entries,) = struct.unpack('<I', f.read(4))
        for i in range(total_file_entries):
            (file_entry_name, file_entry_uncompressed_size, file_entry_compressed_size, file_entry_offset, file_entry_flags) = struct.unpack('<64sIIII', f.read(64 + 4 + 4 + 4 + 4))
            package_file_entries[file_entry_name.rstrip(b'\x00').decode('ASCII')] = [file_entry_offset, file_entry_compressed_size, file_entry_uncompressed_size, file_entry_flags]
        self.file_entries = package_file_entries
        self.compression_flag = 0

    def normalize_path_name(self, name):
        return os.path.normpath(name)

    def check_existent_storage(self, name):
        return name in self.file_entries

    def open(self, name, flags='rb', **kwargs):
        file_entry = self.file_entries[name]
        self.f.seek(file_entry[0])
        output_data = None
        if file_entry[3] & 2:
            self.compression_flag = 2
            self.f.seek(4, io.SEEK_CUR)
        if file_entry[3] & 4:
            self.compression_flag = 4
            output_data = uncompress_lz4(self.f, file_entry[2], file_entry[1])
        elif file_entry[3] & 1:
            self.compression_flag = 1
            output_data = uncompress_nislzss(self.f, file_entry[2], file_entry[1])
        elif file_entry[3] & 8:
            self.compression_flag = 8
            if 'zstandard' in sys.modules:
                output_data = uncompress_zstd(self.f, file_entry[2], file_entry[1])
            else:
                raise Exception('File %s could not be extracted because zstandard module is not installed' % name)
        else:
            self.compression_flag = 0
            output_data = self.f.read(file_entry[2])
        if 'b' in flags:
            return io.BytesIO(output_data, **kwargs)
        else:
            return io.TextIOWrapper(io.BytesIO(output_data), **kwargs)

    def get_list_at(self, name, list_callback):
        llist = sorted(self.file_entries.keys())
        for item in llist:
            if list_callback(item):
                break

class BytesIOOnCloseHandler(io.BytesIO):

    def __init__(self, *args, **kwargs):
        self.handler = None
        super().__init__(*args, **kwargs)

    def close(self, *args, **kwargs):
        if self.handler != None and (not self.closed):
            self.handler(self.getvalue())
        super().close(*args, **kwargs)

    def set_close_handler(self, handler):
        self.handler = handler

class TSpecialMemoryMedia(IStorageMedia):

    def __init__(self):
        self.file_entries = {}

    def normalize_path_name(self, name):
        return os.path.normpath(name)

    def check_existent_storage(self, name):
        return name in self.file_entries

    def open(self, name, flags='rb', **kwargs):
        if 'b' in flags:
            f = None

            def close_handler(value):
                self.file_entries[name] = value
            if name in self.file_entries:
                f = BytesIOOnCloseHandler(self.file_entries[name])
            else:
                f = BytesIOOnCloseHandler()
            f.set_close_handler(close_handler)
            return f
        else:
            raise Exception('Reading in text mode not supported')

    def get_list_at(self, name, list_callback):
        llist = sorted(self.file_entries.keys())
        for item in llist:
            if list_callback(item):
                break

class TSpecialOverlayMedia(IStorageMedia):

    def __init__(self, path, allowed_write_extensions=None):
        self.storage0 = TFileMedia(os.path.dirname(path))
        self.storage1 = TSpecialMemoryMedia()
        self.storage2 = TED8PkgMedia(path)
        self.allowed_write_extensions = allowed_write_extensions

    def normalize_path_name(self, name):
        return os.path.normpath(name)

    def check_existent_storage(self, name):
        return self.storage1.check_existent_storage(name) or self.storage2.check_existent_storage(name)

    def open(self, name, flags='rb', **kwargs):
        if 'w' in flags:
            has_passthrough_extension = True
            if self.allowed_write_extensions != None:
                for x in self.allowed_write_extensions:
                    if name.endswith(x):
                        has_passthrough_extension = True
                        break
            if has_passthrough_extension:
                return self.storage0.open(name, flags, **kwargs)
            return self.storage1.open(name, flags, **kwargs)
        else:
            if self.storage1.check_existent_storage(name):
                return self.storage1.open(name, flags, **kwargs)
            elif self.storage2.check_existent_storage(name):
                return self.storage2.open(name, flags, **kwargs)
            raise Exception('File ' + str(name) + ' not found')

    def get_list_at(self, name, list_callback):
        items = {}

        def xlist_callback(item):
            items[item] = True
        self.storage1.get_list_at('.', xlist_callback)
        self.storage2.get_list_at('.', xlist_callback)
        llist = sorted(items.keys())
        for item in llist:
            if list_callback(item):
                break

def get_texture_size(width, height, bpp, is_dxt):
    current_width = width
    current_height = height
    if is_dxt:
        current_width = current_width + 3 & ~3
        current_height = current_height + 3 & ~3
    return current_width * current_height * bpp // 8

def get_mipmap_offset_and_size(mipmap_level, width, height, texture_format, is_cube_map):
    size_map = {'DXT1': 4, 'DXT3': 8, 'DXT5': 8, 'BC5': 8, 'BC7': 8, 'RGBA8': 32, 'ARGB8': 32, 'L8': 8, 'A8': 8, 'LA88': 16, 'RGBA16F': 64, 'ARGB1555': 16, 'ARGB4444': 16, 'ARGB8_SRGB': 32}
    block_map = ['DXT1', 'DXT3', 'DXT5', 'BC5', 'BC7']
    bpp = size_map[texture_format]
    is_dxt = texture_format in block_map
    offset = 0
    current_mipmap_level = mipmap_level
    current_width = width
    current_height = height
    while current_mipmap_level != 0:
        current_mipmap_level -= 1
        offset += get_texture_size(current_width, current_height, bpp, is_dxt)
        current_width = max(current_width >> 1, 1)
        current_height = max(current_height >> 1, 1)
    if is_dxt:
        current_width = current_width + 3 & ~3
        current_height = current_height + 3 & ~3
    return (offset, current_width * current_height * bpp // 8, current_width, current_height)

def create_texture(g, dict_data, cluster_mesh_info, cluster_header, is_cube_map, pkg_name = ''):
    g.seek(cluster_mesh_info.vram_model_data_offset)
    if is_cube_map:
        image_width = dict_data['m_size']
        image_height = dict_data['m_size']
    else:
        image_width = dict_data['m_width']
        image_height = dict_data['m_height']
    if cluster_header.platform_id == GNM_PLATFORM:
        image_data = g.read(cluster_mesh_info.cluster_header['m_sharedVideoMemoryBufferSize'])
    elif cluster_header.platform_id == GXM_PLATFORM:
        g.seek(64, io.SEEK_CUR)
        texture_size = 0
        if 'm_mainTextureBufferSize' in cluster_mesh_info.cluster_header:
            texture_size = cluster_mesh_info.cluster_header['m_mainTextureBufferSize']
        elif 'm_textureBufferSize' in cluster_mesh_info.cluster_header:
            texture_size = cluster_mesh_info.cluster_header['m_textureBufferSize']
        image_data = g.read(texture_size - 64)
        block_read = 4
        if dict_data['m_format'] == 'DXT5':
            block_read = 8
        image_data = Unswizzle(image_data, image_width >> 1, image_height >> 2, dict_data['m_format'], True, cluster_header.platform_id, 0)
    elif cluster_header.platform_id == DX11_PLATFORM:
        image_data = g.read(cluster_mesh_info.cluster_header['m_maxTextureBufferSize'])
    elif cluster_header.platform_id == GCM_PLATFORM:
        image_data = g.read(cluster_mesh_info.cluster_header['m_vramBufferSize'])
    pitch = 0
    if cluster_header.platform_id == GNM_PLATFORM:
        temporary_pitch = GetInfo(struct.unpack('<I', dict_data['m_texState'][24:28])[0], 26, 13) + 1
        if image_width != temporary_pitch:
            pitch = temporary_pitch
    if cluster_header.platform_id == GNM_PLATFORM or cluster_header.platform_id == GXM_PLATFORM:
        image_data = Unswizzle(image_data, image_width, image_height, dict_data['m_format'], True, cluster_header.platform_id, pitch)
    elif cluster_header.platform_id == GCM_PLATFORM:
        size_map = {'ARGB8': 4, 'RGBA8': 4, 'ARGB4444': 2, 'L8': 1, 'LA8': 2}
        if dict_data['m_format'] in size_map:
            image_data = Unswizzle(image_data, image_width, image_height, dict_data['m_format'], True, cluster_header.platform_id, pitch)
    if 'PAssetReference' in cluster_mesh_info.data_instances_by_class:
        path_name = pkg_name + os.sep + os.path.dirname(cluster_mesh_info.data_instances_by_class['PAssetReference'][0]['m_id']).replace('/', os.sep)
    else:
        path_name = pkg_name + os.sep + 'textures'
    if not os.path.exists(path_name):
        os.makedirs(path_name)
    dds_output_path = path_name + os.sep + cluster_mesh_info.filename.split('.', 1)[0] + '.dds'
    with cluster_mesh_info.storage_media.open(dds_output_path, 'wb') as (f):
        f.write(get_dds_header(dict_data['m_format'], image_width, image_height, None, False))
        f.write(image_data)

    #if True:
        #png_output_path = cluster_mesh_info.filename.rsplit('.', maxsplit=2)[0] + '.png'
        #if True:
            #dxgiFormat = None
            #decode_callback = None
            #if dict_data['m_format'] == 'DXT1' or dict_data['m_format'] == 'BC1':
                #dxgiFormat = 71
            #elif dict_data['m_format'] == 'DXT3' or dict_data['m_format'] == 'BC2':
                #dxgiFormat = 74
            #elif dict_data['m_format'] == 'DXT5' or dict_data['m_format'] == 'BC3':
                #dxgiFormat = 77
            #elif dict_data['m_format'] == 'BC5':
                #dxgiFormat = 83
            #elif dict_data['m_format'] == 'BC7':
                #dxgiFormat = 98
            #elif dict_data['m_format'] == 'LA8':
                #decode_callback = decode_la8_into_abgr8
            #elif dict_data['m_format'] == 'L8':
                #decode_callback = decode_l8_into_abgr8
            #elif dict_data['m_format'] == 'ARGB8' or dict_data['m_format'] == 'ARGB8_SRGB':
                #decode_callback = decode_argb8_into_agbr8
            #elif dict_data['m_format'] == 'RGBA8':
                #decode_callback = decode_rgba8_into_abgr8
            #elif dict_data['m_format'] == 'RGB565':
                #decode_callback = decode_rgb565_into_abgr8
            #elif dict_data['m_format'] == 'ARGB4444':
                #decode_callback = decode_argb4444_into_abgr8
            #else:
                #raise Exception('Unhandled format ' + dict_data['m_format'] + ' for PNG conversion')
            #if dxgiFormat != None:
                #decode_callback = decode_block_into_abgr8
            #zfio = io.BytesIO()
            #zfio.write(image_data)
            #zfio.seek(0)
            #rgba_image_data = decode_callback(zfio, image_width, image_height, dxgiFormat)
            #with cluster_mesh_info.storage_media.open(png_output_path, 'wb') as f:
                #import zlib
                #f.write(b'\x89PNG\r\n\x1a\n')

                #def write_png_chunk(wf, ident, d):
                    #wf.write(len(d).to_bytes(4, byteorder='big'))
                    #wf.write(ident[0:4])
                    #wf.write(d)
                    #wf.write(zlib.crc32(d, zlib.crc32(ident[0:4])).to_bytes(4, byteorder='big'))
                #ihdr_str = struct.pack('>IIBBBBB', image_width, image_height, 8, 6, 0, 0, 0)
                #write_png_chunk(f, b'IHDR', ihdr_str)
                #cbio = io.BytesIO()
                #cobj = zlib.compressobj(level=1)
                #for row in range(image_height):
                    #cbio.write(cobj.compress(b'\x00'))
                    #out_offset = row * image_width * 4
                    #cbio.write(cobj.compress(rgba_image_data[out_offset:out_offset + image_width * 4]))
                #cbio.write(cobj.flush())
                #write_png_chunk(f, b'IDAT', cbio.getbuffer())
                #write_png_chunk(f, b'IEND', b'')

def load_texture(dict_data, cluster_mesh_info, pkg_name = ''):
    dds_basename = os.path.basename(dict_data['m_id'])
    found_basename = []

    def list_callback(item):
        if item[:-6] == dds_basename:
            found_basename.append(item)
            return True
    cluster_mesh_info.storage_media.get_list_at('.', list_callback)
    loaded_texture = False
    if len(found_basename) > 0:
        parse_cluster(found_basename[0], None, cluster_mesh_info.storage_media, pkg_name)
        loaded_texture = True

def load_materials_with_actual_name(dict_data, cluster_mesh_info):
    if type(dict_data['m_effectVariant']) == dict and 'm_id' in dict_data['m_effectVariant']:
        dict_data['mu_compiledShaderName'] = dict_data['m_effectVariant']['m_id']

def load_shader_parameters(g, dict_data, cluster_header):
    if 'mu_shaderParameters' in dict_data:
        return
    old_position = g.tell()
    g.seek(dict_data['mu_memberLoc'])
    parameter_buffer = g.read(dict_data['m_parameterBufferSize'])
    g.seek(old_position)
    shader_parameters = {}
    for x in dict_data['m_tweakableShaderParameterDefinitions']['m_els']:
        parameter_offset = x['m_bufferLoc']['m_offset']
        parameter_size = x['m_bufferLoc']['m_size']
        if x['m_parameterType'] == 66 or x['m_parameterType'] == 68:
            arr = bytearray(parameter_buffer[parameter_offset:parameter_offset + parameter_size])
            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                bytearray_byteswap(arr, 4)
            arr = cast_memoryview(memoryview(arr), 'I')
            shader_parameters[x['m_name']] = arr
            if x['m_name'] in dict_data['mu_tweakableShaderParameterDefinitionsObjectReferences']:
                shader_parameters[x['m_name']] = dict_data['mu_tweakableShaderParameterDefinitionsObjectReferences'][x['m_name']]['m_id']
            else:
                shader_parameters[x['m_name']] = ''
        elif x['m_parameterType'] == 71:
            arr = bytearray(parameter_buffer[parameter_offset:parameter_offset + parameter_size])
            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                bytearray_byteswap(arr, 4)
            arr = cast_memoryview(memoryview(arr), 'I')
            shader_parameters[x['m_name']] = arr
            if x['m_name'] in dict_data['mu_tweakableShaderParameterDefinitionsObjectReferences']:
                shader_parameters[x['m_name']] = dict_data['mu_tweakableShaderParameterDefinitionsObjectReferences'][x['m_name']]
        elif parameter_size == 24:
            shader_parameters[x['m_name']] = struct.unpack('IIQQ', parameter_buffer[parameter_offset:parameter_offset + parameter_size])
        elif parameter_size % 4 == 0:
            arr = bytearray(parameter_buffer[parameter_offset:parameter_offset + parameter_size])
            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                bytearray_byteswap(arr, 4)
            arr = cast_memoryview(memoryview(arr), 'f')
            shader_parameters[x['m_name']] = arr
        else:
            shader_parameters[x['m_name']] = parameter_buffer[parameter_offset:parameter_offset + parameter_size]
    dict_data['mu_shaderParameters'] = shader_parameters

def multiply_array_as_4x4_matrix(arra, arrb):
    newarr = cast_memoryview(memoryview(bytearray(cast_memoryview(memoryview(arra), 'B'))), 'f')
    for i in range(4):
        for j in range(4):
            newarr[i * 4 + j] = 0 + arrb[i * 4 + 0] * arra[j + 0] + arrb[i * 4 + 1] * arra[j + 4] + arrb[i * 4 + 2] * arra[j + 8] + arrb[i * 4 + 3] * arra[j + 12]
    return newarr

def invert_matrix_44(m):
    inv = cast_memoryview(memoryview(bytearray(cast_memoryview(memoryview(m), 'B'))), 'f')
    inv[0] = m[5] * m[10] * m[15] - m[5] * m[11] * m[14] - m[9] * m[6] * m[15] + m[9] * m[7] * m[14] + m[13] * m[6] * m[11] - m[13] * m[7] * m[10]
    inv[1] = -m[1] * m[10] * m[15] + m[1] * m[11] * m[14] + m[9] * m[2] * m[15] - m[9] * m[3] * m[14] - m[13] * m[2] * m[11] + m[13] * m[3] * m[10]
    inv[2] = m[1] * m[6] * m[15] - m[1] * m[7] * m[14] - m[5] * m[2] * m[15] + m[5] * m[3] * m[14] + m[13] * m[2] * m[7] - m[13] * m[3] * m[6]
    inv[3] = -m[1] * m[6] * m[11] + m[1] * m[7] * m[10] + m[5] * m[2] * m[11] - m[5] * m[3] * m[10] - m[9] * m[2] * m[7] + m[9] * m[3] * m[6]
    inv[4] = -m[4] * m[10] * m[15] + m[4] * m[11] * m[14] + m[8] * m[6] * m[15] - m[8] * m[7] * m[14] - m[12] * m[6] * m[11] + m[12] * m[7] * m[10]
    inv[5] = m[0] * m[10] * m[15] - m[0] * m[11] * m[14] - m[8] * m[2] * m[15] + m[8] * m[3] * m[14] + m[12] * m[2] * m[11] - m[12] * m[3] * m[10]
    inv[6] = -m[0] * m[6] * m[15] + m[0] * m[7] * m[14] + m[4] * m[2] * m[15] - m[4] * m[3] * m[14] - m[12] * m[2] * m[7] + m[12] * m[3] * m[6]
    inv[7] = m[0] * m[6] * m[11] - m[0] * m[7] * m[10] - m[4] * m[2] * m[11] + m[4] * m[3] * m[10] + m[8] * m[2] * m[7] - m[8] * m[3] * m[6]
    inv[8] = m[4] * m[9] * m[15] - m[4] * m[11] * m[13] - m[8] * m[5] * m[15] + m[8] * m[7] * m[13] + m[12] * m[5] * m[11] - m[12] * m[7] * m[9]
    inv[9] = -m[0] * m[9] * m[15] + m[0] * m[11] * m[13] + m[8] * m[1] * m[15] - m[8] * m[3] * m[13] - m[12] * m[1] * m[11] + m[12] * m[3] * m[9]
    inv[10] = m[0] * m[5] * m[15] - m[0] * m[7] * m[13] - m[4] * m[1] * m[15] + m[4] * m[3] * m[13] + m[12] * m[1] * m[7] - m[12] * m[3] * m[5]
    inv[11] = -m[0] * m[5] * m[11] + m[0] * m[7] * m[9] + m[4] * m[1] * m[11] - m[4] * m[3] * m[9] - m[8] * m[1] * m[7] + m[8] * m[3] * m[5]
    inv[12] = -m[4] * m[9] * m[14] + m[4] * m[10] * m[13] + m[8] * m[5] * m[14] - m[8] * m[6] * m[13] - m[12] * m[5] * m[10] + m[12] * m[6] * m[9]
    inv[13] = m[0] * m[9] * m[14] - m[0] * m[10] * m[13] - m[8] * m[1] * m[14] + m[8] * m[2] * m[13] + m[12] * m[1] * m[10] - m[12] * m[2] * m[9]
    inv[14] = -m[0] * m[5] * m[14] + m[0] * m[6] * m[13] + m[4] * m[1] * m[14] - m[4] * m[2] * m[13] - m[12] * m[1] * m[6] + m[12] * m[2] * m[5]
    inv[15] = m[0] * m[5] * m[10] - m[0] * m[6] * m[9] - m[4] * m[1] * m[10] + m[4] * m[2] * m[9] + m[8] * m[1] * m[6] - m[8] * m[2] * m[5]
    det = m[0] * inv[0] + m[1] * inv[4] + m[2] * inv[8] + m[3] * inv[12]
    if det == 0:
        return None
    det = 1.0 / det
    for i in range(16):
        inv[i] *= det
    return inv

def dot_product_vector3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def mul_vector3_vector3_float(r, a, f):
    r[0] = a[0] * f
    r[1] = a[1] * f
    r[2] = a[2] * f

def zero_vector3(r):
    r[0] = 0.0
    r[1] = 0.0
    r[2] = 0.0

def normalize_v3_v3_length(r, a, unit_length=1.0):
    d = dot_product_vector3(a, a)
    if d > 1e-35:
        d = d ** 0.5
        mul_vector3_vector3_float(r, a, unit_length / d)
    else:
        zero_vector3(r)
        d = 0.0
    return d

def normalize_matrix_44(m):
    norm = cast_memoryview(memoryview(bytearray(cast_memoryview(memoryview(m), 'B'))), 'f')
    norm[0:15] = m[0:15]
    for i in range(3):
        tmp_v3 = array.array('f')
        tmp_v3.extend(norm[0 + i * 4:3 + i * 4])
        normalize_v3_v3_length(tmp_v3, tmp_v3, 1.0)
        norm[0 + i * 4:3 + i * 4] = tmp_v3
    return norm

def decompose_matrix_44(mat, translation, rotation, scale):
    m00 = mat[0]
    m01 = mat[1]
    m02 = mat[2]
    m03 = mat[3]
    m10 = mat[4]
    m11 = mat[5]
    m12 = mat[6]
    m13 = mat[7]
    m20 = mat[8]
    m21 = mat[9]
    m22 = mat[10]
    m23 = mat[11]
    m30 = mat[12]
    m31 = mat[13]
    m32 = mat[14]
    m33 = mat[15]
    translation[0] = m30
    translation[1] = m31
    translation[2] = m32
    scale[0] = (m00 ** 2 + m10 ** 2 + m20 ** 2) ** 0.5
    scale[1] = (m01 ** 2 + m11 ** 2 + m21 ** 2) ** 0.5
    scale[2] = (m02 ** 2 + m12 ** 2 + m22 ** 2) ** 0.5
    mat = normalize_matrix_44(mat)
    m00 = mat[0]
    m01 = mat[1]
    m02 = mat[2]
    m03 = mat[3]
    m10 = mat[4]
    m11 = mat[5]
    m12 = mat[6]
    m13 = mat[7]
    m20 = mat[8]
    m21 = mat[9]
    m22 = mat[10]
    m23 = mat[11]
    m30 = mat[12]
    m31 = mat[13]
    m32 = mat[14]
    m33 = mat[15]
    tr = 0.25 * (1.0 + m00 + m11 + m22)
    if tr > 0.0001:
        s = tr ** 0.5
        rotation[3] = s
        s = 1.0 / (4.0 * s)
        rotation[0] = (m12 - m21) * s
        rotation[1] = (m20 - m02) * s
        rotation[2] = (m01 - m10) * s
    elif m00 > m11 and m00 > m22:
        s = 2.0 * (1.0 + m00 - m11 - m22) ** 0.5
        rotation[0] = 0.25 * s
        s = 1.0 / s
        rotation[3] = (m12 - m21) * s
        rotation[1] = (m10 + m01) * s
        rotation[2] = (m20 + m02) * s
    elif m11 > m22:
        s = 2.0 * (1.0 + m11 - m00 - m22) ** 0.5
        rotation[1] = 0.25 * s
        s = 1.0 / s
        rotation[3] = (m20 - m02) * s
        rotation[0] = (m10 + m01) * s
        rotation[2] = (m21 + m12) * s
    else:
        s = 2.0 * (1.0 + m22 - m00 - m11) ** 0.5
        rotation[2] = 0.25 * s
        s = 1.0 / s
        rotation[3] = (m01 - m10) * s
        rotation[0] = (m20 + m02) * s
        rotation[1] = (m21 + m12) * s
    rot_len = (rotation[0] * rotation[0] + rotation[1] * rotation[1] + rotation[2] * rotation[2] + rotation[3] * rotation[3]) ** 0.5
    if rot_len != 0.0:
        f = 1.0 / rot_len
        for i in range(len(rotation)):
            rotation[i] *= f
    else:
        rotation[0] = 0.0
        rotation[1] = 0.0
        rotation[2] = 0.0
        rotation[3] = 1.0

def derive_matrix_44(v, mat):
    translation = array.array('f')
    translation.extend([0, 0, 0])
    v['mu_translation'] = translation
    rotation = array.array('f')
    rotation.extend([0, 0, 0, 0])
    v['mu_rotation'] = rotation
    scale = array.array('f')
    scale.extend([0, 0, 0])
    v['mu_scale'] = scale
    decompose_matrix_44(mat, translation, rotation, scale)
indiceTypeLengthMapping = {8: 5125, 12: 5123, 16: 5121, 20: 5123, 24: 5121, 28: 5125, 32: 5122, 36: 5121, 40: 5123, 44: 5121}
indiceTypeLengthMappingPython = {8: 'I', 12: 'H', 16: 'B', 20: 'H', 24: 'B', 28: 'i', 32: 'h', 36: 'b', 40: 'h', 44: 'b'}
indiceTypeMappingSize = {8: 4, 12: 2, 16: 1, 20: 2, 24: 1, 28: 4, 32: 2, 36: 1, 40: 2, 44: 1}
dataTypeMappingForGltf = {0: 5126, 1: 5126, 2: 5126, 3: 5126, 12: 5123, 13: 5123, 14: 5123, 15: 5123, 16: 5121, 17: 5121, 18: 5121, 19: 5121, 20: 5123, 21: 5123, 22: 5123, 23: 5123, 24: 5121, 25: 5121, 26: 5121, 27: 5121, 32: 5123, 33: 5123, 34: 5123, 35: 5123, 36: 5121, 37: 5121, 38: 5121, 39: 5121, 40: 5123, 41: 5123, 42: 5123, 43: 5123, 44: 5121, 45: 5121, 46: 5121, 47: 5121}
dataTypeMappingForPython = {0: 'f', 1: 'f', 2: 'f', 3: 'f', 8: 'I', 9: 'I', 10: 'I', 11: 'I', 12: 'H', 13: 'H', 14: 'H', 15: 'H', 16: 'B', 17: 'B', 18: 'B', 19: 'B', 20: 'H', 21: 'H', 22: 'H', 23: 'H', 24: 'B', 25: 'B', 26: 'B', 27: 'B', 28: 'i', 29: 'i', 30: 'i', 31: 'i', 32: 'h', 33: 'h', 34: 'h', 35: 'h', 36: 'b', 37: 'b', 38: 'b', 39: 'b', 40: 'h', 41: 'h', 42: 'h', 43: 'h', 44: 'b', 45: 'b', 46: 'b', 47: 'b'}
dataTypeMappingSize = {0: 4, 1: 4, 2: 4, 3: 4, 4: 2, 5: 2, 6: 2, 7: 2, 8: 4, 9: 4, 10: 4, 11: 4, 12: 2, 13: 2, 14: 2, 15: 2, 16: 1, 17: 1, 18: 1, 19: 1, 20: 2, 21: 2, 22: 2, 23: 2, 24: 1, 25: 1, 26: 1, 27: 1, 28: 4, 29: 4, 30: 4, 31: 4, 32: 2, 33: 2, 34: 2, 35: 2, 36: 1, 37: 1, 38: 1, 39: 1, 40: 2, 41: 2, 42: 2, 43: 2, 44: 1, 45: 1, 46: 1, 47: 1}
dataTypeCountMappingForGltf = {0: 'SCALAR', 1: 'VEC2', 2: 'VEC3', 3: 'VEC4'}

def render_mesh(g, cluster_mesh_info, cluster_info, cluster_header, pkg_name='', partialmaps = False, allbuffers = False, gltf_nonbinary = False, item_num = 0):
    print("Processing {0}...".format(cluster_mesh_info.filename))
    if 'PTexture2D' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PTexture2D']:
            create_texture(g, v, cluster_mesh_info, cluster_header, False, pkg_name)
    if 'PTextureCubeMap' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PTextureCubeMap']:
            create_texture(g, v, cluster_mesh_info, cluster_header, True, pkg_name)
    if 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
            if v['m_targetAssetType'] == 'PTexture2D' or v['m_targetAssetType'] == 'PTextureCubeMap':
                pass
            load_texture(v, cluster_mesh_info, pkg_name)
    if 'PParameterBuffer' in cluster_mesh_info.data_instances_by_class:
        for k in cluster_mesh_info.data_instances_by_class.keys():
            has_key = False
            if type(k) == int:
                data_instances = cluster_mesh_info.data_instances_by_class[k]
                if len(data_instances) > 0:
                    if data_instances[0]['mu_memberClass'] == 'PParameterBuffer':
                        has_key = True
            if has_key == True:
                for v in cluster_mesh_info.data_instances_by_class[k]:
                    load_shader_parameters(g, v, cluster_header)
    clsuter_basename_noext = cluster_mesh_info.filename.split('.', 1)[0]
    if 'PMaterial' in cluster_mesh_info.data_instances_by_class:
        import hashlib
        for v in cluster_mesh_info.data_instances_by_class['PMaterial']:
            load_materials_with_actual_name(v, cluster_mesh_info)
            if 'mu_name' in v:
                v['mu_materialname'] = v['mu_name']
    pdatablock_list = []
    if 'PDataBlock' in cluster_mesh_info.data_instances_by_class:
        pdatablock_list = cluster_mesh_info.data_instances_by_class['PDataBlock']
    elif 'PDataBlockD3D11' in cluster_mesh_info.data_instances_by_class:
        pdatablock_list = cluster_mesh_info.data_instances_by_class['PDataBlockD3D11']
    elif 'PDataBlockGCM' in cluster_mesh_info.data_instances_by_class:
        pdatablock_list = cluster_mesh_info.data_instances_by_class['PDataBlockGCM']
    elif 'PDataBlockGXM' in cluster_mesh_info.data_instances_by_class:
        pdatablock_list = cluster_mesh_info.data_instances_by_class['PDataBlockGXM']
    g.seek(cluster_mesh_info.vram_model_data_offset)
    indvertbuffer = memoryview(g.read())
    indvertbuffercache = {}
    if 'PMeshSegment' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PMeshSegment']:
            if 'm_mappableBuffers' in v['m_indexData']:
                v['mu_indBufferPosition'] = v['m_indexData']['m_mappableBuffers']['m_offsetInAllocatedBuffer']
                v['mu_indBufferSize'] = v['m_indexData']['m_dataSize']
            else:
                v['mu_indBufferPosition'] = v['m_indexData']['m_offsetInIndexBuffer']
                v['mu_indBufferSize'] = v['m_indexData']['m_dataSize']
            cachekey = v['mu_indBufferPosition'].to_bytes(4, byteorder='little') + v['mu_indBufferSize'].to_bytes(4, byteorder='little')
            if cachekey not in indvertbuffercache:
                indvertbuffercache[cachekey] = bytes(cast_memoryview(indvertbuffer[v['mu_indBufferPosition']:v['mu_indBufferPosition'] + v['mu_indBufferSize']], 'B'))
            v['mu_indBuffer'] = indvertbuffercache[cachekey]
    vertex_buffer_base_position = 0
    if cluster_header.platform_id == GXM_PLATFORM:
        indice_size = 0
        align_size = 0
        if 'PMeshSegment' in cluster_mesh_info.data_instances_by_class:
            for v in cluster_mesh_info.data_instances_by_class['PMeshSegment']:
                indice_size += v['mu_indBufferSize']
                align_size += v['mu_indBufferSize'] % 4
        indice_size += align_size
        vertex_buffer_base_position = indice_size
    for v in pdatablock_list:
        if 'm_mappableBuffers' in v:
            v['mu_vertBufferPosition'] = vertex_buffer_base_position + v['m_mappableBuffers']['m_offsetInAllocatedBuffer']
            v['mu_vertBufferSize'] = v['m_mappableBuffers']['m_strideInAllocatedBuffer']
        elif 'm_indexBufferSize' in cluster_mesh_info.cluster_header:
            v['mu_vertBufferPosition'] = cluster_mesh_info.cluster_header['m_indexBufferSize'] + v['m_offsetInVertexBuffer']
            v['mu_vertBufferSize'] = v['m_dataSize']
        cachekey = v['mu_vertBufferPosition'].to_bytes(4, byteorder='little') + v['mu_vertBufferSize'].to_bytes(4, byteorder='little')
        if cachekey not in indvertbuffercache:
            indvertbuffercache[cachekey] = bytes(cast_memoryview(indvertbuffer[v['mu_vertBufferPosition']:v['mu_vertBufferPosition'] + v['mu_vertBufferSize']], 'B'))
        v['mu_vertBuffer'] = indvertbuffercache[cachekey]
    if True:
        cur_min = float('inf')
        cur_max = float('-inf')
        if 'PAnimationChannelTimes' in cluster_mesh_info.data_instances_by_class:
            for v in cluster_mesh_info.data_instances_by_class['PAnimationChannelTimes']:
                timestamps = cast_memoryview(memoryview(bytearray(cast_memoryview(v['m_timeKeys']['m_els'][:v['m_keyCount']], 'B'))), 'f')
                v['mu_animation_timestamps'] = timestamps
                for x in timestamps:
                    if x < cur_min:
                        cur_min = x
                    if x > cur_max:
                        cur_max = x
        if 'PAnimationClip' in cluster_mesh_info.data_instances_by_class:
            for v in cluster_mesh_info.data_instances_by_class['PAnimationClip']:
                timestamps = cast_memoryview(memoryview(bytearray(2 * 4)), 'f')
                timestamps[0] = v['m_constantChannelStartTime']
                timestamps[1] = v['m_constantChannelEndTime']
                v['mu_animation_timestamps'] = timestamps
                for x in timestamps:
                    if x < cur_min:
                        cur_min = x
                    if x > cur_max:
                        cur_max = x
    map_bone_name_to_matrix = {}
    if 'PMesh' in cluster_mesh_info.data_instances_by_class:
        data_instances = cluster_mesh_info.data_instances_by_class['PMesh']
        for v in cluster_mesh_info.data_instances_by_class['PMesh']:
            bonePosePtr = v['m_defaultPose']['m_els']
            bonePoseName = v['m_matrixNames']['m_els']
            bonePoseInd = v['m_matrixParents']['m_els']
            boneSkelMat = v['m_skeletonMatrices']['m_els']
            boneSkelBounds = v['m_skeletonBounds']['m_els']
            boneSkelMap = {}
            boneSkelInverseMap = {}
            matrix_hierarchy_only_indices = []
            if boneSkelBounds != None and len(boneSkelBounds) > 0 and (type(boneSkelBounds) != int) and ('m_els' not in boneSkelMat):
                bone_hierarchy_indices = []
                for i in range(len(boneSkelBounds)):
                    hierarchy_matrix_index = boneSkelBounds[i]['m_hierarchyMatrixIndex']
                    inverse_bind_matrix_data = boneSkelMat[i]['m_elements']
                    bone_hierarchy_indices.append(hierarchy_matrix_index)
                    matrix_inverted = invert_matrix_44(inverse_bind_matrix_data)
                    if matrix_inverted != None:
                        boneSkelMap[hierarchy_matrix_index] = matrix_inverted
                        boneSkelInverseMap[hierarchy_matrix_index] = inverse_bind_matrix_data
                matrix_hierarchy_only_indices = [i for i in range(len(boneSkelMat)) if i not in bone_hierarchy_indices]
            hierarchy_additional_inverse_bind_matrices = []
            hierarchy_additional_names = []
            if len(bonePosePtr) > 0 and 'm_els' not in bonePosePtr and (type(bonePosePtr[0]) != int):
                skinMat = [bonePosePtr[i]['m_elements'] for i in range(len(bonePosePtr))]
                skinReducedMatrix = {}
                skinRootName = None
                if True:
                    jump_count = 0
                    jump_count_max = len(boneSkelBounds)
                    cur_parent_index = len(boneSkelBounds) - 1
                    while cur_parent_index >= 0 and jump_count < jump_count_max:
                        if cur_parent_index == bonePoseInd[cur_parent_index]:
                            break
                        nex_parent_index = bonePoseInd[cur_parent_index]
                        if nex_parent_index < 0:
                            break
                        cur_parent_index = nex_parent_index
                    if cur_parent_index >= 0 and len(bonePoseName) > cur_parent_index:
                        skinRootName = bonePoseName[cur_parent_index]['m_buffer']
                for sm in range(len(skinMat)):
                    pm = bonePoseInd[sm]
                    pn = 'TERoots'
                    if pm >= 0 and len(bonePoseName) > pm:
                        pn = bonePoseName[pm]['m_buffer']
                    bn = 'TERoots'
                    if sm >= 0 and len(bonePoseName) > sm:
                        bn = bonePoseName[sm]['m_buffer']
                    cur_matrix = skinMat[sm]
                    cur_reduced_matrix = None
                    if sm in boneSkelMap:
                        cur_matrix = boneSkelMap[sm]
                        if pm >= 0 and pm in boneSkelInverseMap:
                            cur_reduced_matrix = multiply_array_as_4x4_matrix(boneSkelInverseMap[pm], cur_matrix)
                    else:
                        jump_count = 0
                        jump_count_max = len(boneSkelBounds)
                        cur_parent_index = pm
                        while cur_parent_index != -1 and len(skinMat) > cur_parent_index and (jump_count < jump_count_max):
                            cur_parent_mat = skinMat[cur_parent_index]
                            if cur_parent_index in boneSkelMap:
                                cur_parent_mat = boneSkelMap[cur_parent_index]
                                cur_matrix = multiply_array_as_4x4_matrix(cur_parent_mat, cur_matrix)
                                break
                            cur_matrix = multiply_array_as_4x4_matrix(cur_parent_mat, cur_matrix)
                            if cur_parent_index == bonePoseInd[cur_parent_index]:
                                break
                            cur_parent_index = bonePoseInd[cur_parent_index]
                    cluster_mesh_info.bone_names.append(bn)
                    if cur_reduced_matrix != None:
                        skinReducedMatrix[bn] = cur_reduced_matrix
                    if sm in matrix_hierarchy_only_indices and bn != '':
                        hierarchy_additional_inverse_bind_matrices.append(invert_matrix_44(cur_matrix))
                        hierarchy_additional_names.append(bn)
                v['mu_reduced_matrix'] = skinReducedMatrix
                v['mu_root_matrix_name'] = skinRootName
                v['mu_hierarchy_additional_inverse_bind_matrices'] = hierarchy_additional_inverse_bind_matrices
                v['mu_hierarchy_additional_names'] = hierarchy_additional_names
            if type(v['m_meshSegments']['m_els']) == list:
                for m in v['m_meshSegments']['m_els']:
                    boneRemapForHierarchy = cast_memoryview(memoryview(bytearray(len(m['m_skinBones']['m_els']) * 2)), 'H')
                    boneRemapForSkeleton = cast_memoryview(memoryview(bytearray(len(m['m_skinBones']['m_els']) * 2)), 'H')
                    if len(bonePosePtr) > 0 and 'm_els' not in bonePosePtr and (len(m['m_skinBones']['m_els']) > 0) and (type(m['m_skinBones']['m_els'][0]) != int):
                        m['m_gltfSkinBoneMap'] = [x['m_skeletonMatrixIndex'] for x in m['m_skinBones']['m_els']]
                        for i in range(len(m['m_skinBones']['m_els'])):
                            sb = m['m_skinBones']['m_els'][i]
                            boneRemapForHierarchy[i] = sb['m_hierarchyMatrixIndex']
                            boneRemapForSkeleton[i] = sb['m_skeletonMatrixIndex']
                    for vertexData in m['m_vertexData']['m_els']:
                        streamInfo = vertexData['m_streams']['m_els'][0]
                        datatype = streamInfo['m_type']
                        dataTypeCount = datatype % 4 + 1
                        blobdata = vertexData['mu_vertBuffer']
                        singleelementsize = dataTypeMappingSize[datatype]
                        blobstride = vertexData['m_stride']
                        streamoffset = vertexData['m_streams']['m_els'][0]['m_offset']
                        elementcount = vertexData['m_elementCount']
                        if streamInfo['m_renderDataType'] == 'SkinIndices':
                            if dataTypeCount * singleelementsize != blobstride:
                                deinterleaved_stride = singleelementsize * dataTypeCount
                                deinterleaved_data = memoryview(bytearray(deinterleaved_stride * elementcount))
                                for i in range(elementcount):
                                    deinterleaved_data[deinterleaved_stride * i:deinterleaved_stride * (i + 1)] = blobdata[blobstride * i + streamoffset:blobstride * i + streamoffset + deinterleaved_stride]
                                blobstride = dataTypeCount * dataTypeMappingSize[datatype]
                                blobdata = bytes(deinterleaved_data)
                            elif dataTypeCount * singleelementsize * elementcount != len(blobdata):
                                blobdata = blobdata[streamoffset:streamoffset + dataTypeCount * singleelementsize * elementcount]
                            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                                blobdatabyteswap = bytearray(blobdata)
                                bytearray_byteswap(blobdatabyteswap, singleelementsize)
                                blobdata = blobdatabyteswap
                            skinInd = cast_memoryview(memoryview(blobdata), dataTypeMappingForPython[datatype])
                            vertexData['mu_originalVertBufferSkeleton'] = skinInd.tobytes()
                            if len(boneRemapForHierarchy) > 0:
                                remapIndForHierarchy = cast_memoryview(memoryview(bytearray(len(skinInd) * 2)), 'H')
                                for i in range(len(skinInd)):
                                    mb = skinInd[i]
                                    remapIndForHierarchy[i] = boneRemapForHierarchy[mb]
                                vertexData['mu_remappedVertBufferHierarchy'] = bytes(cast_memoryview(remapIndForHierarchy, 'B'))
                            if len(boneRemapForSkeleton) > 0:
                                remapIndForSkeleton = cast_memoryview(memoryview(bytearray(len(skinInd) * 2)), 'H')
                                for i in range(len(skinInd)):
                                    mb = skinInd[i]
                                    remapIndForSkeleton[i] = boneRemapForSkeleton[mb]
                                vertexData['mu_remappedVertBufferSkeleton'] = bytes(cast_memoryview(remapIndForSkeleton, 'B'))
    if 'PNode' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PNode']:
            v['mu_matrixToUse'] = v['m_localMatrix']['m_elements']

    def get_all_node_children(deposit_list, parent_of_node):
        current_children = [child for child in cluster_mesh_info.data_instances_by_class['PNode'] if child['m_parent'] is parent_of_node]
        deposit_list.extend(current_children)
        for child in current_children:
            get_all_node_children(deposit_list, child)

    def map_all_node_children(deposit_dict, in_list):
        for node in in_list:
            deposit_dict[node['m_name']] = node
    if 'PNode' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PNode']:
            derive_matrix_44(v, v['mu_matrixToUse'])
    if True:
        gltf_export(g, cluster_mesh_info, cluster_info, cluster_header, pdatablock_list, pkg_name, partialmaps = partialmaps, allbuffers = allbuffers, gltf_nonbinary = gltf_nonbinary, item_num = item_num)
        return

shader_material_switches = {}
animation_metadata = {}

def gltf_export(g, cluster_mesh_info, cluster_info, cluster_header, pdatablock_list, pkg_name='', partialmaps = False, allbuffers = False, gltf_nonbinary = False, item_num = 0):
    global shader_material_switches
    global animation_metadata
    import json
    # Use the presence of metadata files to determine which .dae asset we are processing
    if item_num == 0:
        metadata_json_name = pkg_name + os.sep + "metadata.json" # First file will be metadata.json
        physics_json_name = pkg_name + os.sep + "physics_data.json" # First file will be metadata.json
        mesh_folder_name = pkg_name + os.sep + "meshes"
    else:
        metadata_json_name = pkg_name + os.sep + "metadata_{0}.json".format(str(item_num).zfill(2))
        physics_json_name = pkg_name + os.sep + "physics_data_{0}.json".format(str(item_num).zfill(2))
        mesh_folder_name = pkg_name + os.sep + "meshes_{0}".format(str(item_num).zfill(2))
    metadata_json = {'name': cluster_mesh_info.filename.split('.', 1)[0], 'pkg_name': pkg_name}
    metadata_json['compression'] = cluster_mesh_info.storage_media.storage2.compression_flag
    if not os.path.exists(mesh_folder_name) and 'PMeshInstance' in cluster_mesh_info.data_instances_by_class:
        os.mkdir(mesh_folder_name)
    asset = {}
    asset['generator'] = 'ed8pkg2glb'
    asset['version'] = '2.0'
    cluster_mesh_info.gltf_data['asset'] = asset
    extensionsUsed = []
    cluster_mesh_info.gltf_data['extensionsUsed'] = extensionsUsed
    buffers = []
    need_embed = False
    if True:
        need_embed = True
    if need_embed == False:
        need_embed = cluster_header.cluster_marker == NOEPY_HEADER_BE
    if need_embed == False:
        for v in pdatablock_list:
            datatype = v['m_streams']['m_els'][0]['m_type']
            if datatype >= 4 and datatype <= 7:
                need_embed = True
                break
    buffer0 = {}
    buffers.append(buffer0)
    if need_embed == False:
        buffer1 = {}
        buffer1['uri'] = cluster_mesh_info.filename
        g.seek(0, os.SEEK_END)
        buffer1['byteLength'] = g.tell()
        buffers.append(buffer1)
    cluster_mesh_info.gltf_data['buffers'] = buffers
    bufferviews = []
    accessors = []
    embedded_giant_buffer = []
    embedded_giant_buffer_length = [0]

    def add_bufferview_embed(data, stride=None):
        bufferview = {}
        bufferview['buffer'] = 0
        bufferview['byteOffset'] = embedded_giant_buffer_length[0]
        bufferview['byteLength'] = len(data)
        if stride != None:
            bufferview['byteStride'] = stride
        embedded_giant_buffer.append(data)
        embedded_giant_buffer_length[0] += len(data)
        padding_length = 4 - len(data) % 4
        embedded_giant_buffer.append(b'\x00' * padding_length)
        embedded_giant_buffer_length[0] += padding_length
        bufferviews.append(bufferview)

    def add_bufferview_reference(position, size, stride=None):
        bufferview = {}
        bufferview['buffer'] = 1
        bufferview['byteOffset'] = position
        bufferview['byteLength'] = size
        if stride != None:
            bufferview['byteStride'] = stride
        bufferviews.append(bufferview)
    dummy_color_accessor_index = {}
    dummy_color_float4 = array.array('f')
    dummy_color_float4.append(1.0)
    dummy_color_float4_blob = bytes(dummy_color_float4)

    def get_accessor_color_dummy(count):
        if count in dummy_color_accessor_index:
            return dummy_color_accessor_index[count]
        blobdata = dummy_color_float4_blob * count
        accessor = {}
        accessor['bufferView'] = len(bufferviews)
        accessor['componentType'] = 5126
        accessor['type'] = 'VEC4'
        accessor['count'] = count
        accessor_index = len(accessors)
        accessors.append(accessor)
        add_bufferview_embed(data=blobdata)
        dummy_color_accessor_index[count] = accessor_index
        return accessor_index
    if 'PMeshSegment' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PMeshSegment']:
            accessor = {}
            accessor['bufferView'] = len(bufferviews)
            indiceTypeForGltf = 5123
            if v['m_indexData']['m_type'] in indiceTypeLengthMapping:
                indiceTypeForGltf = indiceTypeLengthMapping[v['m_indexData']['m_type']]
            elementcount = v['m_indexData']['m_elementCount']
            accessor['componentType'] = indiceTypeForGltf
            accessor['min'] = [v['m_indexData']['m_minimumIndex']]
            accessor['max'] = [v['m_indexData']['m_maximumIndex']]
            accessor['type'] = 'SCALAR'
            accessor['count'] = elementcount
            v['mu_gltfAccessorIndex'] = len(accessors)
            if need_embed:
                blobdata = v['mu_indBuffer']
                singleelementsize = indiceTypeMappingSize[v['m_indexData']['m_type']]
                if singleelementsize * elementcount != len(blobdata):
                    blobdata = blobdata[:singleelementsize * elementcount]
                if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                    blobdatabyteswap = bytearray(blobdata)
                    bytearray_byteswap(blobdatabyteswap, singleelementsize)
                    blobdata = blobdatabyteswap
                add_bufferview_embed(data=blobdata)
            else:
                add_bufferview_reference(position=cluster_mesh_info.vram_model_data_offset + v['mu_indBufferPosition'], size=v['mu_indBufferSize'])
            accessors.append(accessor)
    #if 'PMesh' in cluster_mesh_info.data_instances_by_class:
        #for v in cluster_mesh_info.data_instances_by_class['PMesh']:
            #matrix_list = []
            #if 'm_skeletonMatrices' in v and type(v['m_skeletonMatrices']['m_els']) == list:
                #for vv in v['m_skeletonMatrices']['m_els']:
                    #matrix_list.append(bytes(cast_memoryview(vv['m_elements'], 'B')))
            #if len(matrix_list) > 0:
                #blobdata = b''.join(matrix_list)
                #accessor = {}
                #accessor['bufferView'] = len(bufferviews)
                #accessor['componentType'] = 5126
                #accessor['type'] = 'MAT4'
                #accessor['count'] = len(matrix_list)
                #v['mu_gltfAccessorForInverseBindMatrixIndex'] = len(accessors)
                #add_bufferview_embed(data=blobdata)
                #accessors.append(accessor)
    if 'PMeshSegment' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PMeshSegment']:
            for vvv in v['m_vertexData']['m_els']:
                for vvvv in vvv['m_streams']['m_els']:
                    #if vvvv['m_renderDataType'] == 'SkinIndices' and 'mu_remappedVertBufferSkeleton' in vvv:
                        #blobdata = vvv['mu_remappedVertBufferSkeleton']
                        #accessor = {}
                        #accessor['bufferView'] = len(bufferviews)
                        #accessor['componentType'] = 5123
                        #accessor['type'] = 'VEC4'
                        #accessor['count'] = vvv['m_elementCount']
                        #vvvv['mu_gltfAccessorForRemappedSkinIndiciesIndex'] = len(accessors)
                        #add_bufferview_embed(data=blobdata)
                        #accessors.append(accessor)
                    if (vvvv['m_renderDataType'] == 'Tangent' or vvvv['m_renderDataType'] == 'SkinnableTangent') and 'mu_expandedHandednessTangent' in vvv:
                        blobdata = vvv['mu_expandedHandednessTangent']
                        accessor = {}
                        accessor['bufferView'] = len(bufferviews)
                        accessor['componentType'] = 5126
                        accessor['type'] = 'VEC4'
                        accessor['count'] = vvv['m_elementCount']
                        vvvv['mu_gltfAccessorForExpandedHandednessTangent'] = len(accessors)
                        add_bufferview_embed(data=blobdata)
                        accessors.append(accessor)
    for v in pdatablock_list:
        accessor = {}
        accessor['bufferView'] = len(bufferviews)
        dataTypeForGltf = 5123
        datatype = v['m_streams']['m_els'][0]['m_type']
        if datatype in dataTypeMappingForGltf:
            dataTypeForGltf = dataTypeMappingForGltf[datatype]
        elif (datatype >= 4 and datatype <= 7) and need_embed:
            dataTypeForGltf = dataTypeMappingForGltf[datatype - 4]
        dataTypeCount = datatype % 4 + 1
        streamoffset = v['m_streams']['m_els'][0]['m_offset']
        elementcount = v['m_elementCount']
        accessor['componentType'] = dataTypeForGltf
        accessor['type'] = dataTypeCountMappingForGltf[datatype % 4]
        accessor['count'] = elementcount
        v['mu_gltfAccessorIndex'] = len(accessors)
        if need_embed:
            blobdata = v['mu_vertBuffer']
            singleelementsize = dataTypeMappingSize[datatype]
            blobstride = v['m_stride']
            if dataTypeCount * singleelementsize != blobstride:
                deinterleaved_stride = singleelementsize * dataTypeCount
                deinterleaved_data = memoryview(bytearray(deinterleaved_stride * elementcount))
                for i in range(elementcount):
                    deinterleaved_data[deinterleaved_stride * i:deinterleaved_stride * (i + 1)] = blobdata[blobstride * i + streamoffset:blobstride * i + streamoffset + deinterleaved_stride]
                blobstride = dataTypeCount * dataTypeMappingSize[datatype]
                blobdata = bytes(deinterleaved_data)
            elif dataTypeCount * singleelementsize * elementcount != len(blobdata):
                blobdata = blobdata[streamoffset:streamoffset + dataTypeCount * singleelementsize * elementcount]
            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                blobdatabyteswap = bytearray(blobdata)
                bytearray_byteswap(blobdatabyteswap, singleelementsize)
                blobdata = blobdatabyteswap
            if datatype >= 4 and datatype <= 7:
                blobdatafloatextend = cast_memoryview(memoryview(bytearray(dataTypeCount * elementcount * 4)), 'f')
                for i in range(dataTypeCount * elementcount):
                    blobdatafloatextend[i] = struct.unpack('e', blobdata[i * 2:i * 2 + 2])[0]
                blobdata = bytes(cast_memoryview(blobdatafloatextend, 'B'))
                blobstride = dataTypeCount * 4
            add_bufferview_embed(data=blobdata, stride=blobstride)
        else:
            add_bufferview_reference(position=cluster_mesh_info.vram_model_data_offset + v['m_streams']['m_els'][0]['m_offset'] + v['mu_vertBufferPosition'], size=v['mu_vertBufferSize'], stride=v['m_stride'])
        accessors.append(accessor)
    animation_time_accessors = []
    if 'PAnimationChannelTimes' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationChannelTimes']:
            blobdata = bytes(cast_memoryview(v['mu_animation_timestamps'], 'B'))
            if 0.0 != 0.0:
                blobdatafloatextend = cast_memoryview(memoryview(bytearray(blobdata)), 'f')
                if True:
                    float_divided = 1.0 / 0.0
                    for i in range(len(blobdatafloatextend)):
                        blobdatafloatextend[i] += float_divided
                    blobdata = bytes(cast_memoryview(blobdatafloatextend, 'B'))
            accessor = {}
            accessor['bufferView'] = len(bufferviews)
            accessor['componentType'] = 5126
            accessor['type'] = 'SCALAR'
            accessor['count'] = v['m_keyCount']
            cur_min = float('inf')
            cur_max = float('-inf')
            timez = cast_memoryview(memoryview(blobdata), 'f')
            for x in timez:
                if x < cur_min:
                    cur_min = x
                if x > cur_max:
                    cur_max = x
            accessor['min'] = [cur_min]
            accessor['max'] = [cur_max]
            v['mu_gltfAccessorIndex'] = len(accessors)
            animation_time_accessors.append(len(accessors))
            add_bufferview_embed(data=blobdata)
            accessors.append(accessor)
    if 'PAnimationChannel' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationChannel']:
            blobdata = bytes(cast_memoryview(v['m_valueKeys']['m_els'], 'B'))
            accessor = {}
            accessor['bufferView'] = len(bufferviews)
            accessor['componentType'] = 5126
            if v['m_keyType'] == 'Translation' or v['m_keyType'] == 'Scale':
                accessor['type'] = 'VEC3'
                accessor['count'] = v['m_keyCount']
            elif v['m_keyType'] == 'Rotation':
                accessor['type'] = 'VEC4'
                accessor['count'] = v['m_keyCount']
            else:
                accessor['type'] = 'SCALAR'
                accessor['count'] = v['m_keyCount']
            v['mu_gltfAccessorIndex'] = len(accessors)
            accessors.append(accessor)
            add_bufferview_embed(data=blobdata)
    if 'PAnimationConstantChannel' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationConstantChannel']:
            tmparray = bytes(v['m_value'])
            if v['m_keyType'] == 'Scale' or v['m_keyType'] == 'Translation':
                tmparray = tmparray[:-4]
            blobdata = tmparray * 2
            accessor = {}
            accessor['bufferView'] = len(bufferviews)
            accessor['componentType'] = 5126
            if v['m_keyType'] == 'Translation' or v['m_keyType'] == 'Scale':
                accessor['type'] = 'VEC3'
                accessor['count'] = 2
            elif v['m_keyType'] == 'Rotation':
                accessor['type'] = 'VEC4'
                accessor['count'] = 2
            else:
                accessor['type'] = 'SCALAR'
                accessor['count'] = 2
            v['mu_gltfAccessorIndex'] = len(accessors)
            accessors.append(accessor)
            add_bufferview_embed(data=blobdata)
    if 'PAnimationClip' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationClip']:
            tmparray = v['mu_animation_timestamps']
            blobdata = bytes(cast_memoryview(tmparray, 'B'))
            accessor = {}
            accessor['bufferView'] = len(bufferviews)
            accessor['componentType'] = 5126
            accessor['type'] = 'SCALAR'
            accessor['count'] = 2
            accessor['min'] = [tmparray[0]]
            accessor['max'] = [tmparray[1]]
            v['mu_gltfAccessorIndex'] = len(accessors)
            animation_time_accessors.append(len(accessors))
            accessors.append(accessor)
            add_bufferview_embed(data=blobdata)
    images = []
    images_meta = {}
    if 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
            if v['m_targetAssetType'] == 'PTexture2D':
                image = {}
                image_path = os.path.basename(v['m_id'])
                image_name = image_path.rsplit('.', maxsplit=2)[0]
                if True:
                    image_name += '.png'
                if cluster_mesh_info.storage_media.check_existent_storage(image_name):
                    with cluster_mesh_info.storage_media.open(image_name, 'rb') as f:
                        blobdata = f.read()
                        image['bufferView'] = len(bufferviews)
                        if True:
                            image['mimeType'] = 'image/png'
                        add_bufferview_embed(data=blobdata)
                else:
                    image['uri'] = v['m_id'] #image_name
                v['mu_gltfImageIndex'] = len(images)
                images.append(image)
            if v['m_targetAssetType'] in ['PTexture2D', 'PTextureCubeMap']:
                images_meta[v['m_id']] = v['m_targetAssetType']
    cluster_mesh_info.gltf_data['images'] = images
    samplers = []
    filter_map = {0: 9728, 1: 9729, 2: 9984, 3: 9985, 4: 9986, 5: 9987}
    wrap_map = {0: 33071, 1: 10497, 2: 33071, 3: 33071, 4: 33648}
    if 'PSamplerState' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PSamplerState']:
            sampler = {}
            if v['m_magFilter'] in filter_map:
                sampler['magFilter'] = filter_map[v['m_magFilter']]
            if v['m_minFilter'] in filter_map:
                sampler['minFilter'] = filter_map[v['m_minFilter']]
            if v['m_wrapS'] in wrap_map:
                sampler['wrapS'] = wrap_map[v['m_wrapS']]
            if v['m_wrapT'] in wrap_map:
                sampler['wrapT'] = wrap_map[v['m_wrapT']]
            v['mu_gltfSamplerIndex'] = len(samplers)
            samplers.append(sampler)
    cluster_mesh_info.gltf_data['samplers'] = samplers
    textures = []
    if 'PParameterBuffer' in cluster_mesh_info.data_instances_by_class:
        for k in cluster_mesh_info.data_instances_by_class.keys():
            has_key = False
            if type(k) == int:
                data_instances = cluster_mesh_info.data_instances_by_class[k]
                if len(data_instances) > 0:
                    if data_instances[0]['mu_memberClass'] == 'PParameterBuffer':
                        has_key = True
            if has_key == True:
                for parameter_buffer in cluster_mesh_info.data_instances_by_class[k]:
                    shaderparam = parameter_buffer['mu_shaderParameters']
                    if True:
                        samplerstate = None
                        if 'DiffuseMapSamplerS' in shaderparam and type(shaderparam['DiffuseMapSamplerS']) == dict:
                            samplerstate = shaderparam['DiffuseMapSamplerS']
                        elif 'DiffuseMapSamplerSampler' in shaderparam and type(shaderparam['DiffuseMapSamplerSampler']) == dict:
                            samplerstate = shaderparam['DiffuseMapSamplerSampler']
                        if 'DiffuseMapSampler' in parameter_buffer['mu_shaderParameters'] and type(parameter_buffer['mu_shaderParameters']['DiffuseMapSampler']) == str:
                            if 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
                                for vv in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
                                    if vv['m_id'] == parameter_buffer['mu_shaderParameters']['DiffuseMapSampler'] and 'mu_gltfImageIndex' in vv:
                                        texture = {}
                                        if samplerstate != None:
                                            texture['sampler'] = samplerstate['mu_gltfSamplerIndex']
                                        texture['source'] = vv['mu_gltfImageIndex']
                                        parameter_buffer['mu_gltfTextureDiffuseIndex'] = len(textures)
                                        textures.append(texture)
                                        break
                    if True:
                        samplerstate = None
                        if 'NormalMapSamplerS' in shaderparam and type(shaderparam['NormalMapSamplerS']) == dict:
                            samplerstate = shaderparam['NormalMapSamplerS']
                        elif 'NormalMapSamplerSampler' in shaderparam and type(shaderparam['NormalMapSamplerSampler']) == dict:
                            samplerstate = shaderparam['NormalMapSamplerSampler']
                        if 'NormalMapSampler' in parameter_buffer['mu_shaderParameters'] and type(parameter_buffer['mu_shaderParameters']['NormalMapSampler']) == str:
                            if 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
                                for vv in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
                                    if vv['m_id'] == parameter_buffer['mu_shaderParameters']['NormalMapSampler'] and 'mu_gltfImageIndex' in vv:
                                        texture = {}
                                        if samplerstate != None:
                                            texture['sampler'] = samplerstate['mu_gltfSamplerIndex']
                                        texture['source'] = vv['mu_gltfImageIndex']
                                        parameter_buffer['mu_gltfTextureNormalIndex'] = len(textures)
                                        textures.append(texture)
                                        break
                    if True:
                        samplerstate = None
                        if 'SpecularMapSamplerS' in shaderparam and type(shaderparam['SpecularMapSamplerS']) == dict:
                            samplerstate = shaderparam['SpecularMapSamplerS']
                        elif 'SpecularMapSamplerSampler' in shaderparam and type(shaderparam['SpecularMapSamplerSampler']) == dict:
                            samplerstate = shaderparam['SpecularMapSamplerSampler']
                        if 'SpecularMapSampler' in parameter_buffer['mu_shaderParameters'] and type(parameter_buffer['mu_shaderParameters']['SpecularMapSampler']) == str:
                            if 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
                                for vv in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
                                    if vv['m_id'] == parameter_buffer['mu_shaderParameters']['SpecularMapSampler'] and 'mu_gltfImageIndex' in vv:
                                        texture = {}
                                        if samplerstate != None:
                                            texture['sampler'] = samplerstate['mu_gltfSamplerIndex']
                                        texture['source'] = vv['mu_gltfImageIndex']
                                        parameter_buffer['mu_gltfTextureSpecularIndex'] = len(textures)
                                        textures.append(texture)
                                        break
    cluster_mesh_info.gltf_data['textures'] = textures
    materials = []
    materials_struct = {}
    if 'PMaterial' in cluster_mesh_info.data_instances_by_class:
        filter_map = ['NEAREST', 'LINEAR', 'NEAREST_MIPMAP_NEAREST', 'LINEAR_MIPMAP_NEAREST', 'NEAREST_MIPMAP_LINEAR', 'LINEAR_MIPMAP_LINEAR']
        wrap_map = ['CLAMP','REPEAT','CLAMP_TO_EDGE','CLAMP_TO_BORDER','MIRROR']
        for v in cluster_mesh_info.data_instances_by_class['PMaterial']:
            material = {}
            material['name'] = v['mu_materialname']
            parameter_buffer = v['m_parameterBuffer']
            if 'mu_gltfTextureDiffuseIndex' in parameter_buffer:
                textureInfo = {}
                textureInfo['index'] = parameter_buffer['mu_gltfTextureDiffuseIndex']
                pbrMetallicRoughness = {}
                pbrMetallicRoughness['baseColorTexture'] = textureInfo
                pbrMetallicRoughness['metallicFactor'] = 0.0
                material['pbrMetallicRoughness'] = pbrMetallicRoughness
            if 'mu_gltfTextureNormalIndex' in parameter_buffer:
                normalTextureInfo = {}
                normalTextureInfo['index'] = parameter_buffer['mu_gltfTextureNormalIndex']
                material['normalTexture'] = normalTextureInfo
            v['mu_gltfMaterialIndex'] = len(materials)
            materials.append(material)
            if 'dae' in cluster_mesh_info.filename and not (v['mu_materialname'][-8:] == '-Skinned' or v['mu_materialname'][-12:] == '-VertexColor'):
                material = {}
                material['shader'] = v['m_parameterBuffer']['m_effectVariant']['m_id']
                related_materials = {}
                related_materials.update({'skinned_shader':x for x in cluster_mesh_info.data_instances_by_class['PMaterial'] if (x['mu_materialname'] == v['mu_materialname']+'-Skinned')})
                related_materials.update({'vertex_color_shader':x for x in cluster_mesh_info.data_instances_by_class['PMaterial'] if (x['mu_materialname'] == v['mu_materialname']+'-VertexColor')})
                related_materials.update({'skinned_vertex_color_shader':x for x in cluster_mesh_info.data_instances_by_class['PMaterial'] if (x['mu_materialname'] == v['mu_materialname']+'-Skinned-VertexColor')})
                if len(related_materials) > 0:
                    for related_material in related_materials:
                        material[related_material] = related_materials[related_material]['m_parameterBuffer']['m_effectVariant']['m_id']
                shaderParameters = {key:list(value) if isinstance(value, memoryview) else value for (key,value) in v['m_parameterBuffer']['mu_shaderParameters'].items()}
                material['shaderTextures'] = {k:v for (k,v) in shaderParameters.items() if isinstance(v,str)}
                material['non2Dtextures'] = {}
                for texture in material['shaderTextures']:
                    if material['shaderTextures'][texture] in images_meta.keys() and images_meta[material['shaderTextures'][texture]] != "PTexture2D":
                        material['non2Dtextures'][texture] = images_meta[material['shaderTextures'][texture]]
                if len(material['non2Dtextures']) < 1:
                    del(material['non2Dtextures'])
                material['shaderParameters'] = {k:v for (k,v) in shaderParameters.items() if isinstance(v,list)}
                material['shaderSamplerDefs'] = {k:v for (k,v) in shaderParameters.items() if isinstance(v,dict)}
                for samplerDef in material['shaderSamplerDefs']:
                    material['shaderSamplerDefs'][samplerDef] =\
                        {k:wrap_map[v] if 'wrap' in k else filter_map[v] if 'Filter' in k else v for (k,v) in material['shaderSamplerDefs'][samplerDef].items()}
                shader_name = material['shader'].replace("shaders/","")
                if shader_name in shader_material_switches.keys():
                    material['shaderSwitches'] = shader_material_switches[shader_name]
                materials_struct[v['mu_materialname']] = material
        if len(materials_struct.keys()) > 0:
            metadata_json['materials'] = materials_struct

    if 'PMaterialSwitch' in cluster_mesh_info.data_instances_by_class:
        shader_material_switches[cluster_mesh_info.filename.split('.phyre')[0]] =\
            {x["m_name"]:"0" if x["m_value"] == "" else x["m_value"] for x in cluster_mesh_info.data_instances_by_class['PMaterialSwitch']}

    cluster_mesh_info.gltf_data['materials'] = materials
    meshes = []
    mesh_instances = []
    RGBAD = ['R','G','B','A','D']
    bytesize = {5120:'8', 5121: '8', 5122: '16', 5123: '16', 5125: '32', 5126: '32'}
    elementtype = {5120: 'SINT', 5121: 'UINT', 5122: 'SINT', 5123: 'UINT', 5125: 'UINT', 5126: 'FLOAT'}
    numelements = {'SCALAR':1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
    semantics = {'Vertex': 'POSITION', 'Normal': 'NORMAL', 'ST': 'TEXCOORD', 'Tangent': 'TANGENT',\
        'Binormal': 'BINORMAL', 'Color': 'COLOR', 'SkinWeights': 'BLENDWEIGHT', 'SkinIndices': 'BLENDINDICES'}
    if 'PMeshInstance' in cluster_mesh_info.data_instances_by_class:
        mesh_instances = cluster_mesh_info.data_instances_by_class['PMeshInstance']
    for t in mesh_instances:
        curmesh = t['m_mesh']
        t['mu_gltfMeshSegmentsIndicies'] = []
        primitives = []
        for tt in range(len(curmesh['m_meshSegments']['m_els'])):
            primitive = {}
            fmt = {'stride': '0', 'topology': 'trianglelist',\
                'format': "DXGI_FORMAT_R{0}_UINT".format(indiceTypeMappingSize[curmesh['m_meshSegments']['m_els'][tt]['m_indexData']['m_type']] * 8),\
                'elements': []}
            elements = []
            vb = []
            m = curmesh['m_meshSegments']['m_els'][tt]
            if curmesh['m_defaultMaterials']['m_materials']['m_u'] != None and len(curmesh['m_defaultMaterials']['m_materials']['m_u']) > m['m_materialIndex']:
                mat = curmesh['m_defaultMaterials']['m_materials']['m_u'][m['m_materialIndex']]
                if mat != None:
                    primitive['material'] = mat['mu_gltfMaterialIndex']
            segmentcontext = t['m_segmentContext']['m_els'][tt]
            attributes = {}
            colorCount = 0
            tangentCount = 0
            uvTangentBinormalCount = {'ST':0,'Tangent':0,'Binormal':0, 'Color':0}
            valid_uvs = list(set([x['m_inputSet'] for x in t['m_segmentContext']['m_els'][tt]['m_streamBindings']['m_u']]))
            AlignedByteOffset = 0
            for i in range(len(m['m_vertexData']['m_els'])):
                vertexData = m['m_vertexData']['m_els'][i]
                componentType = accessors[vertexData['mu_gltfAccessorIndex']]['componentType']
                accType = accessors[vertexData['mu_gltfAccessorIndex']]['type']
                stride = numelements[accType] * (int(bytesize[componentType]) // 8)
                dxgi_format = "".join([RGBAD[j]+bytesize[componentType] for j in range(numelements[accType])])\
                    + '_' + elementtype[componentType]
                streamInfo = vertexData['m_streams']['m_els'][0]
                vertexBuffer = vertexData['mu_vertBuffer']
                if partialmaps == False and streamInfo['m_renderDataType'] == 'SkinIndices':
                    dxgi_format = "".join([RGBAD[j]+'16' for j in range(numelements[accType])]) + '_UINT'
                    vertexBuffer = vertexData['mu_remappedVertBufferSkeleton']
                    stride = numelements[accType] * 2
                if streamInfo['m_renderDataType'].replace('Skinnable','') in ['ST', 'Tangent', 'Binormal', 'Color']:
                    semantic_index = uvTangentBinormalCount[streamInfo['m_renderDataType'].replace('Skinnable','')]
                    uvTangentBinormalCount[streamInfo['m_renderDataType'].replace('Skinnable','')] += 1
                else:
                    semantic_index = 0
                if semantic_index > 7 and allbuffers == False:
                    continue
                element = {'id': str(i), 'SemanticName': semantics[streamInfo['m_renderDataType'].replace('Skinnable','')],\
                    'SemanticIndex': str(semantic_index), 'Format': dxgi_format, 'InputSlot': '0',\
                    'AlignedByteOffset': str(AlignedByteOffset),\
                    'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}
                with io.BytesIO(vertexBuffer) as vertBufferStream:
                    vb.append({'SemanticName': semantics[streamInfo['m_renderDataType'].replace('Skinnable','')],\
                        'SemanticIndex': str(semantic_index),\
                        'Buffer': [unpack_dxgi_vector(vertBufferStream, stride, dxgi_format, e = '<')\
                            for x in range(accessors[vertexData['mu_gltfAccessorIndex']]['count'])]})
                elements.append(element)
                AlignedByteOffset += stride
                if streamInfo['m_renderDataType'] == 'Vertex' or streamInfo['m_renderDataType'] == 'SkinnableVertex':
                    attributes['POSITION'] = vertexData['mu_gltfAccessorIndex']
                elif streamInfo['m_renderDataType'] == 'Normal' or streamInfo['m_renderDataType'] == 'SkinnableNormal':
                    attributes['NORMAL'] = vertexData['mu_gltfAccessorIndex']
                elif streamInfo['m_renderDataType'] == 'ST':
                    pass
                elif streamInfo['m_renderDataType'] == 'SkinWeights':
                    attributes['WEIGHTS_0'] = vertexData['mu_gltfAccessorIndex']
                elif streamInfo['m_renderDataType'] == 'SkinIndices':
                    if 'mu_gltfAccessorForRemappedSkinIndiciesIndex' in streamInfo:
                        attributes['JOINTS_0'] = streamInfo['mu_gltfAccessorForRemappedSkinIndiciesIndex']
                    else:
                        attributes['JOINTS_0'] = vertexData['mu_gltfAccessorIndex']
                elif streamInfo['m_renderDataType'] == 'Color':
                    attributes['COLOR_' + str(colorCount)] = vertexData['mu_gltfAccessorIndex']
                    colorCount += 1
                elif streamInfo['m_renderDataType'] == 'Tangent' or streamInfo['m_renderDataType'] == 'SkinnableTangent':
                    if 'mu_gltfAccessorForExpandedHandednessTangent' in streamInfo:
                        attributes['TANGENT'] = streamInfo['mu_gltfAccessorForExpandedHandednessTangent']
                    elif tangentCount == 0:
                        attributes['TANGENT'] = vertexData['mu_gltfAccessorIndex']
                    tangentCount += 1
            if len(m['m_vertexData']) > 0:
                fmt['elements'] = elements
                fmt['stride'] = str(AlignedByteOffset)
                write_fmt(fmt, mesh_folder_name + os.sep + "{0}_{1:02d}.fmt".format(t['mu_name'], tt))
                with open(mesh_folder_name + os.sep + "{0}_{1:02d}.ib".format(t['mu_name'], tt), 'wb') as ff:
                    ff.write(curmesh['m_meshSegments']['m_els'][tt]['mu_indBuffer'])
                write_vb(vb, mesh_folder_name + os.sep + "{0}_{1:02d}.vb".format(t['mu_name'], tt), fmt)
                with open(mesh_folder_name + os.sep + "{0}_{1:02d}.material".format(t['mu_name'], tt), "wb") as ff:
                    ff.write(json.dumps({'material': mat['mu_materialname'].split('-VertexColor')[0].split('-Skinned')[0]}, indent=4).encode("utf-8"))
                with open(mesh_folder_name + os.sep + "{0}_{1:02d}.uvmap".format(t['mu_name'], tt), "wb") as ff:
                    ff.write(json.dumps([{'m_name': x['m_name'], 'm_index': x['m_index'], 'm_inputSet': x['m_inputSet']}\
                        for x in t['m_segmentContext']['m_els'][tt]['m_streamBindings']['m_u']], indent=4).encode("utf-8"))
            uvDataStreamSet = {}
            for vertexData in m['m_vertexData']['m_els']:
                streamInfo = vertexData['m_streams']['m_els'][0]
                if streamInfo['m_renderDataType'] == 'ST':
                    streamSet = streamInfo['m_streamSet']
                    uvDataStreamSet[streamSet] = vertexData
            uvDataLowest = None
            for i in sorted(uvDataStreamSet.keys()):
                if uvDataStreamSet[i] != None:
                    uvDataLowest = uvDataStreamSet[i]
                    break
            uvDataRemapped = [uvDataStreamSet[i] for i in sorted(uvDataStreamSet.keys()) if uvDataStreamSet[i] != None]
            if uvDataLowest != None:
                for i in sorted(uvDataStreamSet.keys()):
                    vertexData = uvDataStreamSet[i]
                    if vertexData == None:
                        continue
                    streamInfo = vertexData['m_streams']['m_els'][0]
                    if type(segmentcontext['m_streamBindings']) == dict:
                        for xx in segmentcontext['m_streamBindings']['m_u']:
                            if xx['m_renderDataType'] == 'ST' and xx['m_inputSet'] == streamInfo['m_streamSet']:
                                name_lower = xx['m_name'].lower()
                                name_to_uv_index_map = {'texcoord7': 6, 'texcoord6': 5, 'texcoord5': 4, 'texcoord4': 3, 'texcoord3': 2, 'texcoord2': 1, 'texcoord': 0, 'vitexcoord': 0, 'texcoord0': 0, 'TEX6': 2, 'TEX3': 1, 'TEX0': 0}
                                if name_lower in name_to_uv_index_map:
                                    uvIndex = name_to_uv_index_map[name_lower]
                                    while len(uvDataRemapped) <= uvIndex:
                                        uvDataRemapped.append(None)
                                    uvDataRemapped[uvIndex] = vertexData
            if len(uvDataRemapped) > 0:
                while uvDataRemapped[-1] == None:
                    uvDataRemapped.pop()
            for i in range(len(uvDataRemapped)):
                if uvDataRemapped[i] == None:
                    uvDataRemapped[i] = uvDataLowest
            texcoord_num = 0
            for i in range(len(uvDataRemapped)):
                if i in valid_uvs or i == 0:
                    attributes['TEXCOORD_' + str(texcoord_num)] = uvDataRemapped[i]['mu_gltfAccessorIndex']
                    texcoord_num += 1
            primitive['attributes'] = attributes
            primitive['indices'] = m['mu_gltfAccessorIndex']
            primitiveTypeForGltf = 0
            primitiveTypeMappingForGltf = {0: 0, 1: 1, 2: 4, 3: 5, 4: 6, 5: 0}
            if m['m_primitiveType'] in primitiveTypeMappingForGltf:
                primitiveTypeForGltf = primitiveTypeMappingForGltf[m['m_primitiveType']]
            primitive['mode'] = primitiveTypeForGltf
            mesh = {}
            mesh['primitives'] = [primitive]
            mesh['name'] = "{0}_{1:02d}".format(t['mu_name'],tt)
            #t['mu_gltfMeshIndex'] = len(meshes)
            t['mu_gltfMeshSegmentsIndicies'].append(len(meshes))
            meshes.append(mesh)
    cluster_mesh_info.gltf_data['meshes'] = meshes
    extensions = {}
    lights = []
    if 'PLight' in cluster_mesh_info.data_instances_by_class:
        light_type_map = {'DirectionalLight': 'directional', 'PointLight': 'point', 'SpotLight': 'spot'}
        metadata_json['lights'] = {}
        for v in cluster_mesh_info.data_instances_by_class['PLight']:
            if v['m_lightType'] in light_type_map:
                light = {}
                name = ''
                if name == '':
                    if 'mu_name' in v:
                        name = v['mu_name']
                if name != '':
                    light['name'] = name
                color = v['m_color']['m_elements']
                light['color'] = [color[0], color[1], color[2]]
                light['intensity'] = v['m_intensity']
                light['type'] = light_type_map[v['m_lightType']]
                if light['type'] == 'spot':
                    spot = {}
                    spot['innerConeAngle'] = v['m_innerConeAngle']
                    spot['outerConeAngle'] = v['m_outerConeAngle']
                    light['spot'] = spot
                if light['type'] == 'point' or (light['type'] == 'spot' and v['m_outerRange'] > 0):
                    light['range'] = v['m_outerRange']
                v['mu_gltfLightIndex'] = len(lights)
                lights.append(light)
            light_data = { 'type': v['m_lightType'] }
            light_params = {key:v[key] for key in \
                [k for k in v if (isinstance(v[k], float) or (isinstance(v[k], dict) and 'm_elements' in v[k]))]}
            light_data.update({key:value if isinstance(value,float) else list(value['m_elements']) for (key,value) in light_params.items()})
            metadata_json['lights'][v['mu_name']] = light_data
    if len(lights) > 0:
        KHR_lights_punctual = {}
        KHR_lights_punctual['lights'] = lights
        extensionsUsed.append('KHR_lights_punctual')
        extensions['KHR_lights_punctual'] = KHR_lights_punctual
    if len(extensions) > 0:
        cluster_mesh_info.gltf_data['extensions'] = extensions
    nodes = []
    if 'PNode' in cluster_mesh_info.data_instances_by_class:
        mesh_segment_nodes = []
        for v in cluster_mesh_info.data_instances_by_class['PNode']:
            node = {}
            node_extensions = {}
            if True:
                node['matrix'] = v['mu_matrixToUse'].tolist()
            name = v['m_name']
            if name == '':
                if 'mu_name' in v:
                    name = v['mu_name']
            mesh_node_indices = None
            if 'PMeshInstance' in cluster_mesh_info.data_instances_by_class:
                for vv in cluster_mesh_info.data_instances_by_class['PMeshInstance']:
                    if vv['m_localToWorldMatrix'] is v['m_worldMatrix']:
                        if name == '' and 'mu_name' in vv:
                            name = vv['mu_name']
                        if name == '' and 'mu_name' in vv['m_mesh']:
                            name = vv['m_mesh']['mu_name']
                        if 'mu_gltfMeshIndex' in vv:
                            node['mesh'] = vv['mu_gltfMeshIndex']
                            vv['mu_gltfNodeIndex'] = len(nodes)
                        elif 'mu_gltfMeshSegmentsIndicies' in vv:
                            mesh_node_indices = vv['mu_gltfMeshSegmentsIndicies']
                        break
            if 'PLight' in cluster_mesh_info.data_instances_by_class:
                node_KHR_lights_punctual = {}
                for vv in cluster_mesh_info.data_instances_by_class['PLight']:
                    if vv['m_localToWorldMatrix'] is v['m_worldMatrix'] and 'mu_gltfLightIndex' in vv:
                        if name == '' and 'mu_name' in vv:
                            name = vv['mu_name']
                        node_KHR_lights_punctual['light'] = vv['mu_gltfLightIndex']
                        vv['mu_gltfNodeIndex'] = len(nodes)
                        break
                if len(node_KHR_lights_punctual) > 0:
                    node_extensions['KHR_lights_punctual'] = node_KHR_lights_punctual
            if len(node_extensions) > 0:
                node['extensions'] = node_extensions
            if name != '':
                node['name'] = name
            children = [i for i in range(len(cluster_mesh_info.data_instances_by_class['PNode'])) if cluster_mesh_info.data_instances_by_class['PNode'][i]['m_parent'] is v]
            if mesh_node_indices != None:
                for vv in mesh_node_indices:
                    mesh_segment_node = {}
                    mesh_segment_node['name'] = meshes[vv]['name'] #+ '_node'
                    mesh_segment_node['mesh'] = vv
                    children.append(len(cluster_mesh_info.data_instances_by_class['PNode']) + len(mesh_segment_nodes))
                    mesh_segment_nodes.append(mesh_segment_node)
            if len(children) > 0:
                node['children'] = children
            v['mu_gltfNodeIndex'] = len(nodes)
            v['mu_gltfNodeName'] = name
            nodes.append(node)
        import copy
        metadata_json['heirarchy'] = copy.deepcopy(nodes)
        for v in mesh_segment_nodes:
            nodes.append(v)
    cluster_mesh_info.gltf_data['nodes'] = nodes
    skins = []
    inv_bind_mtxs = {}
    if 'PMeshInstance' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PMeshInstance']:
            mesh = v['m_mesh']
            joint_list = [mesh['m_skeletonBounds']['m_els'][i]['m_hierarchyMatrixIndex'] for i in range(len(mesh['m_skeletonBounds']['m_els']))]
            joint_list_to_node = {}
            matrices = {}
            matrices_by_name = {}
            for j in range(len(joint_list)):
                joint_list_to_node[joint_list[j]] = [i for i in range(len(nodes)) if nodes[i]['name'] == mesh['m_matrixNames']['m_els'][joint_list[j]]['m_buffer']][0]
                matrices[joint_list[j]] = mesh['m_skeletonMatrices']['m_els'][j]['m_elements']
                matrices_by_name[mesh['m_matrixNames']['m_els'][joint_list[j]]['m_buffer']] = mesh['m_skeletonMatrices']['m_els'][j]['m_elements']
            if len(mesh_segment_nodes) > 0:
                inv_bind_mtxs[v['mu_name']] = {k:list(v) for (k,v) in matrices_by_name.items()}
                mesh_nodes = {}
                remapped_vgmap_list = {nodes[joint_list_to_node[joint_list[j]]]['name']:j for j in range(len(joint_list))}
                for i in range(len(mesh_segment_nodes)):
                    mesh_nodes[mesh_segment_nodes[i]['mesh']] = [j for j in range(len(nodes)) if nodes[j]['name'] == mesh_segment_nodes[i]['name']][0]
                for i in range(len(mesh['m_meshSegments']['m_els'])):
                    if 'm_gltfSkinBoneMap' in mesh['m_meshSegments']['m_els'][i] and len(mesh_nodes) > 0:
                        submesh_joint_list = [joint_list_to_node[joint_list[x]] for x in mesh['m_meshSegments']['m_els'][i]['m_gltfSkinBoneMap']]
                        vgmap_list = {name:index for (name,index) in [(nodes[submesh_joint_list[j]]['name'],j) for j in range(len(submesh_joint_list))]}
                        matrix_list = [matrices[joint_list[x]].tobytes() for x in mesh['m_meshSegments']['m_els'][i]['m_gltfSkinBoneMap']]
                        if len(matrix_list) > 0:
                            blobdata = b''.join(matrix_list)
                            accessor = {}
                            accessor['bufferView'] = len(bufferviews)
                            accessor['componentType'] = 5126
                            accessor['type'] = 'MAT4'
                            accessor['count'] = len(matrix_list)
                            mesh['m_meshSegments']['m_els'][i]['mu_gltfAccessorForInverseBindMatrixIndex'] = len(accessors)
                            add_bufferview_embed(data=blobdata)
                            accessors.append(accessor)
                            skin = {"inverseBindMatrices": mesh['m_meshSegments']['m_els'][i]['mu_gltfAccessorForInverseBindMatrixIndex'],\
                                "joints": submesh_joint_list}
                            nodes[mesh_nodes[i]]['skin'] = len(skins)
                            if partialmaps == True:
                                with open(mesh_folder_name + os.sep + "{0}_{1:02d}.vgmap".format(v['mu_name'], i), 'wb') as f:
                                    f.write(json.dumps(vgmap_list, indent=4).encode("utf-8"))
                            else:
                                with open(mesh_folder_name + os.sep + "{0}_{1:02d}.vgmap".format(v['mu_name'], i), 'wb') as f:
                                    f.write(json.dumps(remapped_vgmap_list, indent=4).encode("utf-8"))
                            skins.append(skin)
            if 'mu_gltfAccessorForInverseBindMatrixIndex' in mesh and 'mu_gltfNodeIndex' in v:
                nodes[v['mu_gltfNodeIndex']]['skin'] = len(skins)
                skin = {}
                if 'mu_root_matrix_name' in mesh and mesh['mu_root_matrix_name'] != None:
                    joint = None
                    for i in range(len(nodes)):
                        vvv = nodes[i]
                        if vvv['name'] == mesh['mu_root_matrix_name']:
                            joint = i
                            break
                    if joint != None:
                        skin['skeleton'] = joint
                skin['inverseBindMatrices'] = mesh['mu_gltfAccessorForInverseBindMatrixIndex']
                if len(nodes) > 0 and type(mesh['m_matrixNames']['m_els']) == list and (type(mesh['m_matrixParents']['m_els']) == memoryview or type(mesh['m_matrixParents']['m_els']) == array.array) and (len(mesh['m_matrixNames']['m_els']) == len(mesh['m_matrixParents']['m_els'])):
                    joints = []
                    skeleton_matrix_names = []
                    matrix_index_to_node = {}
                    matrix_names = mesh['m_matrixNames']['m_els']
                    for i in range(len(matrix_names)):
                        matrix_name = matrix_names[i]
                        for ii in range(len(nodes)):
                            vvv = nodes[ii]
                            if vvv['name'] == matrix_name['m_buffer']:
                                matrix_index_to_node[i] = ii
                                break
                    for vv in mesh['m_skeletonBounds']['m_els']:
                        hierarchy_matrix_index = vv['m_hierarchyMatrixIndex']
                        matrix_name = matrix_names[hierarchy_matrix_index]
                        skeleton_matrix_names.append(matrix_name['m_buffer'])
                        joint = None
                        for i in range(len(nodes)):
                            vvv = nodes[i]
                            if vvv['name'] == matrix_name['m_buffer']:
                                joint = i
                                break
                        if joint != None:
                            joints.append(joint)
                            matrix_index_to_node[hierarchy_matrix_index] = joint
                        else:
                            joints.append(1)
                    if len(joints) > 0:
                        skin['joints'] = joints
                        v['mu_gltfSkinMatrixIndexToNode'] = matrix_index_to_node
                v['mu_gltfSkinIndex'] = len(skins)
                skins.append(skin)
    elif 'PAnimationSet' in cluster_mesh_info.data_instances_by_class:
        skin = {}
        skin['skeleton'] = 0
        joints = [i for i in range(len(nodes)) if i != 0]
        if len(joints) > 0:
            skin['joints'] = joints
        skins.append(skin)
    cluster_mesh_info.gltf_data['skins'] = skins
    if 'heirarchy' in metadata_json:
        for i in range(len(metadata_json['heirarchy'])):
            for mesh in inv_bind_mtxs:
                if metadata_json['heirarchy'][i]['name'] in list(inv_bind_mtxs[mesh].keys()):
                    metadata_json['heirarchy'][i][mesh+'_imtx'] = inv_bind_mtxs[mesh][metadata_json['heirarchy'][i]['name']]
    animations = []
    targetMap = {'Translation': 'translation', 'Rotation': 'rotation', 'Scale': 'scale'}
    if 'PAnimationSet' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationSet']:
            for vv in v['m_animationClips']['m_u']:
                animation = {}
                samplers = []
                channels = []
                for vvv in vv['m_channels']['m_els']:
                    if vvv['m_keyType'] not in targetMap:
                        continue
                    channel = {}
                    channel['sampler'] = len(samplers)
                    target = {}
                    target['path'] = targetMap[vvv['m_keyType']]
                    if vvv['m_instanceObjectType'] == 'PNode':
                        if 'PNode' in cluster_mesh_info.data_instances_by_class:
                            for vvvv in cluster_mesh_info.data_instances_by_class['PNode']:
                                if vvvv['mu_gltfNodeName'] == vvv['m_name']:
                                    target['node'] = vvvv['mu_gltfNodeIndex']
                                    break
                    elif vvv['m_instanceObjectType'] == 'PMeshInstance':
                        if vvv['m_name'] == 'm_currentPose':
                            instance_obj = vvv['m_instanceObject']
                            if instance_obj != None:
                                target_node = [x['m_buffer'] for x in instance_obj['m_mesh']['m_matrixNames']['m_els']][vvv['m_index']]
                                node_list = {v['m_name']:v['mu_gltfNodeIndex'] for v in cluster_mesh_info.data_instances_by_class['PNode']}
                                target['node'] = node_list[target_node]
                    channel['target'] = target
                    sampler = {}
                    sampler['input'] = vvv['m_times']['mu_gltfAccessorIndex']
                    sampler['output'] = vvv['mu_gltfAccessorIndex']
                    if vvv['m_interp'] == 2:
                        sampler['interpolation'] = 'STEP'
                    else:
                        sampler['interpolation'] = 'LINEAR'
                    channels.append(channel)
                    samplers.append(sampler)
                for vvv in vv['m_constantChannels']['m_els']:
                    if vvv['m_keyType'] not in targetMap:
                        continue
                    channel = {}
                    channel['sampler'] = len(samplers)
                    target = {}
                    target['path'] = targetMap[vvv['m_keyType']]
                    if 'PNode' in cluster_mesh_info.data_instances_by_class:
                        for vvvv in cluster_mesh_info.data_instances_by_class['PNode']:
                            if vvvv['mu_gltfNodeName'] == vvv['m_name']:
                                target['node'] = vvvv['mu_gltfNodeIndex']
                                break
                    channel['target'] = target
                    sampler = {}
                    sampler['input'] = vv['mu_gltfAccessorIndex']
                    sampler['output'] = vvv['mu_gltfAccessorIndex']
                    if vvv['m_interp'] == 2:
                        sampler['interpolation'] = 'STEP'
                    else:
                        sampler['interpolation'] = 'LINEAR'
                    channels.append(channel)
                    samplers.append(sampler)
                animation['channels'] = channels
                animation['samplers'] = samplers
            animations.append(animation)
    cluster_mesh_info.gltf_data['animations'] = animations
    cluster_mesh_info.gltf_data['scene'] = 0
    scenes = []
    if 'PNode' in cluster_mesh_info.data_instances_by_class:
        scene = {}
        nodes = [v['mu_gltfNodeIndex'] for v in cluster_mesh_info.data_instances_by_class['PNode'] if v['m_parent'] == None]
        scene['nodes'] = nodes
        scenes.append(scene)
    cluster_mesh_info.gltf_data['scenes'] = scenes
    cluster_mesh_info.gltf_data['bufferViews'] = bufferviews
    cluster_mesh_info.gltf_data['accessors'] = accessors
    if 'PLocator' in cluster_mesh_info.data_instances_by_class:
        metadata_json['locators'] = [x['mu_name'] for x in cluster_mesh_info.data_instances_by_class['PLocator']]
    else:
        metadata_json['locators'] = []
    if 'PPhysicsModel' in cluster_mesh_info.data_instances_by_class:
        def ok_json(obj):
            try:
                json.dumps(obj)
                return True
            except:
                return False
        physics_data = {}
        if 'PPhysicsModel' in cluster_mesh_info.data_instances_by_class:
            for v in cluster_mesh_info.data_instances_by_class['PPhysicsModel']:
                current_rigid_body = v['m_rigidBodies']
                rigid_bodies = {}
                if 'PPhysicsRigidBody' in cluster_mesh_info.data_instances_by_class:
                    rigid_body_count = 1
                    while current_rigid_body is not None:
                        vv = current_rigid_body
                        if not 'mu_name' in vv: # CS1 Maps do not have names for the rigid bodies
                            vv['mu_name'] = 'rigidBody{}'.format(rigid_body_count)
                        rigid_bodies[vv['mu_name']] = {'targetNode': vv['m_targetNode']['m_name'],\
                            'material': {item:vv['m_material'][item] for item in vv['m_material'] if isinstance(vv['m_material'][item],float)},\
                            'shapes': {}}
                        rigid_bodies[vv['mu_name']]['parameters'] = {}
                        #Removed variables: 'm_rigidBodyType', 'm_initialPosition', 'm_initialOrientation','m_inertiaTensor', 'm_angularDamping',
                                #'m_scale', 'm_initialTransform', 'm_collisionGroup', 'm_enabled', 'm_scriptHandler' and 'PWorldMatrix'
                        for item in ['m_mass', 'm_massFrameTransform', 'm_linearDamping',\
                                'm_initialLinearVelocity', 'm_initialAngularVelocity']:
                            if not isinstance(vv[item],dict): #or item in ['m_scriptHandler']
                                rigid_bodies[vv['mu_name']]['parameters'][item] = vv[item]
                            elif 'm_elements' in vv[item]:
                                rigid_bodies[vv['mu_name']]['parameters'][item] = list(vv[item]['m_elements'])
                        #Shapes
                        for vvv in vv['m_shapes']['m_u']:
                            shape = vvv['m_shape']
                            rigid_bodies[vv['mu_name']]['shapes'][shape['mu_name']] = {}
                            #Removed variables: 'm_material', 'm_transform', 'm_scale', 'm_type'
                            for item in ['m_hollow', 'm_mass', 'm_density']:
                                if not isinstance(vvv[item],dict):
                                    rigid_bodies[vv['mu_name']]['shapes'][shape['mu_name']][item] = vvv[item]
                                elif 'm_elements' in vvv[item]:
                                    rigid_bodies[vv['mu_name']]['shapes'][shape['mu_name']][item] = list(vvv[item]['m_elements'])
                        current_rigid_body = vv['m_next']
                        rigid_body_count += 1
                # Physics models have an m_next and m_world, but we do not support that (yet)
                physics_data["PPhysicsModel_{0}".format(v['mu_memberLoc'])] = { 'rigid_bodies': rigid_bodies }
        with open(physics_json_name, 'wb') as f:
            f.write(json.dumps(physics_data, indent=4).encode("utf-8"))
    if len(nodes) > 0:
        import json
        import base64
        embedded_giant_buffer_joined = b''.join(embedded_giant_buffer)
        buffer0['byteLength'] = len(embedded_giant_buffer_joined)
        if gltf_nonbinary == True:
            with cluster_mesh_info.storage_media.open(pkg_name + os.sep + cluster_mesh_info.filename.split('.', 1)[0] + '.gltf', 'wb') as f:
                buffer0["uri"] = cluster_mesh_info.filename.split('.', 1)[0] + '.bin'
                jsondata = json.dumps(cluster_mesh_info.gltf_data, indent=4).encode("utf-8")
                f.write(jsondata)
            with cluster_mesh_info.storage_media.open(pkg_name + os.sep + cluster_mesh_info.filename.split('.', 1)[0] + '.bin', 'wb') as f:
                f.write(embedded_giant_buffer_joined)
        else:
            with cluster_mesh_info.storage_media.open(pkg_name + os.sep + cluster_mesh_info.filename.split('.', 1)[0] + '.glb', 'wb') as f:
                jsondata = json.dumps(cluster_mesh_info.gltf_data).encode('utf-8')
                jsondata += b' ' * (4 - len(jsondata) % 4)
                f.write(struct.pack('<III', 1179937895, 2, 12 + 8 + len(jsondata) + 8 + len(embedded_giant_buffer_joined)))
                f.write(struct.pack('<II', len(jsondata), 1313821514))
                f.write(jsondata)
                f.write(struct.pack('<II', len(embedded_giant_buffer_joined), 5130562))
                f.write(embedded_giant_buffer_joined)
        if 'materials' in metadata_json:
            with open(metadata_json_name, 'wb') as f:
                f.write(json.dumps(metadata_json, indent=4).encode("utf-8"))
    if len(animations) > 0:
        animation_metadata[metadata_json['name']] = {'starttime_offset': min([accessors[x]['min'] for x in animation_time_accessors]),\
            'locators': metadata_json['locators']}

def process_pkg(pkg_name, partialmaps = partial_vgmaps_default, allbuffers = False, gltf_nonbinary = False, overwrite = False, dest_dir = None):
    global animation_metadata
    animation_metadata = {}
    storage_media = None
    print("Processing {0}...".format(pkg_name))
    if dest_dir is None:
        dest_dir = pkg_name[:-4]
    else:
        dest_dir = dest_dir + os.sep + os.path.basename(pkg_name[:-4])
    if file_is_ed8_pkg(pkg_name):
        if os.path.exists(dest_dir) and (os.path.isdir(dest_dir)) and (overwrite == False):
            if str(input(dest_dir + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(dest_dir):
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            allowed_write_extensions = ['.glb', '.json', '.dds', '.xml', '.phyre']
            storage_media = TSpecialOverlayMedia(os.path.realpath(pkg_name),  allowed_write_extensions)
            items = []

            def list_callback(item):
                if item[-10:-6] == '.dae':
                    items.append(item)
            storage_media.get_list_at('.', list_callback)
            if len(items) == 0:

                def list_callback2(item):
                    if item[-10:-6] in ['.dds', '.png', '.bmp']:
                        items.append(item)
                storage_media.get_list_at('.', list_callback2)
            for i in range(len(items)):
                print("Parsing {0}...".format(items[i]))
                parse_cluster(items[i], None, storage_media, dest_dir, partialmaps = partialmaps, \
                    allbuffers = allbuffers, gltf_nonbinary = gltf_nonbinary, item_num=i)

            build_items = []
            def list_build_items_callback(item):
                if item[-4:] == '.xml' or item[-42:-38] == '.fx#' or item[-9:-6] == '.fx':
                    build_items.append(item)
            storage_media.get_list_at('.', list_build_items_callback)
            if not os.path.exists(dest_dir + os.sep + os.path.basename(pkg_name)[:-4]):
                os.makedirs(dest_dir + os.sep + os.path.basename(pkg_name)[:-4])
            for i in range(len(build_items)):
                with storage_media.open(build_items[i], 'rb') as f:
                    with open(dest_dir + os.sep + os.path.basename(pkg_name)[:-4] + os.sep + build_items[i], 'wb') as ff:
                        ff.write(f.read())

            if len(animation_metadata) > 0:
                with open(dest_dir + os.sep + 'animation_metadata.json', 'wb') as f:
                    f.write(json.dumps({'pkg_name': dest_dir,\
                    'compression': storage_media.storage2.compression_flag,\
                    'animations': animation_metadata}, indent=4).encode("utf-8"))

            if len(glob.glob(dest_dir + os.sep +'*metadata.json')) == 0:
                with open(dest_dir + os.sep + 'compression.json', 'wb') as f:
                    f.write(json.dumps({'compression': storage_media.storage2.compression_flag},\
                        indent=4).encode("utf-8"))

            return
        else:
            return
    raise Exception('Passed in file is not compatible file')

if __name__ == '__main__':
    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        if partial_vgmaps_default == False:
            parser.add_argument('-p', '--partialmaps', help="Provide vgmaps with non-empty groups only", action="store_true")
        else:
            parser.add_argument('-c', '--completemaps', help="Provide vgmaps with entire skeleton", action="store_false")
        parser.add_argument('-a', '--allbuffers', help="Dump all buffers (default is no more than 8 texcoord/tangent/binormal)", action="store_true")
        parser.add_argument('-t', '--gltf_nonbinary', help="Output glTF files in .gltf format, instead of .glb.", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('-d', '--dest_dir', type=str, help="Path where to extract the pkg.")
        parser.add_argument('pkg_filename', help="Name of pkg file to export from (required).")
        args = parser.parse_args()
        if args.dest_dir:
            if os.path.exists(args.dest_dir) and not os.path.isdir(args.dest_dir):
                raise Exception("--dest_dir (-d) '{}' not a directory.".format(args.dest_dir))
        if partial_vgmaps_default == False:
            partialmaps = args.partialmaps
        else:
            partialmaps = args.completemaps
        if os.path.exists(args.pkg_filename) and args.pkg_filename[-4:].lower() == '.pkg':
            process_pkg(args.pkg_filename, partialmaps = partialmaps, allbuffers = args.allbuffers, \
                gltf_nonbinary = args.gltf_nonbinary, overwrite = args.overwrite, dest_dir = args.dest_dir)
        else:
            print("{} does not exist".format(args.pkg_filename))
    else:
        # Set current directory
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(sys.executable))
        else:
            os.chdir(os.path.abspath(os.path.dirname(__file__)))
        pkg_files = glob.glob('*.pkg')
        for i in range(len(pkg_files)):
            process_pkg(pkg_files[i])
