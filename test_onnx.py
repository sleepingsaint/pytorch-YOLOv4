# running inference on video using onnx runtime
import os
import cv2
import time
import math
import onnxruntime
import numpy as np
from tool.utils import load_class_names, nms_cpu
from halo import Halo

import argparse

# covert the output from model to bounding boxes
def post_processing(img, conf_thresh, nms_thresh, output, verbose):

    # anchors = [12, 16, 19, 36, 40, 28, 36, 75, 76, 55, 72, 146, 142, 110, 192, 243, 459, 401]
    # num_anchors = 9
    # anchor_masks = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    # strides = [8, 16, 32]
    # anchor_step = len(anchors) // num_anchors

    # [batch, num, 1, 4]
    box_array = output[0]
    # [batch, num, num_classes]
    confs = output[1]

    t1 = time.time()

    if type(box_array).__name__ != 'ndarray':
        box_array = box_array.cpu().detach().numpy()
        confs = confs.cpu().detach().numpy()

    num_classes = confs.shape[2]

    # [batch, num, 4]
    box_array = box_array[:, :, 0]

    # [batch, num, num_classes] --> [batch, num]
    max_conf = np.max(confs, axis=2)
    max_id = np.argmax(confs, axis=2)

    t2 = time.time()

    bboxes_batch = []
    for i in range(box_array.shape[0]):
       
        argwhere = max_conf[i] > conf_thresh
        l_box_array = box_array[i, argwhere, :]
        l_max_conf = max_conf[i, argwhere]
        l_max_id = max_id[i, argwhere]

        bboxes = []
        # nms for each class
        for j in range(num_classes):

            cls_argwhere = l_max_id == j
            ll_box_array = l_box_array[cls_argwhere, :]
            ll_max_conf = l_max_conf[cls_argwhere]
            ll_max_id = l_max_id[cls_argwhere]

            keep = nms_cpu(ll_box_array, ll_max_conf, nms_thresh)
            
            if (keep.size > 0):
                ll_box_array = ll_box_array[keep, :]
                ll_max_conf = ll_max_conf[keep]
                ll_max_id = ll_max_id[keep]

                for k in range(ll_box_array.shape[0]):
                    bboxes.append([ll_box_array[k, 0], ll_box_array[k, 1], ll_box_array[k, 2], ll_box_array[k, 3], ll_max_conf[k], ll_max_conf[k], ll_max_id[k]])
        
        bboxes_batch.append(bboxes)

    t3 = time.time()

    if verbose:
      print('-----------------------------------')
      print('       max and argmax : %f' % (t2 - t1))
      print('                  nms : %f' % (t3 - t2))
      print('Post processing total : %f' % (t3 - t1))
      print('-----------------------------------')
    
    return bboxes_batch

# helper function to draw bounding boxes
def plot_boxes_cv2(img, boxes, class_names, verbose, color=None):
    img = np.copy(img)
    colors = np.array([[1, 0, 1], [0, 0, 1], [0, 1, 1], [0, 1, 0], [1, 1, 0], [1, 0, 0]], dtype=np.float32)

    def get_color(c, x, max_val):
        ratio = float(x) / max_val * 5
        i = int(math.floor(ratio))
        j = int(math.ceil(ratio))
        ratio = ratio - i
        r = (1 - ratio) * colors[i][c] + ratio * colors[j][c]
        return int(r * 255)

    width = img.shape[1]
    height = img.shape[0]
    for i in range(len(boxes)):
        box = boxes[i]
        x1 = int(box[0] * width)
        y1 = int(box[1] * height)
        x2 = int(box[2] * width)
        y2 = int(box[3] * height)

        rgb = (255, 0, 0)
        if len(box) >= 7 and class_names:
            cls_conf = box[5]
            cls_id = box[6]
            if verbose:
              print('%s: %f' % (class_names[cls_id], cls_conf))
            classes = len(class_names)
            offset = cls_id * 123457 % classes
            red = get_color(2, offset, classes)
            green = get_color(1, offset, classes)
            blue = get_color(0, offset, classes)
            if color is None:
                rgb = (red, green, blue)
            img = cv2.putText(img, class_names[cls_id], (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 1.2, rgb, 1)
        img = cv2.rectangle(img, (x1, y1), (x2, y2), rgb, 1)

    return img

# run detection on the image/frame using the given onnx session
def detect(session, image_src, class_names, verbose):
    IN_IMAGE_H = session.get_inputs()[0].shape[2]
    IN_IMAGE_W = session.get_inputs()[0].shape[3]

    # Input
    resized = cv2.resize(image_src, (IN_IMAGE_W, IN_IMAGE_H), interpolation=cv2.INTER_LINEAR)
    img_in = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    img_in = np.transpose(img_in, (2, 0, 1)).astype(np.float32)
    img_in = np.expand_dims(img_in, axis=0)
    img_in /= 255.0

    if verbose:
      print("Shape of the network input: ", img_in.shape)

    # Compute
    input_name = session.get_inputs()[0].name

    start = time.time()
    outputs = session.run(None, {input_name: img_in})
    end = time.time()

    boxes = post_processing(img_in, 0.4, 0.6, outputs, verbose)

    image_src = plot_boxes_cv2(image_src, boxes[0], class_names, verbose)
    return image_src, (end - start)

# main function to run the inference
def runInference(model, video_path, output_path, num_frames, class_names, verbose):

    session = onnxruntime.InferenceSession(model)
    video = cv2.VideoCapture(video_path)

    if (video.isOpened() == False):
        print("Error reading video file")

    frame_width = video.get(cv2.CAP_PROP_FRAME_WIDTH)
    frame_height = video.get(cv2.CAP_PROP_FRAME_HEIGHT)
    frame_size = (int(frame_width), int(frame_height))

    yolo_input_res = (608, 608)
    size = (frame_width, frame_height)
	
    if os.path.exists(output_path):
        print("clearing the output path")
        os.remove(output_path)
        
    input_fps = int(video.get(cv2.CAP_PROP_FPS))
    result = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'MP4V'), input_fps, frame_size)

    frame_count = 0

    with Halo(spinner="dots", text="Loading the frames") as sp:
      while(True):
          ret, frame = video.read()
          frame_count += 1

          if ret == True:
              # print(f"Frame {frame_count}")
              sp.text = f"Frame {frame_count}"
              
              detection, inference_time= detect(session, frame, class_names, verbose)
              
              inference_fps = round(1 / inference_time, 2)
              cv2.putText(detection, f"Input FPS: {input_fps} | Inference FPS: {inference_fps}", (50, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 0), 2)

              result.write(detection)

              if num_frames is not None and frame_count == num_frames:
                  break
              if cv2.waitKey(1) & 0xFF == ord('q'):
                  break

          else:
              break

    video.release()
    result.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, required=True, help="Path to the model file")
    parser.add_argument('-i', '--input', type=str, required=True, help="Path to the video file")
    parser.add_argument('-o', '--output', type=str, required=True, help="Path to the output video")
    parser.add_argument('-f', '--frame_count', type=int, help="Number of frames to run the video")
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Enable more details")
    parser.add_argument('-c', '--num_classes', type=int, default=5, help="Number of classes model trained on")
    args = parser.parse_args()
    # print(args)

    if args.num_classes == 20:
        namesfile = 'data/voc.names'
    elif args.num_classes == 80:
        namesfile = 'data/coco.names'
    else:
        namesfile = 'data/names'

    class_names = load_class_names(namesfile)

    runInference(args.model, args.input, args.output, args.frame_count, class_names, args.verbose)