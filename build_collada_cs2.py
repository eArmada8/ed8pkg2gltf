# CS2 COLLADA builder, needs output from my fork of uyjulian/ed8pkg2glb.
# Needs build_collada.py for CS3
#
# GitHub eArmada8/ed8pkg2gltf

try:
    from build_collada import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

if __name__ == '__main__':
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
    models = glob.glob("metadata*.json")
    metadata_list = []
    if os.path.exists("animation_metadata.json"):
        animation_metadata = read_struct_from_json("animation_metadata.json")
    else:
        animation_metadata = {}
    if len(models) > 0:
        for i in range(len(models)):
            build_collada(models[i], animation_metadata)
        metadata_list.extend([read_struct_from_json(x) for x in models])
        print("Writing shader file...")
        write_shader([x['materials'] for x in metadata_list], mode = 'CS2')
    new_times = {}
    if 'animations' in animation_metadata:
        for animation in [x for x in animation_metadata['animations'] if not x in [x['name'] for x in metadata_list]]:
            ani_times = build_animation_collada (animation, animation_metadata)
            if ani_times is not False:
                metadata_list.append({'name': animation, 'pkg_name': animation_metadata['pkg_name'], 'materials': []})
                if not round(ani_times[0],3) == round(animation_metadata['animations'][animation]['starttime_offset'][0],3):
                    new_times[animation] = ani_times
    if len(models) > 0 or ('animations' in animation_metadata and len(animation_metadata['animations']) > 0):
        print("Writing asset_D3D11.xml...")
        write_asset_xml(metadata_list)
        print("Writing RunMe.bat.")
        write_processing_batch_file(models, animation_metadata, processor = 'PhyreAssetProcessor.exe')
        if len(new_times) > 0:
            print("Warning!  There are animations where the start time do not match the metadata!  Ani script updates required.")
            for new_time in new_times:
                print("Animation {0} now has start time of {1} seconds, end time of {2} seconds.".format(new_time,\
                    new_times[new_time][0], new_times[new_time][1]))
                input("Press Enter to continue.")
    else:
        print("No model metadata found, entering texture only mode...")
        asset_xmls = glob.glob('**/asset*.xml', recursive=True)
        for i in range(len(asset_xmls)):
            print("Processing {0}...".format(asset_xmls[i].replace('\\','/')))
            write_texture_processing_batch_file(asset_xmls[i],i, processor = 'PhyreAssetProcessor.exe')
