# Trails of Cold Steel III / IV / into Reverie and Tokyo Xanadu eX+ Model Toolset

This a tool set for making mods of character models in Trails of Cold Steel III, IV and into Reverie (Hajimari) as well as Tokyo Xanadu eX+ for PC (DirectX 11).  There is also experimental support for CS1/CS2.  It is built on top of uyjulian's ed8pkg2glb tool, which is [here](https://github.com/uyjulian/ed8pkg2glb).  I have not removed the functionality of producing glb (gltf) files, although those files are not used in the model compilation process.

## Tutorials:

Please see the [wiki](https://github.com/eArmada8/ed8pkg2gltf/wiki), and the detailed documentation below.

## Credits:
The original phyre asset decompiler is written by Julian Uy (github.com/uyjulian), and I have only made modifications.  I wrote the remaining tools, and am very thankful to Arc, My Name, uyjulian, TwnKey, AdmiralCurtiss, Kyuuhachi and the Kiseki modding discord for their brilliant work and for sharing that work so freely.  I am especially thankful to Arc for sharing expertise in the compilation process and for spending many evenings helping me debug!  I am also very thankful to My Name for sharing models and knowledge as well.

## Requirements:
1. Python 3.9 or newer is required for use of this script.  It is free from the Microsoft Store, for Windows users.  For Linux users, please consult your distro.
2. Numpy, pyquaternion and pygltflib are required by build_collada as well as the glTF mesh exporter.  The zstandard module for python is needed for decompiling zstandard-compressed pkgs.  The lz4 module is used for compressing compiled .pkgs.  Install all of these by running the included install_python_modules.bat or by typing "python3 -m pip install zstandard numpy pyquaternion pygltflib" in the command line / shell.
3. The output can be imported into Blender using DarkStarSword's amazing plugin: https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py (tested on commit [5fd206c](https://raw.githubusercontent.com/DarkStarSword/3d-fixes/5fd206c52fb8c510727d1d3e4caeb95dac807fb2/blender_3dmigoto.py))
4. Compilation is dependent on the phyre Engine tools from [here](https://github.com/Trails-Research-Group/Doc/releases/download/v0.0/WorkFolder.zip), as described on the [tutorial from the Trails-Research-Group](https://github.com/Trails-Research-Group/Doc/wiki/How-to:-Import-custom-models-to-Cold-Steel-IV).  (You do not need the tutorial for basic mods, just the tools.)  The tools require [the Windows SDK](https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/).  (There is experimental CS1 and CS2 support.  Each requires their own specific compiler, which is available on the Kiseki Modding Discord.  The CS1 and CS2 compilers require the MS Visual C++ 2013 runtime libraries.)
5. The compiler can be made to run on Linux; build_collada.py will write a shell script instead of a batch file if Linux is detected (`wine` must be accessible via path).
6. While optional, `write_pkg.py` will take advantage of `sentools.exe` if present to speed up compression.  `sentools.exe` can be obtained from [SenPatcher by AdmiralCurtiss](https://github.com/AdmiralCurtiss/SenPatcher/releases)

## Usage:

### Step 1: Decompilation
Obtain a model or animation pkg file.  In CS3/CS4, the files are stored in assets.pka and must be extracted.  Use [extract_pka.py](https://github.com/eArmada8/unpackpka) in the same folder as assets.pka.  Tokyo Xanadu eX+ assets are stored in .bra archives, txe_file_extract.py can be used and is available as part of [ed8_inject](https://github.com/eArmada8/ed8_inject/releases).

Place ed8pkg2gltf.py and lib_fmtibvb.py into a folder with your character model (.pkg) file.  Double-click ed8pkg2gltf.py.  It will create a folder with the same name as the pkg, and dump in there the model in glb (gltf) form, meshes for modding in a folder, textures in their own folder, and a metadata.json file.  (Note: Vertex group mapping behavior can be configured, see below.)

Note: If there is more than one .pkg file in the directory, the script will dump them all.

### Step 2: Modding

- Ignore the glb (glTF) file for modding models (for animations, see below).  (Or use it for other purposes, but it is not used during compile.)  (***Note:*** v2.1.1 and above include an experimental glTF mesh dumper that can be used to convert glTFs to raw buffers and a skeleton metadata file.  This is ***not*** my recommended way to mod for most simple mods and will increase the complexity of the process, but will be useful for complex mods where the skeleton will be replaced.  See below.)

- There is a folder with the same name as the package, this is the build folder.  The asset_D3D11.xml file and compiled shaders reside here.  For simple mods, nothing here should be changed.

- Textures can be edited in the program of your choice.  If you add files and/or change file names, the metadata.json should be updated.  To see what texture formats are supported, run ```CSIVAssetImportTool.exe -?```  Note, however, that CS3, CS4 and Hajimari expect textures to be in DXT10 BC7_UNORM format (BC7 Linear, not sRBG) - the compiler will accept other formats (e.g. DXT1) but your texture may be horizontally flipped.  Per uyjulian, the original asset import pipeline horizontally flipped textures if they were not BC4, BC5, BC6, BC7 or ETC1.  While it is a pain, for best quality and fewer headaches, I recommend double-exporting from your image editing program in linear BC7 for the game and PNG for Blender.  Also, the decompiler exports all textures *without mipmaps*.  Consider adding them back for large models (maps / levels) for performance.

- Meshes can be modified by importing them into Blender using DarkStarSword's plugin (see above).  Export when finished and overwrite the original files.  Note that meshes with more than 80 active vertex groups will disable GPU skinning (empty groups are okay as the compiler will cull empty groups from skin index of each individual mesh).  To remove a mesh, just delete the files (.fmt/.ib/.vb).  If adding a mesh, be sure it conforms to the existing skeletal map (.vgmap).  (***Note:*** Meshes dumped with this tool have remapped skeletons by default, so existing 3DMigoto meshes cannot be dumped in as-is.  You can either merge into a dumped mesh, or you can run the decompiler with the partial maps option to get meshes with original mapping.  The latter is probably preferred for converting mods since I have confirmed that otherwise you can literally replace the .fmt/.ib/.vb files {keep the .material, .uvmap and .vgmap files} for rapid mod conversion.)

- Material assignments can be changed by changing the .material file associated with the mesh.  Note that the material defines both the textures and the shader.  The build script will not accept any meshes without a .material file.

- New materials can be defined in the metadata (just be careful with commas - you may want to use a dedicated JSON editor).  We cannot make new shaders from scratch, however, so you will need to copy valid metadata (with matching shader hash etc).  To make a new material, copy the material you want from elsewhere (can be from the same character for example, or you can take from a different character) and give it a name that is unique to this model.  Change the textures to what you need (I am pretty sure that the texture *slots* are defined by the shader though - so for example if the shader you pick needs a normal map, you need to provide a normal map).  Update the .material file of the mesh you are assigning it to.  If this is a new shader to this model (i.e. you copied the metadata from a different model), then copy both the *unskinned* and *skinned* shaders to the build directory.  (Meshes / materials without skeletons will not have a skinned shader.)

- Decompiling models with collision (maps) will produce a physics_data.json file.  The collision mesh names should match the target node identified in physics_data.json for a successful compile.  Tuneable parameters will be in this file for defining the rigid bodies (collision meshes) as well, although every map I have examined has the same parameters (except coordinates) so it is likely that there is no good reason to modify these.  There is currently no real documentation for how to make or modify maps; I do not really understand the process.  Consider map support experimental at this time.

- For animation .pkg files, the decompiler will dump all animations in .glb format.  Metadata for animations will be placed in the animation_metadata.json.  The glb files can be directly imported into Blender, but Bone Dir must be set to "Blender (best for re-importing)" upon import or the skeleton will be altered irreversibly, preventing the animation from being used in the game.  Using the files directly is not recommended; instead decompile the base model as well, and put the .glb file in the same folder with the animations and run merge_model_into_animations.py in that folder.  It will insert the model data including meshes / skins / texture references etc into the animation .glb, which will make animation feasible.

### Step 3: Building a COLLADA .dae and compiling

For this step, put build_collada.py, lib_fmtibvb.py, replace_shader_references.py and write_pkg.py in the model directory (the directory with metadata.json).  You will also need to have the contents of WorkFolder.zip in your model directory.  (You need CSIVAssetImportTool.exe, all the PhyreAsset_____ files, PhyreDummyShaderCreator.exe, SQLite.Interop.dll and System.Data.SQLite.dll.  You do not need the shaders directory.)

-Double click build_collada.py.  It will make a .dae file, in the original compile folder as defined in asset_D3D11.xml (by default it is chr/chr/{model name}/).  It will also make a shaders/ed8_chr.fx file for compiling (and/or ed8.fx, etc), and a RunMe.bat (or RunMe.sh if run on Linux).  (For animations, it will make a .dae file for every animation listed in animation_metadata.json.  Animations will not have shader files.)  For CS1, you will need the CS1 processor and its associated files; run build_collada_cs1.py instead of build_collada.py.  (build_collada_cs1.py is only a shell, it requires build_collada.py in the same folder to run.)  Likewise, for CS2, use the CS2 processor and build_collada_cs2.py.

-Double click RunMe.bat / RunMe.sh.  It will run the asset import tool, then it will use the dummy shader creator to identify all the shaders for replacement, then it will use replace_shader_references.py to fix all the shader pointers, and finally it will clean up, move everything to the build directory, and run write_pkg.py to generate your .pkg file.  By default, the original compression will be applied (LZSS/LZ4/None) although zstandard will be replaced with LZ4.  If write_pkg.py finds sentools.exe in the folder, it will utilize that to perform the compression for enhanced speed.

## Notes

**Weight Painting:**

If you would like to weight paint the meshes, you will want to parent to the armature so you can see the results of your painting in Blender.  Import your raw meshes **and** the glTF.  Delete all the meshes from the glTF.  Select all your raw buffers in object mode, then shift-click on the bones (or ctrl-click up_point in the outliner window).  Go to Object menu -> Parent -> Armature Deform (do not select any of the "With" options).  Your meshes are now parented, but still can be exported as .fmt/.ib/.vb.  Note that this is necessary to keep all the original data of the buffers, since the glTF meshes are missing a lot of data and also cannot be exported directly as .fmt/.ib/.vb.  If you want to work with the glTF meshs without going through this parenting process, you can use the glTF extractor (see below) - be sure to import with Bone Dir set to "Blender (best for re-importing)".

**Command line arguments for ed8pkg2gltf.py:**

`ed8pkg2gltf.py [-h] [-p] [-o] pkg_filename`

`-h, --help`
Shows help message.

`-p, --partialmaps`
The default behavior of the script is to provide meshes and .vgmap files with the entire skeleton and every bone available to each mesh.  This will result in many empty vertex groups upon import into Blender.  (All empty groups will be removed at the time of compilation.)  This option will preserve the original mapping with the exact original indexing (such that the .vgmaps would correspond to and be compatible with buffers taken out of GPU memory, e.g. when using 3DMigoto).

`-a, --allbuffers`
The default behavior of the script is to write no more than 8 sets of texcoord/tangent/binormal to the .vb files, as the plugin cannot accommodate more than 8.  This option will result in the dumping all the buffers.  (This is meant for debugging, I have never seen any useful information in the upper buffers.)

`-t, --gltf_nonbinary`
Output glTF files in .gltf format, instead of .glb format.
  
`-o, --overwrite`
Overwrite existing files without prompting.

**Complete VGMap Setting:**

While most modders prefer that complete VGmaps is the default, you may want partial maps to be the default (for example to use existing 3dmigoto mods as a base).  You can (permanently) change the default behavior by editing the python script itself.  There is a line at the top:
`partial_vgmaps_default = False`
which you can change to 
`partial_vgmaps_default = True`
This will also change the command line argument `-p, --partialmaps` into `-c, --completemaps` which you would call to enable complete group vgmaps instead.

**Experimental glTF extractor**

extract_from_gltf.py is available for rapid conversion of existing assets in glTF form.  It will take the meshes out of the the gltf in .fmt/.ib/.vb/.vgmap format, and create a skeleton metadata.json.  Please note that quite a lot of information is lost in this process, although it seems to me that the Cold Steel games do not use any of the information that is lost (e.g. binormals).

Note that when you import the glTF in Blender using the default settings with Bone Dir set to "Temperance (average)", the meshes produced by extract_from_gltf.py are useable but the skeleton will be inaccurate.  If you will need to modify the skeleton, then set Bone Dir to "Blender (best for re-importing)" at the time of import.  Also, note that Blender does not export TANGENT by default; check "Tangent" (Data->Mesh->Tangent in the export window) while exporting to preserve the original tangents otherwise extract_from_gltf.py will auto-calculate tangents using the first UV map and the normals.  Using the "Temperance (average)" Bone Dir setting when importing into Blender should be acceptable if you can use the original skeleton extracted by ed8pkg2gltf.py; this will make weight painting easier.

Guide to fixing the metadata.json file after using the glTF extractor:
- ```name``` should be the internal name of the model, and should match the .inf filename.
- ```pkg_name``` should match the build folder name, so build_collada.py will know where to put all the files needed for RunMe.bat
- ```materials``` will be filled with empty (unuseable) placeholder entries.  Replace these with real material entries taken from the actual metadata.json files generated by ed8pkg2gltf.py.
- ```heirarchy``` should be useable without modification.  This is where the skeleton is - if the skeleton needs modification, modify it in the glTF before running extract_from_gltf.py instead.
- ```locators``` might or might not work without modification.  I suggest copying it over from the original metadata.json, unless the skeleton has been modified.

This tool extracts the glTF assets into its own folder, rather than overwriting all the files in the main folder if you happen to run it on the glTF that was dumped by ed8pkg2gltf.py.  After fixing the metadata, delete the original meshes/metadata and move the meshes and metadata.json files to the correct location.  Do not rely on overwriting for the meshes, as the glTF meshes have different names so you will end up with two sets of meshes in your model if you do not delete the originals.

## Other

Everything below this line is from uyjulian's original README:

### Credits

The PS4, PS3, and Vita image untiling are adapted from here: https://github.com/xdanieldzd/Scarlet/blob/8c56632eb2968e64b6d6fad14af3758e606a127d/Scarlet/Drawing/ImageBinary.cs#L1256  
The PS4 texture information are adapted from here: https://zenhax.com/viewtopic.php?f=7&t=7573  
The LZ4 decompression is adapted from here: https://gist.github.com/weigon/43e217e69418875a55b31b1a5c89662d  
The `nislzss`/LZ77 decompression is adapted from here: https://github.com/Sewer56/Sen-no-Kiseki-PKG-Sharp/blob/3a458e201aa946add705c6ed6aa1dd49dce00223/D/source/decompress.d#L50  
Huge thanks to @PMONickpop123 for assisting with debugging and feature completeness.

### License

The program is licensed under the MIT license. Please check `LICENSE` for more information.
