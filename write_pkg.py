# ED8 .pkg builder.  The lz4 module must be present for compression (which is
# specified at the command line).
#
# GitHub eArmada8/ed8pkg2gltf

import struct, glob, io, os, sys, shutil
from xml.dom.minidom import parse

#Thank you to Admiral Curtiss and uyjulian for assistance in writing this algorithm!
def compress_nislzss(data_block):
    cmpdata = bytearray()
    i = 0
    while i < len(data_block):
        look_back = data_block[i-0xFE if i>0xFE else 0:i]
        if data_block[i] in look_back:
            start_matches = [i - (len(look_back) - j) for j in range(len(look_back)) if look_back[j] == data_block[i]]
            match_lens = []
            for m in start_matches:
                k = 0
                while i+k < len(data_block) and data_block[m+k] == data_block[i+k] and m+k+1 < i:
                    k += 1
                match_lens.append(k)
        if data_block[i] in look_back and max(match_lens) > 3:
            best_match = match_lens.index(max(match_lens))
            cmpdata.extend([0, i-start_matches[best_match]+1, match_lens[best_match]])
            i += match_lens[best_match]
        else:
            if data_block[i] == 0:
                cmpdata.extend([0,0]) # Escape sequence
            else:
                cmpdata.append(data_block[i])
            i += 1
    return(struct.pack("<3I", len(data_block), len(cmpdata) + 12, 0) + cmpdata)

# Adds file onto the end of the stream, and appends name/size to contents.  Offsets are not calculated.
def insert_file_into_stream (f, content_struct, binary_file_data, file_details):
    f.write(binary_file_data)
    content_struct.append(file_details)
    return(content_struct)

# Updates all file offsets in the TOC based on current file size
def update_file_offsets (content_struct):
    current_file_offset = len(content_struct) * 80 + 8 # First file offset is always here
    for i in range(len(content_struct)):
        content_struct[i]["file_entry_offset"] = current_file_offset
        current_file_offset += content_struct[i]["file_entry_compressed_size"]
    return(content_struct)

def write_pkg_file (newfilename, file_stream, content_struct, magic = b'\x00\x00\x00\x00'):
    # Assume all the file offsets are wrong, and fix them
    content_struct = update_file_offsets(content_struct)
    with open(newfilename, 'wb') as f:
        f.write(magic)
        f.write(struct.pack("<I", len(content_struct)))
        for i in range(len(content_struct)):
            f.write(struct.pack("<64s4I", content_struct[i]["file_entry_name"].encode("utf-8").ljust(64,b'\x00'),\
                content_struct[i]["file_entry_uncompressed_size"],\
                content_struct[i]["file_entry_compressed_size"],\
                content_struct[i]["file_entry_offset"],\
                content_struct[i]["file_entry_flags"]))
        file_stream.seek(0)
        f.write(file_stream.read())
    return

#lz4 takes precedent over lzss
def processFolder(pkg_folder, include_all = False, lz4_compress = False, lzss_compress = False, overwrite = False):
    if lz4_compress == True:
        try:
            import lz4.block
            lz4_present = True
        except ModuleNotFoundError:
            lz4_present = False
    if os.path.exists(pkg_folder):
        if include_all == False and os.path.exists(pkg_folder + '/asset_D3D11.xml'):
            xmlfile = parse(pkg_folder + '/asset_D3D11.xml')
            xmlfilelist = [os.path.basename(x.getAttribute("path")).lower() for x\
                in xmlfile.getElementsByTagName("cluster")]+['asset_d3d11.xml']
            files = [x for x in glob.glob(pkg_folder+'/*.*') if os.path.basename(x).lower() in xmlfilelist]
            missing_files = [x for x in xmlfilelist if x not in [os.path.basename(x).lower() for x in files]]
            if len(missing_files) > 0:
                print("Warning!  Files are missing from {0}, and {0}.pkg will likely crash the game!".format(pkg_folder))
                print("Missing files: {0}".format(missing_files))
                input("Press Enter to continue.")
        else:
            files = glob.glob(pkg_folder+'/*.*')
        f = io.BytesIO()
        content_struct = []
        for i in range(len(files)):
            with open(files[i], 'rb') as f2:
                binary_file_data = f2.read()
                unc_size = len(binary_file_data)
                flags = 0
                if lz4_compress == True:
                    if lz4_present == True:
                        binary_file_data = lz4.block.compress(binary_file_data, mode = 'high_compression', store_size=False)
                        flags = 4
                elif lzss_compress == True:
                    binary_file_data = compress_nislzss(binary_file_data)
                    flags = 1
                file_details = {"file_entry_name": os.path.basename(files[i]), "file_entry_uncompressed_size": unc_size,\
                    "file_entry_compressed_size": len(binary_file_data), "file_entry_offset": 0,\
                    "file_entry_flags": flags}
                content_struct = insert_file_into_stream (f, content_struct, binary_file_data, file_details)
        if os.path.exists("{0}.pkg".format(pkg_folder)) and (overwrite == False):
            if str(input("{0}.pkg".format(pkg_folder) + " exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists("{0}.pkg".format(pkg_folder)):
            if os.path.exists("{0}.pkg".format(pkg_folder)):
                shutil.copy2("{0}.pkg".format(pkg_folder), "{0}.pkg.bak".format(pkg_folder))
            if lz4_compress == True and lz4_present == False:
                print("LZ4 compression specified but module is not installed, .pkg not compressed.")
            write_pkg_file ("{0}.pkg".format(pkg_folder), f, content_struct, magic = b'\x00\x00\x00\x00')

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('pkg_folder', help="Name of folder to pack.")
        parser.add_argument('-a', '--include_all', help="Include all files (ignore asset_D3D11.xml)", action="store_true")
        parser.add_argument('-l', '--lz4_compress', help="Apply LZ4 compression", action="store_true")
        parser.add_argument('-lz', '--lzss_compress', help="Apply LZSS compression (LZ4 overrides this)", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        args = parser.parse_args()
        if os.path.exists(args.pkg_folder):
            processFolder(args.pkg_folder, include_all = args.include_all, lz4_compress = args.lz4_compress,\
                lzss_compress = args.lzss_compress, overwrite = args.overwrite)
