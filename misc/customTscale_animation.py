# Tool to scale a gltf animation.  A companion to ed8pkg2gltf.py.
#
# GitHub eArmada8/ed8pkg2gltf

import glob, os, json, struct, numpy, io, sys
from pygltflib import *
from pyquaternion import Quaternion

# Set to a value other than 1 to scale the animation
translation_scale = 1.0

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

def convert_gltf_nodes_matrix_to_trs (gltf_model):
    for i in range(len(gltf_model.nodes)):
        # Model (bind) pose
        if gltf_model.nodes[i].matrix is not None:
            model_t = gltf_model.nodes[i].matrix[12:15]
            model_s = [numpy.linalg.norm(gltf_model.nodes[i].matrix[0:3]), numpy.linalg.norm(gltf_model.nodes[i].matrix[4:7]),\
                numpy.linalg.norm(gltf_model.nodes[i].matrix[8:11])]
            r_mtx = numpy.array([(gltf_model.nodes[i].matrix[0:3]/model_s[0]).tolist(),\
                (gltf_model.nodes[i].matrix[4:7]/model_s[1]).tolist(),\
                (gltf_model.nodes[i].matrix[8:11]/model_s[2]).tolist()]) # Row-major
            # Enforce orthogonality of rotation matrix, Premelani W and Bizard P "Direction Cosine Matrix IMU: Theory" Diy Drone: Usa 1 (2009).
            if (error := numpy.dot(r_mtx[0],r_mtx[1])) != 0.0:
                vectors = [r_mtx[0]-(error/2)*r_mtx[1], r_mtx[1]-(error/2)*r_mtx[0]]
                vectors.append(numpy.cross(vectors[0], vectors[1]))
                r_mtx = numpy.array([x/numpy.linalg.norm(x) for x in vectors]).transpose() # Column-major
            else:
                r_mtx = r_mtx.transpose() # Column-major
            model_q = list(Quaternion(matrix = r_mtx)) #wxyz
            model_r = model_q[1:] + [model_q[0]] #xyzw
        else:
            if gltf_model.nodes[i].translation is not None:
                model_t = gltf_model.nodes[i].translation
            else:
                model_t = [0.0,0.0,0.0]
            if gltf_model.nodes[i].rotation is not None:
                model_r = gltf_model.nodes[i].rotation
            else:
                model_r = [0.0,0.0,0.0,1.0]
            if gltf_model.nodes[i].scale is not None:
                model_s = gltf_model.nodes[i].scale
            else:
                model_s = [1.0,1.0,1.0]
        #Delete current model (bind) pose
        for key in ['matrix', 'translation', 'rotation', 'scale']:
            if getattr(gltf_model.nodes[i], key) is not None:
                setattr(gltf_model.nodes[i], key, None)
        #Insert new pose (T x R x S)
        if model_t != [0.0,0.0,0.0]:
            gltf_model.nodes[i].translation = model_t
        if model_r != [0.0,0.0,0.0,1.0]:
            gltf_model.nodes[i].rotation = model_r
        if model_s != [1.0,1.0,1.0]:
            gltf_model.nodes[i].scale = model_s
    return(gltf_model)

def apply_animations_to_model_gltf (ani_gltf):
    global translation_scale

    # Convert all matrices to TRS
    ani_gltf = convert_gltf_nodes_matrix_to_trs (ani_gltf)
    # Apply translation_scale
    for i in range(len(ani_gltf.nodes)):
        if ani_gltf.nodes[i].translation is not None:
            ani_gltf.nodes[i].translation = (numpy.array(ani_gltf.nodes[i].translation) * translation_scale).tolist()
    # Copy animations into model
    ani_gltf.convert_buffers(BufferFormat.BINARYBLOB)
    binary_blob = ani_gltf.binary_blob()
    blob_len = len(ani_gltf.binary_blob())
    with io.BytesIO(binary_blob) as f:
        for i in range(len(ani_gltf.animations)):
            for j in range(len(ani_gltf.animations[i].channels)):
                if ani_gltf.animations[i].channels[j].target.path == 'translation':
                    sampler_output_acc = ani_gltf.animations[i].samplers[ani_gltf.animations[i].channels[j].sampler].output
                    # Read original values
                    sampler_output = read_gltf_stream(ani_gltf, sampler_output_acc)
                    # Scale the values
                    new_output = [(numpy.array(x) * translation_scale).tolist() for x in sampler_output]
                    accessor = ani_gltf.accessors[sampler_output_acc]
                    bufferview = ani_gltf.bufferViews[accessor.bufferView]
                    f.seek(bufferview.byteOffset)
                    # Overwrite the old values with the new values
                    f.write(numpy.array(new_output,dtype="float32").tobytes())
        f.seek(0)
        new_blob = f.read()
    ani_gltf.set_binary_blob(new_blob)
    return(ani_gltf)

def process_animation (animation):
    print("Processing {0}...".format(animation))
    if os.path.exists(animation+'.gltf'):
        ani_filename = animation+'.gltf'
        output = 'GLTF'
    elif os.path.exists(animation+'.glb'):
        ani_filename = animation+'.glb'
        output = 'GLB'
    else:
        print("Animation {} not found, skipping...".format(animation))
        return False
    ani_gltf = GLTF2().load(ani_filename)
    if len(ani_filename.split('_')) > 1:
        new_model = apply_animations_to_model_gltf (ani_gltf)
        new_model.convert_buffers(BufferFormat.BINARYBLOB)
        if output == 'GLB':
            new_model.save_binary("{}.glb".format(animation))
            return True
        else:
            new_model.save("{}.gltf".format(animation))
            return True

if __name__ == '__main__':
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
    animations = [os.path.basename(x).split('.gl')[0] for x in glob.glob("*.gl*")]
    for animation in animations:
        process_animation (animation)