# Tool to add animation channels to a gltf model.  Will only add channels (and pose data)
# if there are no channels for the associated bone in the original model.
#
# GitHub eArmada8/ed8pkg2gltf

import glob, os, json, struct, numpy, io, sys
from pygltflib import *
from pyquaternion import Quaternion

# Set to True to prevent overwriting the model bind pose with the animation pose
preserve_translation = False
preserve_rotation = False
preserve_scale = False

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

def apply_new_animations_to_model_gltf (model_gltf, ani_gltf):
    global preserve_translation, preserve_rotation, preserve_scale
    global always_transform_locators
    global only_add_nonexistent_animation_bones

    if len(model_gltf.animations) > 0:
        skip_node_names = [model_gltf.nodes[i].name for i in range(len(model_gltf.nodes)) \
            if i in [x.target.node for x in model_gltf.animations[0].channels]]
        animation = model_gltf.animations.pop(0)
    else: # Why are you using this tool if the model has no animations?
        skip_node_names = []
        animation = Animation()
    
    # Apply animation pose to model
    for i in range(len(model_gltf.nodes)):
        if model_gltf.nodes[i].name in [x.name for x in ani_gltf.nodes] and model_gltf.nodes[i].name not in skip_node_names:
            ani_node = [j for j in range(len(ani_gltf.nodes)) if ani_gltf.nodes[j].name == model_gltf.nodes[i].name][0]
            # Model (bind) pose
            if model_gltf.nodes[i].matrix is not None:
                model_s = [numpy.linalg.norm(model_gltf.nodes[i].matrix[0:3]), numpy.linalg.norm(model_gltf.nodes[i].matrix[4:7]),\
                    numpy.linalg.norm(model_gltf.nodes[i].matrix[8:11])]
                t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],model_gltf.nodes[i].matrix[12:15]+[1]]).transpose()
                r_mtx = numpy.array([(model_gltf.nodes[i].matrix[0:3]/model_s[0]).tolist()+[0],\
                    (model_gltf.nodes[i].matrix[4:7]/model_s[1]).tolist()+[0],\
                    (model_gltf.nodes[i].matrix[8:11]/model_s[2]).tolist()+[0],[0,0,0,1]]).transpose()
                s_mtx = numpy.array([[model_s[0],0,0,0],[0,model_s[1],0,0],[0,0,model_s[2],0],[0,0,0,1]])
            else:
                if model_gltf.nodes[i].translation is not None:
                    t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],model_gltf.nodes[i].translation+[1]]).transpose()
                else:
                    t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
                if model_gltf.nodes[i].rotation is not None:
                    r_mtx = Quaternion(model_gltf.nodes[i].rotation[3], model_gltf.nodes[i].rotation[0],\
                        model_gltf.nodes[i].rotation[1], model_gltf.nodes[i].rotation[2]).transformation_matrix
                else:
                    r_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
                if model_gltf.nodes[i].scale is not None:
                    s_mtx = numpy.array([[model_gltf.nodes[i].scale[0],0,0,0],\
                        [0,model_gltf.nodes[i].scale[1],0,0],[0,0,model_gltf.nodes[i].scale[2],0],[0,0,0,1]])
                else:
                    s_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
            # Animation pose
            if ani_gltf.nodes[ani_node].matrix is not None:
                anipose_s = [numpy.linalg.norm(ani_gltf.nodes[ani_node].matrix[0:3]), numpy.linalg.norm(ani_gltf.nodes[ani_node].matrix[4:7]),\
                    numpy.linalg.norm(ani_gltf.nodes[ani_node].matrix[8:11])]
                anipose_t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],ani_gltf.nodes[ani_node].matrix[12:15]+[1]]).transpose()
                anipose_r_mtx = numpy.array([(ani_gltf.nodes[ani_node].matrix[0:3]/anipose_s[0]).tolist()+[0],\
                    (ani_gltf.nodes[ani_node].matrix[4:7]/anipose_s[1]).tolist()+[0],\
                    (ani_gltf.nodes[ani_node].matrix[8:11]/anipose_s[2]).tolist()+[0],[0,0,0,1]]).transpose()
                anipose_s_mtx = numpy.array([[anipose_s[0],0,0,0],[0,anipose_s[1],0,0],[0,0,anipose_s[2],0],[0,0,0,1]])
            else:
                if ani_gltf.nodes[ani_node].translation is not None:
                    anipose_t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],ani_gltf.nodes[ani_node].translation+[1]]).transpose()
                else:
                    anipose_t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
                if ani_gltf.nodes[ani_node].rotation is not None:
                    anipose_r_mtx = Quaternion(ani_gltf.nodes[ani_node].rotation[3], ani_gltf.nodes[ani_node].rotation[0],\
                        ani_gltf.nodes[ani_node].rotation[1], ani_gltf.nodes[ani_node].rotation[2]).transformation_matrix
                else:
                    anipose_r_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
                if ani_gltf.nodes[ani_node].scale is not None:
                    anipose_s_mtx = numpy.array([[ani_gltf.nodes[ani_node].scale[0],0,0,0],\
                        [0,ani_gltf.nodes[ani_node].scale[1],0,0],[0,0,ani_gltf.nodes[ani_node].scale[2],0],[0,0,0,1]])
                else:
                    anipose_s_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
            # Overwrite model pose with animation pose per global variable preference
                if preserve_translation == False:
                    t_mtx = anipose_t_mtx
                if preserve_rotation == False:
                    r_mtx = anipose_r_mtx
                if preserve_scale == False:
                    s_mtx = anipose_s_mtx
            #Delete current model (bind) pose
            for key in ['matrix', 'translation', 'rotation', 'scale']:
                if getattr(model_gltf.nodes[i], key) is not None:
                    setattr(model_gltf.nodes[i], key, None)
            #Insert new pose (T x R x S)
            model_gltf.nodes[i].matrix = numpy.dot(numpy.dot(t_mtx, r_mtx), s_mtx).flatten('F').tolist()
    # Copy animations into model
    model_gltf.convert_buffers(BufferFormat.BINARYBLOB)
    binary_blob = model_gltf.binary_blob()
    blob_len = len(model_gltf.binary_blob())
    allowed_transforms = []
    if preserve_translation == False:
        allowed_transforms.append('translation')
    if preserve_rotation == False:
        allowed_transforms.append('rotation')
    if preserve_scale == False:
        allowed_transforms.append('scale')
    for i in range(len(ani_gltf.animations)):
        for j in range(len(ani_gltf.animations[i].channels)):
            sampler_input_acc = ani_gltf.animations[i].samplers[ani_gltf.animations[i].channels[j].sampler].input
            sampler_input = read_gltf_stream(ani_gltf, sampler_input_acc)
            sampler_output_acc = ani_gltf.animations[i].samplers[ani_gltf.animations[i].channels[j].sampler].output
            sampler_output = read_gltf_stream(ani_gltf, sampler_output_acc)
            sampler_interpolation = ani_gltf.animations[i].samplers[ani_gltf.animations[i].channels[j].sampler].interpolation
            target_path = ani_gltf.animations[i].channels[j].target.path
            target_node_name = ani_gltf.nodes[ani_gltf.animations[i].channels[j].target.node].name
            if target_node_name in [x.name for x in model_gltf.nodes] \
                and target_node_name not in skip_node_names \
                and target_path in allowed_transforms:
                target_node = [k for k in range(len(model_gltf.nodes)) if model_gltf.nodes[k].name == target_node_name][0]
                ani_sampler = AnimationSampler()
                blobdata = numpy.array(sampler_input,dtype="float32").tobytes()
                bufferview = BufferView()
                bufferview.buffer = 0
                bufferview.byteOffset = blob_len
                bufferview.byteLength = len(blobdata)
                binary_blob += blobdata
                blob_len += len(blobdata)
                padding_length = 4 - len(blobdata) % 4
                binary_blob += b'\x00' * padding_length
                blob_len += padding_length      
                accessor = Accessor()
                accessor.bufferView = len(model_gltf.bufferViews)
                accessor.componentType = 5126
                accessor.type = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[len(sampler_input[0])]
                accessor.count = len(sampler_input)
                accessor.min = min(sampler_input)
                accessor.max = max(sampler_input)
                ani_sampler.input = len(model_gltf.accessors)
                model_gltf.accessors.append(accessor)
                model_gltf.bufferViews.append(bufferview)
                blobdata = numpy.array(sampler_output,dtype="float32").tobytes()
                bufferview = BufferView()
                bufferview.buffer = 0
                bufferview.byteOffset = blob_len
                bufferview.byteLength = len(blobdata)
                binary_blob += blobdata
                blob_len += len(blobdata)
                padding_length = 4 - len(blobdata) % 4
                binary_blob += b'\x00' * padding_length
                blob_len += padding_length      
                accessor = Accessor()
                accessor.bufferView = len(model_gltf.bufferViews)
                accessor.componentType = 5126
                accessor.type = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[len(sampler_output[0])]
                accessor.count = len(sampler_input)
                ani_sampler.output = len(model_gltf.accessors)
                model_gltf.accessors.append(accessor)
                model_gltf.bufferViews.append(bufferview)
                ani_sampler.interpolation = sampler_interpolation
                ani_channel = AnimationChannel()
                ani_channel.sampler = len(animation.samplers)
                ani_channel.target = AnimationChannelTarget()
                ani_channel.target.path = target_path
                ani_channel.target.node = target_node
                animation.samplers.append(ani_sampler)
                animation.channels.append(ani_channel)
        model_gltf.animations.append(animation)
    model_gltf.buffers[0].byteLength = blob_len
    model_gltf.set_binary_blob(binary_blob)
    return(model_gltf)

def process_animation (model_filename, new_animation_filename):
    model_gltf = GLTF2().load(model_filename)
    ani_gltf = GLTF2().load(new_animation_filename)
    new_filename = '{0}_{1}_merged.glb'.format(os.path.basename(model_filename).split('.gl')[0],\
        os.path.basename(new_animation_filename).split('.gl')[0])
    new_model = apply_new_animations_to_model_gltf (model_gltf, ani_gltf)
    new_model.convert_buffers(BufferFormat.BINARYBLOB)
    new_model.save_binary("{}.glb".format(new_filename))
    return True

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
        parser.add_argument('model_filename', help="Name of model glb/gltf file with base model (required).")
        parser.add_argument('new_animation_filename', help="Name of model glb/gltf file with new animation channels (required).")
        args = parser.parse_args()
        if os.path.exists(args.model_filename) and os.path.exists(args.new_animation_filename):
            process_animation (args.model_filename, args.new_animation_filename)
    else:
        print("Note: only .glb/.gltf with single animations supported!")
        model_filename = ''
        while model_filename == '':
            try:
                m_input = str(input("GLTF Model with base animations: "))
                if os.path.exists(m_input) and m_input.lower().split('.gl')[1] in ['tf', 'b']:
                    model_filename = m_input
            except:
                pass
        new_animation_filename = ''
        while new_animation_filename == '':
            try:
                a_input = str(input("GLTF Model with additional animation channels: "))
                if os.path.exists(a_input) and a_input.lower().split('.gl')[1] in ['tf', 'b']:
                    new_animation_filename = a_input
            except:
                pass
        process_animation(model_filename, new_animation_filename)