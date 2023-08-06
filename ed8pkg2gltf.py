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
    import itertools, functools
    toeof = iter(functools.partial(f.read, 1), b'')
    return sys.intern(b''.join(itertools.takewhile(b'\x00'.__ne__, toeof)).decode('ASCII'))

def read_integer(f, size, unsigned, endian='<'):
    typemap = {1: 'b', 
     2: 'h', 
     4: 'i', 
     8: 'q'}
    inttype = typemap[size]
    if unsigned == True:
        inttype = inttype.upper()
    return struct.unpack(endian + inttype, f.read(size))[0]

def imageUntilePS4(buffer, width, height, bpb, pitch=0):
    Tile = (0, 1, 8, 9, 2, 3, 10, 11, 16, 17, 24, 25, 18, 19, 26, 27, 4, 5, 12, 13,
            6, 7, 14, 15, 20, 21, 28, 29, 22, 23, 30, 31, 32, 33, 40, 41, 34, 35,
            42, 43, 48, 49, 56, 57, 50, 51, 58, 59, 36, 37, 44, 45, 38, 39, 46, 47,
            52, 53, 60, 61, 54, 55, 62, 63)
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
    Tile = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
            21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38,
            39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56,
            57, 58, 59, 60, 61, 62, 63)
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
    TexParams = (('DXT1', 1, 8), ('DXT3', 1, 16), ('DXT5', 1, 16), ('BC5', 1, 16),
                 ('BC7', 1, 16), ('RGBA8', 0, 4), ('ARGB8', 0, 4), ('L8', 0, 1),
                 ('A8', 0, 1), ('LA88', 0, 2), ('RGBA16F', 0, 8), ('ARGB1555', 0, 2),
                 ('ARGB4444', 0, 2), ('ARGB8_SRGB', 0, 4))
    TexParams = tuple(tuple(TexParams[j][i] for j in range(len(TexParams))) for i in range(len(TexParams[0])))
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

def get_dds_header(fmt, width, height, mipmap_levels, is_cube_map):
    if fmt == "LA8":
        return struct.pack("<4s20I4s10I",   b"DDS\x20", 124, (0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mipmap_levels is not None else 0) |     0x8), height, width, (width * 16 + 7) // 8,                               0, (mipmap_levels if mipmap_levels is not None else 0), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32, (0 | 0x1 | 0x40),                 b"", 16,     0x00FF,     0x00FF,     0x00FF,     0xFF00, (0x8 if mipmap_levels is not None or is_cube_map else 0) | (0x400000 if mipmap_levels is not None else 0) | 0x1000, (0x200 | 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000) if is_cube_map else (0), 0, 0, 0)
    elif fmt == "L8":
        return struct.pack("<4s20I4s10I",   b"DDS\x20", 124, (0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mipmap_levels is not None else 0) |     0x8), height, width, (width *  8 + 7) // 8,                               0, (mipmap_levels if mipmap_levels is not None else 0), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32, (0 |       0x40),                 b"",  8,     0x00FF,     0x00FF,     0x00FF,     0x0000, (0x8 if mipmap_levels is not None or is_cube_map else 0) | (0x400000 if mipmap_levels is not None else 0) | 0x1000, (0x200 | 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000) if is_cube_map else (0), 0, 0, 0)
    elif fmt == "ARGB8":
        return struct.pack("<4s20I4s10I",   b"DDS\x20", 124, (0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mipmap_levels is not None else 0) |     0x8), height, width, (width * 32 + 7) // 8,                               0, (mipmap_levels if mipmap_levels is not None else 0), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32, (0 | 0x1 | 0x40),                 b"", 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000, (0x8 if mipmap_levels is not None or is_cube_map else 0) | (0x400000 if mipmap_levels is not None else 0) | 0x1000, (0x200 | 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000) if is_cube_map else (0), 0, 0, 0)
    elif fmt == "RGBA8":
        return struct.pack("<4s20I4s10I",   b"DDS\x20", 124, (0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mipmap_levels is not None else 0) |     0x8), height, width, (width * 32 + 7) // 8,                               0, (mipmap_levels if mipmap_levels is not None else 0), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32, (0 | 0x1 | 0x40),                 b"", 32, 0xFF000000, 0x00FF0000, 0x0000FF00, 0x000000FF, (0x8 if mipmap_levels is not None or is_cube_map else 0) | (0x400000 if mipmap_levels is not None else 0) | 0x1000, (0x200 | 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000) if is_cube_map else (0), 0, 0, 0)
    elif fmt == "RGB565":
        return struct.pack("<4s20I4s10I",   b"DDS\x20", 124, (0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mipmap_levels is not None else 0) |     0x8), height, width, (width * 16 + 7) // 8,                               0, (mipmap_levels if mipmap_levels is not None else 0), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32, (0 |       0x40),                 b"", 16, 0x0000F800, 0x000007E0, 0x0000001F, 0x00000000, (0x8 if mipmap_levels is not None or is_cube_map else 0) | (0x400000 if mipmap_levels is not None else 0) | 0x1000, (0x200 | 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000) if is_cube_map else (0), 0, 0, 0)
    elif fmt == "ARGB4444":
        return struct.pack("<4s20I4s10I",   b"DDS\x20", 124, (0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mipmap_levels is not None else 0) |     0x8), height, width, (width * 16 + 7) // 8,                               0, (mipmap_levels if mipmap_levels is not None else 0), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32, (0 | 0x1 | 0x40),                 b"", 16, 0x00000F00, 0x000000F0, 0x0000000F, 0x0000F000, (0x8 if mipmap_levels is not None or is_cube_map else 0) | (0x400000 if mipmap_levels is not None else 0) | 0x1000, (0x200 | 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000) if is_cube_map else (0), 0, 0, 0)
    elif fmt == "BC5":
        return struct.pack("<4s20I4s10I5I", b"DDS\x20", 124, (0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mipmap_levels is not None else 0) | 0x80000), height, width, ((width + 3) // 4) * (8),                            0, (mipmap_levels if mipmap_levels is not None else 0), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32,              0x4,             b"DX10",  0,          0,          0,          0,          0, (0x8 if mipmap_levels is not None or is_cube_map else 0) | (0x400000 if mipmap_levels is not None else 0) | 0x1000, (0x200 | 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000) if is_cube_map else (0), 0, 0, 0, 83, 3, 0, 1, 0)
    elif fmt == "BC7":
        return struct.pack("<4s20I4s10I5I", b"DDS\x20", 124, (0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mipmap_levels is not None else 0) | 0x80000), height, width, ((width + 3) // 4) * (8),                            0, (mipmap_levels if mipmap_levels is not None else 0), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32,              0x4,             b"DX10",  0,          0,          0,          0,          0, (0x8 if mipmap_levels is not None or is_cube_map else 0) | (0x400000 if mipmap_levels is not None else 0) | 0x1000, (0x200 | 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000) if is_cube_map else (0), 0, 0, 0, 98, 3, 0, 1, 0)
    elif fmt == "DXT1" or fmt == "DXT3" or fmt == "DXT5":
        return struct.pack("<4s20I4s10I",   b"DDS\x20", 124, (0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mipmap_levels is not None else 0) | 0x80000), height, width, ((width + 3) // 4) * (8 if (fmt == "DXT1") else 16), 0, (mipmap_levels if mipmap_levels is not None else 0), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32,              0x4, fmt.encode("ASCII"),  0,          0,          0,          0,          0, (0x8 if mipmap_levels is not None or is_cube_map else 0) | (0x400000 if mipmap_levels is not None else 0) | 0x1000, (0x200 | 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000) if is_cube_map else (0), 0, 0, 0)
    else:
        print("Unhandled format " + str(fmt) + "!")

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
                        cd[num4] = cd[(num4 - b2)]
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
        """get the length of a lz4 variable length integer."""
        if length != 15:
            return length
        while 1:
            read_buf = src.read(1)
            if len(read_buf) != 1:
                raise Exception('EOF at length read')
            len_part = int.from_bytes(read_buf, byteorder='little')
            length += len_part
            if len_part != 255:
                break

        return length

    while src.tell() <= fin:
        read_buf = src.read(1)
        if not read_buf:
            raise Exception('EOF at reading literal-len')
        token = int.from_bytes(read_buf, byteorder='little')
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
        offset = int.from_bytes(read_buf, byteorder='little')
        if offset == 0:
            raise Exception("offset can't be 0")
        match_len = get_length(src, token >> 0 & 15)
        match_len += min_match_len

        def append_sliding_window(num4):
            if offset < match_len:
                for _ in range(match_len):
                    dst[num4] = dst[(num4 - offset)]
                    num4 += 1

            else:
                sliding_window_pos = num4 - offset
                dst[num4:num4 + match_len] = dst[sliding_window_pos:sliding_window_pos + match_len]
                num4 += match_len
            return num4

        num4 = append_sliding_window(num4)

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

def get_type(id, type_strings, class_descriptors):
    total_types = len(type_strings) + 1
    if id < total_types:
        return type_strings[id]
    else:
        id -= total_types
        return class_descriptors[id].name

def get_class_from_type(id, type_strings):
    total_types = len(type_strings) + 1
    if id < total_types:
        return
    else:
        return id - total_types + 1

def get_reference_from_class_descriptor_index(cluster_info, class_name, index):
    for x in cluster_info.list_for_class_descriptors.keys():
        if cluster_info.classes_strings[x] == class_name and len(cluster_info.list_for_class_descriptors[x]) > index:
            return cluster_info.list_for_class_descriptors[x][index].split('#', 1)

def get_reference_from_class_descriptor(cluster_info, class_name, class_dict):
    for x in cluster_info.list_for_class_descriptors.keys():
        if cluster_info.classes_strings[x] == class_name and len(cluster_info.list_for_class_descriptors[x]) > index:
            for i in range(len(cluster_info.list_for_class_descriptors)):
                if cluster_info.list_for_class_descriptors[i] is class_dict:
                    return get_reference_from_class_descriptor_index(cluster_info, class_name, i)

def get_class_name(cluster_info, id):
    return cluster_info.class_descriptors[(id - 1)].name

def get_class_size(cluster_info, id):
    return cluster_info.class_descriptors[(id - 1)].get_size_in_bytes()

def process_data_members(g, cluster_info, id, member_location, array_location, class_element, cluster_mesh_info, class_name, should_print_class, dict_data, cluster_header, data_instances_by_class, offset_from_parent, array_fixup_count, pointer_fixup_count):
    global g_offcount

    if id > 0:
        class_id = id-1
        class_descriptor = cluster_info.class_descriptors[class_id]
        for m in range(class_descriptor.class_data_member_count):
            member_id = class_descriptor.member_offset+m
            data_member = cluster_info.data_members[member_id]
            type_id = data_member.type_id
            variable_text = data_member.name
            type_text = get_type(type_id, cluster_info.type_strings, cluster_info.class_descriptors)
            class_type_id = get_class_from_type(type_id, cluster_info.type_strings)

            string_variable = ''
            val = None
            data_offset = member_location+data_member.value_offset
            value_offset = data_member.value_offset
            expected_offset = data_member.fixed_array_size
            if expected_offset == 0:
                expected_offset = 1
            expected_size = data_member.size_in_bytes * expected_offset
            g.seek(data_offset)
            if data_instances_by_class is not None:
                if type_text == 'PArray<PUInt32>' or type_text == 'PSharray<PUInt32>':
                    if array_fixup_count > 0:
                        count = dict_data[variable_text]["m_count"]
                        if (count <= 0xffff):
                            old_position = g.tell()
                            g.seek(array_location+cluster_info.array_info[class_element + cluster_info.array_fixup_offset].offset)
                            val = array.array('I', g.read(count * 4))
                            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                                val.byteswap()
                            g.seek(old_position)
                        else:
                            val = []
                    else:
                        val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
                    if expected_size == 8:
                        g.seek(4, io.SEEK_CUR)
                    elif expected_size == 5:
                        g.seek(1, io.SEEK_CUR)
                elif type_text == 'PArray<PInt32>' or type_text == 'PSharray<PInt32>':
                    if array_fixup_count > 0:
                        count = dict_data[variable_text]["m_count"]
                        if (count <= 0xffff):
                            old_position = g.tell()
                            g.seek(array_location+cluster_info.array_info[class_element + cluster_info.array_fixup_offset].offset)
                            val = array.array('i', g.read(count * 4))
                            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                                val.byteswap()
                            g.seek(old_position)
                        else:
                            val = []
                    else:
                        val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
                    if expected_size == 8:
                        g.seek(4, io.SEEK_CUR)
                    elif expected_size == 5:
                        g.seek(1, io.SEEK_CUR)
                elif type_text == 'PArray<float>' or type_text == 'PSharray<float>':
                    if array_fixup_count > 0:
                        count = dict_data[variable_text]["m_count"]

                        if class_element == 0:
                            g_offcount = 0

                        old_position = g.tell()

                        array_info = cluster_info.array_info[class_element + cluster_info.array_fixup_offset]
                        if array_info.count > 0:
                            g.seek(array_location + array_info.offset)
                        else:
                            g.seek(array_location + g_offcount)

                        g_offcount = g_offcount + (count * 4)
                        val = array.array('f', g.read(count * 4))
                        if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                            val.byteswap()
                        g.seek(old_position)
                    else:
                        val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
                    if expected_size == 8:
                        g.seek(4, io.SEEK_CUR)
                    elif expected_size == 5:
                        g.seek(1, io.SEEK_CUR)
                elif type_text == 'PArray<PUInt8>' or type_text == 'PSharray<PUInt8>':
                    if array_fixup_count > 0:
                        count = dict_data[variable_text]["m_count"]
                        if (count <= 0xffff):
                            old_position = g.tell()
                            g.seek(array_location+cluster_info.array_info[class_element + cluster_info.array_fixup_offset].offset)
                            val = g.read(count)
                            g.seek(old_position)
                        else:
                            val = []
                    else:
                        val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
                    if expected_size == 8:
                        g.seek(4, io.SEEK_CUR)
                    elif expected_size == 5:
                        g.seek(1, io.SEEK_CUR)
                elif type_text == 'PArray<PUInt8,4>':
                    val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
                    if expected_size == 5:
                        g.seek(1, io.SEEK_CUR)
                    
                elif (type_text[0:7] == "PArray<") and (type_text[-1:] == ">") and type(dict_data[variable_text]) is dict:
                    array_count = dict_data[variable_text]["m_count"]
                    current_count = 0
                    type_value = type_text[7:-1]
                    is_pointer = False
                    if not (type_value in data_instances_by_class):
                        
                        if type_value[0:10] == "PDataBlock":
                            type_value = type_value[0:10]
                        if type_value[-2:] == " *":
                            type_value = type_value[:-2]
                            is_pointer = True
                    if array_count == 0:
                        val = []
                    elif type_value in data_instances_by_class:
                        for b in range(pointer_fixup_count):
                            pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
                            if pointer_info.source_object_id == class_element and ((is_pointer == True) or (is_pointer == False and pointer_info.som == value_offset + 4)) and (len(cluster_info.classes_strings) > pointer_info.destination_object.object_list) and (cluster_info.classes_strings[pointer_info.destination_object.object_list] == type_value) and (pointer_info.destination_object.object_list in data_instances_by_class):
                                data_instances_by_class_this = data_instances_by_class[pointer_info.destination_object.object_list]
                                if is_pointer == True:
                                    if current_count == 0:
                                        val = [None] * array_count
                                    offset_calculation = pointer_info.destination_object.object_id
                                    if len(data_instances_by_class_this) > offset_calculation:
                                        val[pointer_info.array_index] = data_instances_by_class_this[offset_calculation]
                                    current_count += 1
                                else:
                                    val = []
                                    for i in range(pointer_info.array_index):
                                        val.append(data_instances_by_class_this[pointer_info.destination_object.object_id + i])
                                    if (b == m):
                                        break
                    else:
                        for b in range(pointer_fixup_count):
                            pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
                            user_fix_id = pointer_info.user_fixup_id
                            if pointer_info.source_object_id == class_element and pointer_info.som == value_offset + 4 and not pointer_info.is_class_data_member() and user_fix_id is not None and (user_fix_id < len(cluster_info.user_fixes)) and (type(cluster_info.user_fixes[user_fix_id].data) is str):
                                if current_count == 0:
                                    val = [None] * array_count
                                val[pointer_info.array_index] = cluster_info.user_fixes[user_fix_id].data
                                current_count += 1
                    if type_value == 'PShaderParameterDefinition' and val is not None:
                        shader_object_dict = {}
                        for b in range(pointer_fixup_count):
                            pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
                            if not pointer_info.is_class_data_member():
                                for x in range(len(val)):
                                    value_this = val[x]
                                    
                                    pointer_info_offset_needed = pointer_info.som
                                    if value_this["m_parameterType"] == 71: 
                                        pointer_info_offset_needed -= 8
                                        if value_this["m_bufferLoc"]["m_offset"] == pointer_info_offset_needed:
                                            if (len(cluster_info.classes_strings) > pointer_info.destination_object.object_list) and (pointer_info.destination_object.object_list in data_instances_by_class):
                                                shader_object_dict[value_this["m_name"]] = data_instances_by_class[pointer_info.destination_object.object_list][cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset].destination_object.object_id]
                                    elif value_this["m_parameterType"] == 66 or value_this["m_parameterType"] == 68: 
                                        if value_this["m_bufferLoc"]["m_size"] == 24:
                                            pointer_info_offset_needed -= 16
                                        else:
                                            pointer_info_offset_needed -= 12
                                        if value_this["m_bufferLoc"]["m_offset"] == pointer_info_offset_needed:
                                            user_fix_id = pointer_info.user_fixup_id
                                            if user_fix_id is not None and (user_fix_id < len(cluster_info.user_fixes)) and ('PAssetReferenceImport' in data_instances_by_class) and (type(cluster_info.user_fixes[user_fix_id].data) is int) and (cluster_info.user_fixes[user_fix_id].data < len(data_instances_by_class["PAssetReferenceImport"])):
                                                shader_object_dict[value_this["m_name"]] = data_instances_by_class["PAssetReferenceImport"][cluster_info.user_fixes[user_fix_id].data]
                        dict_data["mu_tweakableShaderParameterDefinitionsObjectReferences"] = shader_object_dict

                elif (((class_name[0:9] == "PSharray<") and (class_name[-1:] == ">"))) and variable_text == "m_u":
                    array_count = dict_data["m_count"]
                    current_count = 0
                    val = [None] * array_count
                    for b in range(pointer_fixup_count):
                        if current_count >= array_count:
                            break
                        pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
                        if (pointer_info.source_object_id == class_element) and (pointer_info.som == offset_from_parent + 4) and (pointer_info.destination_object.object_list in data_instances_by_class):
                            offset_calculation = pointer_info.destination_object.object_id
                            data_instances_by_class_this = data_instances_by_class[pointer_info.destination_object.object_list]
                            if len(data_instances_by_class_this) > offset_calculation:
                                val[pointer_info.array_index] = data_instances_by_class_this[offset_calculation]
                            current_count += 1
                elif (type_text in data_instances_by_class):
                    for b in range(pointer_fixup_count):
                        pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
                        if pointer_info.source_object_id == class_element and pointer_info.som == member_id and pointer_info.is_class_data_member():
                            user_fix_id = pointer_info.user_fixup_id
                            object_id = pointer_info.destination_object.object_id
                            data_instances_by_class_this = data_instances_by_class[pointer_info.destination_object.object_list]
                            if len(data_instances_by_class_this) > object_id:
                                val = data_instances_by_class_this[object_id]
                                break
                elif (type_text in cluster_info.import_classes_strings):
                    for b in range(pointer_fixup_count):
                        pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
                        user_fix_id = pointer_info.user_fixup_id
                        if pointer_info.source_object_id == class_element and pointer_info.som == member_id and pointer_info.is_class_data_member() and user_fix_id is not None and (user_fix_id < len(cluster_info.user_fixes)) and ('PAssetReferenceImport' in data_instances_by_class) and (type(cluster_info.user_fixes[user_fix_id].data) is int) and (cluster_info.user_fixes[user_fix_id].data < len(data_instances_by_class["PAssetReferenceImport"])):
                            val = data_instances_by_class["PAssetReferenceImport"][cluster_info.user_fixes[user_fix_id].data]
                            break
                elif class_type_id is not None and type(dict_data[variable_text]) is dict and ((cluster_info.class_descriptors[class_type_id-1].get_size_in_bytes() * (1 if data_member.fixed_array_size == 0 else data_member.fixed_array_size)) == expected_size):
                    if data_member.fixed_array_size > 0:
                        val = dict_data[variable_text]
                        structsize = cluster_info.class_descriptors[class_type_id-1].get_size_in_bytes()
                        for i in range(data_member.fixed_array_size):
                            val2 = val[i]
                            process_data_members(g, cluster_info, class_type_id, data_offset + (structsize * i), array_location, class_element, cluster_mesh_info, type_text, should_print_class, val2, cluster_header, data_instances_by_class, offset_from_parent + data_member.value_offset + (structsize * i), array_fixup_count, pointer_fixup_count)
                    else:
                        val = dict_data[variable_text]
                        process_data_members(g, cluster_info, class_type_id, data_offset, array_location, class_element, cluster_mesh_info, type_text, should_print_class, val, cluster_header, data_instances_by_class, offset_from_parent + data_member.value_offset, array_fixup_count, pointer_fixup_count)
            elif type_text == 'PUInt8':
                if data_member.fixed_array_size != 0:
                    val = array.array('B', g.read(data_member.fixed_array_size * 1))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        val.byteswap()
                else:
                    val = read_integer(g, 1, True, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text == 'PInt8':
                if data_member.fixed_array_size != 0:
                    val = array.array('b', g.read(data_member.fixed_array_size * 1))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        val.byteswap()
                else:
                    val = read_integer(g, 1, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text == 'PUInt16':
                if data_member.fixed_array_size != 0:
                    val = array.array('H', g.read(data_member.fixed_array_size * 2))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        val.byteswap()
                else:
                    val = read_integer(g, 2, True, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text == 'PInt16':
                if data_member.fixed_array_size != 0:
                    val = array.array('h', g.read(data_member.fixed_array_size * 2))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        val.byteswap()
                else:
                    val = read_integer(g, 2, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text == 'PUInt32':
                if data_member.fixed_array_size != 0:
                    val = array.array('I', g.read(data_member.fixed_array_size * 4))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        val.byteswap()
                else:
                    val = read_integer(g, 4, True, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text == 'PInt32':
                if data_member.fixed_array_size != 0:
                    val = array.array('i', g.read(data_member.fixed_array_size * 4))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        val.byteswap()
                else:
                    val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text == 'PUInt64':
                if data_member.fixed_array_size != 0:
                    val = array.array('Q', g.read(data_member.fixed_array_size * 8))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        val.byteswap()
                else:
                    val = read_integer(g, 8, True, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text == 'PInt64':
                if data_member.fixed_array_size != 0:
                    val = array.array('q', g.read(data_member.fixed_array_size * 8))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        val.byteswap()
                else:
                    val = read_integer(g, 8, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text == 'float':
                if data_member.fixed_array_size != 0:
                    val = array.array('f', g.read(data_member.fixed_array_size * 4))
                    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                        val.byteswap()
                else:
                    val = struct.unpack(('>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<') + "f", g.read(4))[0]
            elif type_text == 'bool':
                if read_integer(g, 1, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<') > 0:
                    val = True
                else:
                    val = False

            elif type_text == 'PChar':
                val = ""
                for b in range(array_fixup_count):
                    array_info = cluster_info.array_info[b + cluster_info.array_fixup_offset]
                    if (array_info.source_object_id == class_element):
                        old_position = g.tell()
                        g.seek(array_location + array_info.offset)
                        try:
                            val = read_null_ending_string(g)
                        except:
                            val = ""
                        g.seek(old_position)
                        break
                if expected_size == 4:
                    g.seek(4, io.SEEK_CUR)
                elif expected_size == 1:
                    g.seek(1, io.SEEK_CUR)
            elif type_text == 'PString' and class_name == 'PNode':
                val = ""
                for b in range(array_fixup_count):
                    array_info = cluster_info.array_info[b + cluster_info.array_fixup_offset]
                    if (array_info.source_object_id == class_element) and ((array_info.som + 4 == value_offset) or (array_info.som == value_offset)):
                        old_position = g.tell()
                        g.seek(array_location + array_info.offset)
                        try:
                            val = read_null_ending_string(g)
                        except:
                            val = ""
                        g.seek(old_position)
                        break
                if expected_size == 4:
                    g.seek(4, io.SEEK_CUR)
                elif expected_size == 1:
                    g.seek(1, io.SEEK_CUR)
            elif type_text == 'PString':
                val = ""
                for b in range(array_fixup_count):
                    array_info = cluster_info.array_info[b + cluster_info.array_fixup_offset]
                    if (array_info.source_object_id == class_element) and (array_info.som == value_offset):
                        old_position = g.tell()
                        g.seek(array_location + array_info.offset)
                        try:
                            val = read_null_ending_string(g)
                        except:
                            val = ""
                        g.seek(old_position)
                        break
                if expected_size == 4:
                    g.seek(4, io.SEEK_CUR)
                elif expected_size == 1:
                    g.seek(1, io.SEEK_CUR)
            elif type_text == 'PTextureStateGNM':
                val = g.read(expected_size)
            elif type_text == 'PCgParameterInfoGCM' or type_text == 'PCgCodebookGCM' or type_text == 'PCgBindingParameterInfoGXM' or type_text == 'PCgBindingSceneConstantsGXM':
                val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
            elif type_text == 'Vector4' and expected_size == 4:
                val = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')

            elif type_text == 'PLightType' or type_text == 'PRenderDataType' or type_text == 'PAnimationKeyDataType' or type_text == 'PTextureFormatBase' or type_text == 'PSceneRenderPassType':
                val = None
                for b in range(pointer_fixup_count):
                    pointer_info = cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset]
                    if pointer_info.source_object_id == class_element and pointer_info.som == member_id and pointer_info.is_class_data_member():
                        user_fix_id = pointer_info.user_fixup_id
                        if user_fix_id is not None and user_fix_id < len(cluster_info.user_fixes):
                            val = cluster_info.user_fixes[user_fix_id].data
                        else:
                            val = pointer_info.destination_object.object_list

            elif type_text == 'PClassDescriptor':
                pointer_info = cluster_info.pointer_info[class_element + cluster_info.pointer_fixup_offset]
                user_fix_id = pointer_info.user_fixup_id
                if user_fix_id is not None and user_fix_id < len(cluster_info.user_fixes):
                    val = cluster_info.user_fixes[user_fix_id].data
                else:
                    val = pointer_info.destination_object.object_list
            elif class_type_id is not None and (((cluster_info.class_descriptors[class_type_id-1].get_size_in_bytes() * (1 if data_member.fixed_array_size == 0 else data_member.fixed_array_size)) == expected_size) or ((type_text[0:7] == "PArray<") and (type_text[-1:] == ">")) or ((((type_text[0:9] == "PSharray<") and (type_text[-1:] == ">"))))):
                if data_member.fixed_array_size > 0:
                    val = []
                    structsize = cluster_info.class_descriptors[class_type_id-1].get_size_in_bytes()
                    for i in range(data_member.fixed_array_size):
                        val2 = {}
                        process_data_members(g, cluster_info, class_type_id, data_offset + (structsize * i), array_location, class_element, cluster_mesh_info, type_text, should_print_class, val2, cluster_header, data_instances_by_class, offset_from_parent + data_member.value_offset + (structsize * i), array_fixup_count, pointer_fixup_count)
                        val.append(val2)
                else:
                    val = {}
                    process_data_members(g, cluster_info, class_type_id, data_offset, array_location, class_element, cluster_mesh_info, type_text, should_print_class, val, cluster_header, data_instances_by_class, offset_from_parent + data_member.value_offset, array_fixup_count, pointer_fixup_count)
            else:
                string_variable = ' : TODO '

            if ((data_instances_by_class is not None) and (val is not None)) or (data_instances_by_class is None):
                dict_data[variable_text] = val

                if data_instances_by_class is None:
                    current_size = g.tell()-(member_location+data_member.value_offset)

                    is_inline_structure = (class_type_id is not None) and (cluster_info.class_descriptors[class_type_id-1].get_size_in_bytes() == expected_size)
                    is_pointer = False
                    if pointer_fixup_count > 0:
                        if cluster_info.pointer_info[cluster_info.pointer_fixup_offset+class_element].som == (value_offset+4):
                            is_pointer = True
                    if is_pointer == False:
                        is_pointer = (class_name[0:7] == "PArray<") and (class_name[-1:] == ">")
                    if is_pointer == False:
                        for b in range(pointer_fixup_count):
                            if cluster_info.pointer_info[b + cluster_info.pointer_fixup_offset].source_object_id == class_element:
                                is_pointer = True

        process_data_members(g, cluster_info, class_descriptor.super_class_id, member_location, array_location, class_element, cluster_mesh_info, class_name, should_print_class, dict_data, cluster_header, data_instances_by_class, offset_from_parent, array_fixup_count, pointer_fixup_count)

def process_cluster_instance_list_header(cluster_instance_list_header, g, count_list, cluster_info, cluster_mesh_info, cluster_header, filename, data_instances_by_class):
    classes_to_handle = [
     'PAnimationChannel',
     'PAnimationChannelTimes',
     'PAnimationClip',
     'PAnimationConstantChannel',
     'PAnimationSet',
     'PAssetReference',
     'PAssetReferenceImport',
     'PCgParameterInfoGCM',
     'PContextVariantFoldingTable',
     'PDataBlock',
     'PDataBlockD3D11',
     'PDataBlockGCM',
     'PDataBlockGNM',
     'PDataBlockGXM',
     'PEffect',
     'PEffectVariant',
     'PLight',
     'PLocator',
     'PMaterial',
     'PMaterialSwitch',
     'PMatrix4',
     'PMesh',
     'PMeshInstance',
     'PMeshInstanceBounds',
     'PMeshInstanceSegmentContext',
     'PMeshInstanceSegmentStreamBinding',
     'PMeshSegment',
     'PNode',
     'PNodeContext',
     'PParameterBuffer',
     'PPhysicsMaterial',
     'PPhysicsMesh',
     'PPhysicsModel',
     'PPhysicsRigidBody',
     'PSamplerState',
     'PSceneRenderPass',
     'PShader',
     'PShaderComputeProgram',
     'PShaderFragmentProgram',
     'PShaderGeometryProgram',
     'PShaderParameterCaptureBufferLocation',
     'PShaderParameterCaptureBufferLocationTypeConstantBuffer',
     'PShaderParameterDefinition',
     'PShaderPass',
     'PShaderPassInfo',
     'PShaderStreamDefinition',
     'PShaderVertexProgram',
     'PShape',
     'PSkeletonJointBounds',
     'PSkinBoneRemap',
     'PString',
     'PTexture2D',
     'PTextureCubeMap',
     'PVertexStream',
     'PWorldMatrix']
    member_location = g.tell()
    array_location = g.tell() + cluster_instance_list_header.objects_size
    should_print_class = ''
    class_name = get_class_name(cluster_info, cluster_instance_list_header.class_id)
    class_size = get_class_size(cluster_info, cluster_instance_list_header.class_id)
    should_print_class = class_name == should_print_class
    should_handle_class = should_print_class or class_name in classes_to_handle
    data_instances = None
    if data_instances_by_class is None:
        cluster_info.classes_strings.append(class_name)
        data_instances = []
    else:
        if count_list in data_instances_by_class:
            data_instances = data_instances_by_class[count_list]
        else:
            should_handle_class = False
    if should_handle_class:
        for i in range(cluster_instance_list_header.count):
            dict_data = None
            if data_instances_by_class is None:
                dict_data = {}
                data_instances.append(dict_data)
            else:
                dict_data = data_instances[i]
            g.seek(member_location)
            process_data_members(g, cluster_info, cluster_instance_list_header.class_id, member_location, array_location, i, cluster_mesh_info, class_name, should_print_class, dict_data, cluster_header, data_instances_by_class, 0, cluster_instance_list_header.array_fixup_count, cluster_instance_list_header.pointer_fixup_count)
            if data_instances_by_class is None:
                dict_data['mu_memberLoc'] = member_location
                dict_data['mu_memberClass'] = class_name
            else:
                reference_from_class_descriptor_index = get_reference_from_class_descriptor_index(cluster_info, class_name, i)
                if reference_from_class_descriptor_index is not None and len(list(reference_from_class_descriptor_index)) > 1:
                    dict_data['mu_name'] = reference_from_class_descriptor_index[1]
            member_location += class_size

    cluster_info.pointer_array_fixup_offset += cluster_instance_list_header.pointer_array_fixup_count
    cluster_info.pointer_fixup_offset += cluster_instance_list_header.pointer_fixup_count
    cluster_info.array_fixup_offset += cluster_instance_list_header.array_fixup_count
    if data_instances_by_class is not None:
        return
    else:
        if class_name == 'PAssetReference':
            for v in data_instances:
                if v['m_assetType'] not in cluster_info.list_for_class_descriptors:
                    cluster_info.list_for_class_descriptors[v['m_assetType']] = []
                cluster_info.list_for_class_descriptors[v['m_assetType']].append(v['m_id'])

        if class_name == 'PAssetReferenceImport':
            for v in data_instances:
                cluster_info.import_classes_strings.append(v['m_targetAssetType'])

        if should_handle_class:
            return data_instances
        return

class ClusterClusterHeader:
    cluster_marker = 0
    size = 0
    packed_namespace_size = 0
    platform_id = 0
    instance_list_count = 0
    array_fixup_size = 0
    array_fixup_count = 0
    pointer_fixup_size = 0
    pointer_fixup_count = 0
    pointer_array_fixup_size = 0
    pointer_array_fixup_count = 0
    pointers_in_arrays_count = 0
    user_fixup_count = 0
    user_fixup_data_size = 0
    total_data_size = 0
    header_class_instance_count = 0
    header_class_child_count = 0

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
    header = 0
    size = 0
    type_count = 0
    class_count = 0
    class_data_member_count = 0
    string_table_size = 0
    default_buffer_count = 0
    default_buffer_size = 0

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
    name_offset = 0
    type_id = 0
    value_offset = 0
    size_in_bytes = 0
    flags = 0
    fixed_array_size = 0
    name = ''

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

    def get_details(self):
        return ' byteSize:' + str(self.size_in_bytes) + ' offset:' + str(self.value_offset) + ' flags:' + str(self.flags) + ' fixedSize:' + str(self.fixed_array_size)

class ClusterPackedClassDescriptor:
    super_class_id = 0
    size_in_bytes_and_alignment = 0
    name_offset = 0
    class_data_member_count = 0
    offset_from_parent = 0
    offset_to_base = 0
    offset_to_base_in_allocated_block = 0
    flags = 0
    default_buffer_offset = 0
    member_offset = 0
    name = ''

    def __init__(self, g, cluster_header, label_offset):
        global g_classMemberCount
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
        self.member_offset = g_classMemberCount
        g_classMemberCount += self.class_data_member_count

    def get_size_in_bytes(self):
        return self.size_in_bytes_and_alignment & 268435455

    def get_alignment(self):
        return 1 << ((self.size_in_bytes_and_alignment & 4026531840) >> 28)

class ClusterInstanceListHeader:
    class_id = 0
    count = 0
    size = 0
    objects_size = 0
    arrays_size = 0
    pointers_in_arrays_count = 0
    array_fixup_count = 0
    pointer_fixup_count = 0
    pointer_array_fixup_count = 0

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
    type_id = 0
    offset = 0
    flags = 0
    count = 0

    def __init__(self, g, cluster_header, type_strings, class_descriptors):
        self.type_id = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.offset = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.flags = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.count = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')

class ClusterUserFixup:
    type_id = 0
    size = 0
    offset = 0

    def __init__(self, g, cluster_header):
        self.type_id = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.size = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')
        self.offset = read_integer(g, 4, False, '>' if cluster_header.cluster_marker == NOEPY_HEADER_BE else '<')

class ClusterUserFixupResult:
    user_fixup_target_offset = None
    user_fixup_type = None
    refer_type = None
    data_offset = 0
    data_size = 0
    defer = False
    data = None
    data_type = ''

    def __init__(self, g, fixup, type_strings, class_descriptors, Loc):
        self.data_type = get_type(fixup.type_id, type_strings, class_descriptors)
        self.defer = False
        old_position = g.tell()
        g.seek(Loc + fixup.offset)
        if self.data_type == 'PAssetReferenceImport':
            self.user_fixup_type = self.data_type
            self.defer = True
            self.data_offset = fixup.offset
            self.data_size = fixup.size
            self.data = read_integer(g, self.data_size, True, '>')
        else:
            self.user_fixup_target_offset = fixup.offset
            self.refer_type = self.data_type
            self.data = read_null_ending_string(g)
        g.seek(old_position)

class ClusterObjectID:
    object_id = 0
    object_list = 0

    def __init__(self):
        self.object_id = 0
        self.object_list = 0

class ClusterBaseFixup:
    source_offset_or_member = 0
    source_object_id = 0
    som = 0

    def unpack_source(self, fixup_buffer):
        som = cluster_variable_length_quantity_unpack(fixup_buffer)
        self.som = som >> 1
        if som & 1 != 0:
            self.source_offset_or_member = som >> 1 | 2147483648
        else:
            self.source_offset_or_member = som >> 1

    def is_class_data_member(self):
        return self.source_offset_or_member & 2147483648 == 0

    def get_source(self):
        if self.is_class_data_member():
            return ' m_memberID:' + str(self.som)
        else:
            return ' m_srcOffset:' + str(self.som)

    def unpack(self, fixup_buffer, mask):
        if mask & 1 == 0:
            self.unpack_source(fixup_buffer)
        if mask & 2 == 0:
            self.source_object_id = cluster_variable_length_quantity_unpack(fixup_buffer)

    def set_source_object_id(self, fixup_buffer, sourceObjectID):
        self.source_object_id = sourceObjectID

class ClusterArrayFixup(ClusterBaseFixup):
    offset = 0
    count = 0
    fixup_type = 'Array'

    def initialize(self):
        self.source_offset_or_member = 0
        self.source_object_id = 0
        self.count = 0
        self.offset = 0

    def get_details(self):
        return ' count:' + str(self.count) + ' offset:' + str(self.offset) + ' source:' + str(self.get_source())

    def unpack_fixup(self, fixup_buffer, mask):
        if mask & 8 == 0:
            self.count = cluster_variable_length_quantity_unpack(fixup_buffer)
        self.offset = cluster_variable_length_quantity_unpack(fixup_buffer)

    def unpack(self, fixup_buffer, mask):
        super(ClusterArrayFixup, self).unpack(fixup_buffer, mask)
        self.unpack_fixup(fixup_buffer, mask)

class ClusterPointerFixup(ClusterBaseFixup):
    destination_object = None
    destination_offset = 0
    array_index = 0
    user_fixup_id = 0
    fixup_type = 'Pointer'

    def initialize(self):
        self.source_offset_or_member = 0
        self.source_object_id = 0
        self.destination_object = ClusterObjectID()
        self.destination_offset = 0
        self.array_index = 0
        self.user_fixup_id = None

    def get_details(self):
        destination_id = None
        destination_list = None
        if self.destination_object is not None:
            destination_id = self.destination_object.object_id
            destination_list = self.destination_object.object_list
        return ' user_fix_id:' + str(self.user_fixup_id) + ' srcObj:' + str(self.source_object_id) + ' arrIdx:' + str(self.array_index) + ' destOff:' + str(self.destination_offset) + ' destID:' + str(destination_id) + ' destLst:' + str(destination_list) + ' source:' + str(self.get_source())

    def unpack_fixup(self, fixup_buffer, mask):
        is_user_fixup = False
        if mask & 16 == 0:
            user_fixup_id = cluster_variable_length_quantity_unpack(fixup_buffer)
            is_user_fixup = user_fixup_id != 0
            if is_user_fixup:
                self.user_fixup_id = user_fixup_id - 1
        else:
            self.user_fixup_id = None
        if is_user_fixup is not True:
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
    unpack_mask = 0
    object_count = 0

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
            next = 0
            if self.object_count < 256:
                next = fixup_buffer.read()
            else:
                next = cluster_variable_length_quantity_unpack(fixup_buffer)
            fixup_buffer.set_fixup(template_fixup)
            unpack_id(fixup_buffer, next, self.unpack_mask)
            fixup_buffer.next_fixup()

        return patching_count

    def unpack_exclusive(self, template_fixup, fixup_buffer):
        patching_count = cluster_variable_length_quantity_unpack(fixup_buffer)
        last = 0
        for i in range(patching_count):
            next = 0
            if self.object_count < 256:
                next = fixup_buffer.read()
            else:
                next = cluster_variable_length_quantity_unpack(fixup_buffer)
            for o in range(last, next):
                fixup_buffer.set_fixup(template_fixup)
                unpack_id(fixup_buffer, o, self.unpack_mask)
                fixup_buffer.next_fixup()

            last = next + 1

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
    pointer_array_fixup_offset = 0
    pointer_fixup_offset = 0
    array_fixup_offset = 0
    pointer_array_info = None
    pointer_info = None
    array_info = None
    class_descriptors = None
    data_members = None
    user_fixes = None
    type_strings = None
    list_for_class_descriptors = None
    classes_strings = None
    import_classes_strings = None

    def __init__(self, pointer_array, pointer, array, class_descriptor, data_members, type_strings, user_fixes, list_for_class_descriptors, classes_strings, import_classes_strings):
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
    pointer_index = 0
    offset = 0
    size = 0
    fixup_buffer = None
    decompressed = []

    def __init__(self, g, size, decompressed):
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
            if self.decompressed[self.pointer_index].destination_object is None:
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
    next = 0
    shift = 0
    while next & 128 != 0 or by_pass:
        by_pass = False
        next = fixup_buffer.read()
        result |= (next & 127) << shift
        shift += 7

    return result

def decompress(fixup_buffer, fixup_count, object_count, is_pointer):
    pointer_end = fixup_buffer.pointer_index + fixup_count
    while fixup_buffer.pointer_index < pointer_end:
        pack_type_with_mask = fixup_buffer.read()
        pack_type = pack_type_with_mask & 7
        mask = pack_type_with_mask & -8
        mask_for_fixups = mask | 1
        if object_count == 1:
            mask_for_fixups |= 2
        template_fixup = None
        if is_pointer:
            template_fixup = ClusterPointerFixup()
        else:
            template_fixup = ClusterArrayFixup()
        template_fixup.initialize()
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

def parse_cluster(filename='', reserved_argument=None, storage_media=None, pkg_name='', partialmaps = False, allbuffers = False, item_num = 0):
    global g_classMemberCount
    class_descriptors = []
    class_data_members = []
    instance_list = []
    user_fixups = []
    user_fixup_results = []
    header_class_children = []
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
    type_ids = array.array('i', g.read(name_spaces.type_count * 4))
    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
        type_ids.byteswap()
    label_offset = g.tell() + name_spaces.class_count * 36 + name_spaces.class_data_member_count * 24
    old_position = g.tell()
    for i in range(len(type_ids)):
        g.seek(label_offset + type_ids[i])
        type_list.append(read_null_ending_string(g))

    g.seek(old_position)
    g_classMemberCount = 0
    for i in range(name_spaces.class_count):
        class_descriptors.append(ClusterPackedClassDescriptor(g, cluster_header, label_offset))

    for i in range(name_spaces.class_data_member_count):
        class_data_members.append(ClusterPackedDataMember(g, cluster_header, label_offset))

    g.seek(g.tell() + name_spaces.string_table_size)
    for i in range(cluster_header.instance_list_count):
        instance_list.append(ClusterInstanceListHeader(g, cluster_header))

    object_data_offset = g.tell()
    g.seek(object_data_offset + cluster_header.total_data_size)
    user_fixup_data_offset = g.tell()
    g.seek(user_fixup_data_offset + cluster_header.user_fixup_data_size)
    for i in range(cluster_header.user_fixup_count):
        user_fixups.append(ClusterUserFixup(g, cluster_header))
        user_fixup_results.append(ClusterUserFixupResult(g, user_fixups[i], type_list, class_descriptors, user_fixup_data_offset))

    header_class_ids = array.array('i', g.read(cluster_header.header_class_instance_count * 4))
    if cluster_header.cluster_marker == NOEPY_HEADER_BE:
        header_class_ids.byteswap()
    for i in range(cluster_header.header_class_child_count):
        header_class_children.append(ClusterHeaderClassChildArray(g, cluster_header, type_list, class_descriptors))

    pointer_fixup_total = 0
    array_fixup_total = 0
    array_pointer_fixup_total = 0
    for i in range(len(instance_list)):
        pointer_fixup_total += instance_list[i].pointer_fixup_count
        array_fixup_total += instance_list[i].array_fixup_count
        array_pointer_fixup_total += instance_list[i].pointer_array_fixup_count

    pointer_array_fixup_offset = g.tell()
    pointer_array_fixups = []
    for i in range(array_pointer_fixup_total):
        pointer_array_fixups.append(ClusterArrayFixup())

    pointer_array_fixups = decompress_fixups(FixUpBuffer(g, cluster_header.pointer_array_fixup_size, pointer_array_fixups), instance_list, True, False)
    g.seek(pointer_array_fixup_offset + cluster_header.pointer_array_fixup_size)
    pointer_fixup_offset = g.tell()
    pointer_fixups = []
    for i in range(pointer_fixup_total):
        pointer_fixups.append(ClusterPointerFixup())

    pointer_fixups = decompress_fixups(FixUpBuffer(g, cluster_header.pointer_fixup_size, pointer_fixups), instance_list, False, True)
    g.seek(pointer_fixup_offset + cluster_header.pointer_fixup_size)
    array_fixup_offset = g.tell()
    array_fixups = []
    for i in range(array_fixup_total):
        array_fixups.append(ClusterArrayFixup())

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
            process_data_members(g, header_processor, i + 1, 0, 0, 0, cluster_mesh_info, class_descriptor.name, False, dict_data, cluster_header, None, 0, 0, 0)
            break

    g.seek(object_data_offset)
    class_location = g.tell()
    count_list = 0
    data_instances_by_class = {}
    for instance_list_header in instance_list:
        g.seek(class_location)
        data_instances = process_cluster_instance_list_header(instance_list_header, g, count_list, header_processor, cluster_mesh_info, cluster_header, filename, None)
        if data_instances is not None:
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

    render_mesh(g, cluster_mesh_info, header_processor, cluster_header, pkg_name, partialmaps = partialmaps, allbuffers = allbuffers, item_num = item_num)
    return cluster_mesh_info

def file_is_ed8_pkg(path):
    path = os.path.realpath(path)
    if not os.path.isfile(path):
        return False
    max_offset = 0
    with open(path, 'rb') as (f):
        f.seek(0, 2)
        length = f.tell()
        f.seek(0, 0)
        if length <= 4:
            return False
        f.seek(4, io.SEEK_CUR)
        total_file_entries, = struct.unpack('<I', f.read(4))
        if length < 8 + 80 * total_file_entries:
            return False
        for i in range(total_file_entries):
            file_entry_name, file_entry_uncompressed_size, file_entry_compressed_size, file_entry_offset, file_entry_flags = struct.unpack('<64sIIII', f.read(80))
            cur_offset = file_entry_offset + file_entry_compressed_size
            if cur_offset > max_offset:
                max_offset = cur_offset

        if length < max_offset:
            return False
    return True

class MeshInfo:
    cluster_header = {}
    data_instances_by_class = {}
    gltf_data = {}
    filename = ''
    storage_media = None
    vram_model_data_offset = 0
    bone_names = []

    def __init__(self):
        self.cluster_header = {}
        self.data_instances_by_class = {}
        self.gltf_data = {}
        self.filename = ''
        self.storage_media = None
        self.vram_model_data_offset = 0
        self.bone_names = []

class IStorageMedia:

    def __init__(self):
        pass

    def normalize_path_name(self, name):
        raise Exception('This member needs to be overrided')

    def check_existent_storage(self, name):
        raise Exception('This member needs to be overrided')

    def open(self, name, flags):
        raise Exception('This member needs to be overrided')

    def get_list_at(self, name, list_callback):
        raise Exception('This member needs to be overrided')

class TFileMedia(IStorageMedia):
    basepath = None

    def __init__(self, basepath):
        basepath = os.path.realpath(basepath)
        if not os.path.isdir(basepath):
            raise Exception('Passed in basepath is not directory')
        self.basepath = basepath

    def normalize_path_name(self, name):
        return os.path.normpath(name)

    def check_existent_storage(self, name):
        return os.path.isfile(self.basepath + '/' + name)

    def open(self, name, flags='rb', **kwargs):
        return open(self.basepath + '/' + name, flags, **kwargs)

    def get_list_at(self, name, list_callback):
        llist = sorted(os.listdir(self.basepath))
        for item in llist:
            if list_callback(item):
                break

class TED8PkgMedia(IStorageMedia):
    path = None
    basepath = None
    file_entries = None
    f = None

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
        total_file_entries, = struct.unpack('<I', f.read(4))
        for i in range(total_file_entries):
            file_entry_name, file_entry_uncompressed_size, file_entry_compressed_size, file_entry_offset, file_entry_flags = struct.unpack('<64sIIII', f.read(80))
            package_file_entries[file_entry_name.rstrip(b'\x00').decode('ASCII')] = [file_entry_offset, file_entry_compressed_size, file_entry_uncompressed_size, file_entry_flags]

        self.file_entries = package_file_entries

    def normalize_path_name(self, name):
        return os.path.normpath(name)

    def check_existent_storage(self, name):
        return name in self.file_entries

    def open(self, name, flags='rb', **kwargs):
        file_entry = self.file_entries[name]
        self.f.seek(file_entry[0])
        output_data = None
        if file_entry[3] & 2:
            self.f.seek(4, io.SEEK_CUR)
        if file_entry[3] & 4:
            output_data = uncompress_lz4(self.f, file_entry[2], file_entry[1])
        elif file_entry[3] & 1:
            output_data = uncompress_nislzss(self.f, file_entry[2], file_entry[1])
        elif file_entry[3] & 8:
            if "zstandard" in sys.modules:
                output_data = uncompress_zstd(self.f, file_entry[2], file_entry[1])
            else:
                print(("File %s could not be extracted because zstandard module is not installed") % (""))
        else:
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
    handler = None

    def close(self, *args, **kwargs):
        if self.handler is not None and not self.closed:
            self.handler(self.getvalue())
        super().close(*args, **kwargs)

    def set_close_handler(self, handler):
        self.handler = handler

class TSpecialMemoryMedia(IStorageMedia):
    file_entries = None

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
        raise Exception('Reading in text mode not supported')

    def get_list_at(self, name, list_callback):
        llist = sorted(self.file_entries.keys())
        for item in llist:
            if list_callback(item):
                break

class TSpecialOverlayMedia(IStorageMedia):
    storage0 = None
    storage1 = None
    storage2 = None

    def __init__(self, path):
        self.storage0 = TFileMedia(os.path.dirname(path))
        self.storage1 = TSpecialMemoryMedia()
        self.storage2 = TED8PkgMedia(path)

    def normalize_path_name(self, name):
        return os.path.normpath(name)

    def check_existent_storage(self, name):
        return self.storage1.check_existent_storage(name) or self.storage2.check_existent_storage(name)

    def open(self, name, flags='rb', **kwargs):
        if 'w' in flags:
            return self.storage0.open(name, flags, **kwargs)
            if name.endswith('.glb'):
                return self.storage0.open(name, flags, **kwargs)
            return self.storage1.open(name, flags, **kwargs)
        if self.storage0.check_existent_storage(name):
            return self.storage0.open(name, flags, **kwargs)
        if self.storage1.check_existent_storage(name):
            return self.storage1.open(name, flags, **kwargs)
        if self.storage2.check_existent_storage(name):
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
        current_width = current_width + 3 & -4
        current_height = current_height + 3 & -4
    return current_width * current_height * bpp // 8

def get_mipmap_offset_and_size(mipmap_level, width, height, texture_format, is_cube_map):
    size_map = {'DXT1': 4, 
     'DXT3': 8, 
     'DXT5': 8, 
     'BC5': 8, 
     'BC7': 8, 
     'RGBA8': 32, 
     'ARGB8': 32, 
     'L8': 8, 
     'A8': 8, 
     'LA88': 16, 
     'RGBA16F': 64, 
     'ARGB1555': 16, 
     'ARGB4444': 16, 
     'ARGB8_SRGB': 32}
    block_map = [
     'DXT1',
     'DXT3',
     'DXT5',
     'BC5',
     'BC7']
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
        current_width = current_width + 3 & -4
        current_height = current_height + 3 & -4
    return (
     offset, current_width * current_height * bpp // 8, current_width, current_height)

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
        print('GXM textures are currently not completely supported. Corrupted texture may result')
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
        image_data = Unswizzle(image_data, image_width, image_height, dict_data["m_format"], True, cluster_header.platform_id, pitch)
    elif cluster_header.platform_id == GCM_PLATFORM:
        size_map = {'ARGB8': 4, 
         'RGBA8': 4, 
         'ARGB4444': 2, 
         'L8': 1, 
         'LA8': 2}
        if dict_data['m_format'] in size_map:
            image_data = Unswizzle(image_data, image_width, image_height, dict_data['m_format'], True, cluster_header.platform_id, pitch)
    if 'PAssetReference' in cluster_mesh_info.data_instances_by_class:
        path_name = pkg_name + '/' + os.path.dirname(cluster_mesh_info.data_instances_by_class['PAssetReference'][0]['m_id'])
    else:
        path_name = pkg_name + '/textures'
    if not os.path.exists(path_name):
        os.makedirs(path_name)
    dds_output_path = path_name + '/' + cluster_mesh_info.filename.split('.', 1)[0] + '.dds'
    with cluster_mesh_info.storage_media.open(dds_output_path, 'wb') as (f):
        f.write(get_dds_header(dict_data['m_format'], image_width, image_height, None, False))
        f.write(image_data)

def load_texture(dict_data, cluster_mesh_info, pkg_name = ''):
    dds_basename = os.path.basename(dict_data['m_id'])
    found_basename = []

    def list_callback(item):
        if item[:-6] == dds_basename:
            found_basename.append(item)
            return True
    cluster_mesh_info.storage_media.get_list_at('.', list_callback)
    if True and len(found_basename) > 0:
        parse_cluster(found_basename[0], None, cluster_mesh_info.storage_media, pkg_name)

def load_materials_with_actual_name(dict_data, cluster_mesh_info):
    if type(dict_data['m_effectVariant']) is dict and 'm_id' in dict_data['m_effectVariant']:
        dict_data['mu_compiledShaderName'] = dict_data['m_effectVariant']['m_id']

def load_shader_parameters(g, dict_data, cluster_header):
    if 'mu_shaderParameters' in dict_data:
        return
    old_position = g.tell()
    g.seek(dict_data['mu_memberLoc'])
    parameter_buffer = g.read(dict_data['m_parameterBufferSize'])
    g.seek(old_position)
    shader_parameters = {}
    for x in dict_data['m_tweakableShaderParameterDefinitions']:
        parameter_offset = x['m_bufferLoc']['m_offset']
        parameter_size = x['m_bufferLoc']['m_size']
        if x['m_parameterType'] == 66 or x['m_parameterType'] == 68:
            arr = array.array('I', parameter_buffer[parameter_offset:parameter_offset + parameter_size])
            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                arr.byteswap()
            shader_parameters[x['m_name']] = arr
            if x['m_name'] in dict_data['mu_tweakableShaderParameterDefinitionsObjectReferences']:
                shader_parameters[x['m_name']] = dict_data['mu_tweakableShaderParameterDefinitionsObjectReferences'][x['m_name']]['m_id']
        elif x['m_parameterType'] == 71:
            arr = array.array('I', parameter_buffer[parameter_offset:parameter_offset + parameter_size])
            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                arr.byteswap()
            shader_parameters[x['m_name']] = arr
            if x['m_name'] in dict_data['mu_tweakableShaderParameterDefinitionsObjectReferences']:
                shader_parameters[x['m_name']] = dict_data['mu_tweakableShaderParameterDefinitionsObjectReferences'][x['m_name']]
        elif parameter_size == 24:
            shader_parameters[x['m_name']] = struct.unpack('IIQQ', parameter_buffer[parameter_offset:parameter_offset + parameter_size])
        elif parameter_size % 4 == 0:
            arr = array.array('f', parameter_buffer[parameter_offset:parameter_offset + parameter_size])
            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                arr.byteswap()
            shader_parameters[x['m_name']] = arr
        else:
            shader_parameters[x['m_name']] = parameter_buffer[parameter_offset:parameter_offset + parameter_size]

    dict_data['mu_shaderParameters'] = shader_parameters

def multiply_array_as_4x4_matrix(arra, arrb):
    newarr = array.array('f', arra)
    for i in range(4):
        for j in range(4):
            newarr[i * 4 + j] = 0 + arrb[(i * 4 + 0)] * arra[(j + 0)] + arrb[(i * 4 + 1)] * arra[(j + 4)] + arrb[(i * 4 + 2)] * arra[(j + 8)] + arrb[(i * 4 + 3)] * arra[(j + 12)]

    return newarr

def invert_matrix_44(m):
    inv = array.array('f', m)
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
        return
    det = 1.0 / det
    for i in range(16):
        inv[i] *= det

    return inv

indiceTypeLengthMapping = {8: 5125, 
 12: 5123, 
 16: 5121, 
 20: 5123, 
 24: 5121, 
 28: 5125, 
 32: 5122, 
 36: 5121, 
 40: 5123, 
 44: 5121}
indiceTypeLengthMappingPython = {8: 'I', 
 12: 'H', 
 16: 'B', 
 20: 'H', 
 24: 'B', 
 28: 'i', 
 32: 'h', 
 36: 'b', 
 40: 'h', 
 44: 'b'}
indiceTypeMappingSize = {8: 4, 
 12: 2, 
 16: 1, 
 20: 2, 
 24: 1, 
 28: 4, 
 32: 2, 
 36: 1, 
 40: 2, 
 44: 1}
dataTypeMappingForGltf = {0: 5126, 
 1: 5126, 
 2: 5126, 
 3: 5126, 
 12: 5123, 
 13: 5123, 
 14: 5123, 
 15: 5123, 
 16: 5121, 
 17: 5121, 
 18: 5121, 
 19: 5121, 
 20: 5123, 
 21: 5123, 
 22: 5123, 
 23: 5123, 
 24: 5121, 
 25: 5121, 
 26: 5121, 
 27: 5121, 
 32: 5123, 
 33: 5123, 
 34: 5123, 
 35: 5123, 
 36: 5121, 
 37: 5121, 
 38: 5121, 
 39: 5121, 
 40: 5123, 
 41: 5123, 
 42: 5123, 
 43: 5123, 
 44: 5121, 
 45: 5121, 
 46: 5121, 
 47: 5121}
dataTypeMappingForPython = {0: 'f', 
 1: 'f', 
 2: 'f', 
 3: 'f', 
 8: 'I', 
 9: 'I', 
 10: 'I', 
 11: 'I', 
 12: 'H', 
 13: 'H', 
 14: 'H', 
 15: 'H', 
 16: 'B', 
 17: 'B', 
 18: 'B', 
 19: 'B', 
 20: 'H', 
 21: 'H', 
 22: 'H', 
 23: 'H', 
 24: 'B', 
 25: 'B', 
 26: 'B', 
 27: 'B', 
 28: 'i', 
 29: 'i', 
 30: 'i', 
 31: 'i', 
 32: 'h', 
 33: 'h', 
 34: 'h', 
 35: 'h', 
 36: 'b', 
 37: 'b', 
 38: 'b', 
 39: 'b', 
 40: 'h', 
 41: 'h', 
 42: 'h', 
 43: 'h', 
 44: 'b', 
 45: 'b', 
 46: 'b', 
 47: 'b'}
dataTypeMappingSize = {0: 4, 
 1: 4, 
 2: 4, 
 3: 4, 
 4: 2, 
 5: 2, 
 6: 2, 
 7: 2, 
 8: 4, 
 9: 4, 
 10: 4, 
 11: 4, 
 12: 2, 
 13: 2, 
 14: 2, 
 15: 2, 
 16: 1, 
 17: 1, 
 18: 1, 
 19: 1, 
 20: 2, 
 21: 2, 
 22: 2, 
 23: 2, 
 24: 1, 
 25: 1, 
 26: 1, 
 27: 1, 
 28: 4, 
 29: 4, 
 30: 4, 
 31: 4, 
 32: 2, 
 33: 2, 
 34: 2, 
 35: 2, 
 36: 1, 
 37: 1, 
 38: 1, 
 39: 1, 
 40: 2, 
 41: 2, 
 42: 2, 
 43: 2, 
 44: 1, 
 45: 1, 
 46: 1, 
 47: 1}
dataTypeCountMappingForGltf = {0: 'SCALAR', 
 1: 'VEC2', 
 2: 'VEC3', 
 3: 'VEC4'}

def render_mesh(g, cluster_mesh_info, cluster_info, cluster_header, pkg_name='', partialmaps = False, allbuffers = False, item_num = 0):
    print("Processing {0}...".format(cluster_mesh_info.filename))
    if 'PTexture2D' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PTexture2D']:
            create_texture(g, v, cluster_mesh_info, cluster_header, False, pkg_name)

    if 'PTextureCubeMap' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PTextureCubeMap']:
            create_texture(g, v, cluster_mesh_info, cluster_header, True, pkg_name)

    if 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
            if not v['m_targetAssetType'] == 'PTexture2D':
                if v['m_targetAssetType'] == 'PTextureCubeMap':
                    pass
            load_texture(v, cluster_mesh_info, pkg_name)

    if 'PParameterBuffer' in cluster_mesh_info.data_instances_by_class:
        for k in cluster_mesh_info.data_instances_by_class.keys():
            has_key = False
            if type(k) is int:
                data_instances = cluster_mesh_info.data_instances_by_class[k]
                if len(data_instances) > 0:
                    if data_instances[0]['mu_memberClass'] == 'PParameterBuffer':
                        has_key = True
            if has_key == True:
                for v in cluster_mesh_info.data_instances_by_class[k]:
                    load_shader_parameters(g, v, cluster_header)

    clsuter_basename_noext = cluster_mesh_info.filename.split('.', 1)[0]
    if 'PMaterial' in cluster_mesh_info.data_instances_by_class:
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
                indvertbuffercache[cachekey] = indvertbuffer[v['mu_indBufferPosition']:v['mu_indBufferPosition'] + v['mu_indBufferSize']].tobytes()
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
            indvertbuffercache[cachekey] = indvertbuffer[v['mu_vertBufferPosition']:v['mu_vertBufferPosition'] + v['mu_vertBufferSize']].tobytes()
        v['mu_vertBuffer'] = indvertbuffercache[cachekey]

    if 'PMesh' in cluster_mesh_info.data_instances_by_class:
        data_instances = cluster_mesh_info.data_instances_by_class['PMesh']
        for v in cluster_mesh_info.data_instances_by_class['PMesh']:
            bonePosePtr = v['m_defaultPose']
            bonePoseName = v['m_matrixNames']
            bonePoseInd = v['m_matrixParents']
            boneSkelMat = v['m_skeletonMatrices']
            boneSkelBounds = v['m_skeletonBounds']
            boneSkelMap = {}
            if boneSkelBounds is not None:
                if len(boneSkelBounds) > 0:
                    if type(boneSkelBounds) is not int:
                        if 'm_els' not in boneSkelMat:
                            for i in range(len(boneSkelBounds)):
                                boneSkelMap[boneSkelBounds[i]['m_hierarchyMatrixIndex']] = invert_matrix_44(boneSkelMat[i]['m_elements'])

            if len(bonePosePtr) > 0 and "m_els" not in bonePosePtr and type(bonePosePtr[0]) is not int:
                skinMat = []

                for i in range(len(bonePosePtr)):
                    skinMat.append(bonePosePtr[i]["m_elements"])

                for sm in range(len(skinMat)):
                    pm = bonePoseInd[sm]
                    pn = 'TERoots'
                    if pm >= 0 and len(bonePoseName) > pm:
                        pn = bonePoseName[pm]["m_buffer"]

                    bn = 'TERoots'
                    if sm >= 0 and len(bonePoseName) > sm:
                        bn = bonePoseName[sm]["m_buffer"]

                    cur_matrix = skinMat[sm]
                    if sm in boneSkelMap:
                        cur_matrix = boneSkelMap[sm]
                    else:
                        jump_count = 0
                        jump_count_max = len(boneSkelBounds)
                        cur_parent_index = pm
                        while cur_parent_index != -1 and cur_parent_index in skinMat and jump_count < jump_count_max:
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

            if type(v['m_meshSegments']) is list:
                for m in v['m_meshSegments']:
                    boneRemap = array.array('H')
                    boneRemap2 = array.array('H')
                    if len(bonePosePtr) > 0:
                        if 'm_els' not in bonePosePtr:
                            if len(m['m_skinBones']) > 0:
                                if type(m['m_skinBones'][0]) is not int:
                                    m['m_gltfSkinBoneMap'] = [x['m_skeletonMatrixIndex'] for x in m['m_skinBones']]
                                    for sb in m['m_skinBones']:
                                        boneRemap.append(sb['m_hierarchyMatrixIndex'])
                                        boneRemap2.append(sb['m_skeletonMatrixIndex'])

                    for vertexData in m['m_vertexData']:
                        streamInfo = vertexData['m_streams'][0]
                        datatype = streamInfo['m_type']
                        dataTypeCount = datatype % 4 + 1
                        blobdata = vertexData['mu_vertBuffer']
                        singleelementsize = dataTypeMappingSize[datatype]
                        blobstride = vertexData['m_stride']
                        if streamInfo['m_renderDataType'] == 'SkinIndices':
                            if dataTypeCount * singleelementsize != blobstride:
                                deinterleaved_data = bytearray()
                                for i in range(vertexData['m_elementCount']):
                                    deinterleaved_data += blobdata[blobstride * i + vertexData['m_streams'][0]['m_offset']:blobstride * i + vertexData['m_streams'][0]['m_offset'] + singleelementsize * dataTypeCount]

                                blobstride = dataTypeCount * dataTypeMappingSize[datatype]
                                blobdata = bytes(deinterleaved_data)
                            elif dataTypeCount * singleelementsize * vertexData['m_elementCount'] != len(blobdata):
                                blobdata = blobdata[vertexData['m_streams'][0]['m_offset']:vertexData['m_streams'][0]['m_offset'] + dataTypeCount * singleelementsize * vertexData['m_elementCount']]
                            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                                blobdatabyteswap = array.array(dataTypeMappingForPython[datatype], blobdata)
                                blobdatabyteswap.byteswap()
                                blobdata = blobdatabyteswap.tobytes()
                            skinInd = array.array(dataTypeMappingForPython[datatype], blobdata)
                            vertexData['mu_originalVertBufferSkeleton'] = skinInd.tobytes()
                            if len(boneRemap) > 0:
                                remapInd = array.array('H')
                                for mb in skinInd:
                                    remapInd.append(boneRemap[mb])

                                vertexData['mu_remappedVertBuffer'] = remapInd.tobytes()
                            if len(boneRemap2) > 0:
                                remapInd2 = array.array('H')
                                for mb in skinInd:
                                    remapInd2.append(boneRemap2[mb])

                                vertexData['mu_remappedVertBufferSkeleton'] = remapInd2.tobytes()

    gltf_export(g, cluster_mesh_info, cluster_info, cluster_header, pdatablock_list, pkg_name, partialmaps = partialmaps, allbuffers = allbuffers, item_num = item_num)

shader_material_switches = {}

def gltf_export(g, cluster_mesh_info, cluster_info, cluster_header, pdatablock_list, pkg_name='', partialmaps = False, allbuffers = False, item_num = 0):
    global shader_material_switches
    import json
    # Use the presence of metadata files to determine which .dae asset we are processing
    if item_num == 0:
        metadata_json_name = pkg_name + "/metadata.json" # First file will be metadata.json
        physics_json_name = pkg_name + "/physics_data.json" # First file will be metadata.json
        mesh_folder_name = pkg_name + "/meshes"
    else:
        metadata_json_name = pkg_name + "/metadata_{0}.json".format(str(item_num).zfill(2))
        physics_json_name = pkg_name + "/physics_data_{0}.json".format(str(item_num).zfill(2))
        mesh_folder_name = pkg_name + "/meshes_{0}".format(str(item_num).zfill(2))
    metadata_json = {'name': cluster_mesh_info.filename.split('.', 1)[0], 'pkg_name': pkg_name}
    if not os.path.exists(mesh_folder_name):
        os.mkdir(mesh_folder_name)
    asset = {}
    asset['generator'] = 'ed8pkg2glb'
    asset['version'] = '2.0'
    cluster_mesh_info.gltf_data['asset'] = asset
    extensionsUsed = []
    cluster_mesh_info.gltf_data['extensionsUsed'] = extensionsUsed
    buffers = []
    need_embed = True
    if need_embed == False:
        need_embed = cluster_header.cluster_marker == NOEPY_HEADER_BE
    if need_embed == False:
        for v in pdatablock_list:
            datatype = v['m_streams'][0]['m_type']
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
    embedded_giant_buffer_length = 0
    if 'PMeshSegment' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PMeshSegment']:
            accessor = {}
            accessor['bufferView'] = len(bufferviews)
            indiceTypeForGltf = 5123
            if v['m_indexData']['m_type'] in indiceTypeLengthMapping:
                indiceTypeForGltf = indiceTypeLengthMapping[v['m_indexData']['m_type']]
            else:
                print('XXX: unhandled indice type ' + str(v['m_indexData']['m_type']))
            accessor['componentType'] = indiceTypeForGltf
            accessor['min'] = [v['m_indexData']['m_minimumIndex']]
            accessor['max'] = [v['m_indexData']['m_maximumIndex']]
            accessor['type'] = 'SCALAR'
            accessor['count'] = v['m_indexData']['m_elementCount']
            v['mu_gltfAccessorIndex'] = len(accessors)
            bufferview = {}
            if need_embed:
                blobdata = v['mu_indBuffer']
                singleelementsize = indiceTypeMappingSize[v['m_indexData']['m_type']]
                if singleelementsize * v['m_indexData']['m_elementCount'] != len(blobdata):
                    blobdata = blobdata[:singleelementsize * v['m_indexData']['m_elementCount']]
                if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                    blobdatabyteswap = array.array(indiceTypeLengthMappingPython[v['m_indexData']['m_type']], blobdata)
                    blobdatabyteswap.byteswap()
                    blobdata = blobdatabyteswap.tobytes()
                bufferview['buffer'] = 0
                bufferview['byteOffset'] = embedded_giant_buffer_length
                bufferview['byteLength'] = len(blobdata)
                embedded_giant_buffer.append(blobdata)
                embedded_giant_buffer_length += len(blobdata)
                padding_length = 4 - len(blobdata) % 4
                embedded_giant_buffer.append(b'\x00' * padding_length)
                embedded_giant_buffer_length += padding_length
            else:
                bufferview['buffer'] = 1
                bufferview['byteOffset'] = cluster_mesh_info.vram_model_data_offset + v['mu_indBufferPosition']
                bufferview['byteLength'] = v['mu_indBufferSize']
            bufferviews.append(bufferview)
            accessors.append(accessor)

    #if 'PMesh' in cluster_mesh_info.data_instances_by_class:
        #for v in cluster_mesh_info.data_instances_by_class['PMesh']:
            #matrix_list = []
            #if 'm_skeletonMatrices' in v and type(v['m_skeletonMatrices']) is list:
                #for vv in v['m_skeletonMatrices']:
                    #matrix_list.append(vv['m_elements'].tobytes())

            #if len(matrix_list) > 0:
                #blobdata = b''.join(matrix_list)
                #bufferview = {}
                #bufferview['buffer'] = 0
                #bufferview['byteOffset'] = embedded_giant_buffer_length
                #bufferview['byteLength'] = len(blobdata)
                #embedded_giant_buffer.append(blobdata)
                #embedded_giant_buffer_length += len(blobdata)
                #padding_length = 4 - len(blobdata) % 4
                #embedded_giant_buffer.append(b'\x00' * padding_length)
                #embedded_giant_buffer_length += padding_length
                #accessor = {}
                #accessor['bufferView'] = len(bufferviews)
                #accessor['componentType'] = 5126
                #accessor['type'] = 'MAT4'
                #accessor['count'] = len(matrix_list)
                #v['mu_gltfAccessorForInverseBindMatrixIndex'] = len(accessors)
                #accessors.append(accessor)
                #bufferviews.append(bufferview)

    if 'PMeshSegment' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PMeshSegment']:
            for vvv in v['m_vertexData']:
                for vvvv in vvv['m_streams']:
                    #if vvvv['m_renderDataType'] == 'SkinIndices' and 'mu_remappedVertBufferSkeleton' in vvv:
                        #blobdata = vvv['mu_remappedVertBufferSkeleton']
                    ##if vvvv['m_renderDataType'] == 'SkinIndices' and 'mu_originalVertBufferSkeleton' in vvv:
                        ##blobdata = vvv['mu_originalVertBufferSkeleton']
                        #bufferview = {}
                        #bufferview['buffer'] = 0
                        #bufferview['byteOffset'] = embedded_giant_buffer_length
                        #bufferview['byteLength'] = len(blobdata)
                        #embedded_giant_buffer.append(blobdata)
                        #embedded_giant_buffer_length += len(blobdata)
                        #padding_length = 4 - len(blobdata) % 4
                        #embedded_giant_buffer.append(b'\x00' * padding_length)
                        #embedded_giant_buffer_length += padding_length
                        #accessor = {}
                        #accessor['bufferView'] = len(bufferviews)
                        #accessor['componentType'] = 5123
                        #accessor['type'] = 'VEC4'
                        #accessor['count'] = vvv['m_elementCount']
                        #vvvv['mu_gltfAccessorForRemappedSkinIndiciesIndex'] = len(accessors)
                        ##vvvv['mu_gltfAccessorForOriginalSkinIndiciesIndex'] = len(accessors)
                        #accessors.append(accessor)
                        #bufferviews.append(bufferview)
                    if (vvvv['m_renderDataType'] == 'Tangent' or vvvv['m_renderDataType'] == 'SkinnableTangent') and 'mu_expandedHandednessTangent' in vvv:
                        blobdata = vvv['mu_expandedHandednessTangent']
                        bufferview = {}
                        bufferview['buffer'] = 0
                        bufferview['byteOffset'] = embedded_giant_buffer_length
                        bufferview['byteLength'] = len(blobdata)
                        embedded_giant_buffer.append(blobdata)
                        embedded_giant_buffer_length += len(blobdata)
                        padding_length = 4 - len(blobdata) % 4
                        embedded_giant_buffer.append(b'\x00' * padding_length)
                        embedded_giant_buffer_length += padding_length
                        accessor = {}
                        accessor['bufferView'] = len(bufferviews)
                        accessor['componentType'] = 5126
                        accessor['type'] = 'VEC4'
                        accessor['count'] = vvv['m_elementCount']
                        vvvv['mu_gltfAccessorForExpandedHandednessTangent'] = len(accessors)
                        accessors.append(accessor)
                        bufferviews.append(bufferview)

    for v in pdatablock_list:
        accessor = {}
        accessor['bufferView'] = len(bufferviews)
        dataTypeForGltf = 5123
        datatype = v['m_streams'][0]['m_type']
        if datatype in dataTypeMappingForGltf:
            dataTypeForGltf = dataTypeMappingForGltf[datatype]
        elif datatype >= 4 and datatype <= 7 and need_embed:
            dataTypeForGltf = dataTypeMappingForGltf[(datatype - 4)]
        else:
            print('XXX: unhandled indice type ' + str(datatype))
        dataTypeCount = datatype % 4 + 1
        accessor['componentType'] = dataTypeForGltf
        accessor['type'] = dataTypeCountMappingForGltf[(datatype % 4)]
        accessor['count'] = v['m_elementCount']
        v['mu_gltfAccessorIndex'] = len(accessors)
        bufferview = {}
        if need_embed:
            blobdata = v['mu_vertBuffer']
            singleelementsize = dataTypeMappingSize[datatype]
            blobstride = v['m_stride']
            if dataTypeCount * singleelementsize != blobstride:
                deinterleaved_data = bytearray()
                for i in range(v['m_elementCount']):
                    deinterleaved_data += blobdata[blobstride * i + v['m_streams'][0]['m_offset']:blobstride * i + v['m_streams'][0]['m_offset'] + singleelementsize * dataTypeCount]

                blobstride = dataTypeCount * dataTypeMappingSize[datatype]
                blobdata = bytes(deinterleaved_data)
            elif dataTypeCount * singleelementsize * v['m_elementCount'] != len(blobdata):
                blobdata = blobdata[v['m_streams'][0]['m_offset']:v['m_streams'][0]['m_offset'] + dataTypeCount * singleelementsize * v['m_elementCount']]
            if cluster_header.cluster_marker == NOEPY_HEADER_BE:
                blobdatabyteswap = array.array(dataTypeMappingForPython[datatype], blobdata)
                blobdatabyteswap.byteswap()
                blobdata = blobdatabyteswap.tobytes()
            if datatype >= 4 and datatype <= 7:
                blobdatafloatextend = array.array('f')
                for i in range(dataTypeCount * v['m_elementCount']):
                    blobdatafloatextend.append(struct.unpack('e', blobdata[i * 2:i * 2 + 2])[0])

                blobdata = blobdatafloatextend.tobytes()
                blobstride = dataTypeCount * 4
            bufferview = {}
            bufferview['buffer'] = 0
            bufferview['byteOffset'] = embedded_giant_buffer_length
            bufferview['byteLength'] = len(blobdata)
            bufferview['byteStride'] = blobstride
            embedded_giant_buffer.append(blobdata)
            embedded_giant_buffer_length += len(blobdata)
            padding_length = 4 - len(blobdata) % 4
            embedded_giant_buffer.append(b'\x00' * padding_length)
            embedded_giant_buffer_length += padding_length
        else:
            bufferview['buffer'] = 1
            bufferview['byteOffset'] = cluster_mesh_info.vram_model_data_offset + v['m_streams'][0]['m_offset'] + v['mu_vertBufferPosition']
            bufferview['byteLength'] = v['mu_vertBufferSize']
            bufferview['byteStride'] = v['m_stride']
        bufferviews.append(bufferview)
        accessors.append(accessor)

    if 'PAnimationChannelTimes' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationChannelTimes']:
            blobdata = v['m_timeKeys'].tobytes()
            bufferview = {}
            bufferview['buffer'] = 0
            bufferview['byteOffset'] = embedded_giant_buffer_length
            bufferview['byteLength'] = len(blobdata)
            embedded_giant_buffer.append(blobdata)
            embedded_giant_buffer_length += len(blobdata)
            padding_length = 4 - len(blobdata) % 4
            embedded_giant_buffer.append(b'\x00' * padding_length)
            embedded_giant_buffer_length += padding_length
            accessor = {}
            accessor['bufferView'] = len(bufferviews)
            accessor['componentType'] = 5126
            accessor['type'] = 'SCALAR'
            accessor['count'] = v['m_keyCount']
            v['mu_gltfAccessorIndex'] = len(accessors)
            accessors.append(accessor)
            bufferviews.append(bufferview)

    if 'PAnimationChannel' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationChannel']:
            blobdata = v['m_valueKeys'].tobytes()
            bufferview = {}
            bufferview['buffer'] = 0
            bufferview['byteOffset'] = embedded_giant_buffer_length
            bufferview['byteLength'] = len(blobdata)
            embedded_giant_buffer.append(blobdata)
            embedded_giant_buffer_length += len(blobdata)
            padding_length = 4 - len(blobdata) % 4
            embedded_giant_buffer.append(b'\x00' * padding_length)
            embedded_giant_buffer_length += padding_length
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
            bufferviews.append(bufferview)

    if 'PAnimationConstantChannel' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationConstantChannel']:
            tmparray = array.array('f', v['m_value'])
            if v['m_keyType'] == 'Scale' or v['m_keyType'] == 'Translation':
                tmparray.pop()
            blobdata = tmparray.tobytes() * 2
            bufferview = {}
            bufferview['buffer'] = 0
            bufferview['byteOffset'] = embedded_giant_buffer_length
            bufferview['byteLength'] = len(blobdata)
            embedded_giant_buffer.append(blobdata)
            embedded_giant_buffer_length += len(blobdata)
            padding_length = 4 - len(blobdata) % 4
            embedded_giant_buffer.append(b'\x00' * padding_length)
            embedded_giant_buffer_length += padding_length
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
            bufferviews.append(bufferview)

    if 'PAnimationClip' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationClip']:
            tmparray = array.array('f', [v['m_constantChannelStartTime'], v['m_constantChannelEndTime']])
            blobdata = tmparray.tobytes()
            bufferview = {}
            bufferview['buffer'] = 0
            bufferview['byteOffset'] = embedded_giant_buffer_length
            bufferview['byteLength'] = len(blobdata)
            embedded_giant_buffer.append(blobdata)
            embedded_giant_buffer_length += len(blobdata)
            padding_length = 4 - len(blobdata) % 4
            embedded_giant_buffer.append(b'\x00' * padding_length)
            embedded_giant_buffer_length += padding_length
            accessor = {}
            accessor['bufferView'] = len(bufferviews)
            accessor['componentType'] = 5126
            accessor['type'] = 'SCALAR'
            accessor['count'] = 2
            v['mu_gltfAccessorIndex'] = len(accessors)
            accessors.append(accessor)
            bufferviews.append(bufferview)

    images = []
    images_meta = []
    if 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
            if v['m_targetAssetType'] == 'PTexture2D':
                image = {}
                #image_name = os.path.basename(v['m_id'])
                image['uri'] = v['m_id'] #image_name
                v['mu_gltfImageIndex'] = len(images)
                images.append(image)
            if v['m_targetAssetType'] in ['PTexture2D', 'PTextureCubeMap']:
                images_meta.append({'uri': v['m_id'], 'm_targetAssetType': v['m_targetAssetType']})
        metadata_json['images'] = images_meta

    cluster_mesh_info.gltf_data['images'] = images
    samplers = []
    filter_map = {0: 9728, 
     1: 9729, 
     2: 9984, 
     3: 9985, 
     4: 9986, 
     5: 9987}
    wrap_map = {0: 33071, 
     1: 10497, 
     2: 33071, 
     3: 33071, 
     4: 33648}
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
            if type(k) is int:
                data_instances = cluster_mesh_info.data_instances_by_class[k]
                if len(data_instances) > 0 and data_instances[0]['mu_memberClass'] == 'PParameterBuffer':
                    has_key = True
                if has_key == True:
                    for parameter_buffer in cluster_mesh_info.data_instances_by_class[k]:
                        shaderparam = parameter_buffer['mu_shaderParameters']
                        samplerstate = None
                        if 'DiffuseMapSamplerS' in shaderparam and type(shaderparam['DiffuseMapSamplerS']) is dict:
                            samplerstate = shaderparam['DiffuseMapSamplerS']
                        elif 'DiffuseMapSamplerSampler' in shaderparam and type(shaderparam['DiffuseMapSamplerSampler']) is dict:
                            samplerstate = shaderparam['DiffuseMapSamplerSampler']
                        if 'DiffuseMapSampler' in parameter_buffer['mu_shaderParameters'] and type(parameter_buffer['mu_shaderParameters']['DiffuseMapSampler']) is str and 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
                            for vv in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
                                if vv['m_id'] == parameter_buffer['mu_shaderParameters']['DiffuseMapSampler'] and 'mu_gltfImageIndex' in vv:
                                    texture = {}
                                    if samplerstate is not None:
                                        texture['sampler'] = samplerstate['mu_gltfSamplerIndex']
                                    texture['source'] = vv['mu_gltfImageIndex']
                                    parameter_buffer['mu_gltfTextureDiffuseIndex'] = len(textures)
                                    textures.append(texture)
                                    break

                        samplerstate = None
                        if 'NormalMapSamplerS' in shaderparam and type(shaderparam['NormalMapSamplerS']) is dict:
                            samplerstate = shaderparam['NormalMapSamplerS']
                        elif 'NormalMapSamplerSampler' in shaderparam and type(shaderparam['NormalMapSamplerSampler']) is dict:
                            samplerstate = shaderparam['NormalMapSamplerSampler']
                        if 'NormalMapSampler' in parameter_buffer['mu_shaderParameters'] and type(parameter_buffer['mu_shaderParameters']['NormalMapSampler']) is str and 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
                            for vv in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
                                if vv['m_id'] == parameter_buffer['mu_shaderParameters']['NormalMapSampler'] and 'mu_gltfImageIndex' in vv:
                                    texture = {}
                                    if samplerstate is not None:
                                        texture['sampler'] = samplerstate['mu_gltfSamplerIndex']
                                    texture['source'] = vv['mu_gltfImageIndex']
                                    parameter_buffer['mu_gltfTextureNormalIndex'] = len(textures)
                                    textures.append(texture)
                                    break

                        samplerstate = None
                        if 'SpecularMapSamplerS' in shaderparam and type(shaderparam['SpecularMapSamplerS']) is dict:
                            samplerstate = shaderparam['SpecularMapSamplerS']
                        elif 'SpecularMapSamplerSampler' in shaderparam and type(shaderparam['SpecularMapSamplerSampler']) is dict:
                            samplerstate = shaderparam['SpecularMapSamplerSampler']
                        if 'SpecularMapSampler' in parameter_buffer['mu_shaderParameters'] and type(parameter_buffer['mu_shaderParameters']['SpecularMapSampler']) is str and 'PAssetReferenceImport' in cluster_mesh_info.data_instances_by_class:
                            for vv in cluster_mesh_info.data_instances_by_class['PAssetReferenceImport']:
                                if vv['m_id'] == parameter_buffer['mu_shaderParameters']['SpecularMapSampler'] and 'mu_gltfImageIndex' in vv:
                                    texture = {}
                                    if samplerstate is not None:
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
            if 'dae' in cluster_mesh_info.filename and 'Skinned' not in v['mu_materialname']:
                material = {}
                material['shader'] = v['m_parameterBuffer']['m_effectVariant']['m_id']
                skinned_material = [x for x in cluster_mesh_info.data_instances_by_class['PMaterial'] if x['mu_materialname'] == v['mu_materialname']+'-Skinned']
                if len(skinned_material) > 0:
                    material['skinned_shader'] = skinned_material[0]['m_parameterBuffer']['m_effectVariant']['m_id']
                shaderParameters = {key:list(value) if isinstance(value, array.array) else value for (key,value) in v['m_parameterBuffer']['mu_shaderParameters'].items()}
                material['shaderTextures'] = {k:v for (k,v) in shaderParameters.items() if isinstance(v,str)}
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
        'Binormal': 'BINORMAL', 'Color': 'COLOR', 'SkinWeights': 'BLENDWEIGHTS', 'SkinIndices': 'BLENDINDICES'}
    if 'PMeshInstance' in cluster_mesh_info.data_instances_by_class:
        mesh_instances = cluster_mesh_info.data_instances_by_class['PMeshInstance']
    for t in mesh_instances:
        curmesh = t['m_mesh']
        t['mu_gltfMeshSegmentsIndicies'] = []
        for tt in range(len(curmesh['m_meshSegments'])):
            primitive = {}
            fmt = {'stride': '0', 'topology': 'trianglelist', 'format': "DXGI_FORMAT_R16_UINT", 'elements': []}
            elements = []
            vb = []
            m = curmesh['m_meshSegments'][tt]
            if curmesh['m_defaultMaterials']['m_materials']['m_u'] is not None and len(curmesh['m_defaultMaterials']['m_materials']['m_u']) > m['m_materialIndex']:
                mat = curmesh['m_defaultMaterials']['m_materials']['m_u'][m['m_materialIndex']]
                if mat is not None:
                    primitive['material'] = mat['mu_gltfMaterialIndex']
                segmentcontext = t['m_segmentContext'][tt]
                attributes = {}
                colorCount = 0
                tangentCount = 0
                uvTangentBinormalCount = {'ST':0,'Tangent':0,'Binormal':0, 'Color':0}
                valid_uvs = list(set([x['m_inputSet'] for x in t['m_segmentContext'][tt]['m_streamBindings']['m_u']]))
                AlignedByteOffset = 0
                for i in range(len(m['m_vertexData'])):
                    vertexData = m['m_vertexData'][i]
                    componentType = accessors[vertexData['mu_gltfAccessorIndex']]['componentType']
                    accType = accessors[vertexData['mu_gltfAccessorIndex']]['type']
                    stride = numelements[accType] * (int(bytesize[componentType]) // 8)
                    dxgi_format = "".join([RGBAD[i]+bytesize[componentType] for i in range(numelements[accType])])\
                        + '_' + elementtype[componentType]
                    streamInfo = vertexData['m_streams'][0]
                    vertexBuffer = vertexData['mu_vertBuffer']
                    if partialmaps == False and streamInfo['m_renderDataType'] == 'SkinIndices':
                        dxgi_format = "".join([RGBAD[i]+'16' for i in range(numelements[accType])]) + '_UINT'
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
                    elif streamInfo['m_renderDataType'] == 'Binormal' or streamInfo['m_renderDataType'] == 'SkinnableBinormal':
                        pass
                    else:
                        print('Unused Stream: ', streamInfo['m_renderDataType'])
                if len(m['m_vertexData']) > 0:
                    fmt['elements'] = elements
                    fmt['stride'] = str(AlignedByteOffset)
                    write_fmt(fmt, mesh_folder_name + "/{0}_{1:02d}.fmt".format(t['mu_name'], tt))
                    with open(mesh_folder_name + "/{0}_{1:02d}.ib".format(t['mu_name'], tt), 'wb') as ff:
                        ff.write(curmesh['m_meshSegments'][tt]['mu_indBuffer'])
                    write_vb(vb, mesh_folder_name + "/{0}_{1:02d}.vb".format(t['mu_name'], tt), fmt)
                    with open(mesh_folder_name + "/{0}_{1:02d}.material".format(t['mu_name'], tt), "wb") as ff:
                        ff.write(json.dumps({'material': mat['mu_materialname'].split('-Skinned')[0]}, indent=4).encode("utf-8"))
                    with open(mesh_folder_name + "/{0}_{1:02d}.uvmap".format(t['mu_name'], tt), "wb") as ff:
                        ff.write(json.dumps([{'m_name': x['m_name'], 'm_index': x['m_index'], 'm_inputSet': x['m_inputSet']}\
                            for x in t['m_segmentContext'][tt]['m_streamBindings']['m_u']], indent=4).encode("utf-8"))

                uvDataStreamSet = {}
                for vertexData in m['m_vertexData']:
                    streamInfo = vertexData['m_streams'][0]
                    if streamInfo['m_renderDataType'] == 'ST':
                        streamSet = streamInfo['m_streamSet']
                        uvDataStreamSet[streamSet] = vertexData

                uvDataLowest = None
                for i in sorted(uvDataStreamSet.keys()):
                    if uvDataStreamSet[i] is not None:
                        uvDataLowest = uvDataStreamSet[i]
                        break

                uvDataRemapped = []
                for i in sorted(uvDataStreamSet.keys()):
                    if uvDataStreamSet[i] is not None:
                        uvDataRemapped.append(uvDataStreamSet[i])

                if uvDataLowest is not None:
                    for i in sorted(uvDataStreamSet.keys()):
                        vertexData = uvDataStreamSet[i]
                        if vertexData is None:
                            pass
                        else:
                            streamInfo = vertexData['m_streams'][0]
                            if type(segmentcontext['m_streamBindings']) is dict:
                                for xx in segmentcontext['m_streamBindings']['m_u']:
                                    if xx['m_renderDataType'] == 'ST' and xx['m_inputSet'] == streamInfo['m_streamSet']:
                                        uvIndex = None
                                        if xx['m_nameHash'] == 41524:
                                            uvIndex = 6
                                        elif xx['m_nameHash'] == 41523:
                                            uvIndex = 5
                                        elif xx['m_nameHash'] == 41522:
                                            uvIndex = 4
                                        elif xx['m_nameHash'] == 41521 or xx['m_nameHash'] == 59967:
                                            uvIndex = 3
                                        elif xx['m_nameHash'] == 41520 or xx['m_nameHash'] == 59964:
                                            uvIndex = 2
                                        elif xx['m_nameHash'] == 41519 or xx['m_nameHash'] == 59961:
                                            uvIndex = 1
                                        elif xx['m_nameHash'] == 21117 or xx['m_nameHash'] == 50588 or xx['m_nameHash'] == 41517 or xx['m_nameHash'] == 59958:
                                            uvIndex = 0
                                        else:
                                            print('Unknown how to handle ' + xx['m_name'])
                                        if uvIndex is not None:
                                            while len(uvDataRemapped) <= uvIndex:
                                                uvDataRemapped.append(None)

                                            uvDataRemapped[uvIndex] = vertexData

                if len(uvDataRemapped) > 0:
                    while uvDataRemapped[(-1)] is None:
                        uvDataRemapped.pop()

                for i in range(len(uvDataRemapped)):
                    if uvDataRemapped[i] is None:
                        uvDataRemapped[i] = uvDataLowest

                texcoord_num = 0
                for i in range(len(uvDataRemapped)):
                    if i in valid_uvs or i == 0:
                        attributes['TEXCOORD_' + str(texcoord_num)] = uvDataRemapped[i]['mu_gltfAccessorIndex']
                        texcoord_num += 1

                primitive['attributes'] = attributes
                primitive['indices'] = m['mu_gltfAccessorIndex']
                primitiveTypeForGltf = 0
                primitiveTypeMappingForGltf = {0: 0, 
                 1: 1, 
                 2: 4, 
                 3: 5, 
                 4: 6, 
                 5: 0}
                if m['m_primitiveType'] in primitiveTypeMappingForGltf:
                    primitiveTypeForGltf = primitiveTypeMappingForGltf[m['m_primitiveType']]
                else:
                    print('XXX: unhandled primitive type for GLTF ' + str(m['m_primitiveType']))
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
        light_type_map = {'DirectionalLight': 'directional', 
         'PointLight': 'point', 
         'SpotLight': 'spot'}
        for v in cluster_mesh_info.data_instances_by_class['PLight']:
            if v['m_lightType'] in light_type_map:
                light = {}
                name = ''
                if name == '' and 'mu_name' in v:
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
                if light['type'] == 'point' or light['type'] == 'spot' and v['m_outerRange'] > 0:
                    light['range'] = v['m_outerRange']
                v['mu_gltfLightIndex'] = len(lights)
                lights.append(light)

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
            node['matrix'] = v['m_localMatrix']['m_elements'].tolist()
            name = v['m_name']
            if name == '' and 'mu_name' in v:
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
            children = []
            for i in range(len(cluster_mesh_info.data_instances_by_class['PNode'])):
                if cluster_mesh_info.data_instances_by_class['PNode'][i]['m_parent'] is v:
                    children.append(i)

            if mesh_node_indices is not None:
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
            joint_list = [mesh['m_skeletonBounds'][i]['m_hierarchyMatrixIndex'] for i in range(len(mesh['m_skeletonBounds']))]
            joint_list_to_node = {}
            matrices = {}
            matrices_by_name = {}
            for j in range(len(joint_list)):
                joint_list_to_node[joint_list[j]] = [i for i in range(len(nodes)) if nodes[i]['name'] == mesh['m_matrixNames'][joint_list[j]]['m_buffer']][0]
                matrices[joint_list[j]] = mesh['m_skeletonMatrices'][j]['m_elements']
                matrices_by_name[mesh['m_matrixNames'][joint_list[j]]['m_buffer']] = mesh['m_skeletonMatrices'][j]['m_elements']
            if len(mesh_segment_nodes) > 0:
                inv_bind_mtxs[v['mu_name']] = {k:list(v) for (k,v) in matrices_by_name.items()}
                mesh_nodes = {}
                remapped_vgmap_list = {nodes[joint_list_to_node[joint_list[j]]]['name']:j for j in range(len(joint_list))}
                for i in range(len(mesh_segment_nodes)):
                    mesh_nodes[mesh_segment_nodes[i]['mesh']] = [j for j in range(len(nodes)) if nodes[j]['name'] == mesh_segment_nodes[i]['name']][0]
                for i in range(len(mesh['m_meshSegments'])):
                    if 'm_gltfSkinBoneMap' in mesh['m_meshSegments'][i] and len(mesh_nodes) > 0:
                        submesh_joint_list = [joint_list_to_node[joint_list[x]] for x in mesh['m_meshSegments'][i]['m_gltfSkinBoneMap']]
                        vgmap_list = {name:index for (name,index) in [(nodes[submesh_joint_list[j]]['name'],j) for j in range(len(submesh_joint_list))]}
                        matrix_list = [matrices[joint_list[x]].tobytes() for x in mesh['m_meshSegments'][i]['m_gltfSkinBoneMap']]
                        if len(matrix_list) > 0:
                            blobdata = b''.join(matrix_list)
                            bufferview = {}
                            bufferview['buffer'] = 0
                            bufferview['byteOffset'] = embedded_giant_buffer_length
                            bufferview['byteLength'] = len(blobdata)
                            embedded_giant_buffer.append(blobdata)
                            embedded_giant_buffer_length += len(blobdata)
                            padding_length = 4 - len(blobdata) % 4
                            embedded_giant_buffer.append(b'\x00' * padding_length)
                            embedded_giant_buffer_length += padding_length
                            accessor = {}
                            accessor['bufferView'] = len(bufferviews)
                            accessor['componentType'] = 5126
                            accessor['type'] = 'MAT4'
                            accessor['count'] = len(matrix_list)
                            mesh['m_meshSegments'][i]['mu_gltfAccessorForInverseBindMatrixIndex'] = len(accessors)
                            accessors.append(accessor)
                            bufferviews.append(bufferview)
                            skin = {"inverseBindMatrices": mesh['m_meshSegments'][i]['mu_gltfAccessorForInverseBindMatrixIndex'],\
                                "joints": submesh_joint_list}
                            nodes[mesh_nodes[i]]['skin'] = len(skins)
                            if partialmaps == True:
                                with open(mesh_folder_name + "/{0}_{1:02d}.vgmap".format(v['mu_name'], i), 'wb') as f:
                                    f.write(json.dumps(vgmap_list, indent=4).encode("utf-8"))
                            else:
                                with open(mesh_folder_name + "/{0}_{1:02d}.vgmap".format(v['mu_name'], i), 'wb') as f:
                                    f.write(json.dumps(remapped_vgmap_list, indent=4).encode("utf-8"))
                            skins.append(skin)
            
            if 'mu_gltfAccessorForInverseBindMatrixIndex' in mesh and 'mu_gltfNodeIndex' in v:
                nodes[v['mu_gltfNodeIndex']]['skin'] = len(skins)
                skin = {}
                skin['skeleton'] = v['mu_gltfNodeIndex']
                skin['inverseBindMatrices'] = mesh['mu_gltfAccessorForInverseBindMatrixIndex']
                if len(nodes) > 0 and type(mesh['m_matrixNames']) is list and type(mesh['m_matrixParents']) is array.array and len(mesh['m_matrixNames']) == len(mesh['m_matrixParents']):
                    joints = []
                    for vv in mesh['m_skeletonBounds']:
                        matrix_name = mesh['m_matrixNames'][vv['m_hierarchyMatrixIndex']]
                        joint = None
                        for i in range(len(nodes)):
                            vvv = nodes[i]
                            if vvv['name'] == matrix_name['m_buffer']:
                                joint = i
                                break

                        if joint is not None:
                            joints.append(joint)
                        else:
                            print('XXX: node ' + matrix_name['m_buffer'] + ' not found in hierarchy')
                            joints.append(1)

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
    targetMap = {'Translation': 'translation', 
     'Rotation': 'rotation', 
     'Scale': 'scale'}
    if 'PAnimationSet' in cluster_mesh_info.data_instances_by_class:
        for v in cluster_mesh_info.data_instances_by_class['PAnimationSet']:
            for vv in v['m_animationClips']['m_u']:
                animation = {}
                samplers = []
                channels = []
                for vvv in vv['m_channels']:
                    if vvv['m_keyType'] not in targetMap:
                        pass
                    else:
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
                        sampler['input'] = vvv['m_times']['mu_gltfAccessorIndex']
                        sampler['output'] = vvv['mu_gltfAccessorIndex']
                        if vvv['m_interp'] == 2:
                            sampler['interpolation'] = 'STEP'
                        else:
                            sampler['interpolation'] = 'LINEAR'
                        channels.append(channel)
                        samplers.append(sampler)

                for vvv in vv['m_constantChannels']:
                    if vvv['m_keyType'] not in targetMap:
                        pass
                    else:
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
        nodes = []
        for v in cluster_mesh_info.data_instances_by_class['PNode']:
            if v['m_parent'] is None:
                nodes.append(v['mu_gltfNodeIndex'])

        scene['nodes'] = nodes
        scenes.append(scene)
    cluster_mesh_info.gltf_data['scenes'] = scenes
    cluster_mesh_info.gltf_data['bufferViews'] = bufferviews
    cluster_mesh_info.gltf_data['accessors'] = accessors

    if 'PLocator' in cluster_mesh_info.data_instances_by_class:
        metadata_json['locators'] = [x['mu_name'] for x in cluster_mesh_info.data_instances_by_class['PLocator']]

    if 'PPhysicsModel' in cluster_mesh_info.data_instances_by_class:
        def ok_json(obj):
            try:
                json.dumps(obj)
                return True
            except:
                return False
        physics_data = {}
        to_process = ['PPhysicsModel', 'PPhysicsMaterial', 'PPhysicsMesh', 'PPhysicsRigidBody', 'PShape']
        for section in to_process:
            if section in cluster_mesh_info.data_instances_by_class:
                physics_data[section] =[]
                for v in cluster_mesh_info.data_instances_by_class[section]:
                    data_dict = {item:v[item] if not isinstance(v[item],dict)\
                        else list(v[item]['m_elements']) if 'm_elements' in v[item]\
                        else v[item]['m_name'] if 'm_name' in v[item]\
                        else v[item]['mu_name'] if 'mu_name' in v[item]\
                        else v[item]['mu_memberLoc'] if 'mu_memberLoc' in v[item]\
                        else [{'mu_memberClass': x['mu_memberClass'], 'mu_memberLoc': x['mu_memberLoc']} for x in v[item]['m_u']] if 'm_u' in v[item]\
                        else v[item] if ok_json(v[item]) == True\
                        else 'unreadable' for item in v}
                    physics_data[section].append(data_dict)
        with open(physics_json_name, 'wb') as f:
            f.write(json.dumps(physics_data, indent=4).encode("utf-8"))

    if len(nodes) > 0:
        import json, base64
        embedded_giant_buffer_joined = b''.join(embedded_giant_buffer)
        buffer0['byteLength'] = len(embedded_giant_buffer_joined)
        with cluster_mesh_info.storage_media.open(pkg_name + "/" + cluster_mesh_info.filename.split('.', 1)[0] + '.gltf', 'wb') as (f):
            buffer0["uri"] = cluster_mesh_info.filename.split('.', 1)[0] + '.bin'
            jsondata = json.dumps(cluster_mesh_info.gltf_data, indent=4).encode("utf-8")
            f.write(jsondata)
        with open(pkg_name + "/" + cluster_mesh_info.filename.split('.', 1)[0] + '.bin', 'wb') as f:
            f.write(embedded_giant_buffer_joined)        
        with open(metadata_json_name, 'wb') as f:
            f.write(json.dumps(metadata_json, indent=4).encode("utf-8"))

def process_pkg(pkg_name, partialmaps = partial_vgmaps_default, allbuffers = False, overwrite = False):
    is_cluster = False
    is_pkg = False
    storage_media = None
    print("Processing {0}...".format(pkg_name))
    with open(pkg_name, 'rb') as (f):
        header1 = f.read(4)
        if len(header1) == 4:
            header2 = struct.unpack('<I', header1[:4])[0]
            is_cluster = header2 == NOEPY_HEADER_BE or header2 == NOEPY_HEADER_LE
    if not is_cluster:
        is_pkg = file_is_ed8_pkg(pkg_name)
    if is_pkg:
        if os.path.exists(pkg_name[:-4]) and (os.path.isdir(pkg_name[:-4])) and (overwrite == False):
            if str(input(pkg_name[:-4] + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(pkg_name[:-4]):
            if not os.path.exists(pkg_name[:-4]):
                os.mkdir(pkg_name[:-4])
            storage_media = TSpecialOverlayMedia(os.path.realpath(pkg_name))
            items = []

            def list_callback(item):
                if item[-10:-6] == '.dae':
                    items.append(item)

            storage_media.get_list_at('.', list_callback)
            if len(items) == 0:
                def list_callback2(item):
                    if item[-10:-6] == '.dds':
                        items.append(item)

                storage_media.get_list_at('.', list_callback2)

            for i in range(len(items)):
                print("Parsing {0}...".format(items[i]))
                parse_cluster(items[i], None, storage_media, pkg_name[:-4], partialmaps = partialmaps, allbuffers = allbuffers, item_num=i)

            build_items = []
            def list_build_items_callback(item):
                if item[-4:] == '.xml' or item[-42:-38] == '.fx#' or item[-9:-6] == '.fx':
                    build_items.append(item)
            storage_media.get_list_at('.', list_build_items_callback)
            if not os.path.exists(pkg_name[:-4] + '/' + pkg_name[:-4]):
                os.makedirs(pkg_name[:-4] + '/' + pkg_name[:-4])
            for i in range(len(build_items)):
                with storage_media.open(build_items[i], 'rb') as f:
                    with open(pkg_name[:-4] + '/' + pkg_name[:-4] + '/' + build_items[i], 'wb') as ff:
                        ff.write(f.read())
    else:
        raise Exception('Passed in file is not compatible file')

if __name__ == '__main__':
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        if partial_vgmaps_default == False:
            parser.add_argument('-p', '--partialmaps', help="Provide vgmaps with non-empty groups only", action="store_true")
        else:
            parser.add_argument('-c', '--completemaps', help="Provide vgmaps with entire skeleton", action="store_false")
        parser.add_argument('-a', '--allbuffers', help="Dump all buffers (default is no more than 3 texcoord/tangent/binormal)", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('pkg_filename', help="Name of pkg file to export from (required).")
        args = parser.parse_args()
        if partial_vgmaps_default == False:
            partialmaps = args.partialmaps
        else:
            partialmaps = args.completemaps
        if os.path.exists(args.pkg_filename) and args.pkg_filename[-4:].lower() == '.pkg':
            process_pkg(args.pkg_filename, partialmaps = partialmaps, allbuffers = args.allbuffers, overwrite = args.overwrite)
    else:
        pkg_files = glob.glob('*.pkg')
        for i in range(len(pkg_files)):
            process_pkg(pkg_files[i])
