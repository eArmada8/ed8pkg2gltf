# ED8 COLLADA builder, needs output from my fork of uyjulian/ed8pkg2glb.
# Needs pyquaternion if heirarchy is inputted as TRS instead of matrix.
#
# GitHub eArmada8/ed8pkg2gltf

try:
    import os, glob, numpy, json, io, sys, xml.dom.minidom
    import xml.etree.ElementTree as ET
    from pyquaternion import Quaternion
    from pygltflib import GLTF2
    from lib_fmtibvb import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

#Does not support sparse
def read_gltf_stream (gltf, accessor_num):
    accessor = gltf.accessors[accessor_num]
    bufferview = gltf.bufferViews[accessor.bufferView]
    buffer = gltf.buffers[bufferview.buffer]
    componentType = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
    componentSize = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    componentCount = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
    componentFormat = "<{0}{1}".format(componentCount[accessor.type],\
        componentType[accessor.componentType])
    componentStride = componentCount[accessor.type] * componentSize[accessor.componentType]
    data = []
    with io.BytesIO(gltf.get_data_from_buffer_uri(buffer.uri)) as f:
        f.seek(bufferview.byteOffset + accessor.byteOffset, 0)
        for i in range(accessor.count):
            data.append(list(struct.unpack(componentFormat, f.read(componentStride))))
            if (bufferview.byteStride is not None) and (bufferview.byteStride > componentStride):
                f.seek(bufferview.byteStride - componentStride, 1)
    if accessor.normalized == True:
        for i in range(len(data)):
            if componentType == 'b':
                data[i] = [x / ((2**(8-1))-1) for x in data[i]]
            elif componentType == 'B':
                data[i] = [x / ((2**8)-1) for x in data[i]]
            elif componentType == 'h':
                data[i] = [x / ((2**(16-1))-1) for x in data[i]]
            elif componentType == 'H':
                data[i] = [x / ((2**16)-1) for x in data[i]]
    return(data)

# Create the basic COLLADA XML document, with values that do not change from model to model (I think)
# TODO: Are units, gravity and time step constant?
def basic_collada ():
    collada = ET.Element('COLLADA')
    collada.set("xmlns", "http://www.collada.org/2005/11/COLLADASchema")
    collada.set("version", "1.4.1")
    asset = ET.SubElement(collada, 'asset')
    asset_unit = ET.SubElement(asset, 'unit')
    asset_unit.set("meter", "0.01")
    asset_unit.set("name", "centimeter")
    asset_up_axis = ET.SubElement(asset, 'up_axis')
    asset_up_axis.text = "Y_UP"
    library_visual_scenes = ET.SubElement(collada, 'library_visual_scenes')
    scene = ET.SubElement(collada, 'scene')
    return(collada)

# Add image URIs
def add_images (collada, images, relative_path = '../../..'):
    library_images = ET.SubElement(collada, 'library_images')
    for image in images:
        image_name = image.replace('.DDS','.dds').split('.dds')[0]
        image_element = ET.SubElement(library_images, 'image')
        image_element.set("id", os.path.basename(image_name)+'_Image')
        image_element.set("name", os.path.basename(image_name)+'_Image')
        image_element_init_from = ET.SubElement(image_element, 'init_from')
        image_element_init_from.text = relative_path + '/' + image
        image_element_extra = ET.SubElement(image_element, 'extra')
        image_element_extra_technique = ET.SubElement(image_element_extra, 'technique')
        image_element_extra_technique.set("profile", "MAYA")
        image_element_extra_technique_dg = ET.SubElement(image_element_extra_technique, 'dgnode_type')
        image_element_extra_technique_dg.text = "kFile"
        image_element_extra_technique_is = ET.SubElement(image_element_extra_technique, 'image_sequence')
        image_element_extra_technique_is.text = "0"
    return(collada)

# Build the materials section
def add_materials (collada, metadata, relative_path = '../../..', forward_render = False):
    materials = metadata['materials']
    # Materials and effects can be done in parallel
    library_materials = ET.SubElement(collada, 'library_materials')
    library_effects = ET.SubElement(collada, 'library_effects')
    all_shader_switches = ['SHADER_'+(v['shader'].split('#')[-1] if len(v['shader'].split('#')) > 1 else '') for (k,v) in materials.items()]
    for material in materials:
        #Materials
        material_element = ET.SubElement(library_materials, 'material')
        material_element.set("id", material)
        material_element.set("name", material)
        instance_effect = ET.SubElement(material_element, 'instance_effect')
        instance_effect.set("url", "#{0}-fx".format(material))
        technique_hint = ET.SubElement(instance_effect, 'technique_hint')
        technique_hint.set("platform", "PC-DX")
        if forward_render == True:
            technique_hint.set("ref", "ForwardRender")
        else:
            technique_hint.set("ref", "Default")
        #Effects
        effect_element = ET.SubElement(library_effects, 'effect')
        effect_element.set("id", material + '-fx')
        profile_HLSL = ET.SubElement(effect_element, 'profile_HLSL')
        profile_HLSL.set('platform', 'PC-DX')
        include = ET.SubElement(profile_HLSL, 'include')
        include.set('sid','include')
        include.set('url', relative_path + '/' + materials[material]['shader'].split('#')[0])
        # Float parameters - I haven't seen anything that isn't float, so I set everything here to float for now
        for parameter in materials[material]['shaderParameters']:
            #Material
            setparam = ET.SubElement(instance_effect, 'setparam')
            setparam.set("ref", material + parameter)
            try:
                values = ET.SubElement(setparam,\
                    'float{0}'.format({1:'', 2:2, 3:3, 4:4, 5:5}[len(materials[material]['shaderParameters'][parameter])]))
            except KeyError:
                print("KeyError: Material {0} parameter {1} has an invalid float{2}.".format(material, parameter,\
                    len(materials[material]['shaderParameters'][parameter])))
                input("Press Enter to abort.")
                raise
            values.text = " ".join(["{0:g}".format(x) for x in materials[material]['shaderParameters'][parameter]])
            #Effect
            newparam = ET.SubElement(profile_HLSL, 'newparam')
            newparam.set('sid', material + parameter)
            annotate = ET.SubElement(newparam, 'annotate')
            annotate.set('name', 'UIName')
            string = ET.SubElement(annotate, 'string')
            string.text = parameter
            if len(materials[material]['shaderParameters'][parameter]) == 1:
                annotate = ET.SubElement(newparam, 'annotate')
                annotate.set('name', 'UIMin')
                string = ET.SubElement(annotate, 'float')
                string.text = '0'
                annotate = ET.SubElement(newparam, 'annotate')
                annotate.set('name', 'UIMax')
                string = ET.SubElement(annotate, 'float')
                string.text = '1'
            else:
                annotate = ET.SubElement(newparam, 'annotate')
                annotate.set('name', 'UIType')
                string = ET.SubElement(annotate, 'string')
                string.text = 'Color'
            semantic = ET.SubElement(newparam, 'semantic')
            semantic.text = parameter
            values = ET.SubElement(newparam, 'float{0}'.format({1:'', 2:2, 3:3, 4:4, 5:5}[len(materials[material]['shaderParameters'][parameter])]))
            values.text = " ".join(["{0:g}".format(x) for x in materials[material]['shaderParameters'][parameter]])
        #Sampler definitions, for the effects section
        for parameter in materials[material]['shaderSamplerDefs']:
            #None in Material
            #Effect
            newparam = ET.SubElement(profile_HLSL, 'newparam')
            newparam.set('sid', parameter)
            samplerDX = ET.SubElement(newparam, 'samplerDX')
            wrap_s = ET.SubElement(samplerDX, 'wrap_s')
            wrap_s.text = materials[material]['shaderSamplerDefs'][parameter]['m_wrapS']
            wrap_t = ET.SubElement(samplerDX, 'wrap_t')
            wrap_t.text = materials[material]['shaderSamplerDefs'][parameter]['m_wrapT']
            wrap_p = ET.SubElement(samplerDX, 'wrap_p')
            wrap_p.text = materials[material]['shaderSamplerDefs'][parameter]['m_wrapR']
            dxfilter = ET.SubElement(samplerDX, 'dxfilter')
            dxfilter.text = 'MIN_MAG_MIP_LINEAR' # This is probably not correct but I don't know the possible codes
            func = ET.SubElement(samplerDX, 'func')
            func.text = 'NEVER' # Again, who knows?
            max_anisotropy = ET.SubElement(samplerDX, 'max_anisotropy')
            max_anisotropy.text = "{0:g}".format(materials[material]['shaderSamplerDefs'][parameter]['m_maxAnisotropy'])
            lod_min_distance = ET.SubElement(samplerDX, 'lod_min_distance')
            lod_min_distance.text = "{0}".format(materials[material]['shaderSamplerDefs'][parameter]['m_baseLevel'])
            lod_max_distance = ET.SubElement(samplerDX, 'lod_max_distance')
            lod_max_distance.text = "{0}".format(materials[material]['shaderSamplerDefs'][parameter]['m_maxLevel'])
            border_color = ET.SubElement(samplerDX, 'border_color')
            border_color.text = '0 0 0 0' # In the example it's always this, and in the phyre file it's a single 0.  I dunno.
        # Texture parameters - only support for 2D currently
        for parameter in materials[material]['shaderTextures']:
            if materials[material]['shaderTextures'][parameter] == '' or not os.path.exists(materials[material]['shaderTextures'][parameter]):
                print("Warning: Material {0} parameter {1} has a missing texture: {2}.".format(material, parameter, materials[material]['shaderTextures'][parameter]))
                print("Compile will likely fail, and the .pkg may crash the game.")
                input("Press Enter to continue.")
            texture_name = materials[material]['shaderTextures'][parameter].replace('.DDS','.dds').split('/')[-1].split('.dds')[0]
            if parameter + 'S' in materials[material]['shaderSamplerDefs']:
                sampler_name = parameter + 'S' # CS2
            else:
                sampler_name = parameter + 'Sampler' # CS3 onward
            if 'non2Dtextures' in materials[material].keys() and parameter in materials[material]['non2Dtextures'].keys() \
                and materials[material]['non2Dtextures'][parameter] == 'PTextureCubeMap':
                sampler_type = 'samplerCUBE'
                tex_type = 'CUBE'
            else:
                sampler_type = 'sampler2D' # Use as default, should be PTexture2D
                tex_type = '2D'
            #Material
            setparam = ET.SubElement(instance_effect, 'setparam')
            setparam.set("ref", material + parameter)
            sampler = ET.SubElement(setparam, sampler_type)
            source = ET.SubElement(sampler, 'source')
            source.text = texture_name + "Surface"
            wrap_s = ET.SubElement(sampler, 'wrap_s')
            wrap_t = ET.SubElement(sampler, 'wrap_t')
            minfilter = ET.SubElement(sampler, 'minfilter')
            magfilter = ET.SubElement(sampler, 'magfilter')
            mipfilter = ET.SubElement(sampler, 'mipfilter')
            mipfilter.text = 'NONE'
            max_anisotropy = ET.SubElement(sampler, 'max_anisotropy')
            if sampler_name in materials[material]['shaderSamplerDefs']:
                wrap_s.text = materials[material]['shaderSamplerDefs'][sampler_name]['m_wrapS']
                wrap_t.text = materials[material]['shaderSamplerDefs'][sampler_name]['m_wrapT']
                minfilter.text = materials[material]['shaderSamplerDefs'][sampler_name]['m_minFilter']
                magfilter.text = materials[material]['shaderSamplerDefs'][sampler_name]['m_magFilter']
                max_anisotropy.text = "{0:g}".format(materials[material]['shaderSamplerDefs'][sampler_name]['m_maxAnisotropy'])
            else: # CartoonMapSampler and SphereMapSampler
                wrap_s.text = 'WRAP'
                wrap_t.text = 'WRAP'
                minfilter.text = 'NONE'
                magfilter.text = 'NONE'
                max_anisotropy.text = '0'
            setparam2 = ET.SubElement(instance_effect, 'setparam')
            setparam2.set("ref", texture_name + "Surface")
            surface = ET.SubElement(setparam2, 'surface')
            surface.set('type', tex_type)
            init_from = ET.SubElement(surface, 'init_from')
            init_from.set("mip", "0")
            init_from.set("slice", "0")
            init_from.text = texture_name + '_Image'
            texformat = ET.SubElement(surface, 'format')
            texformat.text = "A8R8G8B8"
            #Effect
            newparam = ET.SubElement(profile_HLSL, 'newparam')
            newparam.set("sid", material + parameter)
            annotate = ET.SubElement(newparam, 'annotate')
            annotate.set('name', 'UIName')
            string = ET.SubElement(annotate, 'string')
            string.text = parameter
            semantic = ET.SubElement(newparam, 'semantic')
            semantic.text = parameter
            sampler = ET.SubElement(newparam, 'sampler2D')
            source = ET.SubElement(sampler, 'source')
            source.text = texture_name + "Surface"
            wrap_s = ET.SubElement(sampler, 'wrap_s')
            wrap_t = ET.SubElement(sampler, 'wrap_t')
            minfilter = ET.SubElement(sampler, 'minfilter')
            magfilter = ET.SubElement(sampler, 'magfilter')
            mipfilter = ET.SubElement(sampler, 'mipfilter')
            mipfilter.text = 'NONE'
            max_anisotropy = ET.SubElement(sampler, 'max_anisotropy')
            if sampler_name in materials[material]['shaderSamplerDefs']:
                wrap_s.text = materials[material]['shaderSamplerDefs'][sampler_name]['m_wrapS']
                wrap_t.text = materials[material]['shaderSamplerDefs'][sampler_name]['m_wrapT']
                minfilter.text = materials[material]['shaderSamplerDefs'][sampler_name]['m_minFilter']
                magfilter.text = materials[material]['shaderSamplerDefs'][sampler_name]['m_magFilter']
                max_anisotropy.text = "{0:g}".format(materials[material]['shaderSamplerDefs'][sampler_name]['m_maxAnisotropy'])
            else: # CartoonMapSampler and SphereMapSampler
                wrap_s.text = 'WRAP'
                wrap_t.text = 'WRAP'
                minfilter.text = 'NONE'
                magfilter.text = 'NONE'
                max_anisotropy.text = '0'
            newparam2 = ET.SubElement(profile_HLSL, 'newparam')
            newparam2.set("sid", texture_name + "Surface")
            annotate = ET.SubElement(newparam2, 'annotate')
            annotate.set('name', 'UIName')
            string = ET.SubElement(annotate, 'string')
            string.text = texture_name
            surface = ET.SubElement(newparam2, 'surface')
            surface.set('type', '2D')
            init_from = ET.SubElement(surface, 'init_from')
            init_from.set("mip", "0")
            init_from.set("slice", "0")
            init_from.text = texture_name
            texformat = ET.SubElement(surface, 'format')
            texformat.text = "A8R8G8B8"
        extra = ET.SubElement(material_element, 'extra')
        technique = ET.SubElement(extra, 'technique')
        technique.set("profile", "PHYRE")
        material_switches = ET.SubElement(technique, 'material_switches')
        shader_name_split = materials[material]['shader'].split('#')
        current_shader_switch = 'SHADER_' + (shader_name_split[-1] if len(shader_name_split) > 1 else '')
        shader = ET.SubElement(material_switches, current_shader_switch)
        material_switch_list = ET.SubElement(technique, 'material_switch_list')
        if 'shaderSwitches' in materials[material]:
            # Switches are taken from the shader files themselves
            for material_switch in materials[material]['shaderSwitches']:
                material_switch_entry = ET.SubElement(material_switch_list, 'material_switch')
                material_switch_entry.set("name", material_switch)
                material_switch_entry.set("material_switch_value", materials[material]['shaderSwitches'][material_switch])
        for i in range(len(all_shader_switches)):
            material_switch_entry = ET.SubElement(material_switch_list, 'material_switch')
            material_switch_entry.set("name", all_shader_switches[i])
            if all_shader_switches[i] == current_shader_switch:
                material_switch_entry.set("material_switch_value", "1")
            else:
                material_switch_entry.set("material_switch_value", "0")
        forwardrendertechnique = ET.SubElement(profile_HLSL, 'technique')
        if forward_render == True:
            forwardrendertechnique.set("sid", "ForwardRender")
        else:
            forwardrendertechnique.set("sid", "Default")
        renderpass = ET.SubElement(forwardrendertechnique, 'pass')
        shader = ET.SubElement(renderpass, 'shader')
        shader.set('stage','VERTEX')
        for parameter in list(materials[material]['shaderParameters'].keys()) +\
                list(materials[material]['shaderSamplerDefs'].keys()) + list(materials[material]['shaderTextures'].keys()):
            switch_bind = ET.SubElement(shader, 'bind')
            switch_bind.set('symbol', parameter)
            switch_param = ET.SubElement(switch_bind, 'param')
            switch_param.set('ref', material + parameter)
        extra = ET.SubElement(effect_element, 'extra')
        technique = ET.SubElement(extra, 'technique')
        technique.set('profile', 'PHYRE')
        context_switches = ET.SubElement(technique, 'context_switches')
        supported_lights = ET.SubElement(context_switches, 'supported_lights')
        supported_lights.set('max_light_count', '0')
        supported_shadows = ET.SubElement(context_switches, 'supported_shadows')
    return(collada)

def calc_abs_matrix(node, skeleton, skeletal_bones = []):
    try:
        skeleton[node]['abs_matrix'] = numpy.dot(skeleton[skeleton[node]['parent']]['abs_matrix'], skeleton[node]['rel_matrix'])
    except KeyError:
        children_list = {i:skeleton[i]['children'] if 'children' in skeleton[i].keys() else [] for i in range(len(skeleton))}
        parent_list = ", ".join([skeleton[i]['name'] for i in children_list if node in children_list[i]])
        print("KeyError: {0} is missing abs_matrix.  This is often due to an invalid parent assignment!".format(skeleton[node]['name']))
        print("Detected parent(s) of {0}: {1}.".format(skeleton[node]['name'], parent_list))
        input("Press Enter to abort.")
        raise
    try:
        skeleton[node]['inv_matrix'] = numpy.linalg.inv(skeleton[node]['abs_matrix'])
    except numpy.linalg.LinAlgError:
        if skeleton[node]['name'] not in skeletal_bones:
            pass
        else:
            print("LinAlgError: {0} has an invalid matrix and is part of the skeleton.".format(skeleton[node]['name']))
            input("Press Enter to abort.")
            raise
    if 'children' in skeleton[node].keys():
        for child in skeleton[node]['children']:
            if child < len(skeleton):
                skeleton = calc_abs_matrix(child, skeleton)
                skeleton[node]['num_descendents'] += skeleton[child]['num_descendents'] + 1
    return(skeleton)

# Change matrices to numpy arrays, add parent bone ID, world space matrix, inverse bind matrix
def add_bone_info (skeleton, skeletal_bones = []):
    children_list = [{i:skeleton[i]['children'] if 'children' in skeleton[i].keys() else []} for i in range(len(skeleton))]
    parent_dict = {x:list(y.keys())[0] for y in children_list for x in list(y.values())[0]}
    top_nodes = [i for i in range(len(skeleton)) if i not in parent_dict.keys()]
    identity_mtx = [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
    for i in range(len(skeleton)):
        if i in parent_dict.keys():
            skeleton[i]['parent'] = parent_dict[i]
        else:
            skeleton[i]['parent'] = -1
        if 'matrix' in skeleton[i]:
            matrix = numpy.array([skeleton[i]['matrix'][0:4],\
                skeleton[i]['matrix'][4:8], skeleton[i]['matrix'][8:12], skeleton[i]['matrix'][12:16]]).transpose()
        elif 'translation' in skeleton[i].keys() or 'rotation' in skeleton[i].keys() or 'scale' in skeleton[i].keys():
            if 'translation' in skeleton[i].keys():
                t = numpy.array([[1,0,0,skeleton[i]['translation'][0]],[0,1,0,skeleton[i]['translation'][1]],\
                    [0,0,1,skeleton[i]['translation'][2]],[0,0,0,1]])
            else:
                t = numpy.array(identity_mtx)
            if 'rotation' in skeleton[i].keys(): # quaternion is expected in xyzw (GLTF standard)
                r = Quaternion(w=skeleton[i]['rotation'][3], x=skeleton[i]['rotation'][0],\
                    y=skeleton[i]['rotation'][1], z=skeleton[i]['rotation'][2]).transformation_matrix
            else:
                r = numpy.array(identity_mtx)
            if 'scale' in skeleton[i].keys():
                s = numpy.array([[skeleton[i]['scale'][0],0,0,0],[0,skeleton[i]['scale'][1],0,0],\
                    [0,0,skeleton[i]['scale'][2],0],[0,0,0,1]])
            else:
                s = numpy.array(identity_mtx)
            matrix = numpy.dot(numpy.dot(t, r), s)
        else:
            matrix = numpy.array(identity_mtx)
        skeleton[i]['rel_matrix'] = matrix
        skeleton[i]['num_descendents'] = 0
    for node in top_nodes:
        skeleton[node]['abs_matrix'] = skeleton[node]['rel_matrix']
        skeleton[node]['inv_matrix'] = numpy.linalg.inv(skeleton[node]['abs_matrix'])
        if 'children' in skeleton[node].keys():
            for child in skeleton[node]['children']:
                skeleton = calc_abs_matrix(child, skeleton, skeletal_bones = skeletal_bones)
                skeleton[node]['num_descendents'] += skeleton[child]['num_descendents'] + 1
    return(skeleton)

# Ordered_list should be empty when calling
def order_nodes_by_heirarchy (node, filter_list, skeleton, ordered_list = []):
    if node < len(skeleton):
        if skeleton[node]['name'] in filter_list:
            ordered_list.append(skeleton[node]['name'])
        if 'children' in skeleton[node].keys():
            for child in skeleton[node]['children']:
                ordered_list = order_nodes_by_heirarchy (child, filter_list, skeleton, ordered_list)
    return(ordered_list)

# Needs to be ordered by heirarchy, phyre Engine seems very sensitive to this
def get_joint_list (top_node, vgmaps, skeleton):
    ordered_list = order_nodes_by_heirarchy (top_node, vgmaps, skeleton, ordered_list = [])
    return({ordered_list[i]:i for i in range(len(ordered_list))})

def get_bone_dict (skeleton):
    bone_dict = {}
    for i in range(len(skeleton)):
        bone_dict[skeleton[i]['name']] = i
    return(bone_dict)

# Recursive function to fill out the entire node tree; call with the first node and i = 0
def get_children (parent_node, i, metadata, skeletal_bones = []):
    if not metadata['heirarchy'][i]['name'] == parent_node.attrib['name']:
        node = ET.SubElement(parent_node, 'node')
        node.set('id', metadata['heirarchy'][i]['name'])
        node.set('name', metadata['heirarchy'][i]['name'])
        node.set('sid', metadata['heirarchy'][i]['name'])
        if 'rel_matrix' in metadata['heirarchy'][i]:
            matrix = ET.SubElement(node, 'matrix')
            matrix.set('sid','transform')
            matrix.text = " ".join(["{0}".format(x) for x in metadata['heirarchy'][i]['rel_matrix'].flatten('C')])
        if metadata['heirarchy'][i]['name'] in skeletal_bones:
            node.set('type', 'JOINT')
            extra = ET.SubElement(node, 'extra')
            technique = ET.SubElement(extra, 'technique')
            technique.set('profile','PSSG')
            translate_keyed = ET.SubElement(technique, 'translate_keyed')
            rotate_keyed = ET.SubElement(technique, 'rotate_keyed')
            scale_keyed = ET.SubElement(technique, 'scale_keyed')
        else:
            node.set('type', 'NODE')
        if 'children' in metadata['heirarchy'][i].keys():
            for j in range(len(metadata['heirarchy'][i]['children'])):
                if metadata['heirarchy'][i]['children'][j] < len(metadata['heirarchy']):
                    get_children(node, metadata['heirarchy'][i]['children'][j], metadata, skeletal_bones = skeletal_bones)
        extra = ET.SubElement(node, 'extra')
        technique = ET.SubElement(extra, 'technique')
        if 'locators' in metadata.keys() and metadata['heirarchy'][i]['name'] in metadata['locators']:
            technique.set('profile', 'PHYRE')
            locator = ET.SubElement(technique, 'locator')
            locator.text = '1'
        else:
            technique.set('profile', 'MAYA')
            dynamic_attributes = ET.SubElement(technique, 'dynamic_attributes')
            filmboxTypeID = ET.SubElement(dynamic_attributes, 'filmboxTypeID')
            filmboxTypeID.set('short_name', 'filmboxTypeID')
            filmboxTypeID.set('type', 'int')
            filmboxTypeID.text = '5'
            segment_scale_compensate = ET.SubElement(technique, 'segment_scale_compensate')
            segment_scale_compensate.text = '0'
    else:
        # Duplicated child node detected, do not process except to add children to the parent node
        if 'children' in metadata['heirarchy'][i].keys():
            for j in range(len(metadata['heirarchy'][i]['children'])):
                if metadata['heirarchy'][i]['children'][j] < len(metadata['heirarchy']):
                    get_children(parent_node, metadata['heirarchy'][i]['children'][j], metadata, skeletal_bones = skeletal_bones)
    return

# Used to add an empty node to visual scene if no node can be found to attach geometry
def add_empty_node (name, parent_node):
    node = ET.SubElement(parent_node, 'node')
    node.set('id', name)
    node.set('name', name)
    node.set('sid', name)
    node.set('type', 'NODE')
    matrix = ET.SubElement(node, 'matrix')
    matrix.set('sid','transform')
    matrix.text = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"
    extra = ET.SubElement(node, 'extra')
    technique = ET.SubElement(extra, 'technique')
    technique.set('profile', 'MAYA')
    dynamic_attributes = ET.SubElement(technique, 'dynamic_attributes')
    filmboxTypeID = ET.SubElement(dynamic_attributes, 'filmboxTypeID')
    filmboxTypeID.set('short_name', 'filmboxTypeID')
    filmboxTypeID.set('type', 'int')
    filmboxTypeID.text = '5'
    segment_scale_compensate = ET.SubElement(technique, 'segment_scale_compensate')
    segment_scale_compensate.text = '0'
    return(node)

# Build out the base node tree, run this before building geometries
def add_skeleton (collada, metadata, skeletal_bones = [], ani_times = [0,8.33]):
    library_visual_scenes = collada.find('library_visual_scenes')
    scene = collada.find('scene')
    children_nodes = list(set([x for y in [x['children'] for x in metadata['heirarchy'] if 'children' in x.keys()] for x in y]))
    top_nodes = [i for i in range(len(metadata['heirarchy'])) if i not in children_nodes]
    for i in range(len(top_nodes)):
        # Do not add top nodes without children, which are likely an artifact anyway of decompile / noesis / etc
        # All scene nodes should have children (and of course, the compiler only supports single scene)
        if 'children' in metadata['heirarchy'][top_nodes[i]].keys():
            visual_scene = ET.SubElement(library_visual_scenes, 'visual_scene')
            visual_scene.set('id', metadata['heirarchy'][top_nodes[i]]['name'])
            if metadata['heirarchy'][top_nodes[i]]['name'] == 'VisualSceneNode':
                visual_scene.set('name', metadata['name'])
            else:
                # Actually the compiler only supports single scene, so this will create a compile error
                visual_scene.set('name', metadata['heirarchy'][top_nodes[i]]['name'])
            get_children(visual_scene, top_nodes[i], metadata, skeletal_bones = skeletal_bones)
            extra = ET.SubElement(visual_scene, 'extra')
            technique = ET.SubElement(extra, 'technique')
            technique.set('profile','FCOLLADA')
            start_time = ET.SubElement(technique, 'start_time')
            start_time.text = str(ani_times[0])
            end_time = ET.SubElement(technique, 'end_time')
            end_time.text = str(ani_times[1])
            instance_visual_scene = ET.SubElement(scene, 'instance_visual_scene')
            instance_visual_scene.set('url', '#' + metadata['heirarchy'][top_nodes[i]]['name'])
    return(collada)

# Add geometries and skin them.  Needs a base node tree to build links to.
def add_geometries_and_controllers (collada, submeshes, skeleton, materials, has_skeleton = True):
    library_geometries = ET.SubElement(collada, 'library_geometries')
    #Find mesh instances with saved inverted bind matrices
    mesh_instances = list(set([x.split('_imtx')[0] for i in range(len(skeleton)) for x in skeleton[i].keys() if '_imtx' in x]))
    if has_skeleton == True:
        library_controllers = ET.SubElement(collada, 'library_controllers')
        library_visual_scenes = collada.find('library_visual_scenes')
        base_node = [child for child in library_visual_scenes[0] if child.tag == 'node'][0]
        children_of_top_node = {base_node[i].attrib['name']:i for i in range(len(base_node)) if base_node[i].tag == 'node'}
        if 'up_point' in children_of_top_node:
            skeleton_name = 'up_point'
        elif 'root' in children_of_top_node:
            skeleton_name = 'root'
        else:
            print("Warning!  Skeleton detection likely failed, as it is not up_point or root (case-sensitive)!  Defaulting to top node.")
            skeleton_name = base_node.attrib['name']
        skeleton_id = [i for i in range(len(skeleton)) if skeleton[i]['name'] == skeleton_name][0]
        joint_list = get_joint_list(skeleton_id, [x for y in [x['vgmap'].keys() for x in submeshes if 'vgmap' in x] for x in y]+[skeleton_name], skeleton)
        bone_dict = get_bone_dict(skeleton)
    for submesh in submeshes:
        if "_".join(submesh["name"].split("_")[:-1]) in mesh_instances:
            meshname = "_".join(submesh["name"].split("_")[:-1])
        elif "_".join(submesh["name"].split("_")[:-2]) in mesh_instances:
            meshname = "_".join(submesh["name"].split("_")[:-2])
        else:
            meshname = submesh["name"]
        semantics_list = [x['SemanticName'] for x in submesh["vb"]]
        geometry = ET.SubElement(library_geometries, 'geometry')
        geometry.set("id", submesh['name'])
        geometry.set("name", submesh['name'])
        mesh = ET.SubElement(geometry, 'mesh')
        semantic_counter = 0
        for vb in submesh["vb"]:
            if vb['SemanticName'] in ['POSITION', 'NORMAL', 'TEXCOORD', 'TANGENT', 'BINORMAL', 'COLOR']:
                if vb['SemanticName'] == 'POSITION':
                    source_id = submesh['name'] + '-positions'
                    source_name = 'position'
                    param_names = ['X', 'Y', 'Z', 'W']
                elif vb['SemanticName'] == 'NORMAL':
                    source_id = submesh['name'] + '-normals'
                    source_name = 'normal'
                    param_names = ['X', 'Y', 'Z', 'W']
                elif vb['SemanticName'] == 'TEXCOORD':
                    source_id = submesh['name'] + '-UV' + vb['SemanticIndex']
                    source_name = 'UV' + vb['SemanticIndex']
                    param_names = ['S', 'T', 'R']
                elif vb['SemanticName'] == 'TANGENT':
                    source_id = submesh['name'] + '-UV' + vb['SemanticIndex'] + '-tangents'
                    source_name = 'UV' + vb['SemanticIndex'] + '-tangents'
                    param_names = ['X', 'Y', 'Z', 'W']
                elif vb['SemanticName'] == 'BINORMAL':
                    source_id = submesh['name'] + '-UV' + vb['SemanticIndex'] + '-binormals'
                    source_name = 'UV' + vb['SemanticIndex'] + '-binormals'
                    param_names = ['X', 'Y', 'Z', 'W']
                elif vb['SemanticName'] == 'COLOR':
                    source_id = submesh['name'] + '-colors' + vb['SemanticIndex']
                    source_name = 'color' + vb['SemanticIndex']
                    param_names = ['R', 'G', 'B', 'A']
                source = ET.SubElement(mesh, 'source')
                source.set("id", source_id)
                source.set("name", source_name)
                float_array = ET.SubElement(source, 'float_array')
                float_array.set("id", source_id + '-array')
                float_array.set("count", str(len([x for y in vb['Buffer'] for x in y])))
                float_array.text = " ".join(["{0}".format(x) for y in vb['Buffer'] for x in y])
                technique_common = ET.SubElement(source, 'technique_common')
                accessor = ET.SubElement(technique_common, 'accessor')
                accessor.set('source', '#' + source_id + '-array')
                accessor.set('count', str(len(vb['Buffer'])))
                accessor.set('stride', str(len(vb['Buffer'][0])))
                for i in range(len(vb['Buffer'][0])):
                    param = ET.SubElement(accessor, 'param')
                    param.set('name', param_names[i])
                    param.set('type', 'float')
        if ('BLENDWEIGHT' in semantics_list or 'BLENDWEIGHTS' in semantics_list) and 'BLENDINDICES' in semantics_list:
            if 'BLENDWEIGHT' in semantics_list:
                blendweights = [x['Buffer'] for x in submesh["vb"] if x['SemanticName'] == 'BLENDWEIGHT'][0]
            else:
                blendweights = [x['Buffer'] for x in submesh["vb"] if x['SemanticName'] == 'BLENDWEIGHTS'][0]
            blendindices = [x['Buffer'] for x in submesh["vb"] if x['SemanticName'] == 'BLENDINDICES'][0]
            blendjoints = dict(joint_list)
            new_weights = []
            new_indices = []
            local_to_global_joints = {v:blendjoints[k] for (k,v) in submesh['vgmap'].items() if k in blendjoints}
            for i in range(len(blendweights)):
                new_weight = []
                new_index = []
                for j in range(len(blendweights[i])):
                    if blendweights[i][j] > 0.000001:
                        try:
                            new_weight.append(blendweights[i][j])
                            new_index.append(local_to_global_joints[blendindices[i][j]])
                        except KeyError:
                            try:
                                missing_bone = [x for x in submesh['vgmap'].keys() if submesh['vgmap'][x] == blendindices[i][j]][0]
                                print("KeyError: Attempted to map {1} to skeleton while adding submesh {0} to COLLADA, but {1} does not exist in the hierarchy!".format(submesh["name"], missing_bone))
                                input("Press Enter to abort.")
                                raise
                            except IndexError:
                                print("IndexError: Vertex attempted to use group {1} while adding submesh {0} to COLLADA, but group {1} does not exist in the vgmap!".format(submesh["name"], blendindices[i][j]))
                                input("Press Enter to abort.")
                                raise
                new_weights.append(new_weight)
                new_indices.append(new_index)
            #Uncomment the next 3 lines to force local bones instead of global bones
            #new_weights = blendweights
            #new_indices = blendindices
            #blendjoints = submesh['vgmap']
            controller = ET.SubElement(library_controllers, 'controller')
            controller.set('id', submesh['name'] + '-skin')
            controller.set('name', 'skinCluster_' + submesh['name']) #Maya does skinCluster1, skinCluster2... dunno if this matters
            skin = ET.SubElement(controller, 'skin')
            skin.set('source', '#' + submesh['name'])
            bind_shape_matrix = ET.SubElement(skin, 'bind_shape_matrix')
            bind_shape_matrix.text = '1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1'
            vgmap_source = ET.SubElement(skin, 'source')
            vgmap_source.set('id', submesh['name'] + '-skin-joints')
            vgmap_name_array = ET.SubElement(vgmap_source, 'Name_array')
            vgmap_name_array.set('id', submesh['name'] + '-skin-joints-array')
            vgmap_name_array.set('count', str(len(blendjoints)))
            vgmap_name_array.text = " ".join(blendjoints.keys())
            for bone in blendjoints.keys():
                try: # I'm not sure this error can be reached, since invalid bones should have been caught earlier.
                    bone_node = [x for x in collada.iter() if 'sid' in x.attrib and x.attrib['sid'] == bone][0]
                except IndexError:
                    print("IndexError: Attempted to map {1} to skeleton while adding submesh {0} to COLLADA, but {1} does not exist in the heirachy!".format(submesh["name"], bone))
                    input("Press Enter to abort.")
                    raise
                bone_node.set('type', 'JOINT')
            technique_common = ET.SubElement(vgmap_source, 'technique_common')
            accessor = ET.SubElement(technique_common, 'accessor')
            accessor.set('source', '#' + submesh['name'] + '-skin-joints-array')
            accessor.set('count', str(len(blendjoints)))
            accessor.set('stride', '1')
            param = ET.SubElement(accessor, 'param')
            param.set('name', 'JOINT')
            param.set('type', 'Name')
            inv_bind_mtx_source = ET.SubElement(skin, 'source')
            inv_bind_mtx_source.set('id', submesh['name'] + '-skin-bind_poses')
            inv_bind_mtx_array = ET.SubElement(inv_bind_mtx_source, 'float_array')
            inv_bind_mtx_array.set('id', submesh['name'] + '-skin-bind_poses-array')
            inv_bind_mtx_array.set('count', str(len(blendjoints) * 16))
            inv_bind_mtx_array.text = " ".join(["{0}".format(x) for y in\
                [numpy.array([skeleton[bone_dict[x]][meshname+'_imtx'][0:4], skeleton[bone_dict[x]][meshname+'_imtx'][4:8],\
                skeleton[bone_dict[x]][meshname+'_imtx'][8:12], skeleton[bone_dict[x]][meshname+'_imtx'][12:16]]).transpose().flatten('C')\
                if meshname+'_imtx' in skeleton[bone_dict[x]].keys() else skeleton[bone_dict[x]]['inv_matrix'].flatten('C')\
                for x in blendjoints.keys()] for x in y])
            technique_common = ET.SubElement(inv_bind_mtx_source, 'technique_common')
            accessor = ET.SubElement(technique_common, 'accessor')
            accessor.set('source', '#' + submesh['name'] + '-skin-bind_poses-array')
            accessor.set('count', str(len(blendjoints)))
            accessor.set('stride', '16')
            param = ET.SubElement(accessor, 'param')
            param.set('name', 'TRANSFORM')
            param.set('type', 'float4x4')
            blendweights_source = ET.SubElement(skin, 'source')
            blendweights_source.set("id", submesh['name'] + '-skin-weights')
            blendweights_source.set("name", 'skin-weights')
            float_array = ET.SubElement(blendweights_source, 'float_array')
            float_array.set("id", submesh['name'] + '-skin-weights-array')
            float_array.set("count", str(len([x for y in new_weights for x in y])))
            float_array.text = " ".join(["{0}".format(x) for y in new_weights for x in y])
            technique_common = ET.SubElement(blendweights_source, 'technique_common')
            accessor = ET.SubElement(technique_common, 'accessor')
            accessor.set('source', '#' + submesh['name'] + '-skin-weights-array')
            accessor.set('count', str(len([x for y in new_weights for x in y])))
            accessor.set('stride', '1')
            param = ET.SubElement(accessor, 'param')
            param.set('name', 'WEIGHT')
            param.set('type', 'float')
            joints = ET.SubElement(skin, 'joints')
            vgmap_input = ET.SubElement(joints, 'input')
            vgmap_input.set('semantic', 'JOINT')
            vgmap_input.set('source', '#' + submesh['name'] + '-skin-joints')
            inv_bind_mtx_input = ET.SubElement(joints, 'input')
            inv_bind_mtx_input.set('semantic', 'INV_BIND_MATRIX')
            inv_bind_mtx_input.set('source', '#' + submesh['name'] + '-skin-bind_poses')
            # Create an empty vertex weight group, will be filled as we read in the vertex buffers
            vertex_weights = ET.SubElement(skin, 'vertex_weights')
            vertex_weights.set("count", str(len(new_indices)))
            joint_input = ET.SubElement(vertex_weights, 'input')
            joint_input.set('semantic', 'JOINT')
            joint_input.set('source', '#' + submesh['name'] + '-skin-joints')
            joint_input.set('offset', '0')
            weight_input = ET.SubElement(vertex_weights, 'input')
            weight_input.set('semantic', 'WEIGHT')
            weight_input.set('source', '#' + submesh['name'] + '-skin-weights')
            weight_input.set('offset', '1')
            vcount = ET.SubElement(vertex_weights, 'vcount')
            vcount.text = " ".join([str(len(x)) for x in new_indices])
            v = ET.SubElement(vertex_weights, 'v')
            blend_indices = [x for y in new_indices for x in y]
            v.text = " ".join([str(x) for y in [[blend_indices[i],i] for i in range(len(blend_indices))] for x in y])
        vertices = ET.SubElement(mesh, 'vertices')
        vertices.set('id', submesh['name'] + '-vertices')
        vertices_input = ET.SubElement(vertices, 'input')
        vertices_input.set('semantic', 'POSITION')
        vertices_input.set('source', '#' + submesh['name'] + '-positions')
        triangles = ET.SubElement(mesh, 'triangles')
        triangles.set('material', submesh['name'] + 'SG')
        triangles.set('count', str(len(submesh['ib'])))
        input_count = 0
        for vb in submesh["vb"]:
            if vb['SemanticName'] in ['POSITION', 'NORMAL', 'TEXCOORD', 'TANGENT', 'BINORMAL', 'COLOR']:
                triangle_input = ET.SubElement(triangles, 'input')
                if vb['SemanticName'] == 'POSITION':
                    triangle_input.set('semantic', 'VERTEX')
                    triangle_input.set('source', '#' + submesh['name'] + '-vertices')
                elif vb['SemanticName'] == 'NORMAL':
                    triangle_input.set('semantic', 'NORMAL')
                    triangle_input.set('source', '#' + submesh['name'] + '-normals')
                elif vb['SemanticName'] == 'TEXCOORD':
                    triangle_input.set('semantic', 'TEXCOORD')
                    triangle_input.set('source', '#' + submesh['name'] + '-UV' + vb['SemanticIndex'])
                elif vb['SemanticName'] == 'TANGENT':
                    triangle_input.set('semantic', 'TEXTANGENT')
                    triangle_input.set('source', '#' + submesh['name'] + '-UV' + vb['SemanticIndex'] + '-tangents')
                elif vb['SemanticName'] == 'BINORMAL':
                    triangle_input.set('semantic', 'TEXBINORMAL')
                    triangle_input.set('source', '#' + submesh['name'] + '-UV' + vb['SemanticIndex'] + '-binormals')
                elif vb['SemanticName'] == 'COLOR':
                    triangle_input.set('semantic', 'COLOR')
                    triangle_input.set('source', '#' + submesh['name'] + '-colors' + vb['SemanticIndex'])
                triangle_input.set('offset', str(input_count))
                input_count += 1
                if vb['SemanticName'] in ['TEXCOORD', 'TANGENT', 'BINORMAL', 'COLOR']:
                    triangle_input.set('set', vb['SemanticIndex'])
        p = ET.SubElement(triangles, 'p')
        p.text = " ".join([str(x) for y in [[x]*input_count for x in [x for y in submesh['ib'] for x in y]] for x in y])
        extra = ET.SubElement(geometry, 'extra')
        technique = ET.SubElement(extra, 'technique')
        technique.set('profile', 'MAYA')
        double_sided = ET.SubElement(technique, 'double_sided')
        double_sided.text = '1'
        # Create geometry node
        parent_node = [x for x in collada.iter() if 'sid' in x.attrib and x.attrib['sid'] == meshname]
        if ('BLENDWEIGHT' in semantics_list or 'BLENDWEIGHTS' in semantics_list) and 'BLENDINDICES' in semantics_list:
            if len(parent_node) > 0:
                mesh_node = parent_node[0]
            else:
                mesh_node = add_empty_node (meshname+'_node', collada.find('library_visual_scenes')[0])
            instance_geom_controller = ET.SubElement(mesh_node, 'instance_controller')
            instance_geom_controller.set('url', '#' + submesh["name"] + '-skin')
            controller_skeleton = ET.SubElement(instance_geom_controller, 'skeleton')
            controller_skeleton.text = '#' + skeleton_name # Should always be 'up_point' or its equivalent!
        else:
            if meshname[-3] == '_' and meshname[-2:].isdigit() and len([x for x in collada.iter() if 'sid' in x.attrib and x.attrib['sid'] == meshname[:-3]]) > 0:
                mesh_node = add_empty_node (meshname+'_node', [x for x in collada.iter() if 'sid' in x.attrib and x.attrib['sid'] == meshname[:-3]][0])
            else:
                mesh_node = add_empty_node (meshname+'_node', collada.find('library_visual_scenes')[0])
            instance_geom_controller = ET.SubElement(mesh_node, 'instance_geometry')
            instance_geom_controller.set('url', '#' + submesh["name"])
        bind_material = ET.SubElement(instance_geom_controller, 'bind_material')
        technique_common = ET.SubElement(bind_material, 'technique_common')
        instance_material = ET.SubElement(technique_common, 'instance_material')
        instance_material.set('symbol', submesh['name'] + 'SG')
        instance_material.set('target', '#' + submesh['material']['material'])
        try:
            material = [v for (k,v) in materials.items() if k == submesh['material']['material']][0]
        except IndexError:
            print("IndexError: Vertex attempted to use material {1} while adding submesh {0} to COLLADA, but material {1} does not exist in the metadata!".format(submesh["name"], submesh['material']['material']))
            input("Press Enter to abort.")
            raise
        for parameter in material['shaderTextures']:
            # Texture parameters - I think these are constant from texture to texture and model to model, variations are in the effects?
            texture_name = material['shaderTextures'][parameter].replace('.DDS','.dds').split('/')[-1].split('.dds')[0]
            bind = ET.SubElement(instance_material, 'bind')
            bind.set("semantic", parameter)
            bind.set("target", texture_name + '_Image-lib/outColor')
            extra = ET.SubElement(bind, 'extra')
            technique = ET.SubElement(extra, 'technique')
            technique.set('profile', 'PSSG')
            param = ET.SubElement(technique, 'param')
            param.set("name", parameter)
        if 'uvmap' in submesh:
            for i in range(len(submesh["uvmap"])):
                bind_vertex_input = ET.SubElement(instance_material, 'bind_vertex_input')
                bind_vertex_input.set('semantic', "TEX{0}".format(submesh["uvmap"][i]['m_index']))
                bind_vertex_input.set('input_semantic', "TEXCOORD")
                bind_vertex_input.set('input_set', "{0}".format(submesh["uvmap"][i]['m_inputSet']))
        extra = ET.SubElement(instance_geom_controller, 'extra')
        technique = ET.SubElement(extra, 'technique')
        technique.set('profile', 'PHYRE')
        object_render_properties = ET.SubElement(technique, 'object_render_properties')
        object_render_properties.set('castsShadows', '1')
        object_render_properties.set('receiveShadows', '1')
        object_render_properties.set('visibleInReflections', '1')
        object_render_properties.set('visibleInRefractions', '1')
        object_render_properties.set('motionBlurEnabled', '1')
    return(collada)

def add_physics (collada, physics_metadata):
    library_geometries = collada.find('library_geometries')
    library_physics_scenes = ET.SubElement(collada, 'library_physics_scenes')
    physics_scene = ET.SubElement(library_physics_scenes, 'physics_scene')
    physics_scene.set("id","MayaNativePhysicsScene")
    library_physics_scenes_ps_tc = ET.SubElement(physics_scene, 'technique_common')
    library_physics_scenes_ps_tc_gravity = ET.SubElement(library_physics_scenes_ps_tc, 'gravity')
    library_physics_scenes_ps_tc_gravity.text = "0 -980 0"
    library_physics_scenes_ps_tc_time_step = ET.SubElement(library_physics_scenes_ps_tc, 'time_step')
    library_physics_scenes_ps_tc_time_step.text = "0.083"
    scene = collada.find('scene')
    instance_physics_scene = ET.SubElement(scene, 'instance_physics_scene')
    instance_physics_scene.set('url', '#MayaNativePhysicsScene')
    library_physics_materials = ET.SubElement(collada, 'library_physics_materials')
    library_physics_models = ET.SubElement(collada, 'library_physics_models')
    # I'm a little confused here, it seems that there can only be one physics model
    for model in physics_metadata:
        physics_model_element = ET.SubElement(library_physics_models, 'physics_model')
        physics_model_element.set("id", model)
        instance_physics_model = ET.SubElement(physics_scene, 'instance_physics_model')
        instance_physics_model.set('url', '#' + model)
        for body_name in physics_metadata[model]['rigid_bodies']:
            body = physics_metadata[model]['rigid_bodies'][body_name]
            physics_rigid_body = ET.SubElement(physics_model_element, 'rigid_body')
            physics_rigid_body.set("name", body_name)
            physics_rigid_body.set("sid", body_name)
            # Parameters
            technique_common = ET.SubElement(physics_rigid_body, 'technique_common')
            dynamic = ET.SubElement(technique_common, 'dynamic')
            dynamic.set("sid", 'dynamic')
            dynamic.text = "0"
            mass = ET.SubElement(technique_common, 'mass')
            mass.text = "{0}".format(body['parameters']['m_mass'])
            mass_frame = ET.SubElement(technique_common, 'mass_frame')
            mfmtx = body['parameters']['m_massFrameTransform']
            mass_frame_matrix = numpy.array([[mfmtx[3],mfmtx[7],mfmtx[11],0], mfmtx[0:3]+[0], mfmtx[4:7]+[0], mfmtx[8:11]+[1]])
            translate = ET.SubElement(mass_frame, 'translate')
            translate.text = " ".join([str(x) for x in mass_frame_matrix[3][0:3]])
            rotate = ET.SubElement(mass_frame, 'rotate')
            rotate_q = Quaternion(matrix=mass_frame_matrix.transpose())
            rotate.text = " ".join([str(x) for x in list(rotate_q)])
            # Material
            instance_physics_material = ET.SubElement(technique_common, 'instance_physics_material')
            instance_physics_material.set('url', "#PPhysicsMaterial_{0}".format(body_name))
            physics_material_element = ET.SubElement(library_physics_materials, 'physics_material')
            physics_material_element.set("id", "PPhysicsMaterial_{0}".format(body_name))
            physics_material_element.set("name", "PPhysicsMaterial_{0}".format(body_name))
            material_technique_common = ET.SubElement(physics_material_element, 'technique_common')
            dynamic_friction = ET.SubElement(material_technique_common, 'dynamic_friction')
            dynamic_friction.text = "{0}".format(body['material']['m_dynamicFriction'])
            static_friction = ET.SubElement(material_technique_common, 'static_friction')
            static_friction.text = "{0}".format(body['material']['m_staticFriction'])
            restitution = ET.SubElement(material_technique_common, 'restitution')
            restitution.text = "{0}".format(body['material']['m_restitution'])
            # Shape
            for shape_name in body['shapes']:
                rbshape = body['shapes'][shape_name]
                shape = ET.SubElement(technique_common, 'shape')
                hollow = ET.SubElement(shape, 'hollow')
                hollow.text = str(rbshape['m_hollow']).lower()
                mass = ET.SubElement(shape, 'mass')
                mass.text = "{0}".format(rbshape['m_mass'])
                density = ET.SubElement(shape, 'density')
                density.text = "{0}".format(rbshape['m_density'])
                # Strange that the geometry is inside the shape in collada, but inside the rigid body in phyre?
                geometries = [x.attrib['id'] for x in library_geometries.findall('geometry')\
                    if body['targetNode'] in x.attrib['id']]
                for l in range(len(geometries)):
                    instance_geometry = ET.SubElement(shape, 'instance_geometry')
                    instance_geometry.set('url', "#{0}".format(geometries[l]))
            # More parameters
            technique = ET.SubElement(physics_rigid_body, 'technique')
            technique.set("profile", 'MAYA')
            damping = ET.SubElement(technique, 'damping')
            damping.text = "{0}".format(body['parameters']['m_linearDamping']) # Or should this be m_angularDamping?
            instance_rigid_body = ET.SubElement(instance_physics_model, 'instance_rigid_body')
            instance_rigid_body.set("target", "#"+body['targetNode'])
            instance_rigid_body.set("body", body_name)
            technique_common = ET.SubElement(instance_rigid_body, 'technique_common')
            angular_velocity = ET.SubElement(technique_common, 'angular_velocity')
            angular_velocity.text = "{0}".format(" ".join([str(x) for x in body['parameters']['m_initialAngularVelocity']]))
            velocity = ET.SubElement(technique_common, 'velocity')
            velocity.text = "{0}".format(" ".join([str(x) for x in body['parameters']['m_initialLinearVelocity']]))
            dynamic = ET.SubElement(technique_common, 'dynamic')
            dynamic.text = "0"
            mass = ET.SubElement(technique_common, 'mass')
            mass.text = "{0}".format(body['parameters']['m_mass'])
            mass_frame = ET.SubElement(technique_common, 'mass_frame')
            translate = ET.SubElement(mass_frame, 'translate')
            translate.text = " ".join([str(x) for x in mass_frame_matrix[3][0:3]])
            rotate = ET.SubElement(mass_frame, 'rotate')
            rotate_q = Quaternion(matrix=mass_frame_matrix.transpose())
            rotate.text = " ".join([str(x) for x in list(rotate_q)])
            technique = ET.SubElement(instance_rigid_body, 'technique')
            technique.set("profile", 'MAYA')
            damping = ET.SubElement(technique, 'damping')
            damping.text = "{0}".format(body['parameters']['m_linearDamping']) # Or should this be m_angularDamping?
    return(collada)

# We can maintain ability to extract multiple indices, although phyreEngine only has single animations so i=0 always
def extract_animation (gltf, i = 0, start_at_time_zero = False):
    ani_bones = sorted(list(set([x.target.node for x in gltf.animations[i].channels if x.target.node is not None])))
    if len(ani_bones) < 1:
        return({}, [0,0])
    ani_starttime = min([x for y in [x for y in gltf.animations[i].samplers for x in read_gltf_stream(gltf, y.input)] for x in y])
    ani_endtime = max([x for y in [x for y in gltf.animations[i].samplers for x in read_gltf_stream(gltf, y.input)] for x in y])
    if start_at_time_zero == False:
        ani_timeshift = 0
    else:
        ani_timeshift = ani_starttime
    ani_struct = {}
    for j in ani_bones:
        samplers = {y.sampler:y.target.path for y in gltf.animations[i].channels if y.target.node == j}
        timestamps = sorted(set([x for y in [x for y in \
            [read_gltf_stream(gltf, gltf.animations[i].samplers[x].input) for x in samplers.keys()] for x in y] for x in y]))
        transformations = {}
        # Get base pose information
        if gltf.nodes[j].matrix is not None:
            base_s = [numpy.linalg.norm(gltf.nodes[j].matrix[0:3]), numpy.linalg.norm(gltf.nodes[j].matrix[4:7]),\
                numpy.linalg.norm(gltf.nodes[j].matrix[8:11])]
            base_t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],gltf.nodes[j].matrix[12:15]+[1]]).transpose()
            base_r_mtx = numpy.array([(gltf.nodes[j].matrix[0:3]/base_s[0]).tolist()+[0],\
                (gltf.nodes[j].matrix[4:7]/base_s[1]).tolist()+[0],\
                (gltf.nodes[j].matrix[8:11]/base_s[2]).tolist()+[0],[0,0,0,1]]).transpose()
            base_s_mtx = numpy.array([[base_s[0],0,0,0],[0,base_s[1],0,0],[0,0,base_s[2],0],[0,0,0,1]])
        else:
            if gltf.nodes[j].translation is not None:
                base_t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],gltf.nodes[j].translation+[1]]).transpose()
            else:
                base_t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
            if gltf.nodes[j].rotation is not None:
                base_r_mtx = Quaternion(gltf.nodes[j].rotation[3], gltf.nodes[j].rotation[0],\
                    gltf.nodes[j].rotation[1], gltf.nodes[j].rotation[2]).transformation_matrix
            else:
                base_r_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
            if gltf.nodes[j].scale is not None:
                base_s_mtx = numpy.array([[gltf.nodes[j].scale[0],0,0,0],\
                    [0,gltf.nodes[j].scale[1],0,0],[0,0,gltf.nodes[j].scale[2],0],[0,0,0,1]])
            else:
                base_s_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        # Process keyframes
        for k in range(len(timestamps)):
            t = base_t_mtx
            r = base_r_mtx
            s = base_s_mtx
            for sampler in samplers:
                keyed_times = [x for y in read_gltf_stream(gltf, gltf.animations[i].samplers[sampler].input) for x in y]
                outputs = read_gltf_stream(gltf, gltf.animations[i].samplers[sampler].output)
                if timestamps[k] in keyed_times:
                    output = outputs[keyed_times.index(timestamps[k])]
                    if samplers[sampler] == 'translation':
                        t = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],output+[1]]).transpose()
                    elif samplers[sampler] == 'rotation':
                        r = Quaternion(w=output[3], x=output[0], y=output[1], z=output[2]).transformation_matrix
                    elif samplers[sampler] == 'scale':
                        s = numpy.array([[output[0],0,0,0],[0,output[1],0,0],[0,0,output[2],0],[0,0,0,1]])
            transformations[timestamps[k] - ani_timeshift] = " ".join(["{0}".format(x) for x in numpy.dot(numpy.dot(t, r), s).flatten('C')])
        # The most recent sampler is used for interpolation.  We can only use one anyway, since all the transformations are combined.
        ani_struct[gltf.nodes[j].name] = {'interpolation': gltf.animations[i].samplers[sampler].interpolation, 'transformations': transformations}
    return(ani_struct, [ani_starttime-ani_timeshift, ani_endtime-ani_timeshift])

#phyreEngine only has single animations so i=0 always
def add_animations (collada, gltf, ani_struct):
    library_animations = ET.SubElement(collada, 'library_animations')
    for bone in ani_struct:
        animation = ET.SubElement(library_animations, 'animation')
        animation.set('id', "{0}.matrix".format(bone))
        input_source = ET.SubElement(animation, 'source')
        input_source.set('id', "{0}.matrix_{0}_transform-input".format(bone))
        float_array = ET.SubElement(input_source, 'float_array')
        float_array.set('id', "{0}.matrix_{0}_transform-input-array".format(bone))
        float_array.set('count', str(len(ani_struct[bone]['transformations'])))
        float_array.text = " ".join([str(x) for x in ani_struct[bone]['transformations'].keys()])
        technique_common = ET.SubElement(input_source, 'technique_common')
        accessor = ET.SubElement(technique_common, 'accessor')
        accessor.set('source', "#{0}.matrix_{0}_transform-input-array".format(bone))
        accessor.set('count', str(len(ani_struct[bone]['transformations'])))
        accessor.set('stride', '1')
        param = ET.SubElement(accessor, 'param')
        param.set('name','TIME')
        param.set('type','float')
        technique = ET.SubElement(input_source, 'technique')
        technique.set('profile','MAYA')
        pre_infinity = ET.SubElement(technique, 'pre_infinity')
        pre_infinity.text = 'CONSTANT'
        post_infinity = ET.SubElement(technique, 'post_infinity')
        post_infinity.text = 'CONSTANT'
        output_source = ET.SubElement(animation, 'source')
        output_source.set('id', "{0}.matrix_{0}_transform-output".format(bone))
        float_array = ET.SubElement(output_source, 'float_array')
        float_array.set('id', "{0}.matrix_{0}_transform-output-array".format(bone))
        float_array.set('count', str(len(ani_struct[bone]['transformations'])*16))
        float_array.text = " ".join([str(x) for x in ani_struct[bone]['transformations'].values()])
        technique_common = ET.SubElement(output_source, 'technique_common')
        accessor = ET.SubElement(technique_common, 'accessor')
        accessor.set('source', "#{0}.matrix_{0}_transform-output-array".format(bone))
        accessor.set('count', str(len(ani_struct[bone]['transformations'])))
        accessor.set('stride', '16')
        param = ET.SubElement(accessor, 'param')
        param.set('name','TRANSFORM')
        param.set('type','float4x4')
        interpolation_source = ET.SubElement(animation, 'source')
        interpolation_source.set('id', "{0}.matrix_{0}_transform-interpolations".format(bone))
        name_array = ET.SubElement(interpolation_source, 'Name_array')
        name_array.set('id', "{0}.matrix_{0}_transform-interpolations-array".format(bone))
        name_array.set('count', str(len(ani_struct[bone]['transformations'])))
        name_array.text = " ".join([ani_struct[bone]['interpolation'] for x in ani_struct[bone]['transformations'].keys()])
        technique_common = ET.SubElement(interpolation_source, 'technique_common')
        accessor = ET.SubElement(technique_common, 'accessor')
        accessor.set('source', "#{0}.matrix_{0}_transform-interpolations-array".format(bone))
        accessor.set('count', str(len(ani_struct[bone]['transformations'])))
        accessor.set('stride', '1')
        param = ET.SubElement(accessor, 'param')
        param.set('name','INTERPOLATION')
        param.set('type','Name')
        sampler = ET.SubElement(animation, 'sampler')
        sampler.set('id', "{0}.matrix_{0}_transform-sampler".format(bone))
        sampler_input = ET.SubElement(sampler, 'input')
        sampler_input.set('semantic','INPUT')
        sampler_input.set('source', "#{0}.matrix_{0}_transform-input".format(bone))
        sampler_input = ET.SubElement(sampler, 'input')
        sampler_input.set('semantic','OUTPUT')
        sampler_input.set('source', "#{0}.matrix_{0}_transform-output".format(bone))
        sampler_input = ET.SubElement(sampler, 'input')
        sampler_input.set('semantic','INTERPOLATION')
        sampler_input.set('source', "#{0}.matrix_{0}_transform-interpolations".format(bone))
        channel = ET.SubElement(animation, 'channel')
        channel.set('source', "#{0}.matrix_{0}_transform-sampler".format(bone))
        channel.set('target', "{0}/transform".format(bone))
    return(collada)

def write_shader (materials_list, mode = 'CS3'):
    if not os.path.exists("shaders"):
        os.mkdir("shaders")
    filelists = []
    for i in range(len(materials_list)):
        filelists.append(list(set([materials_list[i][x]['shader'].split('#')[0] for x in materials_list[i]])))
    filenames = list(set([x for y in filelists for x in y]))
    for filename in filenames:
        shaderfx = '/*This dummy shader is used to add the correct shader parameters to the .dae.phyre*/\r\n\r\n'
        added_shaders = []
        for i in range(len(materials_list)):
            for material in materials_list[i]:
                shader_name_split = materials_list[i][material]['shader'].split('#')
                shader_switch = 'SHADER_{0}'.format(shader_name_split[-1] if len(shader_name_split) > 1 else '')
                if shader_switch not in added_shaders and materials_list[i][material]['shader'].split('#')[0] == filename:
                    added_shaders.append(shader_switch)
                    # Switchless shaders do not need the #ifdef
                    #if len(materials_list[i][material]['shader'].split('#')) > 1:
                    if 1:
                        shaderfx += '#ifdef {0}\r\n'.format(shader_switch)
                    for parameter in materials_list[i][material]['shaderParameters']:
                        if len(materials_list[i][material]['shaderParameters'][parameter]) == 1:
                            valuetype = 'half'
                            value = "{0:.3f}".format(materials_list[i][material]['shaderParameters'][parameter][0])
                        else:
                            valuetype = 'half{0}'.format(len(materials_list[i][material]['shaderParameters'][parameter]))
                            value = "float{0}({1})".format(len(materials_list[i][material]['shaderParameters'][parameter]),\
                                ", ".join(["{0:.3f}".format(x) for x in materials_list[i][material]['shaderParameters'][parameter]]))
                        shaderfx += '{0} {1} : {1} = {2};\r\n'.format(valuetype, parameter, value)
                    captured_samplers = []
                    if mode == 'CS2':
                        for parameter in materials_list[i][material]['shaderTextures']:
                            sampler_name = parameter + 'S' # CS2
                            if 'non2Dtextures' in materials_list[i][material].keys() and parameter in materials_list[i][material]['non2Dtextures'].keys() \
                                and materials_list[i][material]['non2Dtextures'][parameter] == 'PTextureCubeMap':
                                shaderfx += 'TextureCube {0} : {0};\r\n'.format(parameter)
                            else:
                                shaderfx += 'Texture2D {0} : {0};\r\n'.format(parameter)
                            if sampler_name in materials_list[i][material]['shaderSamplerDefs']:
                                shaderfx += 'sampler {0}{{\r\n\tFilter = {1};\r\n}};\r\n'.format(sampler_name,{0: 21, 64: 148}[materials_list[i][material]['shaderSamplerDefs'][sampler_name]['m_flags'] & 0x40])
                                captured_samplers.append(sampler_name)
                    for parameter in [x for x in materials_list[i][material]['shaderSamplerDefs'] if not x in captured_samplers]:
                        shaderfx += 'sampler {0}{{\r\n\tFilter = {1};\r\n}};\r\n'.format(parameter,{0: 21, 64: 148}[materials_list[i][material]['shaderSamplerDefs'][parameter]['m_flags'] & 0x40])
                    if not mode == 'CS2':
                        for parameter in materials_list[i][material]['shaderTextures']:
                            if 'non2Dtextures' in materials_list[i][material].keys() and parameter in materials_list[i][material]['non2Dtextures'].keys() \
                                and materials_list[i][material]['non2Dtextures'][parameter] == 'PTextureCubeMap':
                                shaderfx += 'TextureCube {0} : {0};\r\n'.format(parameter)
                            else:
                                shaderfx += 'Texture2D {0} : {0};\r\n'.format(parameter)
                    # Switchless shaders do not need the #endif
                    #if len(materials_list[i][material]['shader'].split('#')) > 1:
                    if 1:
                        shaderfx += '#endif //! {0}\r\n'.format(shader_switch)
                    shaderfx += '\r\n\r\n'
        shaderfx += '#ifdef SUBDIV\r\n#undef SKINNING_ENABLED\r\n#undef INSTANCING_ENABLED\r\n#endif // SUBDIV\r\n\r\n'
        shaderfx += '#ifdef SUBDIV_SCALAR_DISPLACEMENT\r\nTexture2D<half> DisplacementScalar;\r\n#endif // SUBDIV_SCALAR_DISPLACEMENT\r\n\r\n'
        shaderfx += '#ifdef SUBDIV_VECTOR_DISPLACEMENT\r\nTexture2D<half4> DisplacementVector;\r\n#define USE_TANGENTS\r\n#endif // SUBDIV_VECTOR_DISPLACEMENT\r\n\r\n'
        shaderfx += '#if defined(SUBDIV_SCALAR_DISPLACEMENT) || defined(SUBDIV_VECTOR_DISPLACEMENT)\r\nhalf DisplacementScale = 1.0f;\r\n'
        shaderfx += '#define USE_UVS\r\n#endif // defined(SUBDIV_SCALAR_DISPLACEMENT) || defined(SUBDIV_VECTOR_DISPLACEMENT)\r\n\r\n'
        shaderfx += 'technique11 ForwardRender\r\n<\r\n	string PhyreRenderPass = "Opaque";\r\n>\r\n{\r\n	pass pass0\r\n	{\r\n	}\r\n}\r\n'
        with open(filename, 'wb') as f:
            f.write(shaderfx.encode('utf-8'))
    return

def asset_info_from_xml(filename):
    assetfile = ET.parse(filename)
    daes = {}
    textures = {}
    for i in range(len(assetfile.getroot())):
        asset_symbol = assetfile.getroot()[i].attrib['symbol']
        dae_files = [x.attrib['path'] for x in assetfile.getroot()[i] if x.attrib['type'] == 'p_collada']
        texture_files = [x.attrib['path'] for x in assetfile.getroot()[i] if x.attrib['type'] == 'p_texture']
        if len(dae_files) > 0:
            for j in range(len(dae_files)):
                daes[dae_files[j].split('/')[-1].split('.dae')[0]] =\
                    {'asset_symbol': asset_symbol, 'dae_path': os.path.dirname(dae_files[j].replace('data/D3D11/',''))}
        if len(texture_files) > 0:
            for j in range(len(texture_files)):
                textures[texture_files[j].split('/')[-1].split('.phyre')[0]] =\
                    {'asset_symbol': asset_symbol, 'dae_path': os.path.dirname(texture_files[j].replace('data/D3D11/',''))}
    return(daes, textures)

def write_asset_xml (metadata_list):
    try:
        xml_info, textures = asset_info_from_xml(metadata_list[0]['pkg_name']+'/asset_D3D11.xml')
    except FileNotFoundError:
        print("FileNotFoundError: Attempted to read {} but it is not present!".format(metadata_list[0]['pkg_name']+'/asset_D3D11.xml'))
        print("Autobuild configuration not possible.")
        input("Press Enter to abort.")
        raise
    if not os.path.exists(metadata_list[0]['pkg_name']):
        os.mkdir(metadata_list[0]['pkg_name'])
    filename = '{0}/asset_D3D11.xml'.format(metadata_list[0]['pkg_name'])
    already_appended = []
    asset_xml = '<?xml version="1.0" encoding="utf-8"?>\r\n<fassets>\r\n'
    for i in range(len(metadata_list)):
        if metadata_list[i]['name'] in xml_info:
            current_xml_asset = xml_info[metadata_list[i]['name']]['asset_symbol']
            current_dae_path = xml_info[metadata_list[i]['name']]['dae_path']
        else:
            current_xml_asset = metadata_list[i]['pkg_name']
            current_dae_path = xml_info[list(xml_info.keys())[0]]['dae_path'] # If asset does not exist, use first entry as it is likely the xml is a template
        images = []
        metadata_images = sorted(list(set([x for y in metadata_list[i]['materials'] for x in metadata_list[i]['materials'][y]['shaderTextures'].values()])))
        for j in range(len(metadata_images)):
            if metadata_images[j] not in already_appended:
                images.append('\t\t<cluster path="data/D3D11/{0}.phyre" type="p_texture" />\r\n'.format(metadata_images[j]))
                already_appended.append(metadata_images[j])
        images.sort()
        shaders = []
        for material in metadata_list[i]['materials']:
            for shader_type in ['shader','skinned_shader','vertex_color_shader','skinned_vertex_color_shader']:
                if shader_type in metadata_list[i]['materials'][material] and metadata_list[i]['materials'][material][shader_type] not in already_appended:
                    shader_name = metadata_list[i]['materials'][material][shader_type]
                    shaders.append('\t\t<cluster path="data/D3D11/{0}.phyre" type="p_fx" />\r\n'.format(shader_name))
                    already_appended.append(metadata_list[i]['materials'][material]['shader'])
        shaders.sort()
        asset_xml += '\t<asset symbol="{0}">\r\n'.format(current_xml_asset)
        asset_xml += '\t\t<cluster path="data/D3D11/{0}/{1}.dae.phyre" type="p_collada" />\r\n'.format(current_dae_path, metadata_list[i]['name'])
        asset_xml += ''.join(images) + ''.join(shaders)
        asset_xml += '\t</asset>\r\n'
    asset_xml += '</fassets>\r\n'
    with open(filename, 'wb') as f:
        f.write(asset_xml.encode('utf-8'))
    return

# ShellScriptBuilder is an abstraction to allow building shell
# scripts without having to think about operating system specifics.
class ShellScriptBuilder:

    def __init__(self):
        # assume we are on windows if /proc/self doesn't exist
        self.windows = not os.path.exists("/proc/self")
        self.buffer = '@ECHO OFF\r\nset "SCE_PHYRE=%cd%"\r\n' if self.windows else "set -eu\nexport SCE_PHYRE=$(pwd)\n"

    def copy_file(self, src, dst, overwrite = False):
        src = self.normalize_path(src)
        dst = self.normalize_path(dst)
        if self.windows:
            flags = "/Y " if overwrite else ""
            self.buffer += "copy {}{} {}\r\n".format(flags, src, dst)
        else:
            flags = "-f " if overwrite else ""
            self.buffer += "cp {}{} {}\n".format(flags, src, dst)
        return

    def run_exe(self, cmd_line):
        if self.windows:
            self.buffer += cmd_line + "\r\n"
            self.buffer += '''if %ERRORLEVEL% NEQ 0 (
    echo command failed: {}
    pause
    goto :EOF
)
'''.format(cmd_line)
        else:
            # wine is quite verbose. discard output.
            self.buffer += "wine " + cmd_line + " &> /dev/null\n"
        return

    def delete_file(self, file):
        file = self.normalize_path(file)
        if self.windows:
            self.buffer += "del {}\r\n".format(file)
        else:
            self.buffer += "rm {}\n".format(file)
        return

    def move_file(self, src, dst):
        src = self.normalize_path(src)
        dst = self.normalize_path(dst)
        if self.windows:
            self.buffer += "move {} {}\r\n".format(src, dst)
        else:
            self.buffer += "mv {} {}\n".format(src, dst)
        return

    def run_raw(self, cmd_line):
        if self.windows:
            self.buffer += "{}\r\n".format(cmd_line)
        else:
            self.buffer += "{}\n".format(cmd_line)
        return

    # accepts a windows or unix path and returns a platform specific path
    def normalize_path(self, path):
        path = path.replace('/',os.sep)
        path = path.replace('\\',os.sep)
        return path

    def write_script(self, path):
        path = self.normalize_path(path)
        ext = ".bat" if self.windows else ".sh"
        with open(path+ext, 'wb') as f:
            f.write(self.buffer.encode('utf-8'))
            if not self.windows:
                os.chmod('RunMe.sh', 0o755)
        return

def write_processing_batch_file (models, animation_metadata = {}, processor = 'CSIVAssetImportTool.exe'):
    compression_level = 0
    metadata_list = [read_struct_from_json(x) for x in models] # A little inefficient but safer
    # Model pkg_name overrides animation pkg_name
    if len(metadata_list) > 0:
        pkg_name = metadata_list[0]['pkg_name']
        compression_level = metadata_list[0]['compression'] if 'compression' in metadata_list[0] else 4
    elif 'pkg_name' in animation_metadata:
        pkg_name = animation_metadata['pkg_name']
        compression_level = animation_metadata['compression'] if 'compression' in animation_metadata else 4
    else:
        return False
    compflag = ''
    if compression_level == 1:
        compflag = '-lz '
    elif compression_level >= 4:
        compflag = '-l '
    xml_info, textures = asset_info_from_xml(pkg_name+'/asset_D3D11.xml')
    batch_file = ShellScriptBuilder()
    for i in range(len(metadata_list)):
        name = metadata_list[i]['name']
        dae_path = xml_info[name]['dae_path']
        path = batch_file.normalize_path('{0}/{1}.dae'.format(dae_path, name))
        processor_cmd = '{0} -fi="{1}" -platform="D3D11" -write=all'.format(processor, path)
        batch_file.run_exe(processor_cmd)
        path = batch_file.normalize_path('D3D11/{0}/{1}.dae.phyre'.format(dae_path, name))
        batch_file.run_exe('PhyreDummyShaderCreator.exe {0}'.format(path))
        batch_file.copy_file(path, '.')
        batch_file.run_raw('python replace_shader_references.py {0}'.format(models[i]))
        batch_file.delete_file('{0}.dae.phyre.bak'.format(name))
        path = '{0}.dae.phyre'.format(name)
        batch_file.copy_file(path, 'D3D11/{0}'.format(dae_path), overwrite = True)
        batch_file.move_file(path, pkg_name)
    if 'animations' in animation_metadata:
        for animation in animation_metadata['animations']:
            if animation in xml_info:
                dae_path = xml_info[animation]['dae_path']
            else:
                dae_path = 'chr/chr/{0}'.format(animation.split('_')[0])
            path = batch_file.normalize_path(dae_path + '/' + animation + ".dae")
            cmd = '{0} -fi="{1}" -platform="D3D11" -write=all'.format(processor, path)
            batch_file.run_exe(cmd)
            batch_file.copy_file('D3D11/{0}/{1}.dae.phyre'.format(dae_path, animation), pkg_name)
    image_folders = sorted(list(set([os.path.dirname(x).replace('/',os.sep) for y in [x['shaderTextures']\
        for y in metadata_list for x in y['materials'].values()] for x in y.values()])))
    if len(image_folders) > 0:
        for folder in image_folders:
            batch_file.copy_file('D3D11/{0}/*.*'.format(folder), metadata_list[0]['pkg_name'])
    batch_file.run_raw('python write_pkg.py {0}-o {1}'.format(compflag, pkg_name))
    if len(metadata_list) > 0:
        batch_file.delete_file('*.fx')
        batch_file.delete_file('*.cgfx')
    batch_file.write_script('RunMe')
    return True

def write_texture_processing_batch_file (asset_xml, xml_num = 0, processor = 'CSIVAssetImportTool.exe'):
    compflag = ''
    if os.path.exists('compression.json'):
        compression_level = read_struct_from_json('compression.json')['compression']
        if compression_level == 1:
            compflag = '-lz '
        elif compression_level >= 4:
            compflag = '-l '
    daes, textures = asset_info_from_xml(asset_xml)
    batch_file = ShellScriptBuilder()
    images = ["{0}/{1}".format(textures[x]['dae_path'],x).replace('/','\\') for x in textures]
    for i in range(len(images)):
        img = batch_file.normalize_path(images[i])
        cmd = '{0} -fi="{1}" -platform="D3D11" -write=all'.format(processor, img)
        batch_file.run_exe(cmd)
    image_folders = [x.replace('/','\\') for x in sorted(list(set([textures[x]['dae_path'] for x in textures])))]
    if len(image_folders) > 0:
        for folder in image_folders:
            batch_file.copy_file('D3D11/{}/*.*'.format(folder), os.path.dirname(asset_xml))
    batch_file.run_raw('python write_pkg.py {0}-o {1}\n'.format(compflag, os.path.dirname(asset_xml)))
    batch_file.write_script('RunMe{}'.format(xml_num if xml_num else ''))
    return

def write_collada (collada, full_dae_path):
    print("Writing COLLADA file...")
    with io.BytesIO() as f:
        f.write(ET.tostring(collada, encoding='utf-8', xml_declaration=True))
        f.seek(0)
        dom = xml.dom.minidom.parse(f)
        pretty_xml_as_string = dom.toprettyxml(indent='  ')
        if not os.path.exists(os.path.dirname(full_dae_path) + '/'):
            os.makedirs(os.path.dirname(full_dae_path)  +'/')
        with open(full_dae_path, 'w') as f2:
            f2.write(pretty_xml_as_string)
    return

def get_gltf_name (animation):
    if os.path.exists(animation+'.glb'):
        filename = animation+'.glb'
    elif os.path.exists(animation+'.gltf'):
        filename = animation+'.gltf'
    else:
        print("Animation {} not found, skipping...".format(animation))
        return False
    return(filename)

def get_gltf_heirarchy (animation):
    filename = get_gltf_name(animation)
    if not filename == False:
        with open(filename, 'rb') as f:
            if f.read(4) == b'glTF': #GLB format
                num_sections, file_length = struct.unpack("<II", f.read(8))
                for i in range(num_sections):
                    section_start = f.tell()
                    section_length, = struct.unpack("<I", f.read(4))
                    section_magic = f.read(4)
                    if section_magic == b'JSON':
                        heirarchy = json.loads(f.read(section_length))['nodes']
                    else:
                        f.seek(section_length, 1)
            else:
                f.seek(0)
                heirarchy = json.loads(f.read())['nodes']
            return(heirarchy)
    else:
        return False

def apply_gltf_pose (heirarchy, animation):
    filename = get_gltf_name(animation)
    if not filename == False:
        ani_gltf = GLTF2().load(filename)
    # Apply animation pose to model
    for i in range(len(heirarchy)):
        if heirarchy[i]['name'] in [x.name for x in ani_gltf.nodes]:
            ani_node = [j for j in range(len(ani_gltf.nodes)) if ani_gltf.nodes[j].name == heirarchy[i]['name']][0]
            for key in ['matrix', 'translation', 'rotation', 'scale']:
                if key in heirarchy[i]:
                    del(heirarchy[i][key])
                if getattr(ani_gltf.nodes[ani_node], key) is not None:
                    heirarchy[i][key] = getattr(ani_gltf.nodes[ani_node], key)
    return(heirarchy)

def add_animation_to_collada (collada, animation, animation_metadata):
    filename = get_gltf_name(animation)
    if not filename == False:
        gltf = GLTF2().load(filename)
        ani_struct, ani_times = extract_animation(gltf)
        if len(ani_struct) > 0:
            collada = add_animations(collada, gltf, ani_struct)
        return (collada, ani_struct, ani_times)
    else:
        return collada, {}, [0,0]

def build_collada (metadata_name, animation_metadata = {}):
    if os.path.exists(metadata_name):
        metadata = read_struct_from_json(metadata_name)
        print("Processing {0}...".format(metadata['pkg_name']))
        dae_path = 'chr/chr/{0}'.format(metadata['name'].split('_')[0]) # Default name, to be overwritten by value in asset_D3D11.xml
        if os.path.exists(metadata['pkg_name']+'/asset_D3D11.xml'):
            xml_info, textures = asset_info_from_xml(metadata['pkg_name']+'/asset_D3D11.xml')
            if metadata['name'] in xml_info:
                dae_path = xml_info[metadata['name']]['dae_path']
        relative_path = '/'.join(['..' for x in range(len(dae_path.split('/')))])
        physics_present = False
        if os.path.exists(metadata_name.replace('metadata','physics_data')):
            print("Physics data found.")
            physics_metadata = read_struct_from_json(metadata_name.replace('metadata','physics_data'))
            physics_present = True
        meshes_path = 'meshes' + metadata_name.split('.json')[0].split('metadata')[-1]
        submeshes = []
        meshes = [x.split(meshes_path+os.sep)[1].split('.fmt')[0] for x in glob.glob(meshes_path+'/*.fmt')]
        for filename in meshes:
            try:
                print("Reading submesh {0}...".format(filename))
                submesh = {'name': filename}
                submesh['fmt'] = read_fmt(meshes_path+'/'+filename+'.fmt')
                submesh['ib'] = read_ib(meshes_path+'/'+filename+'.ib', submesh['fmt'])
                submesh['vb'] = read_vb(meshes_path+'/'+filename+'.vb', submesh['fmt'])
                if os.path.exists(meshes_path+'/'+filename+'.vgmap'):
                    submesh['vgmap'] = read_struct_from_json(meshes_path+'/'+filename+'.vgmap')
                if os.path.exists(meshes_path+'/'+filename+'.uvmap'):
                    submesh['uvmap'] = read_struct_from_json(meshes_path+'/'+filename+'.uvmap')
                submesh['material'] = read_struct_from_json(meshes_path+'/'+filename+'.material')
                submeshes.append(submesh)
            except FileNotFoundError:
                print("Submesh {0} not found, not complete, or corrupt, skipping...".format(filename))
        has_skeleton = False
        skeletal_bones = []
        for i in range(len(submeshes)):
            if 'vgmap' in submeshes[i].keys():
                has_skeleton = True
                skeletal_bones.extend(list(submeshes[i]['vgmap'].keys()))
        skeletal_bones = list(set(skeletal_bones))
        ani_times = [0,8.33] #Default values, unclear if needed or should be 0,0?
        collada = basic_collada()
        images_data = sorted(list(set([x for y in metadata['materials'] for x in metadata['materials'][y]['shaderTextures'].values()])))
        collada = add_images(collada, images_data, relative_path)
        print("Adding materials...")
        collada = add_materials(collada, metadata, relative_path, forward_render = physics_present)
        if 'animations' in animation_metadata and metadata['name'] in animation_metadata['animations']:
            print("Adding animations...")
            metadata['heirarchy'] = apply_gltf_pose(metadata['heirarchy'], metadata['name'])
            collada, ani_struct, ani_times = add_animation_to_collada(collada, metadata['name'], animation_metadata)
            skeletal_bones.extend(ani_struct.keys())
            skeletal_bones = list(set(skeletal_bones))
            if metadata['name'] in animation_metadata['animations'] and 'locators' in animation_metadata['animations'][metadata['name']]:
                metadata['locators'].extend(animation_metadata['animations'][metadata['name']]['locators'])
                metadata['locators'] = list(set(metadata['locators']))
        print("Adding skeleton...")
        unique_bones = set()
        duplicate_bones = [x['name'] for x in metadata['heirarchy'] if x['name'] in unique_bones or unique_bones.add(x['name'])]
        duplicate_bones_ex = [x for x in duplicate_bones if not x in ['VisualSceneNode']] # This is filtered out later
        if len(duplicate_bones_ex) > 0:
            print("Warning! Duplicate bones found: {}.\nThe model will compile but may appear distorted.".format(duplicate_bones_ex))
            input("Press Enter to continue.")
        skeleton = add_bone_info(metadata['heirarchy'], skeletal_bones = skeletal_bones)
        collada = add_skeleton(collada, metadata, skeletal_bones = skeletal_bones, ani_times = ani_times)
        print("Adding geometry...")
        collada = add_geometries_and_controllers(collada, submeshes, skeleton, metadata['materials'], has_skeleton = has_skeleton)
        if physics_present == True:
            print("Adding collision...")
            collada = add_physics(collada, physics_metadata)
        write_collada(collada, dae_path + '/' + metadata['name'] + ".dae")
    return

def build_animation_collada (animation, animation_metadata):
    print("Processing {0}...".format(animation))
    metadata = {'name': animation, 'pkg_name': animation_metadata['pkg_name'], 'locators':[]}
    metadata['heirarchy'] = get_gltf_heirarchy(animation)
    if animation in animation_metadata['animations'] and 'locators' in animation_metadata['animations'][animation]:
        metadata['locators'] = animation_metadata['animations'][animation]['locators']
    dae_path = 'chr/chr/{0}'.format(animation.split('_')[0]) # Default name, to be overwritten by value in asset_D3D11.xml
    if os.path.exists(animation_metadata['pkg_name']+'/asset_D3D11.xml'):
        xml_info, textures = asset_info_from_xml(animation_metadata['pkg_name']+'/asset_D3D11.xml')
        if animation in xml_info:
            dae_path = xml_info[animation]['dae_path']
    collada = basic_collada()
    print("Adding animations...")
    collada, ani_struct, ani_times = add_animation_to_collada(collada, animation, animation_metadata)
    if len(ani_struct) < 1:
        return False
    print("Adding skeleton...")
    skeleton = add_bone_info(metadata['heirarchy'], skeletal_bones = list(ani_struct.keys()))
    collada = add_skeleton(collada, metadata, skeletal_bones = list(ani_struct.keys()), ani_times = ani_times)
    write_collada(collada, dae_path + '/' + metadata['name'] + ".dae")
    return ani_times

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
        write_shader([x['materials'] for x in metadata_list])
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
        print("Writing RunMe.")
        write_processing_batch_file(models, animation_metadata)
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
            write_texture_processing_batch_file(asset_xmls[i],i)
