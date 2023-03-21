# ED8 COLLADA builder, needs output from my fork of uyjulian/ed8pkg2glb.
# Needs pyquaternion if heirarchy is inputted as TRS instead of matrix.
#
# GitHub eArmada8/ed8pkg2gltf

import os, glob, numpy, json, io, sys, xml.dom.minidom
import xml.etree.ElementTree as ET
from lib_fmtibvb import *

# Create the basic COLLADA XML document, with values that do not change from model to model (I think)
# TODO: Are units, gravity and time step constant?
def basic_collada (has_skeleton = True):
    collada = ET.Element('COLLADA')
    collada.set("xmlns", "http://www.collada.org/2005/11/COLLADASchema")
    collada.set("version", "1.4.1")
    asset = ET.SubElement(collada, 'asset')
    asset_unit = ET.SubElement(asset, 'unit')
    asset_unit.set("meter", "0.0099999997764825")
    asset_unit.set("name", "centimeter")
    asset_up_axis = ET.SubElement(asset, 'up_axis')
    asset_up_axis.text = "Y_UP"
    library_physics_scenes = ET.SubElement(collada, 'library_physics_scenes')
    library_physics_scenes_ps = ET.SubElement(library_physics_scenes, 'physics_scene')
    library_physics_scenes_ps.set("id","MayaNativePhysicsScene")
    library_physics_scenes_ps_tc = ET.SubElement(library_physics_scenes_ps, 'technique_common')
    library_physics_scenes_ps_tc_gravity = ET.SubElement(library_physics_scenes_ps_tc, 'gravity')
    library_physics_scenes_ps_tc_gravity.text = "0 -980 0"
    library_physics_scenes_ps_tc_time_step = ET.SubElement(library_physics_scenes_ps_tc, 'time_step')
    library_physics_scenes_ps_tc_time_step.text = "0.0829999968409538"
    library_images = ET.SubElement(collada, 'library_images')
    library_materials = ET.SubElement(collada, 'library_materials')
    library_effects = ET.SubElement(collada, 'library_effects')
    library_geometries = ET.SubElement(collada, 'library_geometries')
    if has_skeleton == True:
        library_controllers = ET.SubElement(collada, 'library_controllers')
    library_visual_scenes = ET.SubElement(collada, 'library_visual_scenes')
    scene = ET.SubElement(collada, 'scene')
    instance_physics_scene = ET.SubElement(scene, 'instance_physics_scene')
    instance_physics_scene.set('url', '#MayaNativePhysicsScene')
    return(collada)

# Add image URIs
def add_images (collada, images, relative_path = '../../..'):
    library_images = collada.find('library_images')
    for image in images:
        image_name = image.replace('.DDS','.dds').split('.dds')[0]
        image_element = ET.SubElement(library_images, 'image')
        image_element.set("id", os.path.basename(image_name))
        image_element.set("name", os.path.basename(image_name))
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
def add_materials (collada, metadata, relative_path = '../../..'):
    materials = metadata['materials']
    # Materials and effects can be done in parallel
    library_materials = collada.find('library_materials')
    library_effects = collada.find('library_effects')
    all_shader_switches = ['SHADER_'+v['shader'].split('#')[-1][0:4] for (k,v) in materials.items()]
    for material in materials:
        #Materials
        material_element = ET.SubElement(library_materials, 'material')
        material_element.set("id", material)
        material_element.set("name", material)
        instance_effect = ET.SubElement(material_element, 'instance_effect')
        instance_effect.set("url", "#{0}-fx".format(material))
        technique_hint = ET.SubElement(instance_effect, 'technique_hint')
        technique_hint.set("platform", "PC-DX")
        technique_hint.set("ref", "ForwardRender")
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
            values = ET.SubElement(setparam, 'float{0}'.format({1:'', 2:2, 3:3, 4:4, 5:5}[len(materials[material]['shaderParameters'][parameter])]))
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
            lod_min_distance.text = '-3402823466385289'
            lod_max_distance = ET.SubElement(samplerDX, 'lod_max_distance')
            lod_max_distance.text = '3402823466385289'
            border_color = ET.SubElement(samplerDX, 'border_color')
            border_color.text = '0 0 0 0' # In the example it's always this, and in the phyre file it's a single 0.  I dunno.
        # Texture parameters - only support for 2D currently
        for parameter in materials[material]['shaderTextures']:
            texture_name = materials[material]['shaderTextures'][parameter].replace('.DDS','.dds').split('/')[-1].split('.dds')[0]
            sampler_name = parameter + 'Sampler'
            texture_entry = [x for x in metadata['images'] if x['uri'] == materials[material]['shaderTextures'][parameter]][0]
            if 'm_targetAssetType' in texture_entry and texture_entry['m_targetAssetType'] == 'PTextureCubeMap':
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
            init_from.text = texture_name
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
        if 'shaderSwitches' in materials[material]:
            material_switches = ET.SubElement(technique, 'material_switches')
            current_shader_switch = 'SHADER_' + materials[material]['shader'].split('#')[-1][0:4]
            shader = ET.SubElement(material_switches, current_shader_switch)
            material_switch_list = ET.SubElement(technique, 'material_switch_list')
            # Switches are taken from the shader files themselves
            for material_switch in materials[material]['shaderSwitches']:
                material_switch_entry = ET.SubElement(material_switch_list, 'material_switch')
                material_switch_entry.set("name", material_switch)
                material_switch_entry.set("material_switch_value", materials[material]['shaderSwitches'][material_switch])
        #for material_switch in ['BLOOM_INTENSITY', 'SAMPLER_TOGGLE', 'VERTEX_COLOR_ENABLED', 'LIGHTING_ENABLED',\
                #'DIFFUSE_ENABLED', 'DIFFUSE2_ENABLED', 'DIFFUSE3_ENABLED', 'ALPHA_BLENDING_ENABLED', 'NORMAL_MAPPING_ENABLED',\
                #'WRAP_DIFFUSE_LIGHTING', 'SPECULAR_ENABLED', 'CASTS_SHADOWS', 'RECEIVE_SHADOWS', 'DOUBLE_SIDED', 'MOTION_BLUR_ENABLED',\
                #'GENERATE_LIGHTS', 'SHININESS', 'RENDER_AS_LOW_RES', 'LIGHTMAP_OCCLUSION', 'SUBDIV', 'SUBDIV_SCALAR_DISPLACEMENT',\
                #'SUBDIV_VECTOR_DISPLACEMENT', 'FOR_EFFECT', 'FOR_SHADOW', 'USE_OUTLINE', 'USE_OUTLINE_COLOR', 'ALPHA_TESTING_ENABLED',\
                #'ADDITIVE_BLENDING_ENABLED', 'SUBTRACT_BLENDING_ENABLED', 'MULTIPLICATIVE_BLENDING_ENABLED', 'TRANSPARENT_DELAY_ENABLED',\
                #'PORTRAIT_GLASS_FIX', 'FOG_ENABLED', 'NO_ALL_LIGHTING_ENABLED', 'NO_MAIN_LIGHT_SHADING_ENABLED',\
                #'FORCE_CHAR_LIGHT_DIRECTION_ENABLED', 'PER_MATERIAL_MAIN_LIGHT_CLAMP_ENABLED', 'SHADOW_COLOR_SHIFT_ENABLED',\
                #'CARTOON_SHADING_ENABLED', 'SPECULAR_COLOR_ENABLED', 'SPECULAR_MAPPING_ENABLED', 'RIM_LIGHTING_ENABLED',\
                #'RIM_TRANSPARENCY_ENABLED', 'NORMAL_MAPP_DXT5_NM_ENABLED', 'EMISSION_MAPPING_ENABLED', 'SPHERE_MAPPING_ENABLED',\
                #'SPHERE_RECEIVE_OFFSET_ENABLED', 'SPHERE_MAPPING_HAIRCUTICLE_ENABLED', 'CUBE_MAPPING_ENABLED', 'DUDV_MAPPING_ENABLED',\
                #'GLARE_ENABLED', 'MULTI_UV_ENANLED', 'MULTI_UV_PROJTEXCOORD', 'MULTI_UV_ADDITIVE_BLENDING_ENANLED', 'MULTI_UV_DUDV_ENANLED',\
                #'MULTI_UV_MULTIPLICATIVE_BLENDING_ENANLED', 'MULTI_UV_MULTIPLICATIVE_BLENDING_EX_ENANLED', 'MULTI_UV_FACE_ENANLED',\
                #'MULTI_UV_NORMAL_MAPPING_ENABLED', 'MULTI_UV_SPECULAR_MAPPING_ENABLED', 'MULTI_UV_GLARE_MAPPING_ENABLED',\
                #'MULTI_UV_NO_DIFFUSE_MAPPING_ENANLED', 'MULTI_UV2_ENANLED', 'MULTI_UV2_ADDITIVE_BLENDING_ENANLED',\
                #'MULTI_UV2_MULTIPLICATIVE_BLENDING_ENANLED', 'MULTI_UV2_MULTIPLICATIVE_BLENDING_EX_ENANLED',\
                #'MULTI_UV2_SPECULAR_MAPPING_ENABLED', 'GAME_MATERIAL_ID', 'GAME_MATERIAL_TEXCOORD', 'GLARE_INTENSITY']:
            #material_switch_entry = ET.SubElement(material_switch_list, 'material_switch')
            #material_switch_entry.set("name", material_switch)
            #material_switch_entry.set("material_switch_value", '0')
            for i in range(len(all_shader_switches)):
                material_switch_entry = ET.SubElement(material_switch_list, 'material_switch')
                material_switch_entry.set("name", all_shader_switches[i])
                if all_shader_switches[i] == current_shader_switch:
                    material_switch_entry.set("material_switch_value", "1")
                else:
                    material_switch_entry.set("material_switch_value", "0")
        forwardrendertechnique = ET.SubElement(profile_HLSL, 'technique')
        forwardrendertechnique.set('sid','ForwardRender')
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

def calc_abs_matrix(node, skeleton):
    skeleton[node]['abs_matrix'] = numpy.dot(skeleton[skeleton[node]['parent']]['abs_matrix'], skeleton[node]['rel_matrix'])
    skeleton[node]['inv_matrix'] = numpy.linalg.inv(skeleton[node]['abs_matrix'])
    if 'children' in skeleton[node].keys():
        for child in skeleton[node]['children']:
            if child < len(skeleton):
                skeleton = calc_abs_matrix(child, skeleton)
                skeleton[node]['num_descendents'] += skeleton[child]['num_descendents'] + 1
    return(skeleton)

# Change matrices to numpy arrays, add parent bone ID, world space matrix, inverse bind matrix
def add_bone_info (skeleton):
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
            from pyquaternion import Quaternion
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
        if 'children' in skeleton[node].keys():
            for child in skeleton[node]['children']:
                skeleton = calc_abs_matrix(child, skeleton)
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
def get_children (parent_node, i, metadata):
    node = ET.SubElement(parent_node, 'node')
    node.set('id', metadata['heirarchy'][i]['name'])
    node.set('name', metadata['heirarchy'][i]['name'])
    node.set('sid', metadata['heirarchy'][i]['name'])
    node.set('type', 'NODE')
    if 'rel_matrix' in metadata['heirarchy'][i]:
        matrix = ET.SubElement(node, 'matrix')
        matrix.text = " ".join(["{0}".format(x) for x in metadata['heirarchy'][i]['rel_matrix'].flatten('C')])
    if 'children' in metadata['heirarchy'][i].keys():
        for j in range(len(metadata['heirarchy'][i]['children'])):
            if metadata['heirarchy'][i]['children'][j] < len(metadata['heirarchy']):
                get_children(node, metadata['heirarchy'][i]['children'][j], metadata)
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
    return

# Used to add an empty node to visual scene if no node can be found to attach geometry
def add_empty_node (name, parent_node):
    node = ET.SubElement(parent_node, 'node')
    node.set('id', name)
    node.set('name', name)
    node.set('sid', name)
    node.set('type', 'NODE')
    matrix = ET.SubElement(node, 'matrix')
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
def add_skeleton (collada, metadata):
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
            get_children(visual_scene, top_nodes[i], metadata)
            extra = ET.SubElement(visual_scene, 'extra')
            technique = ET.SubElement(extra, 'technique')
            technique.set('profile','FCOLLADA')
            start_time = ET.SubElement(technique, 'start_time')
            start_time.text = '0'
            end_time = ET.SubElement(technique, 'end_time')
            end_time.text = '8.333333015441895'
            instance_visual_scene = ET.SubElement(scene, 'instance_visual_scene')
            instance_visual_scene.set('url', '#' + metadata['heirarchy'][top_nodes[i]]['name'])
    return(collada)

# Add geometries and skin them.  Needs a base node tree to build links to.
def add_geometries_and_controllers (collada, submeshes, skeleton, materials, has_skeleton = True):
    library_geometries = collada.find('library_geometries')
    #Find mesh instances with saved inverted bind matrices
    mesh_instances = list(set([x.split('_imtx')[0] for i in range(len(skeleton)) for x in skeleton[i].keys() if '_imtx' in x]))
    if has_skeleton == True:
        library_controllers = collada.find('library_controllers')
        library_visual_scenes = collada.find('library_visual_scenes')
        top_node_children = [x['children'] for x in skeleton if x['name'] == library_visual_scenes[0].attrib['id']][0] # Children of top node
        # I know this results in some overwriting but it does not matter, we are just trying to identify the child of the top node that is the skeleton
        num_kids = {skeleton[x]['num_descendents']:x for x in top_node_children}
        # Whichever child of the top node with the most descendents wins and is crowned the skeleton
        skeleton_id = num_kids[sorted(num_kids.keys(), reverse=True)[0]]
        skeleton_name = skeleton[skeleton_id]['name']
        joint_list = get_joint_list(skeleton_id, [x for y in [x['vgmap'].keys() for x in submeshes] for x in y]+[skeleton_name], skeleton)
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
        if 'BLENDWEIGHTS' in semantics_list and 'BLENDINDICES' in semantics_list:
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
                        new_weight.append(blendweights[i][j])
                        new_index.append(local_to_global_joints[blendindices[i][j]])
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
                try:
                    bone_node = [x for x in collada.iter() if 'sid' in x.attrib and x.attrib['sid'] == bone][0]
                except IndexError:
                    print("bone missing: {0}".format(bone))
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
        if 'BLENDWEIGHTS' in semantics_list and 'BLENDINDICES' in semantics_list:
            if len(parent_node) > 0:
                mesh_node = parent_node[0]
            else:
                mesh_node = add_empty_node (meshname+'_node', collada.find('library_visual_scenes')[0])
            instance_geom_controller = ET.SubElement(mesh_node, 'instance_controller')
            instance_geom_controller.set('url', '#' + submesh["name"] + '-skin')
            controller_skeleton = ET.SubElement(instance_geom_controller, 'skeleton')
            controller_skeleton.text = '#' + skeleton_name # Should always be 'up_point' or its equivalent!
        else:
            mesh_node = add_empty_node (meshname+'_node', collada.find('library_visual_scenes')[0])
            instance_geom_controller = ET.SubElement(mesh_node, 'instance_geometry')
            instance_geom_controller.set('url', '#' + submesh["name"])
        bind_material = ET.SubElement(instance_geom_controller, 'bind_material')
        technique_common = ET.SubElement(bind_material, 'technique_common')
        instance_material = ET.SubElement(technique_common, 'instance_material')
        instance_material.set('symbol', submesh['name'] + 'SG')
        instance_material.set('target', '#' + submesh['material']['material'])
        material = [v for (k,v) in materials.items() if k == submesh['material']['material']][0]
        for parameter in material['shaderTextures']:
            # Texture parameters - I think these are constant from texture to texture and model to model, variations are in the effects?
            texture_name = material['shaderTextures'][parameter].replace('.DDS','.dds').split('/')[-1].split('.dds')[0]
            bind = ET.SubElement(instance_material, 'bind')
            bind.set("semantic", parameter)
            bind.set("target", texture_name + '-lib/outColor')
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

def write_shader (materials_list):
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
                shader_switch = 'SHADER_{0}'.format(materials_list[i][material]['shader'].split('#')[-1][0:4])
                if shader_switch not in added_shaders and materials_list[i][material]['shader'].split('#')[0] == filename:
                    added_shaders.append(shader_switch)
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
                    for parameter in materials_list[i][material]['shaderSamplerDefs']:
                        shaderfx += 'sampler {0} : {0};\r\n'.format(parameter)
                    for parameter in materials_list[i][material]['shaderTextures']:
                        shaderfx += 'Texture2D {0} : {0};\r\n'.format(parameter)
                    shaderfx  += '#endif //! {0}\r\n\r\n\r\n'.format(shader_switch)
        shaderfx += '#ifdef SUBDIV\r\n#undef SKINNING_ENABLED\r\n#undef INSTANCING_ENABLED\r\n#endif // SUBDIV\r\n\r\n'
        shaderfx += '#ifdef SUBDIV_SCALAR_DISPLACEMENT\r\nTexture2D<half> DisplacementScalar;\r\n#endif // SUBDIV_SCALAR_DISPLACEMENT\r\n\r\n'
        shaderfx += '#ifdef SUBDIV_VECTOR_DISPLACEMENT\r\nTexture2D<half4> DisplacementVector;\r\n#define USE_TANGENTS\r\n#endif // SUBDIV_VECTOR_DISPLACEMENT\r\n\r\n'
        shaderfx += '#if defined(SUBDIV_SCALAR_DISPLACEMENT) || defined(SUBDIV_VECTOR_DISPLACEMENT)\r\nhalf DisplacementScale = 1.0f;\r\n'
        shaderfx += '#define USE_UVS\r\n#endif // defined(SUBDIV_SCALAR_DISPLACEMENT) || defined(SUBDIV_VECTOR_DISPLACEMENT)'
        with open(filename, 'wb') as f:
            f.write(shaderfx.encode('utf-8'))
    return

def asset_info_from_xml(filename):
    assetfile = ET.parse(filename)
    daes = {}
    for i in range(len(assetfile.getroot())):
        asset_symbol = assetfile.getroot()[i].attrib['symbol']
        dae_files = [x.attrib['path'] for x in assetfile.getroot()[i] if x.attrib['type'] == 'p_collada']
        if len(dae_files) > 0:
            for j in range(len(dae_files)):
                daes[dae_files[j].split('/')[-1].split('.dae')[0]] =\
                    {'asset_symbol': asset_symbol, 'dae_path': os.path.dirname(dae_files[j].replace('data/D3D11/',''))}
    return(daes)

def write_asset_xml (metadata_list):
    xml_info = asset_info_from_xml(metadata_list[0]['pkg_name']+'/asset_D3D11.xml')
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
        for j in range(len(metadata_list[i]['images'])):
            if metadata_list[i]['images'][j]['uri'] not in already_appended:
                images.append('\t\t<cluster path="data/D3D11/{0}.phyre" type="p_texture" />\r\n'.format(metadata_list[i]['images'][j]['uri']))
                already_appended.append(metadata_list[i]['images'][j]['uri'])
        images.sort()
        shaders = []
        for material in metadata_list[i]['materials']:
            for shader_type in ['shader','skinned_shader']:
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

def write_processing_batch_file (models):
    metadata_list = [read_struct_from_json(x) for x in models] # A little inefficient but safer
    xml_info = asset_info_from_xml(metadata_list[0]['pkg_name']+'/asset_D3D11.xml')
    image_copy_text = ''
    image_folders = list(set([os.path.dirname(x['uri']).replace('/','\\') for y in metadata_list for x in y['images']]))
    if len(image_folders) > 0:
        for folder in image_folders:
            image_copy_text += 'copy D3D11\{0}\*.* {1}\r\n'.format(folder, metadata_list[0]['pkg_name'])
    batch_file = '@ECHO OFF\r\nset "SCE_PHYRE=%cd%"\r\n'
    for i in range(len(metadata_list)):
        batch_file += '''CSIVAssetImportTool.exe -fi="{0}\{1}.dae" -platform="D3D11" -write=all
PhyreDummyShaderCreator.exe D3D11\{0}\{1}.dae.phyre
copy D3D11\{0}\{1}.dae.phyre .
python replace_shader_references.py {2}
del {1}.dae.phyre.bak
move {1}.dae.phyre {3}'''.format(xml_info[metadata_list[i]['name']]['dae_path'].replace('/','\\'),\
        metadata_list[i]['name'], models[i], metadata_list[0]['pkg_name']) + '\r\n'
    batch_file += image_copy_text + 'python write_pkg.py -l -o {0}\r\ndel *.fx\r\ndel *.cgfx\r\n'.format(metadata_list[0]['pkg_name'])
    with open('RunMe.bat', 'wb') as f:
        f.write(batch_file.encode('utf-8'))
    return

def build_collada(metadata_name):
    if os.path.exists(metadata_name):
        metadata = read_struct_from_json(metadata_name)
        print("Processing {0}...".format(metadata['pkg_name']))
        dae_path = 'chr/chr/{0}'.format(metadata['name'].split('_')[0]) # Default name, to be overwritten by value in asset_D3D11.xml
        if os.path.exists(metadata['pkg_name']+'/asset_D3D11.xml'):
            xml_info = asset_info_from_xml(metadata['pkg_name']+'/asset_D3D11.xml')
            if metadata['name'] in xml_info:
                dae_path = xml_info[metadata['name']]['dae_path']
        relative_path = '/'.join(['..' for x in range(len(dae_path.split('/')))])
        meshes_path = 'meshes' + metadata_name.split('.json')[0].split('metadata')[-1]
        submeshes = []
        meshes = [x.split(meshes_path+'\\')[1].split('.fmt')[0] for x in glob.glob(meshes_path+'/*.fmt')]
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
                print("Submesh {0} not found or corrupt, skipping...".format(filename))
        has_skeleton = False
        for i in range(len(submeshes)):
            if 'vgmap' in submeshes[i].keys():
                has_skeleton = True
        collada = basic_collada(has_skeleton = has_skeleton)
        images_data = [x['uri'] for x in metadata['images']]
        collada = add_images(collada, images_data, relative_path)
        print("Adding materials...")
        collada = add_materials(collada, metadata, relative_path)
        print("Adding skeleton...")
        skeleton = add_bone_info(metadata['heirarchy'])
        collada = add_skeleton(collada, metadata)
        print("Adding geometry...")
        collada = add_geometries_and_controllers(collada, submeshes, skeleton, metadata['materials'], has_skeleton = has_skeleton)
        print("Writing COLLADA file...")
        with io.BytesIO() as f:
            f.write(ET.tostring(collada, encoding='utf-8', xml_declaration=True))
            f.seek(0)
            dom = xml.dom.minidom.parse(f)
            pretty_xml_as_string = dom.toprettyxml(indent='  ')
            if not os.path.exists(dae_path + '/'):
                os.makedirs(dae_path  +'/')
            with open(dae_path + '/' + metadata['name'] + ".dae", 'w') as f2:
                f2.write(pretty_xml_as_string)
    return

if __name__ == '__main__':
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
    models = glob.glob("metadata*.json")
    for i in range(len(models)):
        build_collada(models[i])
    metadata_list = [read_struct_from_json(x) for x in models]
    print("Writing shader file...")
    write_shader([x['materials'] for x in metadata_list])
    print("Writing asset_D3D11.xml...")
    write_asset_xml(metadata_list)
    print("Writing RunMe.bat.")
    write_processing_batch_file(models)
