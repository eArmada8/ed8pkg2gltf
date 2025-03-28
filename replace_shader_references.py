# ED8 .dae.phyre shader fixer, needs output from my fork of uyjulian/ed8pkg2glb.
# After running build_collada.py, then CSIVAssetImportTool.exe, copy the compiled
# .dae.phyre file into the directory with metadata.json and run this script to
# replace the shader references to the true shaders.
#
# GitHub eArmada8/ed8pkg2gltf

import os, json, shutil, glob, sys

def make_true_shader_dict(metadata):
    true_shader_dict = {}
    true_shader_dict.update({k:b'\x00'+v['shader'].encode() for (k,v) in metadata['materials'].items()})
    true_shader_dict.update({k+'-Skinned-VertexColor':b'\x00'+v['skinned_vertex_color_shader'].encode() for (k,v) in metadata['materials'].items() if 'skinned_vertex_color_shader' in v.keys()})
    # I am not sure why, but the compiler seems to generate a -Skinned shader even when only a -Skinned-VertexColor shader exists in the original, perhaps it is reused?  This will be overwritten if a real one exists.
    true_shader_dict.update({k+'-Skinned':b'\x00'+v['skinned_vertex_color_shader'].encode() for (k,v) in metadata['materials'].items() if 'skinned_vertex_color_shader' in v.keys()})
    true_shader_dict.update({k+'-VertexColor':b'\x00'+v['vertex_color_shader'].encode() for (k,v) in metadata['materials'].items() if 'vertex_color_shader' in v.keys()})
    true_shader_dict.update({k+'-Skinned':b'\x00'+v['skinned_shader'].encode() for (k,v) in metadata['materials'].items() if 'skinned_shader' in v.keys()})
    return(true_shader_dict)

def make_fake_shader_dict():
    if os.path.exists('materials_list.txt'):
        fake_shader_dict = {}
        with open('materials_list.txt', 'r') as f:
            for line in f:
                entry = line.split(' crc: ')[0].split(' : ')
                if len(entry) > 1:
                    fake_shader_dict[entry[1].strip()] = entry[0].split('dae#')[-1]
        return(fake_shader_dict)
    else:
        return False

def replace_shader_references(filedata, true_shader_dict, fake_shader_dict):
    if filedata[0:4] == b'RYHP':
        shader_loc = filedata.find(b'\x00shader', 1)
        new_phyre = filedata[0:shader_loc]
        while shader_loc > 0:
            shader_filename = filedata[shader_loc+1:filedata.find(b'\x00', shader_loc+1)].decode()
            if shader_filename in fake_shader_dict:
                if fake_shader_dict[shader_filename] in true_shader_dict:
                    new_phyre += true_shader_dict[fake_shader_dict[shader_filename]]
                    if len(true_shader_dict[fake_shader_dict[shader_filename]]) < len(shader_filename) + 1:
                        padding_len = len(shader_filename) + 1 - len(true_shader_dict[fake_shader_dict[shader_filename]])
                        for _ in range(padding_len):
                            new_phyre += b'\x00'
                else:
                    print("KeyError: Attempted to replace shader \"{0}\" but it does not exist in the metadata!".format(fake_shader_dict[shader_key]))
                    input("Press Enter to abort.")
                    raise
            else:
                new_phyre += b'\x00' + shader_filename.encode()
            end_key = filedata.find(b'\x00', shader_loc + 1)
            shader_loc = filedata.find(b'\x00shader', shader_loc + 1)
            if shader_loc > len(new_phyre): # Shaders without hashes sometimes have an extra byte padding (CS2 Maps)
                while shader_loc > len(new_phyre):
                    new_phyre += b'\x00'
        new_phyre += filedata[end_key:]
        return(new_phyre)
    else:
        return False

def process_model(metadata_filename):
    with open(metadata_filename,'rb') as f:
        metadata = json.loads(f.read())
        filename = metadata['name'] + '.dae.phyre'
        true_shader_dict = make_true_shader_dict(metadata)
        fake_shader_dict = make_fake_shader_dict()
        if os.path.exists(filename):
            shutil.copy2(filename, filename + '.bak')
            with open(filename, 'rb') as f:
                filedata = f.read()
            new_phyre = replace_shader_references(filedata, true_shader_dict, fake_shader_dict)
            with open(filename, 'wb') as f:
                f.write(new_phyre)
        else:
            input("{0} missing, copy to folder with metadata.json, press any key to continue".format(filename))
    return()

if __name__ == '__main__':
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to process file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('metadata_filename', help="Name of metadata file to process (required).")
        args = parser.parse_args()
        if os.path.exists(args.metadata_filename) and args.metadata_filename[-5:].lower() == '.json':
            process_model(args.metadata_filename)
    else:
        models = glob.glob("metadata*.json")
        for i in range(len(models)):
            process_model(models[i])